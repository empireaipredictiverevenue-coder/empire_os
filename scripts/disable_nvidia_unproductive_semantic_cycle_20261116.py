"""Guarded NVIDIA synthetic-evaluation semantic scheduler deactivation.

Use authenticated application settings. No process termination or production
service modification. Retains the partial synthetic catalog for audit.
"""
from __future__ import annotations
import json
from pathlib import Path
import httpx

ROOT = Path("/srv/empire_os/runtime/nvidia_ontology_eval")
BASE = "http://localhost:33000"

def main():
    config = dict(line.split("=",1) for line in
                  (ROOT/".env").read_text().splitlines() if "=" in line)
    if config.get("CONNECTION_STRINGS") != "sqlite:////reference/empire_graph.sqlite":
        raise RuntimeError("non-synthetic source present")
    if not (ROOT/"nvidia-model-before-canonical-descriptions-20261116.yaml").is_file():
        raise RuntimeError("private model backup missing")
    with httpx.Client(base_url=BASE, timeout=25, follow_redirects=False,
                      trust_env=False, headers={"Origin":BASE}) as client:
        auth = client.post("/api/auth/sign-in/email", json={
            "email":config["AUTO_ONTOLOGY_ADMIN_EMAIL"],
            "password":config["AUTO_ONTOLOGY_ADMIN_PASSWORD"]
        })
        if auth.status_code != 200 or not client.cookies:
            raise RuntimeError("not an authenticated admin session")
        dbs = client.get("/api/datasources/dbs")
        dbs.raise_for_status()
        rows = dbs.json().get("data", [])
        if len(rows)!=1 or rows[0].get("name")!="empire_graph":
            raise RuntimeError("unexpected catalog source")
        current = client.get("/api/configurations/semantic-compilation")
        current.raise_for_status()
        was_enabled = current.json().get("enabled")
        if was_enabled not in (True,False):
            raise RuntimeError("unrecognized enabled status")
        if was_enabled:
            change = client.put("/api/configurations/semantic-compilation",
                                json={"enabled":False})
            if change.status_code!=200 or change.json().get("enabled") is not False:
                raise RuntimeError("disable request was not confirmed")
        status = client.get("/api/semantic-compilation/status")
        status.raise_for_status()
        verified = client.get("/api/configurations/semantic-compilation")
        verified.raise_for_status()
        assert verified.json().get("enabled") is False
        result = status.json()
        print(json.dumps({
            "status":"NVIDIA_SYNTHETIC_RECURRING_SEMANTIC_COMPILE_DISABLED",
            "settings_enabled":False,
            "current_run_still_active":result.get("running"),
            "last_success_at":result.get("last_success_at"),
            "last_failure_at":result.get("last_failure_at"),
            "catalog_preserved":True,
            "paid_models":False,
            "secrets_disclosed":False,
        },indent=2))
if __name__=="__main__":
    main()
