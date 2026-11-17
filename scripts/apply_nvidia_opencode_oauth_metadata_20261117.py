"""Add only the proven OpenCode V2 metadata hint to NVIDIA's existing MCP entry.

Preserve the live service and all existing owner settings, including concurrent
compaction updates. No tokens, admin credentials, service restarts, or provider
switches. Back up both private configuration files before the atomic edits.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.request import urlopen

ROOT = Path("/home/ubuntu/.config/empire-opencode-v2/opencode")
PERSISTENT = ROOT / "opencode.json"
ACTIVE = Path("/tmp/empire_opencode_v2_free_20261113/config/opencode/opencode.json")
MCP = "nvidia-auto-ontology"
MCP_URL = "http://127.0.0.1:33013/mcp"
ISSUER = "http://localhost:33000/api/auth"
METADATA = ISSUER + "/.well-known/oauth-authorization-server"
DESIRED = {"type": "remote", "url": MCP_URL, "oauth": {"auth_server_metadata_url": METADATA}}


def parse(path: Path) -> tuple[bytes, dict]:
    if not path.is_file() or path.stat().st_mode & 0o077:
        raise RuntimeError("OpenCode config missing or not private")
    original=path.read_bytes()
    obj=json.loads(original)
    if not isinstance(obj,dict):
        raise RuntimeError("invalid OpenCode object")
    current=obj.get("mcp",{}).get("servers",{}).get(MCP)
    if current!={"type":"remote","url":MCP_URL}:
        raise RuntimeError("existing NVIDIA MCP entry differs; no changes")
    return original,obj


def apply() -> None:
    if os.geteuid()==0:
        raise RuntimeError("run only as the existing ubuntu OpenCode owner")
    with urlopen(METADATA,timeout=7) as response:
        remote=json.load(response)
    if remote.get("issuer")!=ISSUER:
        raise RuntimeError("NVIDIA issuer no longer matches metadata")
    sources=[PERSISTENT,ACTIVE]
    existing=[parse(path) for path in sources]
    if set(existing[1][1])!={"$schema","mcp"}:
        raise RuntimeError("active service overlay changes unrelated settings")
    changes=[]
    for path,(raw,obj) in zip(sources,existing):
        backup=path.with_name(path.stem+".pre-oauth-metadata-20261117.json")
        if backup.exists():
            raise RuntimeError("private OAuth metadata rollback already exists")
        updated=json.loads(raw)
        updated["mcp"]["servers"][MCP]=DESIRED
        assert {k:v for k,v in updated.items() if k!="mcp"}=={k:v for k,v in obj.items() if k!="mcp"}
        changes.append((path,backup,raw,updated))
    # Save both originals without altering any running process.
    for path,backup,raw,_ in changes:
        fd=os.open(backup,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"wb") as f:f.write(raw)
    for path,backup,raw,updated in changes:
        if path.read_bytes()!=raw:
            raise RuntimeError("concurrent OpenCode owner updated config; refusing overwrite")
        tmp=path.with_name("."+path.name+".oauth_metadata.tmp")
        fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"w") as f:
            json.dump(updated,f,indent=2,ensure_ascii=False)
            f.write("\n")
        os.replace(tmp,path)
        os.chmod(path,0o600)
    for path,_,_,updated in changes:
        if json.loads(path.read_text())!=updated:
            raise RuntimeError("OAuth metadata config did not read back correctly")
    print(json.dumps({
        "result":"NVIDIA_EXISTING_OPEN_CODE_OAUTH_METADATA_HINT_APPLIED",
        "files_updated":2,
        "issuer":ISSUER,
        "metadata_endpoint":METADATA,
        "prior_settings_preserved":True,
        "existing_agent_service_restarted":False,
        "user_oauth_sign_in_complete":False,
        "secrets_disclosed":False,
    },indent=2))


if __name__=="__main__":
    apply()
