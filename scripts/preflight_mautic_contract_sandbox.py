"""No-write Docker Compose preflight for an isolated official Mautic 7 sandbox.

Does not pull an image, start a container, create credentials/volumes, alter
host firewall or service, or touch production. Prints no secret values.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "tests" / "mautic_sandbox" / "compose.yaml"
REQUIRED_PROFILE = "mautic-contract-only"
EXPECTED_IMAGE = "mautic/mautic:7.2.2-20261026-apache"


def fail(message: str, code: int = 2) -> None:
    print(message)
    raise SystemExit(code)


def main() -> None:
    if not COMPOSE.is_file():
        fail("MISSING_OFFICIAL_MAUTIC_SANDBOX_SPEC")
    env = os.environ.copy()
    env.update({
        "MAUTIC_CONTRACT_DB_PASSWORD": secrets.token_urlsafe(32),
        "MAUTIC_CONTRACT_DB_ROOT_PASSWORD": secrets.token_urlsafe(32),
        "MAUTIC_CONTRACT_HTTP_PORT": "18080",
    })
    # A plain "docker compose up" without the explicitly named manual
    # profile must NOT start even the database fixture by accident.
    no_profile = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), "config", "--services"],
        env=env, capture_output=True, text=True, timeout=20, check=False,
    )
    if no_profile.returncode or no_profile.stdout.strip():
        fail("MANUAL_MAUTIC_COMPOSE_PROFILE_BYPASS")
    command = [
        "docker", "compose", "--profile", REQUIRED_PROFILE,
        "-f", str(COMPOSE), "config", "--format", "json",
    ]
    try:
        result = subprocess.run(
            command, env=env, capture_output=True, text=True,
            timeout=20, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        fail("DOCKER_COMPOSE_V2_UNAVAILABLE")
    if result.returncode:
        fail("ISOLATED_MAUTIC_COMPOSE_CONFIGURATION_INVALID")
    try:
        parsed = json.loads(result.stdout)
    except ValueError:
        fail("ISOLATED_MAUTIC_COMPOSE_JSON_INVALID")
    services = parsed.get("services", {})
    if set(services) != {"db", "mautic_web"}:
        fail("UNEXPECTED_MAUTIC_SERVICE_OR_WORKER")
    if services["mautic_web"].get("image") != EXPECTED_IMAGE:
        fail("UNPINNED_OR_WRONG_MAUTIC_IMAGE")
    if services["db"].get("image") != "mysql:8.4":
        fail("UNEXPECTED_DATABASE_IMAGE")
    for svc in services.values():
        if svc.get("privileged") or svc.get("network_mode") in ("host", "none"):
            fail("UNSAFE_CONTAINER_PRIVILEGES_OR_NETWORK")
        if svc.get("restart") not in ("no", "none"):
            fail("AUTOMATIC_MAUTIC_START_RESTART_FORBIDDEN")
        profiles = svc.get("profiles", [])
        if profiles != [REQUIRED_PROFILE]:
            fail("MAUTIC_MANUAL_ACTIVATION_PROFILE_REQUIRED")
        if set(svc.get("networks", {})) != {"contract_private"}:
            fail("UNEXPECTED_MAUTIC_NETWORK")
        for volume in svc.get("volumes", []):
            if volume.get("type") != "volume":
                fail("HOST_BIND_MOUNT_NOT_ALLOWED_IN_MAUTIC_SANDBOX")
    if not parsed.get("networks", {}).get("contract_private", {}).get("internal"):
        fail("EXTERNAL_NETWORK_NOT_ALLOWED")
    web = services["mautic_web"]
    ports = web.get("ports", [])
    if (len(ports) != 1 or ports[0].get("host_ip") != "127.0.0.1"
            or int(ports[0].get("published", 0)) != 18080):
        fail("MAUTIC_WEB_NOT_BOUND_TO_LOOPBACK")
    environment = web.get("environment", {})
    if environment.get("DOCKER_MAUTIC_ROLE") != "mautic_web":
        fail("MAUTIC_AUTOMATED_WORKER_ROLE_NOT_PERMITTED")
    if environment.get("DOCKER_MAUTIC_LOAD_TEST_DATA") not in ("false", False):
        fail("MAUTIC_UNREVIEWED_TEST_DATA_LOAD_NOT_PERMITTED")
    print("MAUTIC_7_COMPOSE_SYNTAX_AND_ISOLATION_GATES_PASS")
    try:
        status = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=8, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        fail("MAUTIC_RUNTIME_UNAVAILABLE", 24)
    if status.returncode:
        fail("MAUTIC_RUNTIME_BLOCKED_DOCKER_DAEMON_ACCESS", 24)
    print("MAUTIC_DOCKER_RUNTIME_ACCESS_READY_NOT_STARTED")


if __name__ == "__main__":
    main()
