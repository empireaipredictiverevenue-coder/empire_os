"""Prepare an isolated NVIDIA Auto Ontology Docker evaluation (no Docker actions).

This creates only a synthetic SQLite dataset, scoped runtime secrets and a
rewritten Compose file. It does NOT start, stop, pull or build containers.
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
from pathlib import Path

import yaml

from empire_os.nvidia_ontology_shadow import write_private_sqlite_shadow
from scripts.benchmark_nvidia_ontology_shadow_20261116 import (
    EXPECTED_COMMIT,
    UPSTREAM,
    synthetic_graph,
)

ROOT = Path("/srv/empire_os")
TARGET = ROOT / "runtime/nvidia_ontology_eval"
PORT = 33000
PROJECT = "empire-nvidia-ontology-eval"
RESTRICTED_MODEL = "http://127.0.0.1:19999/v1"


def _write_private(path: Path, content: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)


def _check_vendor() -> None:
    if not (UPSTREAM / "docker-compose.yml").is_file():
        raise RuntimeError("reviewed NVIDIA upstream source missing")
    actual = subprocess.check_output(
        ["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"],
        text=True, timeout=6,
    ).strip()
    if actual != EXPECTED_COMMIT:
        raise RuntimeError("NVIDIA upstream commit differs from reviewed version")
    dirty = subprocess.check_output(
        ["git", "-C", str(UPSTREAM), "status", "--porcelain"],
        text=True, timeout=6,
    ).strip()
    if dirty:
        raise RuntimeError("reviewed NVIDIA source has uncommitted changes")


def _check_port() -> None:
    with socket.socket() as sock:
        sock.settimeout(1)
        if sock.connect_ex(("127.0.0.1", PORT)) == 0:
            raise RuntimeError("loopback evaluation port already occupied")


def _env() -> str:
    password = secrets.token_urlsafe(32)
    admin_password = secrets.token_urlsafe(32)
    pgadmin_password = secrets.token_urlsafe(32)
    auth_secret = secrets.token_urlsafe(48)
    # All model endpoints point to an unavailable *local* port. No provider
    # charges or out-of-network requests are possible during startup.
    vars = {
        "POSTGRES_HOST": "postgres",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": password,
        "POSTGRES_DATABASE": "auto_ontology",
        "CONNECTION_STRINGS": "sqlite:////reference/empire_graph.sqlite",
        "PGADMIN_EMAIL": "admin@localhost.invalid",
        "PGADMIN_PASSWORD": pgadmin_password,
        "DEFAULT_MODELS_API_KEY": "offline-model-disabled",
        "DEFAULT_MODELS_ENDPOINT": RESTRICTED_MODEL,
        "DEFAULT_MODELS_MODEL": "offline-model-disabled",
        "REASONING_API_KEY": "offline-model-disabled",
        "REASONING_ENDPOINT": RESTRICTED_MODEL,
        "REASONING_MODEL": "offline-model-disabled",
        "NON_REASONING_API_KEY": "offline-model-disabled",
        "NON_REASONING_ENDPOINT": RESTRICTED_MODEL,
        "NON_REASONING_MODEL": "offline-model-disabled",
        "EMBED_API_KEY": "offline-model-disabled",
        "EMBED_ENDPOINT": RESTRICTED_MODEL,
        "EMBED_MODEL": "offline-model-disabled",
        "RERANK_API_KEY": "offline-model-disabled",
        "RERANK_ENDPOINT": RESTRICTED_MODEL,
        "RERANK_MODEL": "offline-model-disabled",
        "APP_URL": f"http://localhost:{PORT}",
        "AUTO_ONTOLOGY_MCP_PUBLIC_URL": "http://localhost:33003",
        "AUTO_ONTOLOGY_ADMIN_EMAIL": "admin@localhost.invalid",
        "AUTO_ONTOLOGY_ADMIN_PASSWORD": admin_password,
        "AUTH_SECRET": auth_secret,
        "INGEST_INTERVAL_HOURS": "168",
        "INGESTION_SERVICE_URL": "http://ingestion-service:3002",
        "PYTHON_API_URL": "http://auto-ontology:3001",
    }
    return "".join(f"{name}={value}\n" for name, value in vars.items())


def _make_compose(vendor: Path, env_file: Path, source: Path) -> dict:
    original = yaml.safe_load((vendor / "docker-compose.yml").read_text())
    if not isinstance(original, dict):
        raise RuntimeError("invalid vendor Compose")
    services = original["services"]
    expected = {
        "postgres", "pgadmin", "auto-ontology", "ingestion-service",
        "auto-ontology-migrate", "frontend-migrate", "auto-ontology-frontend",
    }
    if set(services) != expected:
        raise RuntimeError("upstream service list changed; fail closed")
    original["name"] = PROJECT
    original["networks"] = {
        "sandbox": {"internal": True},
        # A port published from an exclusively internal network is silently
        # ignored by Docker 29. A dedicated standard bridge is attached only
        # to the frontend; DB, backend and ingestion stay on sandbox.
        "ingress": {
            "driver": "bridge",
            "driver_opts": {
                "com.docker.network.bridge.host_binding_ipv4": "127.0.0.1",
            },
        },
    }
    for name, service in services.items():
        service.pop("container_name", None)
        service["ports"] = []
        service["networks"] = ["sandbox"]
        service["restart"] = "no"
        service["logging"] = {
            "driver": "json-file",
            "options": {"max-size": "5m", "max-file": "2"},
        }
        if "env_file" in service:
            service["env_file"] = [str(env_file)]
        if "build" in service:
            context = (
                vendor / "frontend"
                if name in {"frontend-migrate", "auto-ontology-frontend"}
                else vendor
            )
            service["build"]["context"] = str(context)
        allowed_named_volumes = {
            "postgres": ["postgres_data:/var/lib/postgresql/data"],
            "pgadmin": ["pgadmin_data:/var/lib/pgadmin"],
        }
        if service.get("volumes", []) != allowed_named_volumes.get(name, []):
            raise RuntimeError("unreviewed upstream bind mounts")
    services["pgadmin"]["profiles"] = ["manual"]
    services["auto-ontology-frontend"]["ports"] = [
        f"127.0.0.1:{PORT}:3000",
    ]
    services["auto-ontology-frontend"]["networks"] = ["sandbox", "ingress"]
    for name in {"auto-ontology", "ingestion-service"}:
        services[name]["volumes"] = [{
            "type": "bind",
            "source": str(source),
            "target": "/reference/empire_graph.sqlite",
            "read_only": True,
        }]
    for name in {"auto-ontology", "ingestion-service", "auto-ontology-migrate"}:
        services[name]["image"] = "empire-nvidia-ontology-eval:3825917"
    for name in {"frontend-migrate", "auto-ontology-frontend"}:
        services[name]["image"] = "empire-nvidia-ontology-frontend-eval:3825917"
    services["postgres"]["mem_limit"] = "2g"
    services["auto-ontology"]["mem_limit"] = "4g"
    services["ingestion-service"]["mem_limit"] = "4g"
    services["auto-ontology-frontend"]["mem_limit"] = "4g"
    # Reference image names are namespaced by this project's Compose name.
    return original


def prepare() -> dict:
    _check_vendor()
    _check_port()
    if TARGET.exists():
        raise RuntimeError("evaluation folder already exists; never overwrite")
    TARGET.mkdir(mode=0o700, parents=True)
    try:
        vendor = TARGET / "vendor"
        # Reproducible pinned snapshot survives /tmp cleanup.
        shutil.copytree(UPSTREAM, vendor)
        _write_private(TARGET / ".env", _env())
        source = TARGET / "empire_graph.sqlite"
        graph_report = write_private_sqlite_shadow(
            synthetic_graph(),
            destination=source,
            privacy_key=secrets.token_bytes(32),
            approved_category_labels=frozenset(
                {"Austin", "DFW", "Permit intelligence", "Roofing intelligence"},
            ),
        )
        compose = _make_compose(vendor, TARGET / ".env", source)
        _write_private(
            TARGET / "compose.yaml",
            yaml.safe_dump(compose, sort_keys=False),
        )
        return {
            "status": "EVAL_BUNDLE_PREPARED_NOT_STARTED",
            "path": str(TARGET),
            "upstream_sha": EXPECTED_COMMIT,
            "only_host_port": f"127.0.0.1:{PORT}",
            "network_internal": True,
            "database_source": "SYNTHETIC_ONLY",
            "buyer_edges": graph_report["edge_count"],
            "models_configured": False,
            "containers_started": False,
            "secrets_printed": False,
            "operator_command": (
                "sudo /home/ubuntu/.docker/cli-plugins/docker-compose -f "
                + str(TARGET / "compose.yaml")
                + " --env-file " + str(TARGET / ".env")
                + " up -d --build"
            ),
        }
    except Exception:
        # Preserve unexpected partially written state for inspection.
        raise


if __name__ == "__main__":
    print(json.dumps(prepare(), indent=2, sort_keys=True))
