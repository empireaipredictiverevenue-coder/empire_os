#!/usr/bin/env python3
"""
deep_health_guard.py — systemd ExecStartPost guard for empire-hub-8081.

Polls /v1/health/deep for up to 60 seconds, waiting for revenue_path_ready.
On success: exit 0 (hub stays up).
On timeout/break: exit 1 (systemd restarts the hub).

Writes last result to /run/empire-deep-last.json for forensics.
"""
from __future__ import annotations
import json
import os
import sys
import time
import urllib.error
import urllib.request

HUB_URL = "http://127.0.0.1:8081/v1/health/deep"
LOG_PATH = "/run/empire-deep-last.json"
MAX_WAIT_SECONDS = 60
PER_CALL_TIMEOUT = 10
RETRY_INTERVAL = 1


def main() -> int:
    deadline = time.monotonic() + MAX_WAIT_SECONDS
    last: object = None
    ok = False
    attempt = 0

    while time.monotonic() < deadline:
        attempt += 1
        try:
            with urllib.request.urlopen(HUB_URL,
                                         timeout=PER_CALL_TIMEOUT) as r:
                body = r.read().decode("utf-8", errors="replace")
            data = json.loads(body)
            last = data
            if data.get("revenue_path_ready") is True:
                ok = True
                break
        except (urllib.error.URLError, ConnectionError, TimeoutError,
                json.JSONDecodeError) as e:
            last = f"attempt {attempt}: {type(e).__name__}: {e}"
        except Exception as e:
            last = f"attempt {attempt}: {type(e).__name__}: {e}"
        time.sleep(RETRY_INTERVAL)

    # Persist last result (truncate to keep file small)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        payload = {
            "ok": ok,
            "attempts": attempt,
            "elapsed_seconds": round(time.monotonic() - (
                deadline - MAX_WAIT_SECONDS), 2),
            "last": str(last)[:2000] if last is not None else None,
        }
        with open(LOG_PATH, "w") as f:
            json.dump(payload, f, indent=2)
    except OSError:
        pass  # Don't fail the guard just because logging failed

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())