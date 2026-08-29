#!/usr/bin/env python3
"""Empire OS self-heal watchdog.

Runs on timer (every 10 min). Prevents recurrence of today's breakage:
- transient DB locks killing oneshots
- stale failed units
- DB corruption

Actions:
1. reset-failed + restart any failed empire unit (oneshots only)
2. PRAGMA integrity_check on main DB; if corrupt, page /root/empire_os/feedback
3. warn if si_outbox backlog > 3000 (drain stuck)
4. warn if disk > 90%
Logs to /root/empire_os/feedback/self_heal.log (append, rotated).
"""
import os
import subprocess
import sqlite3
import shutil
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"
FEEDBACK = "/root/empire_os/feedback"
LOG = os.path.join(FEEDBACK, "self_heal.log")
MAX_LOG = 200_000
ONESHOTS = [
    "empire-cortex-engine", "empire-intelligence", "empire-predictive",
    "empire-settle-funnel", "empire-recovery-sequence", "empire-a2a-sales-agent",
    "empire-cortex-engine", "empire-ai-intel", "empire-business-agent",
    "empire-ceo-agent", "empire-company-intel",
]


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line)
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > MAX_LOG:
            try:
                os.rename(LOG, LOG + ".1")
            except OSError:
                pass
        os.makedirs(FEEDBACK, exist_ok=True)
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def run(cmd: list) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as e:  # noqa
        return f"ERR {e}"


def heal_units() -> None:
    failed = run(["systemctl", "list-units", "empire*", "--state=failed",
                  "--no-legend", "--no-pager"]).splitlines()
    names = [l.split()[0] for l in failed if l.strip()]
    if not names:
        log("units: all clean")
        return
    for n in names:
        run(["systemctl", "reset-failed", n])
        # restart only safe oneshots (not long-running daemons)
        if any(n == o or n.startswith(o) for o in ONESHOTS):
            r = run(["systemctl", "start", n])
            log(f"heal: restarted {n} -> {r or 'ok'}")
        else:
            log(f"heal: left {n} (daemon, investigate manually)")


def check_integrity() -> None:
    try:
        con = sqlite3.connect(DB, timeout=30)
        con.execute("PRAGMA busy_timeout=30000")
        res = con.execute("PRAGMA integrity_check").fetchall()
        con.close()
        ok = len(res) == 1 and res[0][0] == "ok"
        log(f"integrity: {'OK' if ok else 'CORRUPT ' + str(res[:3])}")
    except Exception as e:  # noqa
        log(f"integrity: ERR {str(e)[:200]}")


def check_outbox() -> None:
    try:
        con = sqlite3.connect(DB, timeout=30)
        con.execute("PRAGMA busy_timeout=30000")
        n = con.execute("SELECT count(*) FROM si_outbox WHERE status='pending'").fetchone()[0]
        con.close()
        flag = " BACKLOG" if n > 3000 else ""
        log(f"outbox_pending: {n}{flag}")
    except Exception as e:  # noqa
        log(f"outbox: ERR {str(e)[:200]}")


def check_disk() -> None:
    try:
        st = shutil.disk_usage("/root")
        pct = st.used / st.total * 100
        flag = " FULL" if pct > 90 else ""
        log(f"disk_root: {pct:.1f}%{flag}")
    except Exception:  # noqa
        pass


def main() -> None:
    log("=== self-heal tick ===")
    heal_units()
    check_integrity()
    check_outbox()
    check_disk()
    log("=== done ===")


if __name__ == "__main__":
    main()
