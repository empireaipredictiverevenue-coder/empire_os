#!/usr/bin/env python3
"""One local-model, synthetic-only, no-tools flagship red-team check.

Explicit flag only. Uses 127.0.0.1 llama.cpp API via http.client; cannot
follow redirects; sends no tenant data, customer records, credentials,
real company names, links, leads, emails or payments. Output is reduced to
allowlisted verdict. Never activate a BYOM hosted endpoint via this tool.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import http.client
import json
from pathlib import Path

from empire_os.flagship_customer_agent_sandbox import (
    TrustedSandboxSession, run_synthetic_model_sandbox,
    sandbox_preflight,
)

ROOT=Path(__file__).resolve().parents[1]
HOST="127.0.0.1"
PORT=11435
TEST_TENANT="00000000-0000-0000-0000-000000000101"


def local_llama_callback(system: str, user: str, max_tokens: int) -> str:
    conn=http.client.HTTPConnection(HOST,PORT,timeout=40)
    try:
        conn.request("GET", "/v1/models")
        response=conn.getresponse()
        if response.status != 200:
            raise ValueError("model catalogue unavailable")
        catalog=json.loads(response.read(4096))
        entries=catalog.get("data")
        if not isinstance(entries,list) or not entries:
            raise ValueError("no local model")
        model=entries[0].get("id") if isinstance(entries[0],dict) else None
        if not isinstance(model,str) or not 1 <= len(model) <= 120:
            raise ValueError("local model identifier invalid")
        request=json.dumps({
            "model":model, "temperature":0,
            "max_tokens":max_tokens,
            "stream":False,
            "messages":[
                {"role":"system","content":system},
                {"role":"user","content":user},
            ],
            "tools":[], "tool_choice":"none",
            # A server-side grammar may help JSON consistency, but we NEVER
            # trust it: the separate Empire validator checks the exact fields.
            "response_format":{"type":"json_object"},
            "json_schema": {
                "type":"object",
                "properties":{
                    "action":{"type":"string","const":"explain_evidence_hold"},
                    "evidence_state":{"type":"string","const":"UNVERIFIED_BUYER_INTENT"},
                    "result":{"type":"string","const":"NEEDS_FIRST_PARTY_EVIDENCE"},
                    "requested_tools":{"type":"array","maxItems":0},
                },
                "required":["action","evidence_state","result","requested_tools"],
                "additionalProperties":False,
            },
        }).encode("utf-8")
        conn.request("POST","/v1/chat/completions",body=request,headers={
            "Content-Type":"application/json",
            "Accept":"application/json",
        })
        response=conn.getresponse()
        if response.status != 200:
            raise ValueError("synthetic inference unsuccessful")
        raw=response.read(8193)
        if len(raw)>8192:
            raise ValueError("unbounded local inference response")
        body=json.loads(raw)
        choices=body.get("choices")
        if not isinstance(choices,list) or len(choices)!=1:
            raise ValueError("malformed local choice")
        message=choices[0].get("message")
        if not isinstance(message,dict):
            raise ValueError("local assistant message missing")
        if message.get("tool_calls"):
            raise ValueError("unexpected local tool call")
        result=message.get("content")
        if not isinstance(result,str):
            raise ValueError("local text content unavailable")
        return result
    finally:
        conn.close()


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--run-single-synthetic-local-probe", action="store_true")
    args=parser.parse_args()
    config=TrustedSandboxSession(
        tenant_id=TEST_TENANT, authenticated_tenant_id=TEST_TENANT,
        authenticated_server_session=True,
        mode="empire_managed", provider="empire_local",
        provider_config_approved=True,
        max_tokens=96,
    )
    if args.run_single_synthetic_local_probe:
        result=run_synthetic_model_sandbox(
            config,soul_root=ROOT,model_callback=local_llama_callback,
        )
    else:
        result=sandbox_preflight(config,soul_root=ROOT)
    # No model response printed. Never assert that a failed response is
    # provider malfunction or that compliance equals perfect safety.
    print(json.dumps({
        "schema_version":"empire.flagship_customer_local_model_probe.v1",
        "status":result["status"],
        "reason_code":result.get("reason_code"),
        "mode":"empire_managed",
        "model_call_attempted":result.get("model_called",False),
        "original_buyer_evidence_accepted":False,
        "model_tool_execution_enabled":False,
        "crm_writes":False,"outbound_sent":False,
        "payments_moved":False,"external_spend_cents":0,
        "buyer_or_revenue_verified":False,
    },sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
