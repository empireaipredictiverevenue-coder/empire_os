#!/usr/bin/env bash
set -euo pipefail

ROOT="/srv/empire_os"
SYSTEMD_DIR="/etc/systemd/system"
UNITS=(
  "empire-ollama.service"
  "empire-coder-worker.service"
  "empire-coder-worker.timer"
)

if [[ "${1:-}" == "--check" ]]; then
  cd "$ROOT"
  systemd-analyze verify     ./empire-ollama.service     ./empire-coder-worker.service     ./empire-coder-worker.timer
  echo "Empire Coder systemd units verify cleanly."
  exit 0
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 2
fi

cd "$ROOT"
systemd-analyze verify   ./empire-ollama.service   ./empire-coder-worker.service   ./empire-coder-worker.timer

for unit in "${UNITS[@]}"; do
  install -o root -g root -m 0644 "$ROOT/$unit" "$SYSTEMD_DIR/$unit"
done

systemctl daemon-reload
systemctl enable empire-ollama.service
systemctl enable --now empire-coder-worker.timer

if curl -fsS --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null; then
  echo "Existing localhost Ollama is healthy; leaving it undisturbed."
else
  systemctl start empire-ollama.service
fi

if pgrep -u ubuntu -f 'scripts/empire_coder_worker.py --once' >/dev/null; then
  echo "Empire Coder worker is already active; not starting a second copy."
else
  systemctl start empire-coder-worker.service
fi

systemctl --no-pager --full status   empire-coder-worker.timer   empire-ollama.service || true

echo "Empire Coder services installed. API remains disabled unless explicitly configured."
