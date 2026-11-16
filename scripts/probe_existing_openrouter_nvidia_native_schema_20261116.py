"""Read-only model canary: existing free OpenRouter/NVIDIA vs pinned vendor schema.

Sends ONLY invented synthetic table metadata, never PII, to a free model.
Does not configure or restart NVIDIA. Does not submit paid-model fallback.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path("/srv/empire_os")
VENDOR = ROOT / "runtime/nvidia_ontology_eval/vendor"
SECRET = Path("/etc/empire_os/llm_secrets/openrouter.env")
RESULT = ROOT / "runtime/nvidia_ontology_eval/hosted_free_nemotron_native_schema_20261116.json"
MODEL = "nvidia/nemotron-3.5-super-vl:free"
FIELDS = frozenset({
    "id", "source_node_id", "target_node_id", "relation",
    "verification_status", "demand_units",
})
sys.path.insert(0, str(VENDOR))
from auto_ontology.semantic.models import RawTableTermsResult  # noqa: E402


def fetch_json(url: str, *, headers: dict | None = None, data: bytes | None = None) -> dict:
    method = "POST" if data is not None else "GET"
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(request, timeout=95) as response:
        return json.load(response)


def main() -> None:
    if RESULT.exists():
        raise RuntimeError("previous NVIDIA schema receipt exists")
    if SECRET.stat().st_mode & 0o077:
        raise RuntimeError("OpenRouter key file not private")
    secret_map = {}
    for line in SECRET.read_text().splitlines():
        line = line.strip().removeprefix("export ")
        if line and not line.startswith("#") and "=" in line:
            k,v = line.split("=",1)
            secret_map[k] = v.strip().strip('"').strip("'")
    credential = secret_map.get("OPENROUTER_API_KEY")
    if not credential:
        raise RuntimeError("existing key unavailable")
    catalog = fetch_json("https://openrouter.ai/api/v1/models")
    matching = [item for item in catalog.get("data", []) if item.get("id") == MODEL]
    if len(matching) != 1:
        raise RuntimeError("free NVIDIA model unavailable")
    chosen = matching[0]
    prices = chosen.get("pricing") or {}
    if prices.get("prompt") != "0" or prices.get("completion") != "0":
        raise RuntimeError("paid route not authorized")
    features = set(chosen.get("supported_parameters") or [])
    if not {"response_format", "structured_outputs"}.issubset(features):
        raise RuntimeError("native structured output not advertised")
    schema = RawTableTermsResult.model_json_schema()
    payload = {
        "model": MODEL,
        "max_tokens": 750,
        "temperature": 0,
        "stream": False,
        "provider": {"allow_fallbacks": False},
        "messages": [
            {"role":"system", "content":"Invented synthetic schema only. Propose exactly ONE meaningful business term for the table. Assign each of the six physical columns once, preserving exact source_column. Do not infer real customer, revenue, buyer approval or verified sales."},
            {"role":"user", "content":"Table: ontology_edges. Synthetic relationship records, not verified sales. Columns: id TEXT, source_node_id TEXT, target_node_id TEXT, relation TEXT, verification_status TEXT, demand_units INTEGER nullable. Provide one term, a clear explanation and exactly six source-column assignments. Demand units NULL means unknown, never 0."},
        ],
        "response_format": {
            "type":"json_schema",
            "json_schema":{
                "name":"RawTableTermsResult",
                "strict":True,
                "schema":schema,
            },
        },
    }
    started = time.monotonic()
    result = {
        "candidate":MODEL,
        "source":"EXISTING_OPENROUTER_KEY",
        "catalog_prices_verified_zero":True,
        "paid_fallbacks_disabled":True,
        "test":"PINNED_NVIDIA_RAW_TABLE_TERMS_PYDANTIC_SCHEMA",
        "synthetic_only":True,
        "production_or_customer_data_sent":False,
    }
    try:
        response = fetch_json(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization":"Bearer "+credential,
                "Content-Type":"application/json",
                "X-Title":"EmpireOS NVIDIA synthetic schema canary",
            },
            data=json.dumps(payload).encode(),
        )
        result["returned_model"] = response.get("model")
        msg = (response.get("choices") or [{}])[0].get("message") or {}
        content = msg.get("content") or ""
        parsed = RawTableTermsResult.model_validate_json(content)
        terms = parsed.terms
        sources = [attr.source_column for term in terms for attr in term.attributes]
        output_pass = (
            len(terms) == 1
            and len(sources) == len(FIELDS)
            and frozenset(sources) == FIELDS
            and len(set(sources)) == len(sources)
            and bool(terms[0].name and terms[0].description)
        )
        result.update({
            "vendor_pydantic_schema_valid": True,
            "field_coverage":len(set(sources)),
            "term_count":len(terms),
            "complete_structured_pass":output_pass,
            "response_chars":len(content),
            "total_tokens":(response.get("usage") or {}).get("total_tokens"),
        })
    except urllib.error.HTTPError as exc:
        result.update({"complete_structured_pass":False,"http_error_code":exc.code})
    except Exception as exc:
        result.update({"complete_structured_pass":False,"failure_kind":type(exc).__name__})
    result["latency_s"] = round(time.monotonic() - started,2)
    fd = os.open(RESULT,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as f:
        json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
