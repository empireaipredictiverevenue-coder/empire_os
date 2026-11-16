"""Gracefully stop ONLY the isolated NVIDIA synthetic semantic evaluation pass.

Calls NVIDIA's documented ingestion /semantic/stop control on the private
sandbox bridge. Never kills a process, restarts a container or touches
production services. Requires authenticated application setting disabled.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx

ROOT = Path("/srv/empire_os/runtime/nvidia_ontology_eval")
APP = "http://localhost:33000"
INGESTION = "http://172.18.0.3:3002"


def main():
    cfg = dict(line.split("=", 1) for line in
               (ROOT / ".env").read_text().splitlines() if "=" in line)
    if cfg.get("CONNECTION_STRINGS") != "sqlite:////reference/empire_graph.sqlite":
        raise RuntimeError("not the private synthetic connection")
    if not (ROOT / "nvidia-model-before-canonical-descriptions-20261116.yaml").exists():
        raise RuntimeError("model backup not present")
    with httpx.Client(base_url=APP, timeout=15, trust_env=False,
                      headers={"Origin": APP}) as app:
        login = app.post("/api/auth/sign-in/email", json={
            "email": cfg["AUTO_ONTOLOGY_ADMIN_EMAIL"],
            "password": cfg["AUTO_ONTOLOGY_ADMIN_PASSWORD"],
        })
        if login.status_code != 200 or not app.cookies:
            raise RuntimeError("admin authorisation failed")
        databases = app.get("/api/datasources/dbs")
        databases.raise_for_status()
        rows = databases.json().get("data", [])
        if len(rows) != 1 or rows[0].get("name") != "empire_graph":
            raise RuntimeError("unexpected catalog source")
        settings = app.get("/api/configurations/semantic-compilation")
        settings.raise_for_status()
        if settings.json().get("enabled") is not False:
            raise RuntimeError("scheduled compiler must be disabled first")
    with httpx.Client(base_url=INGESTION, timeout=12, trust_env=False) as internal:
        health = internal.get("/health")
        health.raise_for_status()
        info = health.json()
        if (info.get("status") != "ok"
                or info.get("migrations", {}).get("status") != "ok"
                or info.get("postgres", {}).get("status") != "ok"):
            raise RuntimeError("not a healthy, expected NVIDIA ingestion service")
        state = internal.get("/semantic/status")
        state.raise_for_status()
        previous = state.json()
        if previous.get("running") is not True:
            print(json.dumps({
                "status": "COMPILATION_ALREADY_STOPPED",
                "writes": 0,
                "running": previous.get("running"),
                "secrets_disclosed": False,
            }))
            return
        response = internal.post("/semantic/stop")
        if response.status_code != 202 or response.json().get("status") != "accepted":
            raise RuntimeError(f"NVIDIA graceful stop failed HTTP {response.status_code}")
        after = internal.get("/semantic/status")
        after.raise_for_status()
        print(json.dumps({
            "status": "NVIDIA_SYNTHETIC_COMPILER_GRACEFUL_STOP_REQUESTED",
            "control_plane_only": True,
            "internal_api": True,
            "running_after_request": after.json().get("running"),
            "other_containers_restarted": False,
            "customer_data_touched": False,
            "secrets_disclosed": False,
        }, indent=2))


if __name__ == "__main__":
    main()
