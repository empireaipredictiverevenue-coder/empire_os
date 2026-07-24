#!/bin/bash
# cron-health-deep.sh — every 5 min, append deep health snapshot.
# Runs INSIDE empire-hub container. Writes /root/feedback/health_deep.jsonl.
# If the snapshot shows revenue_path_ready=false, optionally notify (when
# telegram wired later).
set -uo pipefail

# Load env from /run/empire-secrets.env if present (so /v1/health/deep
# sees the vault-loaded values when called from this cron context).
ENV_FILE=/run/empire-secrets.env
if [ -r "$ENV_FILE" ]; then
  set -a
  . "$ENV_FILE"
  set +a
fi

# Run from the host shell — call the hub endpoint, log result.
RESP=$(curl -s --max-time 20 http://127.0.0.1:8081/v1/health/deep 2>&1) || {
  # If hub is down, write a minimal "hub unreachable" record
  echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"ok\":false,\"summary\":{\"hub_unreachable\":true}}" >> /root/feedback/health_deep.jsonl
  exit 0
}

# Compact the response (drop nested check details when ok=true)
python3 - <<PYEOF
import json, sys
try:
    r = json.loads('''$RESP''')
except Exception as e:
    print(f"parse_error: {e}", file=sys.stderr)
    sys.exit(0)

row = {"ts": r.get("timestamp"), "ok": r.get("ok"),
       "summary": r.get("summary", {})}
if not r.get("ok"):
    # Surface the failing layer details
    for layer in ("env", "db", "chain", "hub", "listener"):
        if not r.get("summary", {}).get(f"{layer}_ok", True):
            row[f"fail_{layer}"] = r.get("checks", {}).get(layer)

with open("/root/feedback/health_deep.jsonl", "a") as f:
    f.write(json.dumps(row) + "\n")
PYEOF