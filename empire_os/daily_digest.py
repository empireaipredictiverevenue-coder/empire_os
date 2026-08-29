#!/usr/bin/env python3
"""Empire OS v3 — Daily Watchdog Digest (single pane of glass).

Runs every 6h via empire-daily-digest.timer. Samples the revenue engine:

  * status counts per row in a2a_quotes / si_subscription / si_outbox / si_settlements
  * last 50 lines of every operational jsonl (grip_*, outbox_reaper, settlement_gateway)
  * host free RAM + loadavg (1 / 5 / 15 min)
  * health flags: HIGH_LOAD (>30), HIGH_OUTBOX (>10K pending), NO_SETTLEMENTS_24H, DAEMON_DOWN

Always sys.exit(0). Short timeouts. Append-only JSONL at
/root/empire_os/feedback/daily_digest.jsonl.

Wired by:
  /etc/systemd/system/empire-daily-digest.{service,timer}
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB = "/root/empire_os/empire_os.db"
FEEDBACK_DIR = Path("/root/empire_os/feedback")
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
DIGEST_PATH = FEEDBACK_DIR / "daily_digest.jsonl"
LOG_DIR = Path("/root/empire_os/logs")

# Daemons we expect to be active. DAEMON_DOWN fires when ANY of these has
# stopped writing to its primary log file within the freshness window.
DAEMONS = {
    "grip_inbox_reaper":   FEEDBACK_DIR / "grip_inbox_reaper.jsonl",
    "grip_lead_rotator":   FEEDBACK_DIR / "grip_lead_rotator.jsonl",
    "grip_quote_reaper":   FEEDBACK_DIR / "grip_quote_reaper.jsonl",
    "outbox_reaper":       FEEDBACK_DIR / "outbox_reaper.jsonl",
    "settlement_gateway":  LOG_DIR     / "settlement_gateway.jsonl",
}

TAIL_LINES = 50                       # how many lines per jsonl to keep
DAEMON_FRESH_MIN = 90                 # minutes — grace window
SQLITE_TIMEOUT = 10
PROCMEM_LINE_IDX = 1                  # "MemFree:" is line 2 of /proc/meminfo


# ── helpers ──────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(fn, default=None):
    """Run fn(); never let one probe take down the digest."""
    try:
        return fn()
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _tail_jsonl(path: Path, n: int = TAIL_LINES) -> list[dict]:
    """Return last n non-empty lines of a JSONL file, parsed."""
    if not path.exists():
        return []
    try:
        # Slurp is fine: largest daemon log here is ~1MB.
        with open(path, "rb") as f:
            data = f.read().splitlines()
        lines = [ln for ln in data[-n:] if ln.strip()]
        out = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                # Some daemons print bare text — preserve as raw line.
                out.append({"_raw": ln.decode("utf-8", "replace")[:500]})
        return out
    except Exception as exc:
        return [{"_error": f"tail_failed: {exc}"}]


def _last_log_ts(path: Path) -> str | None:
    """Best-effort timestamp of the last log line."""
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            data = f.read().splitlines()
        for ln in reversed(data[-200:]):
            ln = ln.strip()
            if not ln:
                continue
            try:
                rec = json.loads(ln)
                return rec.get("ts") or rec.get("settled_at") or rec.get("created_at")
            except Exception:
                continue
        return None
    except Exception:
        return None


# ── collectors ───────────────────────────────────────────────────────

def collect_table_status() -> dict:
    """Per-status counts for the 4 money-system tables."""
    out = {}
    targets = {
        "a2a_quotes":      "status",
        "si_subscription": "status",
        "si_outbox":       "status",
        "si_settlements":  "settled_by",  # this table has no `status` col
    }
    for tbl, col in targets.items():
        try:
            conn = sqlite3.connect(DB, timeout=SQLITE_TIMEOUT)
            try:
                rows = conn.execute(
                    f"SELECT {col} AS k, COUNT(*) AS n FROM {tbl} GROUP BY {col}"
                ).fetchall()
                out[tbl] = {k: n for k, n in rows}
                out[f"{tbl}_total"] = sum(n for _, n in rows)
            finally:
                conn.close()
        except Exception as exc:
            out[tbl] = {"_error": f"{type(exc).__name__}: {exc}"}
    return out


def collect_settlements_24h() -> dict:
    """Count settlements + total USDC in the last 24 hours."""
    try:
        conn = sqlite3.connect(DB, timeout=SQLITE_TIMEOUT)
        try:
            since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(amount_cents),0) "
                "FROM si_settlements WHERE settled_at >= ?",
                (since,),
            ).fetchone()
            count, cents = (row[0] or 0), (row[1] or 0)
            return {"count_24h": count, "usdc_24h": round(cents / 100.0, 4)}
        finally:
            conn.close()
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def collect_logs() -> dict:
    """Last 50 lines per operational jsonl."""
    return {
        name: {
            "path": str(path),
            "exists": path.exists(),
            "last_ts": _last_log_ts(path),
            "tail": _tail_jsonl(path),
        }
        for name, path in DAEMONS.items()
    }


def collect_system() -> dict:
    """Free RAM + loadavg from /proc."""
    out = {"ts": _now()}
    try:
        with open("/proc/meminfo") as f:
            lines = f.read().splitlines()
        kv = {}
        for ln in lines:
            if ":" in ln:
                k, v = ln.split(":", 1)
                kv[k.strip()] = v.strip()
        out["mem_total_kb"] = int(kv.get("MemTotal", "0").split()[0])
        out["mem_free_kb"]  = int(kv.get("MemFree",  "0").split()[0])
        out["mem_avail_kb"] = int(kv.get("MemAvailable", "0").split()[0])
    except Exception as exc:
        out["mem_error"] = f"{type(exc).__name__}: {exc}"
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
        out["load_1"]  = float(parts[0])
        out["load_5"]  = float(parts[1])
        out["load_15"] = float(parts[2])
        out["procs"]   = parts[3]
    except Exception as exc:
        out["load_error"] = f"{type(exc).__name__}: {exc}"
    return out


# ── health flags ─────────────────────────────────────────────────────

HIGH_LOAD_THRESHOLD = 30.0
HIGH_OUTBOX_THRESHOLD = 10_000

def compute_flags(table_status: dict, system_info: dict,
                  settlements_24h: dict, daemon_logs: dict) -> list[str]:
    flags = []
    load_1 = float(system_info.get("load_1", 0.0) or 0.0)
    if load_1 > HIGH_LOAD_THRESHOLD:
        flags.append(f"HIGH_LOAD(load1={load_1:.2f})")

    outbox = table_status.get("si_outbox", {})
    if isinstance(outbox, dict):
        pending = outbox.get("pending", 0)
        if pending > HIGH_OUTBOX_THRESHOLD:
            flags.append(f"HIGH_OUTBOX(pending={pending})")

    if settlements_24h.get("count_24h", -1) == 0:
        flags.append("NO_SETTLEMENTS_24H")

    # DAEMON_DOWN: any expected daemon whose log hasn't ticked in DAEMON_FRESH_MIN
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=DAEMON_FRESH_MIN)
    for name, info in daemon_logs.items():
        last = info.get("last_ts")
        if not last:
            # No log at all → treat as down if the file *should* exist.
            # If it genuinely doesn't exist (daemon never started), still flag.
            flags.append(f"DAEMON_DOWN({name}=no_log)")
            continue
        try:
            ts = datetime.fromisoformat(last.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                flags.append(f"DAEMON_DOWN({name}=stale_{int((datetime.now(timezone.utc)-ts).total_seconds())}s)")
        except Exception:
            flags.append(f"DAEMON_DOWN({name}=bad_ts)")
    return flags


# ── main ─────────────────────────────────────────────────────────────

def main() -> int:
    started_at = _now()
    digest = {
        "ts":          started_at,
        "kind":        "daily_digest",
        "tables":      _safe(collect_table_status, default={}),
        "settlements": _safe(collect_settlements_24h, default={}),
        "logs":        _safe(collect_logs, default={}),
        "system":      _safe(collect_system, default={}),
    }
    try:
        flags = compute_flags(
            digest["tables"], digest["system"],
            digest["settlements"], digest["logs"],
        )
    except Exception:
        flags = ["HEALTH_CHECK_FAILED"]
    digest["health_flags"] = flags
    digest["healthy"] = (len(flags) == 0)

    try:
        with open(DIGEST_PATH, "a") as f:
            f.write(json.dumps(digest, default=str) + "\n")
    except Exception as exc:
        print(f"[daily_digest] write failed: {exc}", flush=True)

    # Always exit 0 — digest daemon must not thrash systemd.
    print(json.dumps({
        "ts": started_at,
        "kind": "daily_digest",
        "ok": True,
        "flags": flags,
        "healthy": digest["healthy"],
        "settlements_24h": digest["settlements"],
        "load_1": digest["system"].get("load_1"),
    }), flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Last-ditch: never propagate to systemd.
        traceback.print_exc()
        sys.exit(0)