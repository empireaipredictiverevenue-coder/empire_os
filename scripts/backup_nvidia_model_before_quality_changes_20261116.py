"""Export an authenticated, read-only backup of isolated NVIDIA semantic model.

No model imports, database mutations or privileged Docker commands.
The full model stays in a private file and is never printed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import httpx
import yaml

ROOT = Path("/srv/empire_os/runtime/nvidia_ontology_eval")
OUT = ROOT / "nvidia-model-before-canonical-descriptions-20261116.yaml"
BASE = "http://localhost:33000"
EXPECTED_TABLES = {
    "ontology_nodes", "ontology_edges",
    "node_evidence_fingerprints", "edge_evidence_fingerprints",
}

def main() -> None:
    if OUT.exists():
        raise RuntimeError("model backup already exists; refusing overwrite")
    cfg = dict(line.split("=",1) for line in (ROOT/".env").read_text().splitlines() if "=" in line)
    assert cfg["CONNECTION_STRINGS"] == "sqlite:////reference/empire_graph.sqlite"
    with httpx.Client(
        base_url=BASE, timeout=25, follow_redirects=False, trust_env=False,
        headers={"Origin": BASE, "Accept": "application/json"},
    ) as client:
        login = client.post("/api/auth/sign-in/email", json={
            "email": cfg["AUTO_ONTOLOGY_ADMIN_EMAIL"],
            "password": cfg["AUTO_ONTOLOGY_ADMIN_PASSWORD"],
        })
        if login.status_code != 200 or not client.cookies:
            raise RuntimeError("isolated admin authentication rejected")
        databases = client.get("/api/datasources/dbs")
        databases.raise_for_status()
        entries = databases.json().get("data", [])
        if len(entries) != 1 or entries[0].get("name") != "empire_graph":
            raise RuntimeError("unexpected catalog source; no export")
        database_id = entries[0].get("id")
        if not isinstance(database_id, str):
            raise RuntimeError("catalog missing canonical database ID")
        response = client.post("/api/model/export", json={
            "databases": [database_id], "format": "auto_ontology",
            "include_ontology": False,
        })
        if response.status_code != 200:
            raise RuntimeError(f"native model export failed {response.status_code}")
        document = yaml.safe_load(response.text)
        databases_data = document.get("data_layer", {}).get("databases", [])
        if len(databases_data) != 1:
            raise RuntimeError("model export contains unexpected database count")
        tables = {
            t.get("name") for schema in databases_data[0].get("schemas", [])
            for t in schema.get("tables", [])
        }
        if tables != EXPECTED_TABLES:
            raise RuntimeError(f"model tables not approved: {tables}")
        term_count = len(document.get("semantic_layer", {}).get("terms", []))
        fd = os.open(OUT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(response.text)
        print(json.dumps({
            "status": "NVIDIA_SYNTHETIC_MODEL_BACKUP_SAVED",
            "table_count": len(tables),
            "term_count": term_count,
            "only_synthetic": True,
            "path": str(OUT),
            "mode": oct(OUT.stat().st_mode & 0o777),
            "secrets_disclosed": False,
            "database_modified": False,
        }, indent=2))

if __name__ == "__main__":
    main()
