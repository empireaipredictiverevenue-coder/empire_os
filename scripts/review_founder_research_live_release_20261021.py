"""Observe current Founder Research release readiness, without secrets or writes.

Never interprets a running Cloudflare Tunnel as Cloudflare Access approval.
Does not deploy, read JWT values, restart services, or grant session identity.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

IDENTITY_KEYS = (
    "EMPIRE_FOUNDER_CF_TEAM_DOMAIN",
    "EMPIRE_FOUNDER_CF_ACCESS_AUD",
    "EMPIRE_RESEARCH_ALLOWED_FOUNDER_SUB",
)
ORIGIN_KEY = "EMPIRE_FOUNDER_RESEARCH_ORIGIN"
SSH_GATE_KEYS = (
    "EMPIRE_FOUNDER_RESEARCH_AUTH_MODE",
    "EMPIRE_RESEARCH_SSH_PRIVATE_ENABLED",
    "EMPIRE_PRIVATE_FOUNDER_INGRESS_REVIEWED",
    "EMPIRE_RESEARCH_SSH_BRIDGE_SECRET",
)
EXPECTED_RELEASE = "/home/ubuntu/empire_releases/founder_research_ssh_private_20261021/candidate-39d028058bcd"


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


_HTTP = build_opener(ProxyHandler({}), _NoRedirects())


def _unit(name: str) -> dict:
    result = subprocess.run(
        ["systemctl", "show", name, "-p", "MainPID", "-p",
         "ActiveState", "-p", "WorkingDirectory", "-p", "ExecStart"],
        text=True, capture_output=True, timeout=6,
    )
    if result.returncode:
        return {"active": False, "process_identity_config": "UNKNOWN"}
    data = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    pid = int(data.get("MainPID", "0"))
    env_names = None
    if pid:
        try:
            blob = (Path("/proc") / str(pid) / "environ").read_bytes()
            env_names = {s.partition(b"=")[0].decode("ascii", "ignore")
                         for s in blob.split(b"\x00") if b"=" in s}
        except OSError:
            pass
    return {
        "active": data.get("ActiveState") == "active",
        "working_directory": data.get("WorkingDirectory") or None,
        "pid_present": pid > 0,
        "exec_start": data.get("ExecStart") or None,
        "ssh_gate_key_names_present": (
            all(k in env_names for k in SSH_GATE_KEYS) if env_names is not None else None
        ),
        # Name presence only; no environment values, JWTs or secret paths.
        "identity_key_presence": (
            {k: k in env_names for k in IDENTITY_KEYS}
            if env_names is not None else None
        ),
        "origin_config_present": (
            ORIGIN_KEY in env_names if env_names is not None else None
        ),
    }


def _http_code(url: str) -> int | None:
    try:
        request = Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "Empire-ReadOnly-Founder-Preflight",
        })
        with _HTTP.open(request, timeout=5) as res:
            return res.status
    except HTTPError as exc:
        return exc.code
    except (URLError, OSError, TimeoutError, ValueError):
        return None


def _production_git_state() -> tuple[str | None, int | None]:
    base = ["git", "-C", "/srv/empire_os"]
    try:
        head = subprocess.run(base + ["rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=8, check=True).stdout.strip()
        dirty = subprocess.run(base + ["status", "--porcelain"],
                               capture_output=True, text=True, timeout=15, check=True).stdout
        return head, len(dirty.splitlines())
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None, None


def evaluate(source: dict) -> dict:
    api = source.get("api") or {}
    web = source.get("web") or {}
    tunnel = source.get("tunnel") or {}
    fields = api.get("identity_key_presence")
    signed_identity_config = (isinstance(fields, dict)
                              and all(fields.get(k) is True for k in IDENTITY_KEYS))
    web_origin_config = web.get("origin_config_present") is True
    protected_runtime = (
        api.get("active") is True and web.get("active") is True
        and signed_identity_config and web_origin_config
    )
    catalog_code = source.get("api_catalog_http")
    # The SSH-private release is a separate production access boundary, not a
    # Cloudflare Access identity. Check exact active release roots and HTTP
    # behaviour independently of any environment value we cannot safely read.
    exact_release_roots = (
        (EXPECTED_RELEASE + "/api") in str(api.get("exec_start") or "")
        and web.get("working_directory") == EXPECTED_RELEASE + "/web"
    )
    ssh_gate_names = api.get("ssh_gate_key_names_present") is True
    ssh_runtime = (
        api.get("active") is True and web.get("active") is True
        and exact_release_roots and ssh_gate_names
        and catalog_code == 401
        and source.get("web_research_http") == 200
        and source.get("public_research_http") == 404
    )
    release_installed = (
        api.get("active") is True and web.get("active") is True
        and exact_release_roots and catalog_code == 401
    )
    return {
        "schema_version": "empire.research.founder_release_truth.v2",
        "status": (
            "LIVE_SSH_PRIVATE_RESEARCH_OPERATOR_LOGIN_NOT_INDEPENDENTLY_ATTESTED"
            if ssh_runtime else "HOLD_INDEPENDENT_FOUNDER_EDGE_AND_SCOPED_RELEASE_APPROVAL"
        ),
        "ssh_private_release_currently_active": ssh_runtime,
        "ssh_private_server_config_key_names_present": ssh_gate_names,
        "exact_production_release_roots_verified": exact_release_roots,
        "private_research_page_http": source.get("web_research_http"),
        "public_research_page_http": source.get("public_research_http"),
        "founder_api_active": api.get("active") is True,
        "founder_console_active": web.get("active") is True,
        "cloudflare_tunnel_active": tunnel.get("active") is True,
        "cloudflare_tunnel_is_access_authorisation": False,
        "api_identity_key_names_present": signed_identity_config,
        "web_origin_key_name_present": web_origin_config,
        "api_catalog_http": catalog_code,
        "research_api_route_deployed": catalog_code in (401, 403, 405, 503),
        "runtime_key_configuration_present": protected_runtime or ssh_runtime,
        "real_access_session_verified": False,
        "cloudflare_access_edge_rule_verified": False,
        "scoped_production_change_approved": False,
        "production_head": source.get("production_head"),
        "production_dirty_paths_count": source.get("production_dirty_paths_count"),
        "live_api_working_directory": api.get("working_directory"),
        "live_web_working_directory": web.get("working_directory"),
        "research_agent_commercial_authority": "none",
        "source_rights_granted": False,
        "outbound_sent": False,
        "database_writes": False,
        "money_moved": False,
        "release_performed": release_installed,
        "next_action": (
            "FOUNDER_OPERATOR_INDEPENDENTLY_ATTEST_SSH_SESSION_AND_REVIEW_ORIGINAL_SOURCE_RIGHTS"
            if ssh_runtime else
            "EXISTING_FOUNDER_ACCESS_OWNER_VERIFY_REAL_SESSION_THEN_SCOPED_RELEASE_OWNER_REVIEW"
        ),
    }


def review() -> dict:
    prod_head, prod_dirty = _production_git_state()
    return evaluate({
        "api": _unit("empire-founder-dashboard-api"),
        "web": _unit("empire-founder-console"),
        "tunnel": _unit("empire-cloudflared"),
        "api_catalog_http": _http_code(
            "http://127.0.0.1:8766/v1/founder-research-products/catalog"
        ),
        "web_research_http": _http_code("http://127.0.0.1:3001/founder/research"),
        "public_research_http": _http_code("https://empire-ai.co.uk/founder/research"),
        "production_head": prod_head,
        "production_dirty_paths_count": prod_dirty,
    })


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(review(), sort_keys=True))
    return 0  # Observation only; deployment authority is never granted.


if __name__ == "__main__":
    raise SystemExit(main())
