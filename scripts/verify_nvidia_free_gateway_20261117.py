"""End-to-end private gateway canary with real free NVIDIA inference.

Runs the existing Handler in a temporary loopback-only HTTP server,
then uses the exact LangChain client behaviour NVIDIA's vendor uses.
No Docker/service changes. Uses only fabricated synthetic table names.
"""
from __future__ import annotations
import json,os,threading,time
from http.server import ThreadingHTTPServer
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage,SystemMessage
from pydantic import BaseModel,Field
from scripts.nvidia_ontology_local_model_gateway_20261116 import Handler
from scripts.nvidia_free_openrouter_relay_20261117 import GATEWAY_ALIAS
from scripts.probe_existing_openrouter_nvidia_native_schema_20261116 import RawTableTermsResult

RECEIPT=Path("/srv/empire_os/runtime/nvidia_ontology_eval/nvidia_free_gateway_live_contract_20261117.json")
COLUMNS={"id","source_node_id","target_node_id","relation","verification_status","demand_units"}

class FindSyntheticRelation(BaseModel):
    """Select a synthetic graph relation for database inspection."""
    relation: str=Field(...,description="Exact relation constant")

def main():
    if RECEIPT.exists():raise RuntimeError("previous receipt exists")
    os.environ["EMPIRE_NVIDIA_EVAL_FREE_HOSTED_ENABLED"]="1"
    with ThreadingHTTPServer(("127.0.0.1",0),Handler) as server:
        server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        llm=ChatOpenAI(
            model=GATEWAY_ALIAS,
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            api_key="offline-model-disabled",
            max_tokens=8192,timeout=90,max_retries=0,
        )
        out={"gateway":"EXISTING_HANDLER_TEMPORARY_LOOPBACK",
             "remote_model_alias":GATEWAY_ALIAS,
             "secret_in_docker":False,"paid_fallbacks":False,"synthetic_only":True}
        start=time.monotonic()
        try:
            p=llm.with_structured_output(RawTableTermsResult).invoke([
                SystemMessage(content="Only synthetic schema; return ONE term with six source column assignments, no invented columns."),
                HumanMessage(content="Synthetic ontology_edges columns id, source_node_id, target_node_id, relation, verification_status, demand_units. NULL is unknown. Relationship is not proof of a sale. Output one Term with six attributes."),
            ])
            cols=[a.source_column for t in p.terms for a in t.attributes]
            out["schema_pass"]=len(p.terms)==1 and len(cols)==6 and set(cols)==COLUMNS
        except Exception as exc:
            out["schema_pass"]=False
            out["schema_error"]=type(exc).__name__
        out["schema_latency_s"]=round(time.monotonic()-start,2)
        start=time.monotonic()
        try:
            answer=llm.bind_tools([FindSyntheticRelation],tool_choice="FindSyntheticRelation").invoke([
                HumanMessage(content="Call FindSyntheticRelation for BUYER_DEMANDS_LANE, synthetic only.")
            ])
            calls=answer.tool_calls or []
            out["tool_call_pass"]=len(calls)==1 and calls[0].get("name")=="FindSyntheticRelation" and calls[0].get("args",{}).get("relation")=="BUYER_DEMANDS_LANE"
        except Exception as exc:
            out["tool_call_pass"]=False
            out["tool_error"]=type(exc).__name__
        out["tool_latency_s"]=round(time.monotonic()-start,2)
        server.shutdown()
        thread.join(timeout=5)
    out["pass"]=bool(out["schema_pass"] and out["tool_call_pass"])
    fd=os.open(RECEIPT,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as f:json.dump(out,f,indent=2)
    print(json.dumps(out,indent=2))
if __name__=="__main__":
    main()
