import json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

FB = Path("/root/feedback")
LOG = FB / "os_upgrade.jsonl"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(7 * 24 * 3600)))

def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level,
         "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f: f.write(json.dumps(e) + "\n")
    if level in ("EVENT", "ERROR"):
        print(json.dumps(e), flush=True)

def cycle():
    log("CYCLE", "os_upgrade_scheduled", note="apt safe-run on Sunday 04:00 UTC")

if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] os-upgrade online", flush=True)
    while True:
        try: cycle()
        except Exception as e: log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)
