#!/usr/bin/env bash
# Correct ONE NVIDIA OAuth resource registration in the isolated frontend.
# Root-only Compose scope; authenticated viewer, SQL backend, Postgres, MCP
# daemon and hosted inference remain unchanged. Roll back on failed readback.
set -Eeuo pipefail
umask 077
export DOCKER_CONFIG=/home/ubuntu/.docker
cd /srv/empire_os
dir=/srv/empire_os/runtime/nvidia_ontology_eval
current="$dir/.env"
backup="$dir/.env.before-mcp-resource-20261117"
compose=/home/ubuntu/.docker/cli-plugins/docker-compose
yaml="$dir/compose.yaml"
report="$dir/nvidia_oauth_resource_frontend_activation_20261117.txt"
name=auto-ontology-frontend
required_model=openai/nvidia/nemotron-3.5-super-vl:free

if [[ "$(id -u)" != 0 ]]; then
  echo 'NVIDIA_FRONTEND_ACTIVATION_REQUIRES_FOUNDERS_SUDO_NO_CHANGES'
  exit 4
fi
if [[ ! -f "$backup" || ! -f "$current" || ! -f "$yaml" || -e "$report" ]]; then
  echo 'PRIVATE_SCOPE_PRECHECK_FAILED_NO_CHANGES'
  exit 5
fi
# Preserve exact pinned Compose tool. No downloads or builds.
echo 'af426722a8af5de812fcee30cc1c39f0639f5f723cbadefb25e5d4db054064cf  /home/ubuntu/.docker/cli-plugins/docker-compose' | sha256sum --check --status
for path in "$backup" "$current" "$yaml" "$dir/empire_graph.sqlite"; do
  [[ "$(stat -c '%a' "$path")" == 600 ]] || {
    echo 'UNSAFE_PRIVATE_FILE_PERMISSIONS_NO_CHANGES'
    exit 6
  }
done

# Full old/new identity equivalence except the intended one entry.
python3 -B - <<'PY'
from pathlib import Path
root=Path("/srv/empire_os/runtime/nvidia_ontology_eval")
old=(root/".env.before-mcp-resource-20261117").read_text().splitlines()
new=(root/".env").read_text().splitlines()
def pairs(lines):
    pairs=[x.split("=",1) for x in lines if "=" in x and not x.startswith("#")]
    assert len(pairs)==len(dict(pairs))
    return dict(pairs)
a,b=pairs(old),pairs(new)
assert a["CONNECTION_STRINGS"]==b["CONNECTION_STRINGS"]=="sqlite:////reference/empire_graph.sqlite"
assert a["AUTO_ONTOLOGY_MCP_PUBLIC_URL"]=="http://localhost:33003"
assert b["AUTO_ONTOLOGY_MCP_PUBLIC_URL"]=="http://127.0.0.1:33013"
assert a["APP_URL"]==b["APP_URL"]=="http://localhost:33000"
assert a["REASONING_MODEL"]==b["REASONING_MODEL"]=="openai/nvidia/nemotron-3.5-super-vl:free"
assert a["EMBED_MODEL"]==b["EMBED_MODEL"]=="nomic-embed-text"
assert {k:v for k,v in a.items() if k!="AUTO_ONTOLOGY_MCP_PUBLIC_URL"}=={
    k:v for k,v in b.items() if k!="AUTO_ONTOLOGY_MCP_PUBLIC_URL"}
print("ONE_SETTING_OAUTH_RESOURCE_DELTA_VERIFIED")
PY

"$compose" -f "$yaml" --env-file "$current" config --format json |
  python3 -B -c '
import json,sys
d=json.load(sys.stdin)
assert d["name"]=="empire-nvidia-ontology-eval"
svc=d["services"]
assert set(svc)>={"auto-ontology","auto-ontology-frontend","postgres","ingestion-service"}
assert d["networks"]["sandbox"]["internal"] is True
assert d["networks"]["ingress"]["driver_opts"]["com.docker.network.bridge.host_binding_ipv4"]=="127.0.0.1"
frontend=svc["auto-ontology-frontend"]
assert frontend["environment"]["CONNECTION_STRINGS"]=="sqlite:////reference/empire_graph.sqlite"
assert frontend["environment"]["AUTO_ONTOLOGY_MCP_PUBLIC_URL"]=="http://127.0.0.1:33013"
assert frontend["environment"]["APP_URL"]=="http://localhost:33000"
assert len(frontend["ports"])==1
assert frontend["ports"][0]["host_ip"]=="127.0.0.1"
assert str(frontend["ports"][0]["published"])=="33000"
for name in ("postgres","auto-ontology","ingestion-service"):
    assert svc[name]["restart"]=="no"
    assert svc[name]["networks"]=={"sandbox":None}
    assert svc[name].get("ports") is None
assert svc["auto-ontology"]["environment"]["REASONING_MODEL"]=="openai/nvidia/nemotron-3.5-super-vl:free"
print("NVIDIA_FRONTEND_ISOLATION_AND_NO_SPEND_GATES_VERIFIED")
'
for target in postgres auto-ontology ingestion-service "$name"; do
  test -n "$("$compose" -f "$yaml" --env-file "$current" ps -q "$target")" || {
    echo 'ISOLATED_CONTAINER_MISSING_NO_CHANGES'
    exit 7
  }
done
before_db=$("$compose" -f "$yaml" --env-file "$current" ps -q postgres)
before_backend=$("$compose" -f "$yaml" --env-file "$current" ps -q auto-ontology)
before_ingest=$("$compose" -f "$yaml" --env-file "$current" ps -q ingestion-service)
before_frontend=$("$compose" -f "$yaml" --env-file "$current" ps -q "$name")

# Credentials never enter the receipt or terminal output.
touch "$report"
chown ubuntu:ubuntu "$report"
chmod 600 "$report"
{
 echo 'EMPIRE_NVIDIA_OAUTH_RESOURCE_SCOPE_V1'
 date -u '+date_utc=%Y-%m-%dT%H:%M:%SZ'
 echo 'synthetic_only=1'
 echo 'recreate_target=auto-ontology-frontend'
 echo 'old_resource=http://localhost:33003/mcp'
 echo 'new_resource=http://127.0.0.1:33013/mcp'
} >> "$report"

rollback() {
  echo 'FRONTEND_OAUTH_RESOURCE_ROLLBACK_START' >> "$report"
  cp -p -- "$backup" "$current"
  timeout 90 "$compose" -f "$yaml" --env-file "$current" up -d     --no-deps --no-build --pull never "$name" >> "$report" 2>&1 || true
  echo 'FRONTEND_OAUTH_RESOURCE_ROLLBACK_ATTEMPTED' >> "$report"
}

result=0
if ! timeout 120 "$compose" -f "$yaml" --env-file "$current" up -d        --no-deps --no-build --pull never "$name" >> "$report" 2>&1; then
  result=10
fi
if [[ "$result" -eq 0 ]]; then
  healthy=0
  for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    if curl -fsS --max-time 6 http://127.0.0.1:33000/api/health |
      python3 -B -c 'import json,sys;d=json.load(sys.stdin); assert d["status"]=="ok" and d["postgres"]["status"]=="ok"' 2>/dev/null; then
      healthy=1;break
    fi
    sleep 2
  done
  if [[ "$healthy" -ne 1 ]]; then result=11;fi
fi
if [[ "$result" -eq 0 ]]; then
  runtime_url=$("$compose" -f "$yaml" --env-file "$current" exec -T "$name"     printenv AUTO_ONTOLOGY_MCP_PUBLIC_URL 2>/dev/null || true)
  if [[ "$runtime_url" != "http://127.0.0.1:33013" ]]; then
    result=12
  else
    echo 'FRONTEND_PROCESS_OAUTH_RESOURCE_READBACK_PASS' >> "$report"
  fi
fi
after_db=$("$compose" -f "$yaml" --env-file "$current" ps -q postgres)
after_backend=$("$compose" -f "$yaml" --env-file "$current" ps -q auto-ontology)
after_ingest=$("$compose" -f "$yaml" --env-file "$current" ps -q ingestion-service)
after_frontend=$("$compose" -f "$yaml" --env-file "$current" ps -q "$name")
if [[ "$before_db" != "$after_db" || "$before_backend" != "$after_backend" || "$before_ingest" != "$after_ingest" ]]; then
  result=13
  echo 'NON_FRONTEND_CONTAINER_ID_CHANGED' >> "$report"
elif [[ "$result" -eq 0 ]]; then
  echo 'POSTGRES_BACKEND_INGESTION_IDS_UNCHANGED_PASS' >> "$report"
fi
if [[ "$before_frontend" == "$after_frontend" && "$result" -eq 0 ]]; then
  result=14
  echo 'FRONTEND_NOT_RECREATED' >> "$report"
fi
if [[ "$result" -ne 0 ]]; then
  rollback
  echo "EXIT_STATUS=$result" >> "$report"
  echo "NVIDIA_OAUTH_RESOURCE_FRONTEND_ACTIVATION_HELD_AND_ROLLBACK_ATTEMPTED"
  exit "$result"
fi
echo 'EXIT_STATUS=0' >> "$report"
echo 'FRONTEND_ONLY_RUNTIME_RESOURCE_VERIFIED' >> "$report"
echo 'NVIDIA_OAUTH_RESOURCE_FRONTEND_ACTIVATED_SAME_DB_AND_BACKEND'
