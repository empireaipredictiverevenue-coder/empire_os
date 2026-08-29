#!/usr/bin/env python3
"""Empire OS Supervisor — senior-architect guardian.

Polls every 60s. Auto-fixes 5 categories of failure:

 1. WAL HEALTH: if empire_os.db-wal > 500MB, run PRAGMA wal_checkpoint(TRUNCATE)
 2. LOAD HEALTH: if load avg > 15 for 3 consecutive checks, log warning
 3. AGENT REGISTRY DRIFT: if /v1/agents != {hub:10.118.155.218:8081}, restart hub
 4. MAIL_SENDER GUARD: verify mail_sender.py has _daily_quota_ok + DAILY_SEND_LIMIT
 5. INBOUND REPLIES: verify /v1/replies/unprocessed returns 200

ALWAYS sys.exit(0). Short timeouts. Logs to supervisor_actions.jsonl.
"""
from __future__ import annotations

import json
import os
import signal
import sqlite3
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# --- config ---
INTERVAL_S = 60
WAL_LIMIT_MB = 500
LOAD_LIMIT = 15.0
LOAD_CONSEC_REQUIRED = 3
HTTP_TIMEOUT_S = 4
SHELL_TIMEOUT_S = 8

DB_PATH = "/root/empire_os/empire_os.db"
# Canonical hub runs INSIDE the empire-hub container at 10.118.155.218:8081.
# Do NOT point at 127.0.0.1 — that would make the supervisor restart the
# duplicate host hub, creating two competing instances on 8081.
HUB_URL = os.environ.get("HUB_URL", "http://10.118.155.218:8081")
MAIL_SENDER_PATH = "/root/empire_os/empire_os/mail_sender.py"
ACTIONS_LOG = Path("/root/empire_os/feedback/supervisor_actions.jsonl")

KNOWN_GOOD_AGENT = {"name": "hub", "host": "10.118.155.218", "port": 8081}

_shutdown = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(action: str, decision: str, **extra) -> None:
    """Append one JSONL line. Never raises."""
    entry = {"ts": _now(), "action": action, "decision": decision}
    entry.update(extra)
    try:
        ACTIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ACTIONS_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
    print("{} {} {} {}".format(entry["ts"], action, decision, extra), flush=True)


def _http_get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S) as r:
            return r.status, r.read().decode()
    except Exception as e:
        return 0, str(e)[:80]


def _wal_check() -> dict:
    """Check WAL size; truncate if over limit."""
    wal_path = DB_PATH + "-wal"
    try:
        sz = os.path.getsize(wal_path)
    except OSError:
        return {"action": "wal_check", "decision": "no_wal_file"}
    mb = sz / (1024 * 1024)
    if mb < WAL_LIMIT_MB:
        return {"action": "wal_check", "decision": "ok", "size_mb": round(mb, 1)}
    # over limit — truncate
    try:
        c = sqlite3.connect(f"file:{DB_PATH}?mode=rw", uri=True, timeout=20)
        busy, log, ckpt = c.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        c.close()
        return {
            "action": "wal_check",
            "decision": "truncated",
            "size_mb_before": round(mb, 1),
            "busy": busy,
            "log": log,
            "frames": ckpt,
        }
    except Exception as e:
        return {
            "action": "wal_check",
            "decision": "truncate_failed",
            "error": str(e)[:120],
            "size_mb": round(mb, 1),
        }


def _load_check(load_streak: list[bool]) -> dict:
    """Check load avg; track consecutive high-load streak."""
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
        load1 = float(parts[0])
    except Exception as e:
        return {"action": "load_check", "decision": "read_failed", "error": str(e)[:80]}
    high = load1 > LOAD_LIMIT
    load_streak.append(high)
    if len(load_streak) > LOAD_CONSEC_REQUIRED:
        load_streak.pop(0)
    if len(load_streak) == LOAD_CONSEC_REQUIRED and all(load_streak):
        return {
            "action": "load_check",
            "decision": "warning_sustained_high_load",
            "load1": load1,
            "streak": LOAD_CONSEC_REQUIRED,
        }
    return {"action": "load_check", "decision": "ok", "load1": load1}


def _agent_registry_check() -> dict:
    """Verify /v1/agents has exactly the known-good entry."""
    code, body = _http_get(HUB_URL + "/v1/agents")
    if code != 200:
        # hub down — try restart (rate-limited)
        return _maybe_restart_hub("hub_unreachable")
    try:
        d = json.loads(body)
    except Exception as e:
        return {"action": "agent_registry", "decision": "json_parse_failed", "error": str(e)[:80]}
    agents = d.get("agents", [])
    if len(agents) != 1:
        return _maybe_restart_hub(f"drift_count={len(agents)}")
    a = agents[0]
    if (a.get("name") != KNOWN_GOOD_AGENT["name"]
            or a.get("host") != KNOWN_GOOD_AGENT["host"]
            or a.get("port") != KNOWN_GOOD_AGENT["port"]):
        return _maybe_restart_hub("drift_entry")
    health = a.get("health", {})
    if health.get("status") not in ("online", "healthy"):
        return _maybe_restart_hub(f"drift_unhealthy={health.get('status')}")
    return {"action": "agent_registry", "decision": "ok", "count": 1}


def _restart_hub() -> None:
    # Canonical hub lives in the empire-hub container. Restart there, never
    # on the host (host copy is masked + must stay dead to avoid 8081 conflict).
    try:
        subprocess.run(
            ["incus", "exec", "empire-hub", "--",
             "systemctl", "restart", "empire-hub-8081"],
            timeout=SHELL_TIMEOUT_S,
            capture_output=True,
        )
    except Exception:
        pass


# ── restart cooldown ──
# Hub needs 30-60s to boot + run migrations. Restarting more often than that
# just kills it mid-startup (and can corrupt a WAL write → "database is locked"
# → the hub then refuses to start → permanent death-loop). Never restart twice
# within COOLDOWN_S of the last restart.
COOLDOWN_S = 180
_last_restart = 0.0


def _maybe_restart_hub(reason: str) -> dict:
    global _last_restart
    now = time.time()
    if now - _last_restart < COOLDOWN_S:
        return {"action": "agent_registry",
                "decision": "restart_suppressed_cooldown",
                "reason": reason,
                "cooldown_remaining_s": int(COOLDOWN_S - (now - _last_restart))}
    _last_restart = now
    _restart_hub()
    return {"action": "agent_registry", "decision": "hub_restarted",
            "reason": reason}


def _mail_guard_check() -> dict:
    """Verify mail_sender.py has the daily-limit guard tokens."""
    try:
        text = Path(MAIL_SENDER_PATH).read_text()
    except OSError as e:
        return {"action": "mail_guard", "decision": "file_missing", "error": str(e)[:80]}
    has_quota_fn = "def _daily_quota_ok" in text
    has_const = "DAILY_SEND_LIMIT" in text
    if has_quota_fn and has_const:
        return {"action": "mail_guard", "decision": "ok",
                "tokens": ["def _daily_quota_ok", "DAILY_SEND_LIMIT"]}
    return {"action": "mail_guard", "decision": "missing_tokens",
            "has_quota_fn": has_quota_fn, "has_const": has_const}


def _inbound_replies_check() -> dict:
    """Verify /v1/replies/unprocessed returns 200."""
    code, body = _http_get(HUB_URL + "/v1/replies/unprocessed")
    if code == 200:
        try:
            d = json.loads(body)
            return {"action": "inbound_replies", "decision": "ok",
                    "unprocessed": d.get("unprocessed")}
        except Exception:
            return {"action": "inbound_replies", "decision": "ok_body_unparsed"}
    return {"action": "inbound_replies", "decision": "endpoint_down", "http": code}


def _handle_signal(signum, frame):
    global _shutdown
    _shutdown = True


def main() -> int:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    _log("supervisor_started", "ok", interval_s=INTERVAL_S,
         wal_limit_mb=WAL_LIMIT_MB, load_limit=LOAD_LIMIT)
    load_streak: list[bool] = []
    while not _shutdown:
        try:
            results = [
                _wal_check(),
                _load_check(load_streak),
                _agent_registry_check(),
                _mail_guard_check(),
                _inbound_replies_check(),
            ]
            for r in results:
                _log(r["action"], r["decision"], **{k: v for k, v in r.items() if k not in ("action", "decision")})
        except Exception as e:
            _log("supervisor_loop", "exception", error=str(e)[:200])
        # sleep in small chunks so SIGTERM is responsive
        for _ in range(INTERVAL_S):
            if _shutdown:
                break
            time.sleep(1)
    _log("supervisor_stopped", "ok")
    return 0


if __name__ == "__main__":
    sys_exit_code = main()
    import sys
    sys.exit(sys_exit_code)