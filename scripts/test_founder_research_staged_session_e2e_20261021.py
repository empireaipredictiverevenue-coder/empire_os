"""Ephemeral signed-session end-to-end test of two already staged applications.

No deployment, changes to production, real credentials or Cloudflare Access
assumptions. The mock JWK source is injected ONLY into a disposable local
uvicorn process. PyJWT's actual RS256 signature/aud/issuer/exp/sub verification
and the real Next.js bridge and Research product are exercised unchanged.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

API_PORT = 3097
WEB_PORT = 3098
ROOT_PREFIXES = ("empire-research-api-stage-", "empire-research-next-stage-")
TEAM = "empire-isolated-stage.cloudflareaccess.com"
AUD = "empire-isolated-stage-audience"
SUB = "empire-isolated-founder"
ORIGIN = "https://founder-isolated-stage.empire-ai.co.uk"
READER = build_opener(ProxyHandler({}))
API_SCRIPT = """
import base64,os
from types import SimpleNamespace
from cryptography.hazmat.primitives import serialization
from empire_os import founder_research_auth
public = serialization.load_pem_public_key(base64.b64decode(os.environ.pop("EMPIRE_SYNTHETIC_STAGE_PUB_PEM_B64")))
def local_ephemeral_jwks(team):
    return SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=public))
founder_research_auth._jwks_client = local_ephemeral_jwks
from empire_os.founder_dashboard_service import app
import uvicorn
uvicorn.run(app,host="127.0.0.1",port=3097,workers=1,log_level="critical",access_log=False)
"""


def _verify_stage(root: Path, prefix: str, indicator: str) -> None:
    if (root.is_symlink() or root.parent.resolve() != Path("/tmp")
            or not root.name.startswith(prefix) or not root.is_dir()
            or root.stat().st_mode & 0o077
            or not (root / indicator).is_file()):
        raise ValueError("UNTRUSTED_EPHEMERAL_APPLICATION_STAGE")


def _free_port(port: int) -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        return probe.connect_ex(("127.0.0.1", port)) != 0
    finally:
        probe.close()


def _request(port: int, path: str, *, method="GET", headers=None, body=None):
    request = Request("http://127.0.0.1:" + str(port) + path,
                      method=method, headers=headers or {},
                      data=(json.dumps(body).encode() if body is not None else None))
    try:
        with READER.open(request, timeout=7) as response:
            return response.status, response.read(1500000)
    except HTTPError as exc:
        return exc.code, exc.read(1500000)


def _await_port(port, process):
    until = time.monotonic() + 20
    while time.monotonic() < until:
        if process.poll() is not None:
            raise ValueError("ISOLATED_SERVER_PROCESS_EXITED")
        if not _free_port(port):
            return
        time.sleep(0.2)
    raise ValueError("ISOLATED_SERVER_NOT_READY")


def _shutdown(p):
    if p is None:
        return
    try:
        os.killpg(p.pid, signal.SIGTERM)
        p.wait(timeout=6)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _token(private, *, sub=SUB, aud=AUD, issuer="https://" + TEAM,
           expiry=None):
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "sub": sub, "aud": aud, "iss": issuer,
        "iat": now, "exp": expiry or now + timedelta(minutes=4),
    }, private, algorithm="RS256", headers={"kid": "stage-ephemeral-only"})


def _safe_state(values):
    passed = all(values.values())
    return {
        "schema_version": "empire.research.isolated_signed_session_e2e.v1",
        "status": ("ISOLATED_SIGNED_FOUNDER_RESEARCH_SESSION_E2E_PASS"
                   if passed else "HOLD_ISOLATED_FOUNDER_E2E_CHECKS_FAILED"),
        "checks": values,
        "synthetic_ephemeral_signer": True,
        "real_cloudflare_access_jwks_tested": False,
        "real_founder_session_verified": False,
        "live_ingress_policy_verified": False,
        "production_code_changed": False,
        "user_data_written": False,
        "customer_messages_sent": False,
        "financial_actions_authorized": False,
    }


def run(api_stage: Path, web_stage: Path) -> dict:
    _verify_stage(api_stage, ROOT_PREFIXES[0], "empire_os/founder_dashboard_service.py")
    _verify_stage(web_stage, ROOT_PREFIXES[1], ".next/BUILD_ID")
    if not _free_port(API_PORT) or not _free_port(WEB_PORT):
        raise ValueError("STAGING_LOOPBACK_PORT_ALREADY_OCCUPIED")
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(api_stage),
        "EMPIRE_FOUNDER_CF_TEAM_DOMAIN": TEAM,
        "EMPIRE_FOUNDER_CF_ACCESS_AUD": AUD,
        "EMPIRE_RESEARCH_ALLOWED_FOUNDER_SUB": SUB,
        "EMPIRE_SYNTHETIC_STAGE_PUB_PEM_B64": base64.b64encode(public_pem).decode(),
    }
    webenv = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "NODE_ENV": "production",
        "EMPIRE_RESEARCH_ISOLATED_STAGE": "1",
        "EMPIRE_FOUNDER_RESEARCH_ORIGIN": ORIGIN,
        "NEXT_TELEMETRY_DISABLED": "1",
    }
    api = web = None
    try:
        api = subprocess.Popen(
            [sys.executable, "-B", "-c", API_SCRIPT],
            cwd=api_stage, env=env, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
        _await_port(API_PORT, api)
        web = subprocess.Popen(
            [str(web_stage / "node_modules/.bin/next"), "start",
             "-H", "127.0.0.1", "-p", str(WEB_PORT)],
            cwd=web_stage, env=webenv, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
        _await_port(WEB_PORT, web)
        good = _token(private)
        wrong_sub = _token(private, sub="not-the-authorised-founder")
        wrong_aud = _token(private, aud="other-audience")
        wrong_iss = _token(private, issuer="https://wrong.cloudflareaccess.com")
        another_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        invalid_signature = _token(another_key)
        expired = _token(private, expiry=datetime.now(timezone.utc) - timedelta(minutes=10))
        prefix = "/founder/research"
        valid_assertion = {"cf-access-jwt-assertion": good}
        request_headers = {
            **valid_assertion, "Origin": ORIGIN,
            "Sec-Fetch-Site": "same-origin",
            "Content-Type": "application/json",
        }
        code, html = _request(WEB_PORT, prefix)
        locked_without_token = (
            code == 200 and b"Verified Founder session required" in html
            and b"Private Research Workbench" not in html
        )
        code, html = _request(WEB_PORT, prefix, headers=valid_assertion)
        page_with_valid_token = code == 200 and b"Private Research Workbench" in html
        token_never_rendered_into_html = good.encode() not in html
        code, html = _request(WEB_PORT, prefix,
                              headers={"cf-access-jwt-assertion": wrong_sub})
        rejected_subject_page = code == 200 and b"Verified Founder session required" in html
        code, html = _request(WEB_PORT, prefix,
                              headers={"cf-access-jwt-assertion": wrong_aud})
        rejected_audience_page = code == 200 and b"Verified Founder session required" in html
        code, _ = _request(WEB_PORT, prefix + "/execute")
        get_not_executable = code == 405
        code, _ = _request(
            WEB_PORT, prefix + "/execute", method="POST",
            headers={k: v for k, v in request_headers.items() if k != "cf-access-jwt-assertion"},
            body={"product": "empire_agent"},
        )
        missing_assertion = code == 401
        code, _ = _request(
            WEB_PORT, prefix + "/execute", method="POST",
            headers={**request_headers, "Origin": "https://unexpected.example"},
            body={"product": "empire_agent"},
        )
        cross_origin_denied = code == 403
        code, _ = _request(
            WEB_PORT, prefix + "/execute", method="POST",
            headers={**request_headers, "cf-access-jwt-assertion": wrong_sub},
            body={"product": "empire_agent"},
        )
        wrong_subject_denied = code == 403
        code, _ = _request(
            WEB_PORT, prefix + "/execute", method="POST",
            headers={**request_headers, "cf-access-jwt-assertion": expired},
            body={"product": "empire_agent"},
        )
        expired_session_denied = code == 401
        code, _ = _request(
            WEB_PORT, prefix + "/execute", method="POST",
            headers={**request_headers, "cf-access-jwt-assertion": wrong_iss},
            body={"product": "empire_agent"},
        )
        wrong_issuer_denied = code == 401
        code, _ = _request(
            WEB_PORT, prefix + "/execute", method="POST",
            headers={**request_headers, "cf-access-jwt-assertion": invalid_signature},
            body={"product": "empire_agent"},
        )
        forged_signature_denied = code == 401
        code, _ = _request(
            WEB_PORT, prefix + "/execute", method="POST",
            headers=request_headers,
            body={"product": "empire_agent", "fresh_discovery": "true"},
        )
        invalid_boolean_denied = code == 422
        code, _ = _request(
            WEB_PORT, prefix + "/execute", method="POST",
            headers=request_headers,
            body={"product": "empire_agent", "shell": "echo unsafe"},
        )
        extra_field_denied = code == 422
        payload = {"product": "empire_agent", "country": "GB",
                   "niche": "property", "depth": "speed",
                   "fresh_discovery": False}
        code, blob = _request(WEB_PORT, prefix + "/execute",
                              method="POST", headers=request_headers,
                              body=payload)
        try:
            result = json.loads(blob)
        except (UnicodeDecodeError, json.JSONDecodeError):
            result = {}
        verified_agent_product = (
            code == 200 and result.get("product_id") == "empire_agent"
            and result.get("niche") == "property"
            and result.get("market") == "GB"
            and result.get("original_source_count") == 0
            and result.get("outbound_authorized") is False
            and result.get("customer_delivery_authorized") is False
            and result.get("finance_authorized") is False
            and result.get("database_writes") is False
            and result.get("editorial_approval_verified") is False
            and result.get("research", {}).get("status") ==
                "HELD_NICHE_ORIGINAL_SOURCE_INTAKE_REQUIRED"
        )
        code, _ = _request(WEB_PORT, prefix + "/execute", method="POST",
                           headers=request_headers, body=payload)
        duplicate_cooldown = code == 429
        code, _ = _request(WEB_PORT, "/founder/intent-review")
        existing_owner_page_preserved = code == 200
        return _safe_state({
            "page_without_token_locked": locked_without_token,
            "valid_signed_token_displays_workbench": page_with_valid_token,
            "signed_token_not_rendered_into_html": token_never_rendered_into_html,
            "unapproved_subject_page_locked": rejected_subject_page,
            "unapproved_audience_page_locked": rejected_audience_page,
            "get_execution_refused": get_not_executable,
            "missing_assertion_refused": missing_assertion,
            "cross_origin_post_refused": cross_origin_denied,
            "unapproved_subject_post_refused": wrong_subject_denied,
            "expired_signed_session_refused": expired_session_denied,
            "wrong_token_issuer_refused": wrong_issuer_denied,
            "forged_token_signature_refused": forged_signature_denied,
            "nonboolean_discovery_flag_refused": invalid_boolean_denied,
            "unexpected_execution_fields_refused": extra_field_denied,
            "authorised_signed_agent_research_completed": verified_agent_product,
            "second_execution_cooldown_enforced": duplicate_cooldown,
            "existing_founder_owner_page_preserved": existing_owner_page_preserved,
        })
    finally:
        _shutdown(web)
        _shutdown(api)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", required=True, action="store_true")
    parser.add_argument("--synthetic-stage-session", required=True, action="store_true")
    parser.add_argument("--api-stage-root", required=True, type=Path)
    parser.add_argument("--web-stage-root", required=True, type=Path)
    options = parser.parse_args(argv)
    try:
        answer = run(options.api_stage_root, options.web_stage_root)
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired, URLError):
        answer = _safe_state({"isolated_signed_session_harness_unavailable": False})
    print(json.dumps(answer, sort_keys=True))
    return 0 if answer["status"] == "ISOLATED_SIGNED_FOUNDER_RESEARCH_SESSION_E2E_PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
