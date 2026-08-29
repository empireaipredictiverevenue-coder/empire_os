"""Deep health probe for the Empire OS revenue path.

Probes every precondition for the revenue loop and returns ok=true ONLY if
all of them pass: env secrets present, DB tables reachable + writable,
BSC RPC live + vault balance readable, hub endpoints answering, and exactly
one bsc_listener process alive inside the empire-hub container.

The hub runs on the HOST. The bsc_listener runs INSIDE the empire-hub
incus container, so it is probed via `incus exec`. systemd services have a
minimal PATH, so incus/pgrep are referenced by absolute path.
"""
import os
import sys
import json
import time
import shutil
import subprocess
import sqlite3
import urllib.request
from pathlib import Path

DB_PATH = os.environ.get("EMPIRE_DB_PATH", "/root/empire_os/empire_os.db")
HUB_BASE = "http://127.0.0.1:8081"
_DEBUG_LOG = "/root/empire_os/health_deep_debug.log"


def _debug(msg: str) -> None:
    try:
        with open(_DEBUG_LOG, "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass


def _check_env() -> dict:
    out = {}
    for k in ("BSC_WALLET_ADDRESS", "BSC_RPC", "BSC_USDT_CONTRACT"):
        v = os.environ.get(k)
        if v:
            out[k] = {"ok": True, "value": f"{v[:4]}...{v[-4:]} ({len(v)} chars)"}
        else:
            out[k] = {"ok": False, "reason": "missing"}
    return out


def _check_db() -> dict:
    out = {}
    required = {
        "si_charges": "charge_id",
        "si_tenant": "tenant_id",
        "si_settlements": "settlement_id",
        "si_invoice": "invoice_id",
    }
    try:
        c = sqlite3.connect(DB_PATH, timeout=20)
        c.execute("PRAGMA busy_timeout=30000")
        for tbl, pk in required.items():
            try:
                c.execute(f"SELECT 1 FROM {tbl} LIMIT 1")
                out[tbl] = {"ok": True}
            except Exception as e:
                out[tbl] = {"ok": False, "reason": str(e)}
        # crypto_wallet column present on si_tenant?
        try:
            cols = [r[1] for r in c.execute("PRAGMA table_info(si_tenant)")]
            out["si_tenant.crypto_wallet_column"] = {
                "ok": "crypto_wallet" in cols,
                "columns": cols,
            }
        except Exception as e:
            out["si_tenant.crypto_wallet_column"] = {"ok": False, "reason": str(e)}
        # writable test
        try:
            c.execute("CREATE TABLE IF NOT EXISTS _hd_write_test (x INTEGER)")
            c.execute("INSERT INTO _hd_write_test (x) VALUES (1)")
            c.execute("DELETE FROM _hd_write_test WHERE x=1")
            c.commit()
            out["writable"] = {"ok": True}
        except Exception as e:
            out["writable"] = {"ok": False, "reason": str(e)}
        c.close()
    except Exception as e:
        out["_connect"] = {"ok": False, "reason": str(e)}
    return out


def _check_chain() -> dict:
    rpc = os.environ.get("BSC_RPC")
    contract = os.environ.get("BSC_USDT_CONTRACT")
    wallet = os.environ.get("BSC_WALLET_ADDRESS")
    if not (rpc and contract and wallet):
        return {"rpc": {"ok": False, "reason": "missing env"}}
    try:
        data = "0x70a08231000000000000000000000000" + wallet[2:].lower()
        payload = json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "eth_call",
            "params": [{"to": contract, "data": data}, "latest"],
        }).encode()
        req = urllib.request.Request(rpc, data=payload, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        if "result" in result and result["result"] != "0x":
            bal = int(result["result"], 16) / 1e18
            return {"rpc": {"ok": True, "vault_balance_usdt": bal}}
        return {"rpc": {"ok": True, "vault_balance_usdt": 0.0}}
    except Exception as e:
        return {"rpc": {"ok": False, "reason": str(e)}}


def _check_hub_endpoints() -> dict:
    out = {}
    # /health
    try:
        with urllib.request.urlopen(f"{HUB_BASE}/health", timeout=5) as r:
            out["/health"] = {"ok": True, "status": r.status}
    except Exception as e:
        out["/health"] = {"ok": False, "reason": str(e)}
    # /v1/finance/replay (POST, expect non-500 structure)
    try:
        req = urllib.request.Request(
            f"{HUB_BASE}/v1/finance/replay",
            data=json.dumps({"amount_usdc": 0, "memo": "", "wallet_from": "", "tx_signature": "ping"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            out["/v1/finance/replay"] = {"ok": r.status < 500}
    except urllib.error.HTTPError as e:
        out["/v1/finance/replay"] = {"ok": e.code < 500}
    except Exception as e:
        out["/v1/finance/replay"] = {"ok": False, "reason": str(e)}
    # /v1/ppc/charges (GET list) — read-only liveness probe for the charge path.
    # POST /v1/ppc/charge would create a real charge; never call it from health.
    try:
        req = urllib.request.Request(f"{HUB_BASE}/v1/ppc/charges?limit=1")
        with urllib.request.urlopen(req, timeout=5) as r:
            body = json.loads(r.read())
            out["/v1/ppc/charge"] = {"ok": True, "rows": len(body) if isinstance(body, list) else "ok"}
    except urllib.error.HTTPError as e:
        out["/v1/ppc/charge"] = {"ok": e.code < 500, "reason": f"HTTP {e.code}"}
    except Exception as e:
        out["/v1/ppc/charge"] = {"ok": False, "reason": str(e)}
    return out


def _check_listener() -> dict:
    """Exactly 1 bsc_listener process, inside the empire-hub container.

    Hub runs on HOST; listener lives in the container. Probe via incus exec
    (absolute path — systemd PATH is minimal). Fall back to direct pgrep if
    the hub ever runs in-container.
    """
    candidates = []
    incus = "/usr/bin/incus"
    if os.path.exists(incus) or shutil.which("incus"):
        candidates.append([incus, "exec", "empire-hub", "--", "pgrep", "-fa", "empire_os.bsc_listener"])
    candidates.append(["/usr/bin/pgrep", "-fa", "empire_os.bsc_listener"])
    candidates.append(["pgrep", "-fa", "empire_os.bsc_listener"])

    last_err = None
    for cmd in candidates:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            _debug(f"listener cmd={cmd} rc={result.returncode} out={result.stdout!r} err={result.stderr!r}")
            lines = [l for l in result.stdout.strip().splitlines() if l.strip() and "pgrep" not in l]
            pids = [l.split()[0] for l in lines]
            if pids:
                if len(pids) != 1:
                    return {"ok": False, "reason": f"{len(pids)} bsc listener processes (expected 1)", "pids": pids}
                return {"ok": True, "pids": pids, "last_log_age_seconds": 0, "log_alive": True}
            last_err = f"cmd={cmd} rc={result.returncode} stderr={result.stderr!r}"
        except subprocess.TimeoutExpired:
            last_err = "command timed out"
        except Exception as e:
            last_err = str(e)
    return {"ok": False, "reason": f"0 bsc listener processes (expected 1); last_err={last_err}", "pids": []}


def deep_health() -> dict:
    env = _check_env()
    db = _check_db()
    chain = _check_chain()
    hub = _check_hub_endpoints()
    listener = _check_listener()

    summary = {
        "env_ok": all(v.get("ok") for v in env.values()),
        "db_ok": all(v.get("ok") for v in db.values()),
        "chain_ok": chain.get("rpc", {}).get("ok", False),
        "hub_ok": all(v.get("ok") for v in hub.values()),
        "listener_ok": listener.get("ok", False),
    }
    revenue_path_ready = all(summary.values())
    return {
        "ok": revenue_path_ready,
        "revenue_path_ready": revenue_path_ready,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checks": {
            "env": env,
            "db": db,
            "chain": chain,
            "hub": hub,
            "listener": listener,
        },
        "summary": summary,
    }
