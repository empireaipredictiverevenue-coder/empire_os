"""Test the existing SSH-private Founder Console route through two staged services.

Authenticates human operators via the already deployed SSH/loopback boundary.
A disposable per-run server bridge credential authenticates Next -> API.
No public exposure, Cloudflare bypass, test credential persistence or release.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from scripts.test_founder_research_staged_session_e2e_20261021 import (
    API_PORT, WEB_PORT, ROOT_PREFIXES, _await_port, _free_port, _request,
    _safe_state, _shutdown, _verify_stage,
)

API_CODE = """
from empire_os.founder_dashboard_service import app
import uvicorn
uvicorn.run(app,host="127.0.0.1",port=3097,workers=1,log_level="critical",access_log=False)
"""


def run(api_stage: Path, web_stage: Path) -> dict:
    _verify_stage(api_stage, ROOT_PREFIXES[0], "empire_os/founder_dashboard_service.py")
    _verify_stage(web_stage, ROOT_PREFIXES[1], ".next/BUILD_ID")
    if not (_free_port(API_PORT) and _free_port(WEB_PORT)):
        raise ValueError("EXISTING_LOOPBACK_SERVICE_MUST_NOT_BE_REPLACED")
    shared_key = secrets.token_urlsafe(48)
    common = {
        "EMPIRE_FOUNDER_RESEARCH_AUTH_MODE": "ssh_loopback",
        "EMPIRE_RESEARCH_SSH_PRIVATE_ENABLED": "1",
        "EMPIRE_PRIVATE_FOUNDER_INGRESS_REVIEWED": "1",
        "EMPIRE_RESEARCH_SSH_BRIDGE_SECRET": shared_key,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
    }
    api_env = {**common, "PYTHONPATH": str(api_stage)}
    web_env = {
        **common, "EMPIRE_RESEARCH_ISOLATED_STAGE": "1",
        "NEXT_TELEMETRY_DISABLED": "1", "NODE_ENV": "production",
    }
    api = web = None
    try:
        api = subprocess.Popen(
            [sys.executable, "-B", "-c", API_CODE],
            cwd=api_stage, env=api_env, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
        _await_port(API_PORT, api)
        web = subprocess.Popen(
            [str(web_stage / "node_modules/.bin/next"), "start",
             "-H", "127.0.0.1", "-p", str(WEB_PORT)],
            cwd=web_stage, env=web_env, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
        _await_port(WEB_PORT, web)
        endpoint = "/founder/research"
        headers = {
            "Content-Type": "application/json",
            "Origin": "http://127.0.0.1:3098",
            "Sec-Fetch-Site": "same-origin",
        }
        payload = {"product": "empire_agent", "country": "US",
                   "niche": "legal", "depth": "speed",
                   "fresh_discovery": False}
        code, html = _request(WEB_PORT, endpoint)
        ssh_page_ready = (code == 200 and b"Private Research Workbench" in html
                          and shared_key.encode() not in html)
        code, _ = _request(WEB_PORT, endpoint, headers={"Host": "founder.empire-ai.co.uk"})
        public_host_refused = code == 404
        code, _ = _request(WEB_PORT, endpoint, headers={"x-forwarded-for": "203.0.113.50"})
        proxy_remote_refused = code == 404
        code, _ = _request(WEB_PORT, endpoint, headers={"cf-ray": "fake"})
        cloudflare_proxy_refused = code == 404
        code, _ = _request(API_PORT, "/v1/founder-research-products/catalog")
        direct_api_anonymous_refused = code == 401
        code, _ = _request(
            API_PORT, "/v1/founder-research-products/catalog",
            headers={"authorization": "Bearer " + ("X" * 64)},
        )
        direct_api_invalid_key_refused = code == 401
        code, _ = _request(
            API_PORT, "/v1/founder-research-products/catalog",
            headers={"authorization": "Bearer " + shared_key,
                     "x-forwarded-for": "203.0.113.80"},
        )
        direct_api_forged_proxy_refused = code == 403
        code, _ = _request(WEB_PORT, endpoint + "/execute")
        get_not_executable = code == 405
        code, _ = _request(WEB_PORT, endpoint + "/execute", method="POST",
                           headers={**headers, "Origin": "https://attacker.example"},
                           body=payload)
        cross_origin_denied = code == 403
        code, _ = _request(WEB_PORT, endpoint + "/execute", method="POST",
                           headers={k: v for k, v in headers.items()
                                    if k != "Sec-Fetch-Site"}, body=payload)
        missing_fetch_site_denied = code == 403
        code, _ = _request(WEB_PORT, endpoint + "/execute", method="POST",
                           headers={**headers, "cf-connecting-ip": "203.0.113.80"},
                           body=payload)
        proxy_post_denied = code == 404
        code, data = _request(WEB_PORT, endpoint + "/execute", method="POST",
                              headers=headers, body=payload)
        try:
            result = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError):
            result = {}
        authorised_ssh_research = (
            code == 200 and result.get("product_id") == "empire_agent"
            and result.get("niche") == "legal"
            and result.get("market") == "US"
            and result.get("original_source_count") == 0
            and result.get("outbound_authorized") is False
            and result.get("database_writes") is False
            and result.get("finance_authorized") is False
            and result.get("customer_delivery_authorized") is False
            and result.get("editorial_approval_verified") is False
        )
        code, _ = _request(WEB_PORT, endpoint + "/execute", method="POST",
                           headers=headers, body=payload)
        cooldown_works = code == 429
        code, _ = _request(WEB_PORT, "/founder/intent-review")
        existing_founder_page_preserved = code == 200
        return _safe_state({
            "ssh_private_ui_opens_without_browser_secret": ssh_page_ready,
            "public_hostname_rejected": public_host_refused,
            "forwarded_remote_client_rejected": proxy_remote_refused,
            "cloudflare_forwarding_rejected": cloudflare_proxy_refused,
            "direct_api_anonymous_rejected": direct_api_anonymous_refused,
            "direct_api_wrong_bridge_secret_rejected": direct_api_invalid_key_refused,
            "direct_api_proxy_header_rejected": direct_api_forged_proxy_refused,
            "get_execution_rejected": get_not_executable,
            "cross_origin_post_rejected": cross_origin_denied,
            "missing_fetch_metadata_rejected": missing_fetch_site_denied,
            "proxy_post_rejected": proxy_post_denied,
            "ssh_private_agent_research_read_only_pass": authorised_ssh_research,
            "repeat_execution_cooldown": cooldown_works,
            "existing_founder_intent_page_preserved": existing_founder_page_preserved,
        })
    finally:
        _shutdown(web)
        _shutdown(api)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only", required=True, action="store_true")
    p.add_argument("--synthetic-ssh-stage", required=True, action="store_true")
    p.add_argument("--api-stage-root", required=True, type=Path)
    p.add_argument("--web-stage-root", required=True, type=Path)
    options = p.parse_args(argv)
    try:
        result = run(options.api_stage_root, options.web_stage_root)
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        result = _safe_state({"private_ssh_session_integration_unavailable": False})
    ssh_pass = result["status"] == "ISOLATED_SIGNED_FOUNDER_RESEARCH_SESSION_E2E_PASS"
    ssh_report = {
        **result,
        "schema_version": "empire.research.isolated_ssh_private_e2e.v1",
        "status": ("ISOLATED_SSH_PRIVATE_FOUNDER_RESEARCH_E2E_PASS"
                   if ssh_pass else "HOLD_ISOLATED_SSH_FOUNDER_E2E_FAILED"),
        "synthetic_ephemeral_signer": False,
        "credential_persisted": False,
        "ssh_operator_login_independently_confirmed": False,
        "cloudflare_access_implemented": False,
        "production_deployed": False,
    }
    print(json.dumps(ssh_report, sort_keys=True))
    return 0 if ssh_pass else 3


if __name__ == "__main__":
    raise SystemExit(main())
