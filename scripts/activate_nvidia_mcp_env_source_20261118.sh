#!/usr/bin/env bash
# Activate the existing NVIDIA MCP readiness correction on ONE user service.
# Do not alter the application, backend, DB, model, users or OpenCode service.
# Always preserve a private source rollback before touching the running MCP.
set -Eeuo pipefail
umask 077

[[ "$(id -un)" == "ubuntu" && "$(id -u)" != 0 ]] || {
  echo "NVIDIA_MCP_OWNER_REQUIRED_NO_CHANGES"; exit 3;
}
cd /srv/empire_os
unit=/srv/empire_os/deploy/systemd-user/empire-nvidia-ontology-mcp-eval.service
service=empire-nvidia-ontology-mcp-eval.service
src=/srv/empire_os/scripts/nvidia_mcp_verified_issuer_20261117.py
fix=/srv/empire_os/scripts/nvidia_mcp_env_source_compat_20261118.py
backup=/srv/empire_os/runtime/nvidia_ontology_eval/nvidia_mcp_launcher_pre_env_source_20261118.py
report=/srv/empire_os/runtime/nvidia_ontology_eval/nvidia_mcp_env_source_activation_20261118.txt
venv=/srv/empire_os/runtime/nvidia_ontology_eval/.mcp_venv/bin/python

[[ -f "$src" && -f "$fix" && -f "$unit" && ! -e "$backup" && ! -e "$report" ]] || {
  echo "NVIDIA_MCP_SCOPED_PREFLIGHT_UNEXPECTED_FILES_NO_CHANGES"; exit 4;
}
grep -Fq 'ExecStart=/srv/empire_os/runtime/nvidia_ontology_eval/.mcp_venv/bin/python -B /srv/empire_os/scripts/nvidia_mcp_verified_issuer_20261117.py' "$unit"
grep -Fq 'install_env_readiness(mcp, _client)' "$src"
grep -Fq 'ENV_SOURCE_PATH="/api/connections/source"' "$fix"
"$venv" -B -m py_compile "$src" "$fix"
python3 - <<'PY'
from pathlib import Path
s=Path('/srv/empire_os/runtime/nvidia_ontology_eval/.env').read_text().splitlines()
d=dict(x.split('=',1) for x in s if '=' in x and not x.startswith('#'))
assert d['CONNECTION_STRINGS']=='sqlite:////reference/empire_graph.sqlite'
assert d['REASONING_MODEL']=='openai/nvidia/nemotron-3.5-super-vl:free'
assert d['AUTO_ONTOLOGY_MCP_PUBLIC_URL']=='http://127.0.0.1:33013'
print('NVIDIA_MCP_SYNTHETIC_FREE_BACKEND_PREFLIGHT_PASS')
PY

export XDG_RUNTIME_DIR=/run/user/1000
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
systemctl --user is-active --quiet "$service"
old_pid="$(systemctl --user show "$service" -p MainPID --value)"
[[ "$old_pid" =~ ^[0-9]+$ && "$old_pid" -gt 0 ]]
[[ "$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:33013/mcp)" == 401 ]]

git diff --cached --quiet -- scripts/nvidia_mcp_verified_issuer_20261117.py || {
  echo "UNRELATED_STAGED_LAUNCHER_CHANGES_NO_ACTION"; exit 5;
}
git show HEAD:scripts/nvidia_mcp_verified_issuer_20261117.py > "$backup"
chmod 600 "$backup"
test -s "$backup"
: > "$report"
chmod 600 "$report"
{
  echo 'NVIDIA_MCP_ENV_SOURCE_ACTIVATION_V1'
  date -u '+date_utc=%Y-%m-%dT%H:%M:%SZ'
  echo "previous_pid=$old_pid"
  echo 'synthetic_only=1'
  echo 'restarted_service=empire-nvidia-ontology-mcp-eval.service'
  echo 'restart_of_database_frontend_backend_opencode=0'
  echo 'pre_restart_unauthorized_mcp_http=401'
} >> "$report"

rollback() {
  echo 'MCP_READINESS_ROLLBACK_START' >> "$report"
  cp -- "$backup" "$src"
  chmod 644 "$src"
  systemctl --user restart "$service" >> "$report" 2>&1 || true
  echo 'MCP_READINESS_ROLLBACK_ATTEMPTED' >> "$report"
}
if ! systemctl --user restart "$service" >> "$report" 2>&1; then
  rollback
  echo 'exit_status=7' >> "$report"
  exit 7
fi
good=0
for _ in {1..20}; do
  if systemctl --user is-active --quiet "$service" &&
     curl -fsS --max-time 4 'http://127.0.0.1:33013/.well-known/oauth-protected-resource/mcp' |
       python3 -c 'import json,sys;d=json.load(sys.stdin);assert d["resource"]=="http://127.0.0.1:33013/mcp";assert d["authorization_servers"]==["http://localhost:33000/api/auth"]' 2>/dev/null &&
     [[ "$(curl -sS --max-time 4 -o /dev/null -w '%{http_code}' http://127.0.0.1:33013/mcp)" == 401 ]]; then
    good=1;break
  fi
  sleep 1
done
new_pid="$(systemctl --user show "$service" -p MainPID --value)"
if [[ "$good" != 1 || "$new_pid" == "$old_pid" || "$new_pid" == 0 ]]; then
  rollback
  echo 'exit_status=8' >> "$report"
  echo 'NVIDIA_MCP_READINESS_ACTIVATION_ROLLED_BACK'
  exit 8
fi
{
  echo "new_pid=$new_pid"
  echo 'oauth_issuer_metadata_consistent=1'
  echo 'anonymous_mcp_http=401'
  echo 'verified_restarted_original_user_service=1'
  echo 'source_patch_imported=1'
  echo 'exit_status=0'
} >> "$report"
echo 'NVIDIA_MCP_ENV_SOURCE_READINESS_ACTIVATED_SINGLE_SERVICE'
