"""Stage free NVIDIA reasoning in the existing isolated evaluation.

Changes only the private Compose environment file. Never touches Docker,
production routing, service units, application credentials or model gateway.
"""
from __future__ import annotations
import json,os,shutil,subprocess
from pathlib import Path
from urllib.request import urlopen
from scripts.nvidia_free_openrouter_relay_20261117 import GATEWAY_ALIAS

ROOT=Path("/srv/empire_os/runtime/nvidia_ontology_eval")
CONFIG=ROOT/".env"
BACKUP=ROOT/".env.before-free-nemotron-20261117"
SOURCE=ROOT/"empire_graph.sqlite"
COMPOSE="/home/ubuntu/.docker/cli-plugins/docker-compose"
FIELDS=("DEFAULT_MODELS_MODEL","REASONING_MODEL","NON_REASONING_MODEL")
OLD="openai/qwen2.5-coder:1.5b"
ENDPOINT="http://172.18.0.1:19999/v1"

def main():
    if BACKUP.exists():raise RuntimeError("staging already exists; refuse overwrite")
    if CONFIG.stat().st_mode & 0o077 or SOURCE.stat().st_mode & 0o077:
        raise RuntimeError("private file permissions required")
    cfg=dict(s.split("=",1) for s in CONFIG.read_text().splitlines() if "=" in s)
    for k in FIELDS:
        if cfg.get(k)!=OLD:raise RuntimeError("unexpected existing model: "+k)
    for k in ("DEFAULT_MODELS_ENDPOINT","REASONING_ENDPOINT","NON_REASONING_ENDPOINT","EMBED_ENDPOINT"):
        if cfg.get(k)!=ENDPOINT:raise RuntimeError("private endpoint mismatch: "+k)
    if cfg.get("EMBED_MODEL")!="nomic-embed-text" or cfg.get("RERANK_ENDPOINT")!="http://127.0.0.1:19999/v1":
        raise RuntimeError("embedding/rerank controls drifted")
    if cfg.get("CONNECTION_STRINGS")!="sqlite:////reference/empire_graph.sqlite":
        raise RuntimeError("non-synthetic connection; refuse stage")
    for k in ("DEFAULT_MODELS_API_KEY","REASONING_API_KEY","NON_REASONING_API_KEY","EMBED_API_KEY"):
        if cfg.get(k)!="offline-model-disabled":
            raise RuntimeError("unexpected credential value")
    if "OPENROUTER_API_KEY" in cfg:
        raise RuntimeError("host credential must never be in Docker env")
    with urlopen("http://172.18.0.1:19999/health",timeout=5) as result:
        if json.load(result).get("status")!="ok":
            raise RuntimeError("existing gateway unhealthy")
    shutil.copy2(CONFIG,BACKUP)
    os.chmod(BACKUP,0o600)
    tmp=ROOT/".env.free-nemotron-staging"
    if tmp.exists():raise RuntimeError("staging temp collision")
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as out:
        for key,value in cfg.items():
            out.write(key+"="+(GATEWAY_ALIAS if key in FIELDS else value)+"\n")
    os.replace(tmp,CONFIG)
    os.chmod(CONFIG,0o600)
    p=subprocess.run([COMPOSE,"-f",str(ROOT/"compose.yaml"),"--env-file",str(CONFIG),"config","-q"],
                     capture_output=True,text=True,timeout=15)
    if p.returncode:
        shutil.copy2(BACKUP,CONFIG)
        raise RuntimeError("new Compose config failed; original restored")
    print(json.dumps({
        "status":"ISOLATED_NVIDIA_FREE_NEMOTRON_STAGED_NOT_APPLIED",
        "model":GATEWAY_ALIAS,
        "source":"SYNTHETIC_SQLITE_ONLY",
        "embedding_local_unchanged":True,
        "key_in_container":False,
        "paid_inference":False,
        "only_private_env_file_changed":True,
        "containers_restarted":False,
        "backup_mode":oct(BACKUP.stat().st_mode & 0o777),
    },indent=2))
if __name__=="__main__":main()
