"""Bounded read-only OpenCode free provider route smoke.

Uses existing server, exact model catalogue, current Viewer OAuth grant.
No new provider or agent; no global config change; never logs credentials.
"""
from __future__ import annotations
import json,os,subprocess
from pathlib import Path

ROOT=Path("/srv/empire_os/runtime/nvidia_ontology_eval")
P=Path("/tmp/empire_opencode_v2_free_20261113/config/opencode/service.json")
CLI="/home/ubuntu/.local/share/empire-opencode-v2-isolated/node_modules/@opencode/cli/bin/opencode.exe"
MODEL="opencode/mimo-v2.6-flash-free"
LOG=ROOT/"opencode_mimo_free_route_nvidia_viewer_20261118.jsonl"
RECEIPT=ROOT/"opencode_mimo_free_route_nvidia_viewer_20261118.json"
EXPECTED={
    'return await tools["nvidia-auto-ontology"].check_readiness({})',
    'const r = await tools["nvidia-auto-ontology"].check_readiness();\nreturn r;',
}

def main():
    if LOG.exists() or RECEIPT.exists():
        raise RuntimeError("immutable test evidence already exists")
    if P.stat().st_mode & 0o077:
        raise RuntimeError("private OpenCode service config not protected")
    env={**os.environ,"OPENCODE_PASSWORD":json.loads(P.read_text())["password"]}
    catalog=subprocess.run([CLI,"models","--server","http://127.0.0.1:49374"],
        cwd="/srv/empire_os",env=env,capture_output=True,text=True,timeout=25)
    if catalog.returncode or MODEL not in catalog.stdout.splitlines():
        raise RuntimeError("free model not advertised by existing service")
    report={
        "model":MODEL,"free_model_advertised":True,
        "existing_opencode_service":True,"existing_mcp_viewer_oauth":True,
        "changed_global_model":False,"new_provider_created":False,
        "synthetic_only":True,"paid_spend_authorized":False,
        "agent":"plan","execute_wrapper_called":False,
        "nvidia_check_readiness_completed":False,
        "errors":[],"private_log":True,"token_disclosed":False
    }
    fd=os.open(LOG,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as f:
        try:
            result=subprocess.run([
                CLI,"run","--server","http://127.0.0.1:49374",
                "--model",MODEL,"--agent","plan","--archived",
                "--format","json","--title",
                "NVIDIA Viewer original MCP free model route read-only acceptance",
                "Use ONLY the connected nvidia-auto-ontology check_readiness MCP tool. "
                "Make exactly one call with no arguments. Do not use shell, file, web, "
                "edit or write tools. Synthetic-only evaluation. In one sentence report readiness."
            ],cwd="/srv/empire_os",env=env,stdout=f,stderr=subprocess.STDOUT,
            timeout=90)
            report["exit_code"]=result.returncode
        except subprocess.TimeoutExpired:
            report["exit_code"]=124
            report["errors"].append("BOUNDED_TIMEOUT")
    events=[]
    for line in LOG.read_text(errors="replace").splitlines():
        try:events.append(json.loads(line))
        except (ValueError,TypeError):continue
    calls=[x.get("part") or {} for x in events if x.get("type")=="tool_use"]
    report["tool_call_count"]=len(calls)
    if len(calls)==1:
        c=calls[0]
        state=c.get("state") or {}
        code=(state.get("input") or {}).get("code")
        report["execute_wrapper_called"]=(
            c.get("tool")=="execute" and code in EXPECTED
        )
        report["nvidia_check_readiness_completed"]=(
            report["execute_wrapper_called"] and state.get("status")=="completed"
            and isinstance(state.get("output"),str)
            and '"empire_graph"' in state["output"]
        )
    report["event_types"]=sorted({str(x.get("type")) for x in events})
    report["errors"].extend([
        str(e.get("error",{}).get("type") or "agent_error")
        for e in events if e.get("type")=="error"
        and isinstance(e.get("error"),dict)
    ])
    report["verified"]=(
        report.get("exit_code")==0 and report["nvidia_check_readiness_completed"]
    )
    fd=os.open(RECEIPT,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as f:json.dump(report,f,indent=2,sort_keys=True)
    print(json.dumps(report,indent=2,sort_keys=True))
    if not report["verified"]:raise SystemExit(2)
if __name__=="__main__":main()
