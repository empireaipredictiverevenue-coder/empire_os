#!/usr/bin/env bash
set -euo pipefail

CF_CONFIG=/home/ubuntu/.cloudflared/config.yml
BACKUP="${1:-}"

if [[ -z "$BACKUP" || ! -f "$BACKUP" ]]; then
  echo "valid Cloudflare backup path required" >&2
  exit 2
fi

case "$BACKUP" in
  /home/ubuntu/.cloudflared/config.yml.remote-commander.*.bak) ;;
  *)
    echo "backup path outside Remote Commander backup pattern" >&2
    exit 2
    ;;
esac

sudo cp -a "$BACKUP" "$CF_CONFIG"
sudo systemctl restart empire-cloudflared.service
sudo systemctl disable --now empire-ops-mcp.service || true

echo "rollback=complete"
echo "restored=$BACKUP"
