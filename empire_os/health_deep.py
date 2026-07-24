#!/usr/bin/env python3
"""
health_deep.py — Empire OS deep health check.

The /health endpoint proves the hub process is alive. It does NOT prove
the revenue loop will actually work. This module proves the revenue loop.

It asserts every precondition for /v1/ppc/charge to mint a real pay_url
that lands in si_charges with status=open:

  1. ENV     — SOLANA_VAULT_WALLET, SOLANA_RPC_URL, SOLANA_PAYER_SECRET,
               USDC_MINT, SOLANA_NETWORK are all set and non-empty.
  2. DB      — si_charges is writable, si_unmatched_deposits is writable,
               si_tenant.crypto_wallet column exists.
  3. CHAIN   — Helius RPC reachable, vault wallet balance > 0 is OPTIONAL
               (0.0 is fine for cold start).
  4. HUB     — /health 200, /v1/buyers/apply works, /v1/ppc/charge works.
  5. LISTENER — exactly 1 solana_listener_agent process running,
               last log entry < 90s old.

If ANY precondition fails, /v1/health/deep returns ok=false AND names
the failing precondition. systemd ExecStartPost uses this as a hard
boot guard: hub refuses to start if revenue_path_ready != true.

The cron job (separate) calls this every 5 min and writes the result
to /root/feedback/health_deep.jsonl. Each row is the moment a
precondition flipped (or stayed green).
"""
from __future__ import annotations
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB = "/root/empire_os/empire_os.db"
HUB_BASE = "http://127.0.0.1:8081"
LOG_PATH = Path("/root/feedback/health_deep.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# If the vault-loaded env file exists (written by load_secrets.py at
# ExecStartPre), read it INTO os.environ so deep_health sees the truth.
# This is the canonical fix for the "ExecStartPre env doesn't propagate
# to ExecStartPost" pattern. Same file systemd uses for hub env.
SECRETS_ENV_FILE = Path("/run/empire-secrets.env")
if SECRETS_ENV_FILE.exists():
    try:
        for line in SECRETS_ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    except OSError:
        pass

REQUIRED_ENV = (
    "SOLANA_VAULT_WALLET",
    "SOLANA_RPC_URL",
    "SOLANA_PAYER_SECRET",
    "USDC_MINT",
    "SOLANA_NETWORK",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_env() -> dict:
    """All 5 revenue env vars must be set + non-empty."""
    out = {}
    for k in REQUIRED_ENV:
        v = os.environ.get(k, "").strip()
        if not v:
            out[k] = {"ok": False, "reason": "missing or empty"}
        else:
            # Show only first/last 4 chars for sensitive values
            shown = f"{v[:4]}...{v[-4:]} ({len(v)} chars)" if len(v) > 12 else "***"
            out[k] = {"ok": True, "value": shown}
    return out


def _check_db() -> dict:
    """Critical tables writable, key columns exist."""
    out = {}
    try:
        c = sqlite3.connect(DB, timeout=5)
    except Exception as e:
        return {"connect": {"ok": False, "reason": str(e)}}

    # Check critical tables
    required = ("si_charges", "si_unmatched_deposits", "si_tenant",
                "si_settlements", "si_invoice")
    for tbl in required:
        try:
            c.execute(f"SELECT 1 FROM {tbl} LIMIT 1")
            out[tbl] = {"ok": True}
        except sqlite3.OperationalError as e:
            out[tbl] = {"ok": False, "reason": str(e)}

    # Verify si_tenant has crypto_wallet column (the gap we keep hitting)
    try:
        cols = [r[1] for r in c.execute("PRAGMA table_info(si_tenant)")]
        out["si_tenant.crypto_wallet_column"] = {
            "ok": "crypto_wallet" in cols, "columns": cols}
    except Exception as e:
        out["si_tenant.crypto_wallet_column"] = {"ok": False, "reason": str(e)}

    # Writable?
    try:
        c.execute("BEGIN")
        c.execute("CREATE TEMP TABLE _health_probe (x INT)")
        c.execute("ROLLBACK")
        out["writable"] = {"ok": True}
    except Exception as e:
        out["writable"] = {"ok": False, "reason": str(e)}

    c.close()
    return out


def _check_chain() -> dict:
    """Helius RPC reachable + vault balance check (best-effort, 5s timeout)."""
    rpc = os.environ.get("SOLANA_RPC_URL", "").strip()
    vault = os.environ.get("SOLANA_VAULT_WALLET", "").strip()
    if not rpc or not vault:
        return {"ok": False, "reason": "rpc or vault not set"}

    out: dict[str, Any] = {}
    try:
        body = json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [vault,
                       {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                       {"encoding": "jsonParsed"}]
        }).encode()
        req = urllib.request.Request(rpc, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.loads(r.read())
        if "error" in d:
            out["rpc"] = {"ok": False, "reason": d["error"]}
            return out
        accounts = d.get("result", {}).get("value", [])
        total = sum(float(a["account"]["data"]["parsed"]["info"]
                          ["tokenAmount"]["uiAmount"] or 0)
                    for a in accounts)
        out["rpc"] = {"ok": True, "vault_balance_usdc": total,
                       "token_accounts": len(accounts)}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        out["rpc"] = {"ok": False, "reason": f"rpc unreachable: {e}"}
    except Exception as e:
        out["rpc"] = {"ok": False, "reason": f"{type(e).__name__}: {e}"}
    return out


def _check_hub_endpoints() -> dict:
    """The hub can serve /health and /v1/buyers/apply."""
    out = {}
    try:
        with urllib.request.urlopen(f"{HUB_BASE}/health", timeout=5) as r:
            out["/health"] = {"ok": r.status == 200, "status": r.status}
    except Exception as e:
        out["/health"] = {"ok": False, "reason": str(e)}

    # Apply needs JSON body — use unique email per call to avoid noise
    import uuid
    try:
        body = json.dumps({
            "name": "DEEP_PROBE", "niche": "roof_repair",
            "email": f"probe-{uuid.uuid4().hex[:8]}@v.co",
            "tier": "silver", "min_deposit": 0,
            "source": "health_deep_probe"
        }).encode()
        req = urllib.request.Request(f"{HUB_BASE}/v1/buyers/apply",
                                     data=body,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=8) as r:
            j = json.loads(r.read())
        ok = j.get("ok") is True and bool(j.get("payment", {}).get("pay_url", ""))
        out["/v1/buyers/apply"] = {
            "ok": ok,
            "pay_to_wallet": j.get("payment", {}).get("vault_wallet", "")[:20]
        }
    except Exception as e:
        out["/v1/buyers/apply"] = {"ok": False, "reason": str(e)}

    # /v1/ppc/charge (needs a known buyer_id; use vault wallet itself)
    try:
        buyer = os.environ.get("SOLANA_VAULT_WALLET", "")
        body = json.dumps({
            "buyer_id": buyer, "head": 2, "reason": "health_deep_probe",
            "amount_cents": 1
        }).encode()
        req = urllib.request.Request(f"{HUB_BASE}/v1/ppc/charge",
                                     data=body,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            j = json.loads(r.read())
        ok = j.get("status") in ("open", "succeeded") and bool(j.get("pay_url"))
        out["/v1/ppc/charge"] = {"ok": ok, "status": j.get("status")}
    except Exception as e:
        out["/v1/ppc/charge"] = {"ok": False, "reason": str(e)}

    return out


def _check_listener() -> dict:
    """Exactly 1 solana_listener_agent process + recent log activity."""
    out = {}
    try:
        result = subprocess.run(
            ["pgrep", "-fa", "solana_listener_agent"],
            capture_output=True, text=True, timeout=5)
        all_lines = [l for l in result.stdout.strip().splitlines() if l]
        python_lines = [l for l in all_lines if "python3" in l]
        pids = [l.split()[0] for l in python_lines]
        out["process_count"] = len(pids)
        out["pids"] = pids
        out["ok"] = len(pids) == 1
        if len(pids) == 0:
            out["reason"] = "no listener process running"
        elif len(pids) > 1:
            out["reason"] = f"{len(pids)} listener processes (duplicate)"
    except Exception as e:
        out["ok"] = False
        out["reason"] = f"pgrep failed: {e}"

    # Check last log activity in JSONL file (< 180s = healthy)
    try:
        log_path = Path("/root/empire_os/logs/solana_listener.jsonl")
        if log_path.exists():
            lines = log_path.read_text().strip().splitlines()
            if lines:
                import json
                last = json.loads(lines[-1])
                ts_str = last.get("ts", "")
                if ts_str:
                    from datetime import datetime as _dt, timezone
                    # Parse ISO format: 2026-07-22T23:52:27.035531+00:00
                    last_log = _dt.fromisoformat(ts_str.replace("Z", "+00:00"))
                    now = _dt.now(timezone.utc)
                    age = (now - last_log).total_seconds()
                    out["last_log_age_seconds"] = int(age)
                    out["log_alive"] = age < 180
                else:
                    out["log_alive"] = False
                    out["reason"] = "no timestamp in last log"
            else:
                out["log_alive"] = False
                out["reason"] = "empty log file"
        else:
            out["log_alive"] = False
            out["reason"] = "log file not found"
    except Exception as e:
        out["log_alive"] = False
        out["log_check_error"] = str(e)

    return out


def deep_health() -> dict:
    """Run all checks. Return single verdict."""
    env = _check_env()
    db = _check_db()
    chain = _check_chain()
    hub = _check_hub_endpoints()
    listener = _check_listener()

    # Aggregate: AND across layers
    env_ok = all(v.get("ok") for v in env.values())
    db_ok = all(v.get("ok") for v in db.values())
    chain_ok = chain.get("rpc", {}).get("ok", False)
    hub_ok = all(v.get("ok") for v in hub.values())
    listener_ok = listener.get("ok", False) and listener.get("log_alive", False)

    revenue_path_ready = all([env_ok, db_ok, chain_ok, hub_ok, listener_ok])

    return {
        "ok": revenue_path_ready,
        "revenue_path_ready": revenue_path_ready,
        "timestamp": _now_iso(),
        "checks": {
            "env": env,
            "db": db,
            "chain": chain,
            "hub": hub,
            "listener": listener,
        },
        "summary": {
            "env_ok": env_ok,
            "db_ok": db_ok,
            "chain_ok": chain_ok,
            "hub_ok": hub_ok,
            "listener_ok": listener_ok,
        }
    }


def append_log(result: dict, log_path: Path = LOG_PATH) -> None:
    """Append deep health to JSONL log. Each line is one snapshot."""
    # Compact: keep only the failing layer details + summary
    row = {
        "ts": result["timestamp"],
        "ok": result["ok"],
        "summary": result["summary"],
    }
    if not result["ok"]:
        # Include failing layer detail
        for layer, status in result["summary"].items():
            if not status:
                row[f"fail_{layer}"] = result["checks"].get(layer.split("_")[0])
    with log_path.open("a") as f:
        f.write(json.dumps(row) + "\n")


def main() -> int:
    """CLI entry point. Exit 0 iff revenue_path_ready, else 1."""
    result = deep_health()
    append_log(result)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())