#!/usr/bin/env bash
# NVIDIA Auto Ontology evaluation: local model activation, isolated only.
# Do not change production services, published endpoints or global Docker state.
set -Eeuo pipefail
umask 077
export DOCKER_CONFIG=/home/ubuntu/.docker
dir=/srv/empire_os/runtime/nvidia_ontology_eval
compose=/home/ubuntu/.docker/cli-plugins/docker-compose
report="$dir/local_models_activation_readback.txt"

# Do not run root-controlled user CLI binaries if hashes differ.
echo 'af426722a8af5de812fcee30cc1c39f0639f5f723cbadefb25e5d4db054064cf  /home/ubuntu/.docker/cli-plugins/docker-compose' | sha256sum --check --status
echo '5fb31a097304fbf6dd4038649a0decf32c2b9510e4047acd7d68b9d700c46194  /home/ubuntu/.docker/cli-plugins/docker-buildx' | sha256sum --check --status

if [[ "$(id -u)" != 0 ]]; then
 echo 'ROOT_REQUIRED_NO_CHANGES'
 exit 4
fi
if [[ ! -f "$dir/.env" || ! -f "$dir/compose.yaml" || ! -f "$dir/.env.disabled-models-20261116" ]]; then
 echo 'PRIVATE_EVALUATION_CONFIG_MISSING'
 exit 5
fi
touch "$report"
chmod 600 "$report"
{
 echo 'EMPIRE_NVIDIA_LOCAL_MODELS_ACTIVATION_READBACK_V1'
 date -u '+checked_utc=%Y-%m-%dT%H:%M:%SZ'
 echo '[privileged config preflight]'
} > "$report"

finish() {
 local code="$1"
 {
  echo
  echo "ACTIVATION_EXIT_CODE=$code"
  echo '[nvidia project state]'
  "$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" ps -a 2>&1 || true
  echo '[last 70 backend and ingestion logs]'
  "$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" logs --no-color --tail 35 auto-ontology ingestion-service 2>&1 | tail -n 90 || true
  echo '[frontend health]'
  curl -fsS --max-time 5 http://127.0.0.1:33000/api/health 2>&1 || true
  echo
  echo 'END_NVIDIA_LOCAL_MODELS_READBACK'
 } >> "$report"
 if [[ "$code" -eq 0 ]]; then
   echo 'NVIDIA_LOCAL_MODELS_ROLLOUT_PASS; inspect semantic ingestion separately.'
 else
   echo 'NVIDIA_LOCAL_MODELS_ROLLOUT_HELD; inspect server readback.'
 fi
}

if ! "$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" config --format json |
 python3 -c '
import json,sys
x=json.load(sys.stdin); s=x["services"]; n=x["networks"]
assert x["name"]=="empire-nvidia-ontology-eval"
assert n["sandbox"]["internal"] is True
assert n["ingress"]["driver"]=="bridge"
assert "pgadmin" not in s
ports=[(name,port) for name,service in s.items() for port in service.get("ports",[])]
assert len(ports)==1 and ports[0][0]=="auto-ontology-frontend"
assert ports[0][1]["host_ip"]=="127.0.0.1" and str(ports[0][1]["published"])=="33000"
for name, service in s.items():
 assert service.get("restart")=="no" and not service.get("container_name")
 if name not in ("auto-ontology-frontend",):
  assert service.get("networks")=={"sandbox":None}
  assert not service.get("ports")
for name in ("auto-ontology","ingestion-service"):
 service=s[name]
 assert service["environment"]["EMBED_ENDPOINT"]=="http://172.18.0.1:19999/v1"
 assert service["environment"]["EMBED_MODEL"]=="nomic-embed-text"
 assert service["environment"]["REASONING_MODEL"]=="openai/qwen2.5-coder:1.5b"
 assert service["environment"]["REASONING_ENDPOINT"]=="http://172.18.0.1:19999/v1"
 assert service["environment"]["RERANK_ENDPOINT"]=="http://127.0.0.1:19999/v1"
 assert service["environment"]["CONNECTION_STRINGS"]=="sqlite:////reference/empire_graph.sqlite"
 assert service["environment"]["EMBED_API_KEY"]=="offline-model-disabled"
 assert service["environment"]["REASONING_API_KEY"]=="offline-model-disabled"
 mounts=service["volumes"]
 assert len(mounts)==1
 assert mounts[0]["read_only"] is True
 assert mounts[0]["source"]=="/srv/empire_os/runtime/nvidia_ontology_eval/empire_graph.sqlite"
print("ISOLATED_LOCAL_MODEL_CONFIG_PASS")
' >> "$report" 2>&1; then
 echo 'CONFIG_SECURITY_PREFLIGHT_FAILED' >> "$report"
 finish 11
 exit 11
fi

if ! curl -fsS --max-time 5 http://172.18.0.1:19999/health |
 python3 -c 'import sys,json; j=json.load(sys.stdin); assert j["status"]=="ok" and j["local_only"] is True' >> "$report" 2>&1; then
 echo 'LOCAL_MODEL_GATEWAY_UNHEALTHY' >> "$report"
 finish 12
 exit 12
fi

echo '[ingestion-container private network connectivity canary]' >> "$report"
if ! timeout 45 "$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" exec -T ingestion-service python - >> "$report" 2>&1 <<'PY'
import json
import urllib.request
url="http://172.18.0.1:19999"
with urllib.request.urlopen(url+"/health",timeout=7) as response:
    h=json.load(response)
assert h["status"]=="ok"
body=json.dumps({
  "model":"nomic-embed-text",
  "input":["synthetic buyer-market evidence"],
  "input_type":"passage",
  "truncate":"END",
  "modality":"text"
}).encode()
req=urllib.request.Request(url+"/v1/embeddings",data=body,headers={"Content-Type":"application/json"})
with urllib.request.urlopen(req,timeout=35) as response:
    data=json.load(response)
assert len(data["data"])==1
assert len(data["data"][0]["embedding"])==768
print("CONTAINER_TO_GATEWAY_EMBEDDING_PASS_768_DIM")
PY
then
 echo 'PRIVATE_NETWORK_CANARY_FAILED; containers unchanged' >> "$report"
 finish 13
 exit 13
fi

echo '[backend-container model reasoning canary]' >> "$report"
if ! timeout 190 "$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" exec -T auto-ontology python - >> "$report" 2>&1 <<'PY'
import json
import urllib.request
url="http://172.18.0.1:19999/v1/chat/completions"
body=json.dumps({
  "model":"openai/qwen2.5-coder:1.5b",
  "messages":[{"role":"user","content":"Answer only OK"}],
  "stream":False,
  "max_tokens":12
}).encode()
req=urllib.request.Request(url,data=body,headers={"Content-Type":"application/json"})
with urllib.request.urlopen(req,timeout=170) as response:
    data=json.load(response)
message=data["choices"][0]["message"]["content"]
assert isinstance(message,str) and message.strip().upper().strip(".!")=="OK", "unexpected synthetic reply"
print("CONTAINER_TO_GATEWAY_CHAT_PASS")
PY
then
 echo 'PRIVATE_MODEL_CANARY_FAILED; containers unchanged' >> "$report"
 finish 14
 exit 14
fi

echo '[save unaffected production and NVIDIA frontend container IDs]' >> "$report"
before_postgres=$("$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" ps -q postgres)
before_frontend=$("$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" ps -q auto-ontology-frontend)
if [[ -z "$before_postgres" || -z "$before_frontend" ]]; then
 echo 'SCOPE_GUARD_NO_DB_OR_FRONTEND; do not restart' >> "$report"
 finish 15
 exit 15
fi

echo '[recreate ingestion and backend ONLY]' >> "$report"
set +e
timeout 180 "$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" up -d --no-deps --no-build --pull never ingestion-service auto-ontology >> "$report" 2>&1
code=$?
set -e
after_postgres=$("$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" ps -q postgres)
after_frontend=$("$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" ps -q auto-ontology-frontend)
if [[ "$before_postgres" != "$after_postgres" || "$before_frontend" != "$after_frontend" ]]; then
 echo 'ISOLATION_VIOLATION_FOUND_OTHER_CONTAINERS_CHANGED' >> "$report"
 code=16
else
 echo 'UNTOUCHED_DB_AND_FRONTEND_IDS_CONFIRMED' >> "$report"
fi
# Allow the restarted ingestion service a short opportunity to ingest the fixture.
sleep 7
finish "$code"
exit "$code"
