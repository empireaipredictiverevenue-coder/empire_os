"""Import *only* the missing fourth canonical NVIDIA term in isolated evaluation.

Never replace catalog records; authenticate with the generated local admin
session, verify exact live IDs and synthetic scope, and refuse while the native
semantic compiler is still running.
"""
from __future__ import annotations

import json
from pathlib import Path
import httpx
import yaml
from empire_os.nvidia_ontology_shadow import SOURCE_TABLES

ROOT = Path("/srv/empire_os/runtime/nvidia_ontology_eval")
BASE = "http://localhost:33000"
BACKUP = ROOT / "nvidia-model-before-canonical-descriptions-20261116.yaml"
CANDIDATE = ROOT / "nvidia-model-with-canonical-ontology-nodes-20261116.yaml"
EXPECTED = {n.replace("_"," ").title() for n in SOURCE_TABLES}

def _ids(document):
    return {
        "database": {d["id"] for d in document["data_layer"]["databases"]},
        "tables": {
            t["id"] for d in document["data_layer"]["databases"]
            for s in d["schemas"] for t in s["tables"]
        },
        "columns": {
            c["id"] for d in document["data_layer"]["databases"]
            for s in d["schemas"] for t in s["tables"] for c in t["columns"]
        },
    }

def run():
    if not BACKUP.exists() or not CANDIDATE.exists():
        raise RuntimeError("private validated model and original backup required")
    if any(p.stat().st_mode & 0o077 for p in (BACKUP,CANDIDATE)):
        raise RuntimeError("canonical model file permissions unsafe")
    prior = yaml.safe_load(BACKUP.read_text())
    candidate = yaml.safe_load(CANDIDATE.read_text())
    if _ids(prior) != _ids(candidate) or len(candidate["semantic_layer"]["terms"]) != 4:
        raise RuntimeError("candidate changes the catalog schema or term count")
    config = dict(s.split("=",1) for s in (ROOT/".env").read_text().splitlines() if "=" in s)
    if config["CONNECTION_STRINGS"] != "sqlite:////reference/empire_graph.sqlite":
        raise RuntimeError("unexpected data connection")
    with httpx.Client(base_url=BASE,timeout=45,trust_env=False,
                      follow_redirects=False,headers={"Origin":BASE}) as client:
        login=client.post("/api/auth/sign-in/email",json={
            "email":config["AUTO_ONTOLOGY_ADMIN_EMAIL"],
            "password":config["AUTO_ONTOLOGY_ADMIN_PASSWORD"],
        })
        if login.status_code!=200 or not client.cookies:
            raise RuntimeError("isolated admin sign-in failed")
        state=client.get("/api/semantic-compilation/status")
        state.raise_for_status()
        if state.json().get("running") is not False:
            return {
                "status":"HELD_COMPILATION_STILL_RUNNING",
                "writes":0,
                "secrets_disclosed":False,
            }
        setting=client.get("/api/configurations/semantic-compilation")
        setting.raise_for_status()
        if setting.json().get("enabled") is not False:
            raise RuntimeError("automatic compiler not disabled")
        databases=client.get("/api/datasources/dbs")
        databases.raise_for_status()
        data=databases.json().get("data",[])
        if len(data)!=1 or data[0].get("name")!="empire_graph":
            raise RuntimeError("source scope changed")
        terms_request=client.get("/api/terms?limit=100")
        terms_request.raise_for_status()
        terms=terms_request.json().get("terms",[])
        names={item.get("name") for item in terms}
        if names==EXPECTED:
            return {"status":"FOUR_TERMS_ALREADY_PRESENT","writes":0}
        if names != EXPECTED-{"Ontology Nodes"}:
            raise RuntimeError(f"unexpected existing semantic terms {names}")
        live_export=client.post("/api/model/export",json={
            "databases":[data[0]["id"]],
            "format":"auto_ontology",
            "include_ontology":False,
        })
        live_export.raise_for_status()
        live_model=yaml.safe_load(live_export.text)
        if _ids(live_model) != _ids(candidate):
            raise RuntimeError("catalog IDs drifted; refusing import")
        if {t["id"] for t in live_model["semantic_layer"]["terms"]} != {
            t["id"] for t in prior["semantic_layer"]["terms"]
        }:
            raise RuntimeError("existing terms changed; refusing import")
        result=client.post(
            "/api/model/import?replace=false&embed=true",
            content=CANDIDATE.read_bytes(),
            headers={"Content-Type":"application/x-yaml"},
            timeout=180,
        )
        if result.status_code!=200:
            raise RuntimeError(f"nonreplace native import rejected HTTP {result.status_code}")
        info=result.json()
        if info.get("success") is not True or not isinstance(info.get("summary"), dict):
            raise RuntimeError("native import did not report success")
        created=info["summary"].get("created",{})
        if created.get("databases",0) or created.get("tables",0) or created.get("columns",0):
            raise RuntimeError("unexpected data catalog creation during model import")
        after=client.get("/api/terms?limit=100")
        after.raise_for_status()
        current=after.json().get("terms",[])
        success=len(current)==4 and {t.get("name") for t in current}==EXPECTED
        return {
            "status":"NVIDIA_FOUR_CANONICAL_TERMS_PRESENT" if success else "NVIDIA_IMPORT_READBACK_FAIL",
            "semantic_term_count":len(current),
            "created_terms":created.get("terms"),
            "existing_catalog_preserved":True,
            "source":"CANONICAL_EMPIREOS_MODEL_NOT_LLM_GENERATED",
            "secrets_disclosed":False,
            "paid_models":False,
        }

if __name__=="__main__":
    print(json.dumps(run(),indent=2,sort_keys=True))
