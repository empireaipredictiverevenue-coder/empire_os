"""Apply canonical EmpireOS definitions to NVIDIA's synthetic semantic terms.

Works exclusively through authenticated NVIDIA UI APIs when the semantic
compiler is inactive, following an original private model backup. These
canonical descriptions are not represented as successful model inference.
Never marks generated definitions as founder-certified.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx

from empire_os.nvidia_ontology_shadow import SOURCE_TABLES, TABLE_DESCRIPTIONS

ROOT = Path("/srv/empire_os/runtime/nvidia_ontology_eval")
BASE = "http://localhost:33000"
BACKUP = ROOT / "nvidia-model-before-canonical-descriptions-20261116.yaml"


def execute() -> dict:
    if not BACKUP.is_file() or (BACKUP.stat().st_mode & 0o077):
        raise RuntimeError("private original-model backup not present")
    cfg = dict(line.split("=", 1) for line in
               (ROOT / ".env").read_text().splitlines() if "=" in line)
    if cfg.get("CONNECTION_STRINGS") != "sqlite:////reference/empire_graph.sqlite":
        raise RuntimeError("unexpected source connection")
    with httpx.Client(
        base_url=BASE, timeout=45, follow_redirects=False,
        headers={"Origin": BASE}, trust_env=False,
    ) as client:
        auth = client.post("/api/auth/sign-in/email", json={
            "email": cfg["AUTO_ONTOLOGY_ADMIN_EMAIL"],
            "password": cfg["AUTO_ONTOLOGY_ADMIN_PASSWORD"],
        })
        if auth.status_code != 200 or not client.cookies:
            raise RuntimeError("authenticated admin access required")
        dbs = client.get("/api/datasources/dbs")
        dbs.raise_for_status()
        data = dbs.json().get("data", [])
        if len(data) != 1 or data[0].get("name") != "empire_graph":
            raise RuntimeError("refusing non-synthetic source")
        status_response = client.get("/api/semantic-compilation/status")
        status_response.raise_for_status()
        status = status_response.json()
        if status.get("running") is not False:
            return {
                "status": "WAIT_FOR_INFLIGHT_SEMANTIC_COMPILATION_TO_STOP",
                "running": status.get("running"),
                "last_success_at": status.get("last_success_at"),
                "last_failure_at": status.get("last_failure_at"),
                "writes": 0,
            }
        terms_response = client.get("/api/terms?skip=0&limit=100")
        terms_response.raise_for_status()
        terms = terms_response.json().get("terms", [])
        by_name = {item["name"]: item for item in terms}
        expected_names = {
            name.replace("_", " ").title(): name for name in SOURCE_TABLES
        }
        if set(by_name) != set(expected_names) or len(terms) != 4:
            raise RuntimeError("semantic terms do not match canonical four-table schema")
        updates = []
        for display_name, table_name in expected_names.items():
            item = by_name[display_name]
            current = item.get("description")
            expected = TABLE_DESCRIPTIONS[table_name]
            fallback = f"Business entity represented by table {table_name}"
            if current == expected:
                continue
            if current != fallback:
                raise RuntimeError(f"unreviewed Term description: {display_name}")
            updates.append((str(item["id"]), display_name, expected))
        applied = []
        for term_id, display_name, expected in updates:
            response = client.patch(f"/api/terms/{term_id}", json={
                "description": expected,
            })
            if response.status_code != 200:
                raise RuntimeError(f"approved description failed for {display_name}: {response.status_code}")
            row = response.json().get("data", {})
            if row.get("description") != expected:
                raise RuntimeError(f"description readback mismatch for {display_name}")
            applied.append(display_name)
        after = client.get("/api/terms?skip=0&limit=100")
        after.raise_for_status()
        current = {item["name"]: item.get("description")
                   for item in after.json().get("terms", [])}
        exact = all(
            current.get(name.replace("_", " ").title()) == desc
            for name, desc in TABLE_DESCRIPTIONS.items()
        )
        return {
            "status": "CANONICAL_SYNTHETIC_DESCRIPTIONS_PASS" if exact else "DESCRIPTION_READBACK_FAIL",
            "canonical_definitions_verified": sum(
                current.get(name.replace("_", " ").title()) == desc
                for name, desc in TABLE_DESCRIPTIONS.items()
            ),
            "updated_terms": applied,
            "founder_certified": False,
            "paid_requests": False,
            "secrets_disclosed": False,
        }


if __name__ == "__main__":
    print(json.dumps(execute(), indent=2, sort_keys=True))
