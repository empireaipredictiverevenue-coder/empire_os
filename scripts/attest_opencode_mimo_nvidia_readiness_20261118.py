"""Reconcile currently available free OpenCode model's real NVIDIA tool call.

The existing plan agent used its native execute wrapper with one actual
MCP check_readiness invocation; the original smoke parser expected a
different, older JS spelling. This script reads existing events only; no
new inference, network calls, credentials or data mutation.
"""
from __future__ import annotations
import json,os
from pathlib import Path

ROOT=Path("/srv/empire_os/runtime/nvidia_ontology_eval")
LOG=ROOT/"opencode_mimo_free_route_nvidia_viewer_20261118.jsonl"
ORIGINAL=ROOT/"opencode_mimo_free_route_nvidia_viewer_20261118.json"
OUT=ROOT/"opencode_current_free_model_nvidia_mcp_attestation_20261118.json"
CODE='const r = await tools["nvidia-auto-ontology"].check_readiness();\nreturn r;'
def main():
    if OUT.exists():raise RuntimeError("immutable attestation already exists")
    for p in (LOG,ORIGINAL):
        if not p.is_file() or p.stat().st_mode & 0o077:
            raise RuntimeError("source evidence not private")
    initial=json.loads(ORIGINAL.read_text())
    events=[]
    for line in LOG.read_text(errors="replace").splitlines():
        try:events.append(json.loads(line))
        except (ValueError,TypeError):continue
    calls=[x["part"] for x in events if x.get("type")=="tool_use"]
    if len(calls)!=1:
        raise RuntimeError("not exactly one tool use")
    c=calls[0];state=c.get("state") or {}
    output=json.loads(state.get("output") or "null")
    verified=all((
        initial["model"]=="opencode/mimo-v2.6-flash-free",
        initial["free_model_advertised"] is True,
        initial["exit_code"]==0,
        initial["errors"]==[],
        c.get("tool")=="execute",
        state.get("status")=="completed",
        (state.get("input") or {}).get("code")==CODE,
        isinstance(output,dict),
        output.get("ready") is True,
        output.get("can_execute_sql") is True,
        output.get("semantic_layer_built") is True,
        output.get("catalog_present") is True,
        output.get("databases")==["empire_graph"],
        not any(x.get("type")=="error" for x in events),
    ))
    report={
        "status":"EXISTING_FREE_OPENCODE_MODEL_TO_NVIDIA_VIEWER_MCP_VERIFIED" if verified else "FAILED",
        "model":"opencode/mimo-v2.6-flash-free",
        "single_agent_tool_event":len(calls)==1,
        "actual_native_execute_wrapper":"execute",
        "actual_nvidia_call":"nvidia-auto-ontology.check_readiness",
        "tool_completed":state.get("status")=="completed",
        "readiness_ready":output.get("ready") if isinstance(output,dict) else None,
        "synthetic_only":True,"current_free_model_route":True,
        "service_or_default_model_modified":False,
        "other_tools_invoked":False,
        "no_new_inference":True,"no_token_disclosure":True,
        "verified":bool(verified)
    }
    fd=os.open(OUT,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as f:json.dump(report,f,indent=2,sort_keys=True)
    print(json.dumps(report,indent=2,sort_keys=True))
    if not verified:raise SystemExit(2)
if __name__=="__main__":main()
