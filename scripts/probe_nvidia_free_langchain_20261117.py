"""Read-only LangChain contract preflight for NVIDIA free inference.

Calls a zero-price free model through existing OpenRouter key, using
synthetic ontology only. Does not alter running containers or saved config.
"""
from __future__ import annotations
import json,os,time
from pathlib import Path
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage,SystemMessage
from scripts.probe_existing_openrouter_nvidia_native_schema_20261116 import (
 SECRET,MODEL,RawTableTermsResult,fetch_json,ROOT,
)
OUTPUT=ROOT/"runtime/nvidia_ontology_eval/free_nvidia_langchain_compat_20261117.json"
FIELDS={"id","source_node_id","target_node_id","relation","verification_status","demand_units"}

class FindSyntheticRelation(BaseModel):
    """Find a relationship in the synthetic ontology edges table."""
    relation: str = Field(...,description="Exact relation name")

def run():
    if OUTPUT.exists():raise RuntimeError("immutable prior result exists")
    if SECRET.stat().st_mode & 0o077:raise RuntimeError("private credential permissions expected")
    key=""
    for s in SECRET.read_text().splitlines():
        s=s.strip().removeprefix("export ")
        if s.startswith("OPENROUTER_API_KEY="):
            key=s.split("=",1)[1].strip().strip('"').strip("'")
    if not key:raise RuntimeError("existing key missing")
    models=fetch_json("https://openrouter.ai/api/v1/models").get("data",[])
    matching=[m for m in models if m.get("id")==MODEL]
    if len(matching)!=1 or any((matching[0].get("pricing") or {}).get(k)!="0" for k in ("prompt","completion")):
        raise RuntimeError("model no longer free")
    llm=ChatOpenAI(
        model=MODEL,api_key=key,base_url="https://openrouter.ai/api/v1",
        max_tokens=1000,timeout=55,max_retries=0,
        extra_body={"provider":{"allow_fallbacks":False}},
    )
    result={"source":"EXISTING_KEY_FREE_MODEL_ONLY","model":MODEL,
            "test":"PINNED_NVIDIA_LANGCHAIN_AND_TOOL_CALL",
            "paid_fallbacks_disabled":True,"synthetic_only":True,"customer_data_sent":False}
    start=time.monotonic()
    try:
        msgs=[
            SystemMessage(content="Output one Term with exact column references. One only, no invented columns, zero demand distinct from unknown NULL."),
            HumanMessage(content="Synthetic ontology_edges table columns id, source_node_id, target_node_id, relation, verification_status, demand_units. Describe relationships not confirmed sales. Return ONE Term and six attributes."),
        ]
        # The actual NVIDIA runtime uses .with_structured_output; no custom parsing shortcut.
        parsed=llm.with_structured_output(RawTableTermsResult).invoke(msgs)
        sources=[a.source_column for term in parsed.terms for a in term.attributes]
        result["vendor_structured_pass"]=(len(parsed.terms)==1 and len(sources)==6 and set(sources)==FIELDS)
        result["vendor_schema_class"]=type(parsed).__name__
    except Exception as e:
        result["vendor_structured_pass"]=False
        result["vendor_error_kind"]=type(e).__name__
    result["structured_latency_s"]=round(time.monotonic()-start,2)
    start2=time.monotonic()
    try:
        toolcall=llm.bind_tools([FindSyntheticRelation],tool_choice="FindSyntheticRelation").invoke([
            HumanMessage(content="Call FindSyntheticRelation for relation BUYER_DEMANDS_LANE. Synthetic request only.")
        ])
        calls=getattr(toolcall,"tool_calls",[]) or []
        result["tool_call_pass"]=len(calls)==1 and calls[0].get("name")=="FindSyntheticRelation" and calls[0].get("args",{}).get("relation")=="BUYER_DEMANDS_LANE"
        result["tool_call_count"]=len(calls)
    except Exception as e:
        result["tool_call_pass"]=False
        result["tool_error_kind"]=type(e).__name__
    result["tool_latency_s"]=round(time.monotonic()-start2,2)
    result["overall_pass"]=bool(result["vendor_structured_pass"] and result["tool_call_pass"])
    fd=os.open(OUTPUT,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=="__main__":
    run()
