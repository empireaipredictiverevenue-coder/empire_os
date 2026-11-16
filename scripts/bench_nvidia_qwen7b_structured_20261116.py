"""Benchmark one preinstalled local candidate for NVIDIA structured output.

Synthetic input. Read-only to Ollama. Does not touch NVIDIA containers, app,
production DB, inference settings or user services.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
import httpx

MODEL = "qwen2.5-coder:7b"
URL = "http://127.0.0.1:11434/v1/chat/completions"
OUT = Path("/srv/empire_os/runtime/nvidia_ontology_eval/qwen7b_model_capability_probe_20261116.json")
SCHEMA = {
    "type": "object",
    "properties": {
        "terms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "attributes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source_column": {"type": "string"},
                                "display_name": {"type": "string"},
                            },
                            "required": ["source_column", "display_name"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["name", "description", "attributes"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["terms"],
    "additionalProperties": False,
}
MESSAGES = [
    {"role":"system","content":"Propose exactly one readable business Term for this synthetic relational table and assign ALL columns without inventing other columns. Only valid JSON."},
    {"role":"user","content":"Table ontology_edges. Synthetic evidence-referenced buyer-demand graph relationships; not proof of sales or verified buyers. Columns: id TEXT, source_node_id TEXT, target_node_id TEXT, relation TEXT, verification_status TEXT, demand_units INTEGER nullable. Return one Term and six attributes."},
]

def run():
    if OUT.exists():
        raise RuntimeError("previous evaluation exists; preserve it")
    started = time.monotonic()
    output = {
        "model": MODEL, "synthetic_only":True,
        "test":"NVIDIA_RAW_TABLE_TERMS_STRUCTURED_JSON_SCHEMA",
        "source":"LOCAL_PREINSTALLED_OLLAMA",
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(175.0,connect=8.0),
                          trust_env=False) as client:
            reply=client.post(URL,json={
                "model":MODEL, "messages":MESSAGES,"stream":False,
                "max_tokens":550,
                "temperature":0,
                "response_format":{
                    "type":"json_schema",
                    "json_schema":{
                        "name":"raw_table_terms_result", "strict":True, "schema":SCHEMA,
                    },
                },
            })
        output["http"]=reply.status_code
        if reply.status_code != 200:
            output["error_code"]="HTTP_"+str(reply.status_code)
        else:
            result=reply.json()
            output["usage"]=result.get("usage")
            content=(result.get("choices") or [{}])[0].get("message",{}).get("content") or ""
            try:
                parsed=json.loads(content)
                terms=parsed.get("terms",[])
                fields=set()
                for term in terms:
                    for attr in term.get("attributes",[]):
                        fields.add(attr["source_column"])
                expected={"id","source_node_id","target_node_id","relation","verification_status","demand_units"}
                output["valid_json"]=True
                output["term_count"]=len(terms)
                output["attributes_covered"]=len(fields)
                output["column_coverage_exact"]=fields==expected
                output["term_name"]=terms[0].get("name") if terms else None
                output["structured_pass"]=len(terms)==1 and fields==expected
            except (ValueError,KeyError,TypeError,AttributeError):
                output["valid_json"]=False
                output["structured_pass"]=False
                output["response_length"]=len(content)
    except Exception as exc:
        output["error_kind"]=type(exc).__name__
        output["structured_pass"]=False
    output["duration_s"]=round(time.monotonic()-started,2)
    fd=os.open(OUT,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        json.dump(output,f,indent=2)
    print(json.dumps(output,indent=2,sort_keys=True))

if __name__=="__main__":
    run()
