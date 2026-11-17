"""Pin NVIDIA's existing OpenCode V2 OAuth loopback callback to SSH-forwardable port.

Change only mcp.servers.nvidia-auto-ontology.oauth.callback_port in the
persistent and original running service configuration. Preserve unrelated
model and agent edits. Rollback snapshots are private and immutable.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

PERSISTENT=Path("/home/ubuntu/.config/empire-opencode-v2/opencode/opencode.json")
RUNNING=Path("/tmp/empire_opencode_v2_free_20261113/config/opencode/opencode.json")
NAME="nvidia-auto-ontology"
PORT=33018
EXPECTED={
    "type":"remote",
    "url":"http://127.0.0.1:33013/mcp",
    "oauth":{
        "auth_server_metadata_url":
            "http://localhost:33000/api/auth/.well-known/oauth-authorization-server"
    }
}


def main() -> None:
    if os.geteuid()==0:raise RuntimeError("only existing Ubuntu OpenCode owner may apply")
    states=[]
    for path in (PERSISTENT,RUNNING):
        if not path.is_file() or path.stat().st_mode & 0o077:
            raise RuntimeError("private OpenCode configuration missing")
        raw=path.read_bytes()
        obj=json.loads(raw)
        if obj.get("mcp",{}).get("servers",{}).get(NAME)!=EXPECTED:
            raise RuntimeError("unexpected OpenCode MCP entry; refuse changes")
        backup=path.with_name("opencode.pre-ssh-oauth-callback-20261117.json")
        if backup.exists():raise RuntimeError("backup already exists; do not overwrite")
        states.append((path,backup,raw,obj))
    if set(states[1][3])!={"$schema","mcp"}:
        raise RuntimeError("running OpenCode overlay modifies unrelated fields")
    for path,backup,raw,_ in states:
        fd=os.open(backup,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"wb") as f:f.write(raw)
    for path,backup,raw,original in states:
        if path.read_bytes()!=raw:
            raise RuntimeError("OpenCode config changed concurrently; refuse overwrite")
        updated=json.loads(raw)
        updated["mcp"]["servers"][NAME]["oauth"]["callback_port"]=PORT
        assert all(updated.get(key)==value for key,value in original.items() if key!="mcp")
        temp=path.with_name("."+path.name+".nvidia_callback.tmp")
        fd=os.open(temp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"w") as f:json.dump(updated,f,indent=2);f.write("\n")
        os.replace(temp,path)
        os.chmod(path,0o600)
        assert json.loads(path.read_text())==updated
    print(json.dumps({
        "status":"NVIDIA_MCP_SSH_OAUTH_CALLBACK_PINNED",
        "callback_port":PORT,
        "ssh_forward_required":[33000,PORT],
        "config_files_updated":2,
        "other_existing_settings_unchanged":True,
        "server_restart_required":False,
        "private_snapshots_created":2,
        "oauth_user_sign_in_completed":False,
    },indent=2))


if __name__=="__main__":
    main()
