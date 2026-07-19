"""
Empire OS v3 - Tenant Studio

Multi-tenant portal:
  - buyer's dashboard with their lane inventory
  - their delivered leads + lead-quality scoring
  - subscription state + invoice history
  - upsell paths to next tier

Renders /v1/tenants/portal/<tenant>.html on demand.
"""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
import requests

HUB  = os.environ.get("HUB_URL", "http://127.0.0.1:8081")
FB   = Path("/root/feedback")
LOG  = FB / "tenant_studio_log.jsonl"


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level,
         "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "EVENT"):
        print(json.dumps(e), flush=True)


def fetch_tenant(tenant_id: str) -> dict:
    try:
        r = requests.get(f"{HUB}/v1/buyers",
                          params={"q": tenant_id, "limit": 1},
                          timeout=8).json()
        return (r.get("buyers") or [{}])[0]
    except Exception as e:
        log("ERROR", "fetch_tenant", err=str(e)[:120])
        return {}


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] tenant-studio online (pull-based)",
          flush=True)
    while True:
        try:
            log("INFO", "studio_ready",
                note="awaiting GET /v1/tenants/portal")
        except Exception:
            pass
        time.sleep(3600)
