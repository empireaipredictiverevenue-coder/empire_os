"""
Empire OS v3 — Crawler Agent (inside Incus container)

The container has a tiny loop that triggers the host's crawler_runner
via HTTPS (because the container's outbound network is slow/limited,
and the host has faster public API access).

Strategy:
  - Container loop runs every 30 minutes
  - Calls https://empire-ai.co.uk/internal/cron/crawler-run via Resend-style hook
  - Logs outcome
  - Falls back to local run with timeout if hook unavailable
"""
import urllib.request
import urllib.error
import time
import json
from datetime import datetime, timezone
from pathlib import Path


HOOK_URL = "http://10.118.155.218:8081/internal/cron/crawler-run"
INTERVAL = 30 * 60  # 30 min — host runs faster direct runs every 6h, this just syncs faster


def trigger_remote():
    try:
        req = urllib.request.Request(
            HOOK_URL,
            data=json.dumps({"trigger": "agent"}).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        with urllib.request.urlopen(req) as r:
            return r.status, r.read().decode()[:200]
    except Exception as e:
        return 0, str(e)


def trigger_local():
    """Fallback: run the crawler locally with timeout."""
    import subprocess
    try:
        r = subprocess.run(
            ["/root/venv/bin/python3", "-m", "empire_os.crawler_runner"],
            capture_output=True, text=True, timeout=180,
            cwd="/root/empire_os",
        )
        return r.returncode, r.stdout[-200:] if r.stdout else ""
    except Exception as e:
        return 1, str(e)


def main():
    Path("/root/feedback").mkdir(parents=True, exist_ok=True)
    log = Path("/root/feedback/crawler_agent.log")

    print(f"[{datetime.now(timezone.utc).isoformat()}] crawler-agent starting — interval {INTERVAL}s")

    while True:
        try:
            status, body = trigger_remote()
            if 200 <= status < 300:
                print(f"[{datetime.now(timezone.utc).isoformat()}] remote ok: {body}")
            else:
                rc, out = trigger_local()
                print(f"[{datetime.now(timezone.utc).isoformat()}] local fallback rc={rc}: {out[:100]}")
        except Exception as e:
            print(f"[{datetime.now(timezone.utc).isoformat()}] failed: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
