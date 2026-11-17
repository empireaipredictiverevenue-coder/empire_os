"""Stage one corrected NVIDIA OAuth MCP resource URL, no container changes.

NVIDIA Better Auth registered resource was localhost:33003/mcp, but native
MCP server and OpenCode use 127.0.0.1:33013/mcp, causing invalid_target.
Scope: isolated synthetic evaluation only, private rollback preserved.
"""
from __future__ import annotations
import json,os,subprocess
from pathlib import Path

ROOT=Path("/srv/empire_os/runtime/nvidia_ontology_eval")
ENV=ROOT/".env"
BACKUP=ROOT/".env.before-mcp-resource-20261117"
COMPOSE=ROOT/"compose.yaml"
CLI="/home/ubuntu/.docker/cli-plugins/docker-compose"
OLD="http://localhost:33003"
NEW="http://127.0.0.1:33013"

def main():
    if os.geteuid()==0:raise RuntimeError("stage as ubuntu owner only")
    if BACKUP.exists():raise RuntimeError("rollback already exists; do not overwrite")
    for path in (ENV,COMPOSE,ROOT/"empire_graph.sqlite"):
        if not path.is_file() or path.stat().st_mode & 0o077:
            raise RuntimeError("private synthetic data/config missing")
    data=ENV.read_bytes()
    lines=data.decode().splitlines()
    pairs=[line.split("=",1) for line in lines if "=" in line and not line.startswith("#")]
    config=dict(pairs)
    if len(pairs)!=len(config):raise RuntimeError("ambiguous environment variables")
    if config.get("CONNECTION_STRINGS")!="sqlite:////reference/empire_graph.sqlite":
        raise RuntimeError("non-synthetic source")
    if config.get("AUTO_ONTOLOGY_MCP_PUBLIC_URL")!=OLD:
        raise RuntimeError("unexpected previous MCP address")
    if config.get("APP_URL")!="http://localhost:33000":
        raise RuntimeError("unexpected frontend address")
    if config.get("REASONING_MODEL")!="openai/nvidia/nemotron-3.5-super-vl:free":
        raise RuntimeError("existing free inference backend changed")
    if config.get("EMBED_MODEL")!="nomic-embed-text":
        raise RuntimeError("local embeddings changed")
    fd=os.open(BACKUP,os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600)
    with os.fdopen(fd,"wb") as f:f.write(data)
    updated=[("AUTO_ONTOLOGY_MCP_PUBLIC_URL="+NEW)
              if line.startswith("AUTO_ONTOLOGY_MCP_PUBLIC_URL=") else line
              for line in lines]
    if updated==lines:raise RuntimeError("no resource entry changed")
    temp=ROOT/".env.mcp_resource_stage_tmp"
    fd=os.open(temp,os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as f:f.write("\n".join(updated)+"\n")
    os.replace(temp,ENV)
    os.chmod(ENV,0o600)
    p=subprocess.run([CLI,"-f",str(COMPOSE),"--env-file",str(ENV),
                      "config","--format","json"],capture_output=True,text=True,timeout=20)
    if p.returncode:
        ENV.write_bytes(data);os.chmod(ENV,0o600)
        raise RuntimeError("Compose validation failed; old configuration restored")
    loaded=json.loads(p.stdout)
    f=loaded["services"]["auto-ontology-frontend"]
    if f["environment"].get("AUTO_ONTOLOGY_MCP_PUBLIC_URL")!=NEW or (
        f["environment"].get("APP_URL")!="http://localhost:33000"
    ):
        ENV.write_bytes(data);os.chmod(ENV,0o600)
        raise RuntimeError("frontend resource did not propagate; old configuration restored")
    print(json.dumps({
        "status":"NVIDIA_OAUTH_RESOURCE_FIX_STAGED_NOT_APPLIED",
        "old_resource":OLD+"/mcp",
        "expected_resource":NEW+"/mcp",
        "synthetic_only":True,
        "frontend_compose_config_valid":True,
        "unchanged_environment_fields_verified":len(config)-1,
        "backup_mode":"0600",
        "docker_containers_changed":False,
        "user_credentials_disclosed":False,
        "next_step":"scoped root-only frontend restart"
    },indent=2))
if __name__=="__main__":main()
