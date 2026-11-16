"""Read-only NVIDIA synthetic semantic quality snapshot.

Authenticates only to locally running evaluation. Never prints cookies or
credentials. Only prints small synthetic-term metadata for quality comparison.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx

ROOT = Path("/srv/empire_os/runtime/nvidia_ontology_eval")
BASE = "http://localhost:33000"
ALLOW = {"name", "term", "label", "table_name", "database_name",
         "schema_name", "description", "data_type", "type"}


def main() -> None:
    cfg = dict(item.split("=", 1) for item in
               (ROOT / ".env").read_text().splitlines() if "=" in item)
    assert cfg["CONNECTION_STRINGS"] == "sqlite:////reference/empire_graph.sqlite"
    with httpx.Client(base_url=BASE, timeout=20, trust_env=False,
                      headers={"Origin": BASE}) as client:
        login = client.post("/api/auth/sign-in/email", json={
            "email": cfg["AUTO_ONTOLOGY_ADMIN_EMAIL"],
            "password": cfg["AUTO_ONTOLOGY_ADMIN_PASSWORD"],
        })
        if login.status_code != 200:
            raise RuntimeError("local admin login was rejected")
        status = client.get("/api/semantic-compilation/status")
        status.raise_for_status()
        terms = client.get("/api/terms?skip=0&limit=50")
        terms.raise_for_status()
        info = terms.json()
        listed = info.get("terms", [])
        if not isinstance(listed, list):
            raise RuntimeError("unexpected semantic term schema")
        print(json.dumps({
            "status": "SYNTHETIC_SEMANTIC_QUALITY_SNAPSHOT",
            "semantic": status.json(),
            "terms_total": info.get("total"),
            "terms_returned": len(listed),
            "terms": [
                {k: str(v)[:170] for k, v in term.items() if k in ALLOW}
                for term in listed[:30] if isinstance(term, dict)
            ],
            "first_term_keys": sorted(listed[0].keys()) if listed else [],
            "secrets_disclosed": False,
        }, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
