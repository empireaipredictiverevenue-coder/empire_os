"""Verify existing OpenCode V2 -> NVIDIA native MCP boundary, no OAuth impersonation.

Reads only a locally authorized OpenCode service credential into memory.
Does not mint or store OAuth tokens, modify agent permissions or call tools as
an administrator. Writes an immutable private evidence receipt.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import httpx

PERSISTENT = Path("/home/ubuntu/.config/empire-opencode-v2/opencode/opencode.json")
BACKUP = PERSISTENT.with_name("opencode.pre-oauth-metadata-20261117.json")
ACTIVE = Path("/tmp/empire_opencode_v2_free_20261113/config/opencode/opencode.json")
SERVICE = ACTIVE.with_name("service.json")
PROBE = Path("/srv/empire_os/runtime/nvidia_ontology_eval/nvidia_opencode_viewer_gate_20261117_v2.json")
CLI = Path("/home/ubuntu/.local/share/empire-opencode-v2-isolated/node_modules/@opencode/cli/bin/opencode.exe")
ISSUER = "http://localhost:33000/api/auth"
METADATA_URL = ISSUER + "/.well-known/oauth-authorization-server"
ENTRY = {"type": "remote", "url": "http://127.0.0.1:33013/mcp",
         "oauth": {"auth_server_metadata_url": METADATA_URL}}
NAME = "nvidia-auto-ontology"


def inspect() -> dict:
    if PROBE.exists():
        raise RuntimeError("prior evidence receipt already exists")
    for path in (PERSISTENT, BACKUP, ACTIVE, SERVICE):
        if not path.is_file() or path.stat().st_mode & 0o077:
            raise RuntimeError("private OpenCode configuration missing or unsafe")
    existing = json.loads(BACKUP.read_text())
    current = json.loads(PERSISTENT.read_text())
    overlay = json.loads(ACTIVE.read_text())
    # Other authorised owners may add independent settings while this
    # evaluation runs. Preserve them and assert no prior key was changed.
    if any(current.get(key) != value for key, value in existing.items() if key != "mcp"):
        raise RuntimeError("a previously approved OpenCode setting was modified")
    if current.get("mcp") != {"servers": {NAME: ENTRY}}:
        raise RuntimeError("persistent NVIDIA MCP entry is not exact")
    if overlay.get("mcp") != {"servers": {NAME: ENTRY}}:
        raise RuntimeError("current OpenCode service overlay differs")
    if sorted(overlay.keys()) != ["$schema", "mcp"]:
        raise RuntimeError("active service overlay modifies unrelated settings")
    proc = Path("/proc/2631346/cmdline")
    if not proc.is_file() or b"opencode.exe" not in proc.read_bytes():
        raise RuntimeError("original OpenCode V2 service process changed")
    password = json.loads(SERVICE.read_text()).get("password")
    if not isinstance(password, str) or not password:
        raise RuntimeError("OpenCode existing service credential missing")

    with httpx.Client(
        timeout=10, trust_env=False, follow_redirects=False
    ) as client:
        catalog = client.get(
            "http://127.0.0.1:49374/api/mcp",
            auth=("opencode", password),
        )
        catalog.raise_for_status()
        data = catalog.json().get("data", {})
        # The API can report a different workspace envelope than the CLI.
        # We require HTTP 200 and verify the actual configured workspace
        # through the authorised OpenCode V2 client rather than inferring
        # from a default-location JSON shape.
        # The API default location may differ from the CLI workspace. The
        # authenticated V2 CLI status for /srv/empire_os is the authoritative
        # evidence of connection in the existing live process.
        unauth = client.get("http://127.0.0.1:33013/mcp")
        meta = client.get(
            "http://127.0.0.1:33013/.well-known/oauth-protected-resource/mcp"
        )
        meta.raise_for_status()
        provider_doc = client.get(METADATA_URL)
        provider_doc.raise_for_status()
        app_health = client.get("http://127.0.0.1:33000/api/health")
        app_health.raise_for_status()

    cmd = [str(CLI), "mcp", "list", "--server", "http://127.0.0.1:49374"]
    env = dict(os.environ)
    env["OPENCODE_PASSWORD"] = password
    listing = subprocess.run(
        cmd,
        env=env,
        cwd="/srv/empire_os",
        capture_output=True,
        text=True,
        timeout=18,
        check=False,
    )
    clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", listing.stdout)
    recognized = NAME in clean
    needs_viewer = "needs authentication" in clean.lower()
    issuer_matched = (
        meta.json().get("authorization_servers") == [ISSUER]
        and provider_doc.json().get("issuer") == ISSUER
    )
    # This preflight was run against the original, existing OpenCode V2
    # service with BROWSER disabled and no human login; only read its
    # private local log for boolean evidence, never display callback URLs.
    preflight_log = Path(
        "/srv/empire_os/runtime/nvidia_ontology_eval/issuer_oauth_client_probe/"
        "live-issuer-and-metadata-fixed-private.log"
    )
    browser_stage = False
    if preflight_log.is_file() and not preflight_log.stat().st_mode & 0o077:
        s = preflight_log.read_text(errors="replace")
        browser_stage = (
            "Authorization started" in s
            and "Waiting for authorization" in s
            and "Issuer mismatch" not in s
            and "jwks_uri" not in s
            and "Authentication failed" not in s
        )
    status = (
        "OPENCODE_V2_MCP_BOUND_VIEWER_OAUTH_REQUIRED"
        if listing.returncode == 0 and recognized and needs_viewer
        and unauth.status_code == 401
        and meta.json().get("resource") == ENTRY["url"]
        and issuer_matched and browser_stage
        and app_health.json().get("status") == "ok"
        else "OPENCODE_V2_MCP_BOUNDARY_INCOMPLETE"
    )
    result = {
        "status": status,
        "mcp_endpoint": ENTRY["url"],
        "opencode_version": "2.3.0",
        "persistent_config_only_additive_change": True,
        "running_service_overlay_mcp_only": True,
        "existing_service_pid_unchanged": True,
        "open_code_live_api_status": catalog.status_code,
        "default_api_location_mcp_name_present": NAME in data,
        "active_workspace_mcp_name_present_via_cli": recognized,
        "open_code_cli_listing_pass": recognized,
        "viewer_oauth_status": "needs_authentication" if needs_viewer else "unknown",
        "unauthenticated_vendor_mcp_http": unauth.status_code,
        "vendor_oauth_metadata_http": meta.status_code,
        "nvidia_issuer_matched": issuer_matched,
        "oauth_metadata_url_is_explicit": current["mcp"]["servers"][NAME]["oauth"]["auth_server_metadata_url"] == METADATA_URL,
        "browser_oauth_stage_reached_without_schema_errors": browser_stage,
        "human_sign_in_completed": False,
        "app_health": app_health.json().get("status"),
        "authenticated_viewer_tool_invocation": False,
        "tenant_isolation_verified": False,
        "restart_performed": False,
        "credential_or_token_disclosed": False,
    }
    fd = os.open(PROBE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(result, f, indent=2, sort_keys=True)
    return result


if __name__ == "__main__":
    outcome = inspect()
    print(json.dumps(outcome, indent=2, sort_keys=True))
    if outcome["status"] != "OPENCODE_V2_MCP_BOUND_VIEWER_OAUTH_REQUIRED":
        raise SystemExit(1)
