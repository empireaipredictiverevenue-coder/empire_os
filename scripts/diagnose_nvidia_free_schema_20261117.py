"""Diagnose a failed NVIDIA native-schema response using the existing free key.

Only synthetic table metadata leaves EmpireOS. No secrets or raw LLM text
are printed or recorded. Provider fallback disabled, zero-price model checked.
"""
from __future__ import annotations
import json, os, time, urllib.error
from pathlib import Path
from pydantic import ValidationError
from scripts.probe_existing_openrouter_nvidia_native_schema_20261116 import (
    ROOT, SECRET, MODEL, RawTableTermsResult, fetch_json,
)
OUTPUT=ROOT/"runtime/nvidia_ontology_eval/free_nvidia_schema_diagnosis_20261117.json"

def run():
    if OUTPUT.exists():
        raise RuntimeError("immutable receipt already exists")
    if SECRET.stat().st_mode & 0o077:
        raise RuntimeError("key is not private")
    key=""
    for line in SECRET.read_text().splitlines():
        line=line.strip().removeprefix("export ")
        if line.startswith("OPENROUTER_API_KEY="):
            key=line.partition("=")[2].strip().strip('"').strip("'")
    if not key:
        raise RuntimeError("existing key missing")
    items=fetch_json("https://openrouter.ai/api/v1/models").get("data",[])
    candidates=[x for x in items if x.get("id")==MODEL]
    if len(candidates)!=1 or (candidates[0].get("pricing") or {}).get("prompt")!="0" or (candidates[0].get("pricing") or {}).get("completion")!="0":
        raise RuntimeError("free model price not verified")
    schema=RawTableTermsResult.model_json_schema()
    request={
        "model":MODEL,
        "temperature":0,
        "max_tokens":1100,
        "stream":False,
        "provider":{"allow_fallbacks":False},
        "response_format":{"type":"json_schema","json_schema":{"name":"RawTableTermsResult","strict":True,"schema":schema}},
        "messages":[
            {"role":"system","content":"Return exactly a JSON object with key terms. terms must contain precisely ONE object with name, description and attributes. Each attribute must have source_column and display_name. Do not invent columns or claim a verified sale."},
            {"role":"user","content":"SYNTHETIC ontology_edges. id, source_node_id, target_node_id, relation, verification_status, demand_units. Produce one term with six attributes, one per named source column. NULL demand means unknown, never zero."}
        ]
    }
    result={"model":MODEL,"free_price_verified":True,"customer_data_sent":False,
            "used_original_schema":True,"paid_fallback":False,"result":"FAIL"}
    start=time.monotonic()
    try:
        response=fetch_json(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},
            data=json.dumps(request).encode(),
        )
        result["returned_model"]=response.get("model")
        msg=(response.get("choices") or [{}])[0].get("message") or {}
        content=msg.get("content") or ""
        result["content_length"]=len(content)
        result["finish_reason"]=(response.get("choices") or [{}])[0].get("finish_reason")
        try:
            raw=json.loads(content)
            result["response_root_type"]=type(raw).__name__
            if isinstance(raw,dict):
                result["top_level_keys"]=list(raw.keys())[:15]
                terms=raw.get("terms")
                result["terms_type"]=type(terms).__name__
                if isinstance(terms,list):
                    result["term_count"]=len(terms)
                    if terms and isinstance(terms[0],dict):
                        result["term_keys"]=list(terms[0].keys())[:15]
                        attrs=terms[0].get("attributes")
                        result["attribute_count"]=len(attrs) if isinstance(attrs,list) else -1
                        result["attribute_field_shapes"]=[
                            sorted(z.keys()) if isinstance(z,dict) else type(z).__name__
                            for z in (attrs or [])[:6]
                        ] if isinstance(attrs,list) else []
        except ValueError:
            result["invalid_json"]=True
        try:
            parsed=RawTableTermsResult.model_validate_json(content)
            terms=parsed.terms
            cols=[a.source_column for t in terms for a in t.attributes]
            expected={"id","source_node_id","target_node_id","relation","verification_status","demand_units"}
            result["schema_valid"]=True
            result["coverage_valid"]=len(terms)==1 and len(cols)==6 and set(cols)==expected
            result["result"]="PASS" if result["coverage_valid"] else "INVALID_COVERAGE"
        except ValidationError as exc:
            result["schema_valid"]=False
            result["validation_errors"]=[
                {"loc":"/".join(str(x) for x in e["loc"]), "type":e["type"]}
                for e in exc.errors(include_input=False)[:9]
            ]
    except urllib.error.HTTPError as exc:
        result["http_error"]=exc.code
    except Exception as exc:
        result["error_kind"]=type(exc).__name__
    result["elapsed_s"]=round(time.monotonic()-start,2)
    fd=os.open(OUTPUT,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=="__main__":
    run()
