"""One bounded OpenCode V2 hosted-free read-only NVIDIA MCP agent check.

Uses the already-connected existing service and active NVIDIA viewer grant.
No auto-approve, no shell/file permission changes, no deployment or paid model.
"""
import json,os,subprocess
from pathlib import Path

ROOT=Path("/srv/empire_os")
MODEL="opencode/glm-5.3-flash-free"
BIN="/home/ubuntu/.local/share/empire-opencode-v2-isolated/node_modules/@opencode/cli/bin/opencode.exe"
SERVICE=Path("/tmp/empire_opencode_v2_free_20261113/config/opencode/service.json")
RUNTIME=ROOT/"runtime/nvidia_ontology_eval"
LOG=RUNTIME/"opencode_free_model_nvidia_viewer_agent_20261117.jsonl"
RECEIPT=RUNTIME/"opencode_free_model_nvidia_viewer_agent_20261117.json"

def main():
    if LOG.exists() or RECEIPT.exists():
        raise RuntimeError("do not overwrite agent acceptance evidence")
    if SERVICE.stat().st_mode & 0o077:
        raise RuntimeError("OpenCode service config not private")
    password=json.loads(SERVICE.read_text())["password"]
    env={**os.environ,"OPENCODE_PASSWORD":password}
    listing=subprocess.run([BIN,"models","--server","http://127.0.0.1:49374"],
        cwd=str(ROOT),env=env,capture_output=True,text=True,timeout=20)
    registered=listing.returncode==0 and MODEL in listing.stdout.splitlines()
    report={
        "existing_open_code_v2_service":True,
        "model":MODEL,
        "free_only":True,
        "model_registered":registered,
        "agent":"plan",
        "explicit_auto_permission":False,
        "existing_mcp_viewer_grant":True,
        "synthetic_only":True,
        "agent_run_started":False,
        "tool_invoked":False,
        "tool_completed":False,
        "no_new_model_provider":True,
        "credential_disclosure":False,
        "error":None,
    }
    if registered:
        fd=os.open(LOG,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        args=[
            BIN,"run","--server","http://127.0.0.1:49374",
            "--model",MODEL,"--agent","plan","--archived",
            "--title","NVIDIA viewer read-only readiness check",
            "--format","json",
            "Call the connected nvidia-auto-ontology MCP tool named check_readiness EXACTLY ONCE "
            "with no arguments, and report the returned readiness verdict. "
            "Do not execute shell commands, browse, inspect files, write, edit, publish, "
            "deploy or use any other tool. The data is synthetic."
        ]
        with os.fdopen(fd,"w") as log:
            try:
                result=subprocess.run(args,cwd=str(ROOT),env=env,
                    stdout=log,stderr=subprocess.STDOUT,timeout=75)
                report["agent_run_started"]=True
                report["agent_exit_code"]=result.returncode
            except subprocess.TimeoutExpired:
                report["agent_run_started"]=True
                report["error"]="BOUNDED_AGENT_TIMEOUT"
        events=[]
        for line in LOG.read_text(errors="replace").splitlines():
            try:d=json.loads(line)
            except ValueError:continue
            events.append(d)
        report["event_types"]=sorted(set(str(d.get("type")) for d in events))
        tool_states=[]
        tool_events=[d for d in events if d.get("type")=="tool_use"]
        expected_code='return await tools["nvidia-auto-ontology"].check_readiness({})'
        for d in tool_events:
            part=d.get("part") or {}
            if not isinstance(part,dict):
                continue
            state=part.get("state") or {}
            if not isinstance(state,dict):
                continue
            tool=str(part.get("tool") or part.get("name") or "")
            via_native_execute=(
                tool=="execute" and
                (state.get("input") or {}).get("code")==expected_code
            )
            if "check_readiness" in tool or via_native_execute:
                report["tool_invoked"]=True
                tool_states.append(str(state.get("status") or "unknown"))
        report["tool_states"]=tool_states
        report["tool_completed"]=bool(
            len(tool_events)==1 and
            report["tool_invoked"] and
            any(x in ("completed","success") for x in tool_states)
        )
        if report["error"] is None:
            for d in events:
                if d.get("type")=="error":
                    e=d.get("error")
                    report["error"]=str(e.get("type") or "") if isinstance(e,dict) else "AGENT_ERROR"
                    break
    else:
        report["error"]="FREE_MODEL_NOT_REGISTERED"
    fd=os.open(RECEIPT,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as f:json.dump(report,f,indent=2,sort_keys=True)
    print(json.dumps(report,indent=2,sort_keys=True))
    if not report["tool_completed"]:
        raise SystemExit(2)

if __name__=="__main__":
    main()
