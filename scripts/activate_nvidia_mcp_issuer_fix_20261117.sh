#!/usr/bin/env bash
# Bounded user-service restart of the already-running NVIDIA MCP evaluation.
# No frontend/backend/DB restart, no new identities, no OAuth bypass.
set -Eeuo pipefail
if [[ "$(id -un)" != "ubuntu" ]]; then echo "USER_SERVICE_OWNER_REQUIRED"; exit 3; fi
cd /srv/empire_os
unit=deploy/systemd-user/empire-nvidia-ontology-mcp-eval.service
backup=runtime/nvidia_ontology_eval/mcp-unit.pre-issuer-fix-20261117.service
old='ExecStart=/srv/empire_os/runtime/nvidia_ontology_eval/.mcp_venv/bin/python -B -m auto_ontology_mcp'
new='ExecStart=/srv/empire_os/runtime/nvidia_ontology_eval/.mcp_venv/bin/python -B /srv/empire_os/scripts/nvidia_mcp_verified_issuer_20261117.py'
service=empire-nvidia-ontology-mcp-eval.service
if [[ -e "$backup" ]]; then echo "MCP_ROLLBACK_ALREADY_EXISTS_NO_CHANGES"; exit 5; fi
if [[ "$(grep -cFx "$old" "$unit")" != 1 ]]; then echo "MCP_UNIT_CHANGED_NO_CHANGES"; exit 4; fi
python3 -B -m py_compile scripts/nvidia_mcp_verified_issuer_20261117.py
cp -- "$unit" "$backup"
chmod 600 "$backup"
rollback() {
  cp -- "$backup" "$unit"
  systemctl --user daemon-reload
  systemctl --user restart "$service" || true
  echo "MCP_ISSUER_ACTIVATION_ROLLED_BACK"
}
export XDG_RUNTIME_DIR=/run/user/1000
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
python3 - "$unit" "$old" "$new" <<'PY'
from pathlib import Path
import sys
path=Path(sys.argv[1])
text=path.read_text()
if text.count(sys.argv[2])!=1:raise SystemExit("MCP_EXACT_MATCH_FAILED")
path.write_text(text.replace(sys.argv[2],sys.argv[3]))
PY
if ! systemd-analyze verify "$unit" || ! systemctl --user daemon-reload || ! systemctl --user restart "$service"; then
  rollback
  exit 6
fi
ok=0
for i in {1..12}; do
  if systemctl --user is-active --quiet "$service" && python3 -B - <<'PY'
import json,urllib.request,urllib.error
base='http://127.0.0.1:33013'
with urllib.request.urlopen(base+'/.well-known/oauth-protected-resource/mcp',timeout=3) as resp:
    doc=json.load(resp)
assert doc['resource']==base+'/mcp'
assert doc['authorization_servers']==['http://localhost:33000/api/auth']
for headers in ({},{'Authorization':'Bearer invalid-issuer-probe'}):
    req=urllib.request.Request(base+'/mcp',headers=headers)
    try:urllib.request.urlopen(req,timeout=3)
    except urllib.error.HTTPError as error:
        assert error.code==401
    else:raise AssertionError("MCP unauthorized request accepted")
PY
  then
    ok=1
    break
  fi
  sleep 1
done
if [[ "$ok" -ne 1 ]]; then
  rollback
  exit 7
fi
echo "NVIDIA_NATIVE_MCP_RFC8414_ISSUER_CORRECTED_AND_ANONYMOUS_DENIAL_VERIFIED"
