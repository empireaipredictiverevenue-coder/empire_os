#!/usr/bin/env bash
set -euo pipefail

export HOME=/home/ubuntu
export NVM_DIR="$HOME/.nvm"

if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  # shellcheck disable=SC1090
  . "$NVM_DIR/nvm.sh"
fi

if ! command -v omniroute >/dev/null 2>&1; then
  echo "omniroute executable not found in ubuntu runtime PATH" >&2
  exit 127
fi

exec omniroute --no-open
