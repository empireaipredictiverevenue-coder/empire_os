"""Bounded existing OpenCode V2 model-routing and MCP readiness smoke.

Reuses the same running service and its private local service password.
Never prints credentials, uses only the existing free local model and
limits requested tools to NVIDIA's check_readiness in the prompt.
"""
from __future__ import annotations
import json,os,re,subprocess
from pathlib import Path

ROOT=Path("/srv/empire_os")
OUT=ROOT/"runtime/nvidia_ontology_eval/opencode_native_mcp_viewer_agent_20261117.json"
LOG=ROOT/"runtime/nvidia_ontology_eval/opencode_native_mcp_viewer_agent_20261117.jsonl"
SERVICE=Path("/tmp/empire_opencode_v2_free_20261113/config/opencode/service.json")
CLI="/home/ubuntu/.local/share/empire-opencode-v2-isolated/node_modules/@opencode/cli/bin/opencode.exe"
MODEL="ollama/qwen2.5-coder:1.5b"

def main():
    if OUT.exists() or LOG.exists():
        raise RuntimeError("do not overwrite prior agent outcome")
    if SERVICE.stat().st_mode & 0o077:
        raise RuntimeError("OpenCode service credentials are not private")
    password=json.loads(SERVICE.read_text()).get("password")
    if not isinstance(password,str) or not password:
        raise RuntimeError("existing OpenCode private credential unavailable")
    env={**os.environ,"OPENCODE_PASSWORD":password}
    models=subprocess.run([CLI,"models","--server","http://127.0.0.1:49374"],
        cwd=str(ROOT),env=env,capture_output=True,text=True,timeout=28)
    registered=MODEL in models.stdout.splitlines()
    report={
        "model":MODEL,
        "model_registered_in_existing_service":registered,
        "using_existing_open_code_service":True,
        "paid_model_used":False,
        "no_production_data":True,
        "credentials_not_exposed":True,
        "agent_call_started":False,
        "nvidia_mcp_tool_invoked":False,
        "agent_error":None,
    }
    if registered:
        argv=[
            CLI,"run","--server","http://127.0.0.1:49374",
            "--model",MODEL,"--agent","build","--archived",
            "--format","json",
            "--title","NVIDIA Viewer Readiness - local model, no writes",
            "Use ONLY the currently connected nvidia-auto-ontology check_readiness MCP tool. "
            "Make exactly one call with no arguments. "
            "Never run shell, inspect files, edit, write, publish, install, or call any other tool. "
            "Report the readiness verdict in one sentence. The data is synthetic."
        ]
        log_fd=os.open(LOG,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            with os.fdopen(log_fd,"w") as log:
                result=subprocess.run(argv,cwd=str(ROOT),env=env,
                    stdout=log,stderr=subprocess.STDOUT,timeout=95)
            report["agent_call_started"]=True
            report["agent_exit_code"]=result.returncode
            events=[]
            for line in LOG.read_text(errors="replace").splitlines():
                try:e=json.loads(line)
                except ValueError:continue
                events.append(e)
            report["event_types"]=sorted({str(e.get("type")) for e in events})
            tool_events=[]
            for e in events:
                part=e.get("part") or {}
                data=e.get("data") or {}
                text_fields=json.dumps({
                    "type":e.get("type"),"tool":part.get("tool"),
                    "name":data.get("name") if isinstance(data,dict) else None
                })
                if "nvidia-auto-ontology" in text_fields or "check_readiness" in text_fields:
                    tool_events.append(text_fields)
            report["nvidia_mcp_tool_invoked"]=len(tool_events)>0
            err=next((e.get("error") for e in events if e.get("type")=="error"),None)
            if isinstance(err,dict):
                report["agent_error"]=(str(err.get("type") or "unknown")
                                       +":"+str(err.get("message") or "")[:170])
        except subprocess.TimeoutExpired:
            report["agent_error"]="LOCAL_AGENT_EXECUTION_TIMEOUT"
    else:
        report["agent_error"]="MODEL_NOT_REGISTERED_WITH_RUNNING_SERVICE"
    fd=os.open(OUT,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as f:json.dump(report,f,indent=2,sort_keys=True)
    print(json.dumps(report,indent=2,sort_keys=True))
    if not report["nvidia_mcp_tool_invoked"]:
        raise SystemExit(2)

if __name__=="__main__":
    main()
