"""Enable semantic compilation only in the isolated NVIDIA synthetic evaluation.

The action uses the application owner's authenticated settings endpoint.
No direct database modifications, Docker control or production credentials.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx

ROOT = Path("/srv/empire_os/runtime/nvidia_ontology_eval")
BASE = "http://localhost:33000"

def main() -> None:
    config = dict(line.split("=", 1) for line in
                  (ROOT / ".env").read_text().splitlines() if "=" in line)
    expected = {
        "CONNECTION_STRINGS": "sqlite:////reference/empire_graph.sqlite",
        "REASONING_ENDPOINT": "http://172.18.0.1:19999/v1",
        "REASONING_MODEL": "openai/qwen2.5-coder:1.5b",
        "EMBED_ENDPOINT": "http://172.18.0.1:19999/v1",
        "EMBED_MODEL": "nomic-embed-text",
        "RERANK_ENDPOINT": "http://127.0.0.1:19999/v1",
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise RuntimeError(f"Isolated evaluation configuration mismatch: {key}")
    with httpx.Client(
        base_url=BASE, timeout=35, follow_redirects=False,
        headers={"Origin": BASE, "Accept": "application/json"},
        trust_env=False,
    ) as client:
        sign_in = client.post("/api/auth/sign-in/email", json={
            "email": config["AUTO_ONTOLOGY_ADMIN_EMAIL"],
            "password": config["AUTO_ONTOLOGY_ADMIN_PASSWORD"],
        })
        if sign_in.status_code != 200 or not client.cookies:
            raise RuntimeError(f"Authentic bootstrap sign-in failed: {sign_in.status_code}")
        catalog = client.get("/api/datasources/dbs")
        catalog.raise_for_status()
        databases = catalog.json().get("data")
        if (not isinstance(databases, list) or len(databases) != 1
                or databases[0].get("name") != "empire_graph"):
            raise RuntimeError("Unexpected database; refused to enable compilation")
        settings = client.get("/api/configurations/semantic-compilation")
        settings.raise_for_status()
        status = client.get("/api/semantic-compilation/status")
        status.raise_for_status()
        before = status.json()
        was_enabled = settings.json().get("enabled")
        if was_enabled not in (True, False):
            raise RuntimeError("Unexpected semantic compilation setting")
        if before.get("running"):
            print(json.dumps({
                "status": "ALREADY_RUNNING_NO_CHANGE",
                "enabled": was_enabled,
                "calculated": before.get("calculated"),
                "secrets_disclosed": False,
            }))
            return
        if was_enabled:
            print(json.dumps({
                "status": "ALREADY_ENABLED_NO_CHANGE",
                "calculated": before.get("calculated"),
                "last_success_at": before.get("last_success_at"),
                "secrets_disclosed": False,
            }))
            return
        change = client.put(
            "/api/configurations/semantic-compilation",
            json={"enabled": True},
            timeout=35,
        )
        if change.status_code != 200 or change.json().get("enabled") is not True:
            raise RuntimeError(f"Authenticated semantic enable failed: HTTP {change.status_code}")
        after_response = client.get("/api/semantic-compilation/status")
        after = after_response.json() if after_response.status_code == 200 else {}
        print(json.dumps({
            "status": "SYNTHETIC_SEMANTIC_COMPILATION_ENABLED",
            "http": change.status_code,
            "compiled": after.get("calculated"),
            "running": after.get("running"),
            "last_success_at": after.get("last_success_at"),
            "last_failure_at": after.get("last_failure_at"),
            "source_database_count": 1,
            "only_synthetic_data": True,
            "secrets_disclosed": False,
            "paid_models": False,
        }, indent=2))

if __name__ == "__main__":
    main()
