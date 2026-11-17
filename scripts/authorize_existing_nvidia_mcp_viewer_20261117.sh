#!/usr/bin/env bash
# User-initiated OAuth with an authorised NVIDIA *viewer* identity.
# It does not mint tokens, copy bootstrap administrator credentials or
# alter a running OpenCode service. Browser sign-in must be completed by user.
set -euo pipefail
if [[ "$(id -un)" != "ubuntu" ]]; then
  printf '%s\n' 'NVIDIA_VIEWER_OAUTH_REQUIRES_EXISTING_UBUNTU_SHELL'
  exit 3
fi
base=/tmp/empire_opencode_v2_free_20261113
service_config="$base/config/opencode/service.json"
mcp_config="$base/config/opencode/opencode.json"
binary=/home/ubuntu/.local/share/empire-opencode-v2-isolated/node_modules/@opencode/cli/bin/opencode.exe
if [[ ! -f "$service_config" || ! -f "$mcp_config" || ! -x "$binary" ]]; then
  echo 'EXISTING_OPEN_CODE_V2_NOT_READY'
  exit 4
fi
if ! curl -sf --max-time 6 http://127.0.0.1:33013/.well-known/oauth-protected-resource/mcp >/dev/null; then
  echo 'NVIDIA_MCP_OAUTH_PROVIDER_NOT_READY'
  exit 5
fi
export XDG_CONFIG_HOME="$base/config"
export XDG_DATA_HOME="$base/data"
export XDG_CACHE_HOME="$base/cache"
export OPENCODE_PASSWORD="$(/srv/empire_os/.venv/bin/python -B - <<'PY'
import json
from pathlib import Path
p=Path("/tmp/empire_opencode_v2_free_20261113/config/opencode/service.json")
assert p.stat().st_mode & 0o077 == 0
password=json.loads(p.read_text())["password"]
assert isinstance(password,str) and len(password)>10
print(password)
PY
)"
unset AUTO_ONTOLOGY_ADMIN_PASSWORD AUTO_ONTOLOGY_ADMIN_EMAIL || true
cd /srv/empire_os
echo 'Starting the existing OpenCode V2 OAuth flow. Sign in only as an approved NVIDIA viewer.'
echo 'Do not paste passwords, authorization codes, tokens or callback URLs into ChatGPT.'
exec "$binary" mcp auth nvidia-auto-ontology --server http://127.0.0.1:49374
