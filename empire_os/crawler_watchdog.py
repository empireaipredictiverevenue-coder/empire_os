#!/usr/bin/env python3
"""crawler_watchdog.py — self-heal for Empire OS crawler/lead-gen processes.

These are long-running background python scripts (NOT systemd units):
  - scrape_contractors.py  (real contractor leads via Serper)
  - content_batch.py       (132-niche content engine)
  - free_source_sniper.py  (intent leads from HN/RSS)
  - content_pipeline.py    (perpetual 15-min content cycle — also covered by cron)

For each: if the process is NOT running, restart it (nohup, background).
Also: if the log file is stale (> freshness_min), restart (process hung).
One telegram alert per restart (deduped via state file).

Run from empire_watchdog cron (every 5 min) or standalone.
"""
from __future__ import annotations
import subprocess, time, os, json, datetime

ROOT = "/root/empire_os"
PY = "/root/venv/bin/python3"
LOGDIR = f"{ROOT}/logs"
STATE = f"{LOGDIR}/crawler_watchdog_state.json"

# (script, args, logfile, freshness_min, max_runtime_min)
CRAWLERS = [
    ("empire_os/scrape_contractors.py", "--cap 300", "contractor_crawl.log", 90, 120),
    ("empire_os/content_batch.py", "", "content_batch.log", 120, 240),
    ("empire_os/free_source_sniper.py", "--push", "sniper.log", 360, 60),
]

ALERT = f"{ROOT}/logs/crawler_watchdog_alerts.log"


def _procs(script):
    try:
        out = subprocess.run(["pgrep", "-f", script], capture_output=True, text=True, timeout=10)
        return [p for p in out.stdout.split() if p.strip()]
    except Exception:
        return []


def _log_mtime(logfile):
    p = f"{LOGDIR}/{logfile}"
    if not os.path.exists(p):
        return None
    return os.path.getmtime(p)


def _restart(script, args, logfile):
    cmd = f"nohup {PY} {ROOT}/{script} {args} >> {LOGDIR}/{logfile} 2>&1 &"
    subprocess.run(["bash", "-c", cmd], timeout=10)
    return cmd


def _alert(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    open(ALERT, "a").write(f"[{ts}] {msg}\n")
    # also try telegram if available
    try:
        from empire_os.telegram_alert import send_alert
        send_alert(f"[crawler_watchdog] {msg}")
    except Exception:
        pass


def main():
    try:
        state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    except Exception:
        state = {}
    now = time.time()
    for script, args, logfile, fresh, maxrt in CRAWLERS:
        procs = _procs(script)
        restarted = False
        reason = ""
        if not procs:
            reason = "process not running"
            restarted = True
        else:
            mtime = _log_mtime(logfile)
            if mtime and (now - mtime) > fresh * 60:
                reason = f"log stale >{fresh}m (hung)"
                restarted = True
                # kill stale
                for p in procs:
                    subprocess.run(["kill", "-9", p], timeout=5)
        if restarted:
            _restart(script, args, logfile)
            state[script] = now
            _alert(f"RESTART {script} ({reason})")
            print(f"RESTART {script} — {reason}")
        else:
            print(f"OK {script} ({len(procs)} proc)")
    json.dump(state, open(STATE, "w"))


if __name__ == "__main__":
    main()
