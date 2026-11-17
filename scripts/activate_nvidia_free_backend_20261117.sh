#!/usr/bin/env bash
# Founder-controlled isolated NVIDIA backend ONLY — free hosted model.
# Requires existing authenticated local gateway and synthetic source.
set -Eeuo pipefail
umask 077
export DOCKER_CONFIG=/home/ubuntu/.docker
dir=/srv/empire_os/runtime/nvidia_ontology_eval
compose=/home/ubuntu/.docker/cli-plugins/docker-compose
report="$dir/free_backend_activation_readback_20261117.txt"
model="openai/nvidia/nemotron-3.5-super-vl:free"

if [[ "$(id -u)" != 0 ]]; then echo 'ROOT_REQUIRED_NO_CHANGES'; exit 4; fi
echo 'af426722a8af5de812fcee30cc1c39f0639f5f723cbadefb25e5d4db054064cf  /home/ubuntu/.docker/cli-plugins/docker-compose' | sha256sum --check --status
echo '5fb31a097304fbf6dd4038649a0decf32c2b9510e4047acd7d68b9d700c46194  /home/ubuntu/.docker/cli-plugins/docker-buildx' | sha256sum --check --status
if [[ ! -f "$dir/.env.before-free-nemotron-20261117" || ! -f "$dir/.env" || ! -f "$dir/compose.yaml" ]]; then
 echo 'NVIDIA_FREE_MODEL_PRIVATE_BUNDLE_MISSING'; exit 5
fi
touch "$report"; chmod 600 "$report"
{
 echo 'NVIDIA_FREE_HOSTED_BACKEND_ACTIVATION_READBACK_V1'
 date -u '+checked_utc=%Y-%m-%dT%H:%M:%SZ'
} > "$report"

finish() {
 local status="$1"
 {
   echo "ACTIVATION_EXIT_CODE=$status"
   echo "[isolated project status]"
   "$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" ps -a 2>&1 || true
   echo "[backend last 50 lines]"
   "$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" logs --no-color --tail 50 auto-ontology 2>&1 | tail -n 60 || true
   echo "[private app health]"
   curl -sS --fail --max-time 5 http://127.0.0.1:33000/api/health 2>&1 || true
   echo
   echo 'END_NVIDIA_FREE_BACKEND_READBACK'
 } >> "$report"
 if [[ "$status" == 0 ]]; then
   echo 'NVIDIA_FREE_MODEL_BACKEND_ACTIVATED; NLP-SQL acceptance still required.'
 else
   echo 'NVIDIA_FREE_MODEL_ACTIVATION_HELD; inspect private readback.'
 fi
}

# Fail closed if topology, placeholder credentials, data source or port differ.
if ! "$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" config --format json | python3 -c '
import json,sys
x=json.load(sys.stdin)
assert x["name"]=="empire-nvidia-ontology-eval"
s=x["services"]; n=x["networks"]
assert n["sandbox"]["internal"] is True
assert n["ingress"]["driver"]=="bridge"
assert n["ingress"]["driver_opts"]["com.docker.network.bridge.host_binding_ipv4"]=="127.0.0.1"
assert "pgadmin" not in s
ports=[(name,p) for name,v in s.items() for p in v.get("ports",[])]
assert len(ports)==1 and ports[0][0]=="auto-ontology-frontend"
assert ports[0][1]["host_ip"]=="127.0.0.1" and str(ports[0][1]["published"])=="33000"
for name,service in s.items():
 assert service.get("restart")=="no" and not service.get("container_name")
 if name!="auto-ontology-frontend":
  assert service["networks"]=={"sandbox":None} and not service.get("ports")
for name in ("auto-ontology","ingestion-service"):
 v=s[name]
 e=v["environment"]
 assert e["CONNECTION_STRINGS"]=="sqlite:////reference/empire_graph.sqlite"
 assert e["DEFAULT_MODELS_MODEL"]=="openai/nvidia/nemotron-3.5-super-vl:free"
 assert e["REASONING_MODEL"]=="openai/nvidia/nemotron-3.5-super-vl:free"
 assert e["NON_REASONING_MODEL"]=="openai/nvidia/nemotron-3.5-super-vl:free"
 for k in ("DEFAULT_MODELS_ENDPOINT","REASONING_ENDPOINT","NON_REASONING_ENDPOINT","EMBED_ENDPOINT"):
  assert e[k]=="http://172.18.0.1:19999/v1"
 assert e["EMBED_MODEL"]=="nomic-embed-text"
 assert e["RERANK_ENDPOINT"]=="http://127.0.0.1:19999/v1"
 for k in ("DEFAULT_MODELS_API_KEY","REASONING_API_KEY","NON_REASONING_API_KEY","EMBED_API_KEY"):
  assert e[k]=="offline-model-disabled"
 assert "OPENROUTER_API_KEY" not in e
 mounts=v["volumes"]
 assert len(mounts)==1
 assert mounts[0]["source"]=="/srv/empire_os/runtime/nvidia_ontology_eval/empire_graph.sqlite"
 assert mounts[0]["read_only"] is True
print("NVIDIA_FREE_HOSTED_COMPOSE_SECURITY_PASS")
' >>"$report" 2>&1; then
 echo 'COMPOSE_SCOPE_GUARD_FAILED' >>"$report"; finish 11; exit 11
fi

if ! curl -fsS --max-time 7 http://172.18.0.1:19999/health |
  python3 -c 'import sys,json; assert json.load(sys.stdin)["status"]=="ok"' >>"$report" 2>&1; then
 echo 'HOST_GATEWAY_UNHEALTHY' >>"$report"; finish 12; exit 12
fi

# BEFORE recreating anything, execute real LangChain native-schema and tool
# requests inside NVIDIA's existing backend container against the free gateway.
echo '[existing backend -> free gateway Pydantic and tool canaries]' >>"$report"
if ! timeout 145 "$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" exec -T auto-ontology python - >>"$report" 2>&1 <<'PY'
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage,SystemMessage
from auto_ontology.semantic.models import RawTableTermsResult
from pydantic import BaseModel,Field

class FindSyntheticRelation(BaseModel):
    """Select a relationship in the synthetic graph."""
    relation:str=Field(...,description="Exact relation")

llm=ChatOpenAI(
    model="openai/nvidia/nemotron-3.5-super-vl:free",
    api_key="offline-model-disabled",
    base_url="http://172.18.0.1:19999/v1",
    max_tokens=8192,timeout=100,max_retries=0,
)
response=llm.with_structured_output(RawTableTermsResult).invoke([
    SystemMessage(content="Synthetic-only graph. Return exactly one Term with six attributes. No invented fields or verified sales."),
    HumanMessage(content="ontology_edges columns id, source_node_id, target_node_id, relation, verification_status, demand_units; unknown demand NULL is not zero."),
])
sources=[a.source_column for t in response.terms for a in t.attributes]
assert len(response.terms)==1 and len(sources)==6
assert set(sources)=={"id","source_node_id","target_node_id","relation","verification_status","demand_units"}
print("NVIDIA_CONTAINER_TO_FREE_GATEWAY_STRUCTURED_SCHEMA_PASS",flush=True)

response=llm.bind_tools([FindSyntheticRelation],tool_choice="FindSyntheticRelation").invoke([
    HumanMessage(content="Use FindSyntheticRelation for synthetic BUYER_DEMANDS_LANE")
])
calls=response.tool_calls or []
assert len(calls)==1 and calls[0]["name"]=="FindSyntheticRelation"
assert calls[0]["args"]["relation"]=="BUYER_DEMANDS_LANE"
print("NVIDIA_CONTAINER_TO_FREE_GATEWAY_TOOL_CALL_PASS",flush=True)
PY
then
 echo 'FREE_MODEL_CONTAINER_CANARY_FAILED; containers unchanged' >>"$report"
 finish 13; exit 13
fi

before_db=$("$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" ps -q postgres)
before_ui=$("$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" ps -q auto-ontology-frontend)
before_ingest=$("$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" ps -q ingestion-service)
before_backend=$("$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" ps -q auto-ontology)
if [[ -z "$before_db" || -z "$before_ui" || -z "$before_ingest" || -z "$before_backend" ]]; then
 echo 'PROJECT_SERVICES_NOT_PRESENT'; finish 14; exit 14
fi
echo '[recreating isolated NVIDIA backend ONLY]' >>"$report"
set +e
timeout 160 "$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" up -d --no-deps --no-build --pull never auto-ontology >>"$report" 2>&1
status=$?
set -e
after_db=$("$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" ps -q postgres)
after_ui=$("$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" ps -q auto-ontology-frontend)
after_ingest=$("$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" ps -q ingestion-service)
if [[ "$before_db" != "$after_db" || "$before_ui" != "$after_ui" || "$before_ingest" != "$after_ingest" ]]; then
 echo 'NON_BACKEND_CONTAINER_CHANGED' >>"$report"
 status=15
else
 echo 'UNTOUCHED_POSTGRES_FRONTEND_INGESTION_IDS_CONFIRMED' >>"$report"
fi
if [[ "$status" == 0 ]]; then
 sleep 5
 if ! "$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" exec -T auto-ontology python -c '
import os
assert os.environ["REASONING_MODEL"]=="openai/nvidia/nemotron-3.5-super-vl:free"
assert os.environ["CONNECTION_STRINGS"]=="sqlite:////reference/empire_graph.sqlite"
assert os.environ["EMBED_MODEL"]=="nomic-embed-text"
print("NVIDIA_FREE_BACKEND_RUNTIME_ENV_VERIFIED")
' >>"$report" 2>&1; then
  status=16
 fi
 if ! curl -fsS --max-time 10 http://127.0.0.1:33000/api/health |
   python3 -c 'import json,sys;d=json.load(sys.stdin);assert d["status"]=="ok" and d["postgres"]["status"]=="ok"' >>"$report" 2>&1; then
  status=17
 fi
fi
if [[ "$status" != 0 ]]; then
 echo '[activation incomplete: restoring original private .env and backend]' >>"$report"
 cp "$dir/.env.before-free-nemotron-20261117" "$dir/.env"
 chmod 600 "$dir/.env"
 "$compose" -f "$dir/compose.yaml" --env-file "$dir/.env" up -d --no-deps --no-build --pull never auto-ontology >>"$report" 2>&1 || true
 echo 'NVIDIA_BACKEND_ROLLBACK_ATTEMPTED' >>"$report"
fi
finish "$status"
exit "$status"
