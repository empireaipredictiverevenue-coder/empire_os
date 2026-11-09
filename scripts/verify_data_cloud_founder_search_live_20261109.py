"""Exactly one protected Data Cloud production search; owner-signed transport canary.

No simulated meter, no fake provider, no app modification. This does NOT claim
to be a CRM-browser-originated session exchange. Never print credentials.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import stat
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives import serialization

ROOT = Path("/etc/empire-data-cloud-founder-20261107")
RUNTIME = Path("/var/lib/empire-data-cloud-founder-pilot/runtime.json")
JOURNAL = Path("/var/lib/empire-data-cloud-search-owner-20261109-v2/JOURNAL.json")
SIGNER = ROOT / "data-cloud-signing.pem"
KEY = ROOT / "founder-api-key.secret"
API = "http://127.0.0.1"
QUERY = "python programming language"
LIMIT = 2

def check(path: Path, mode: int, owner: int, *, read: bool) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("protected_file_missing_or_redirected")
    st = path.stat()
    if st.st_uid != owner or stat.S_IMODE(st.st_mode) != mode or st.st_nlink != 1:
        raise ValueError("protected_file_custody_changed")
    return path.read_bytes() if read else b""

def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

def approved() -> dict:
    if os.geteuid() != 0:
        raise ValueError("root_only_approved_canary")
    check(SIGNER, 0o400, 0, read=False)
    check(KEY, 0o400, 0, read=False)
    check(RUNTIME, 0o600, 1000, read=False)
    check(JOURNAL, 0o600, 0, read=False)
    details = json.loads(check(JOURNAL, 0o600, 0, read=True))
    if details.get("phase") != "active" or not details.get("receipt_sha256"):
        raise ValueError("guarded_release_not_active")
    cfg = json.loads(check(RUNTIME, 0o600, 1000, read=True))
    if cfg.get("scope") != "FOUNDER_ONLY_USAGE_NO_PROVIDERS" or cfg.get("release_version") != 1:
        raise ValueError("founder_scope_or_original_runtime_changed")
    if not all(isinstance(cfg.get(k), str) and cfg[k] for k in ("owner_actor_id", "owner_tenant_id", "data_signing_public_key_hex")):
        raise ValueError("original_founder_identity_unavailable")
    return cfg

def owner_token(cfg: dict) -> str:
    signer = serialization.load_pem_private_key(check(SIGNER, 0o400, 0, read=True), password=None)
    if signer.public_key().public_bytes_raw().hex() != cfg["data_signing_public_key_hex"]:
        raise ValueError("founder_signing_key_pin_changed")
    now = int(time.time())
    header = {"alg": "EdDSA", "typ": "JWT", "kid": cfg["data_signing_key_id"]}
    claims = {
        "iss": "empire-os", "aud": "empire-data-cloud",
        "sub": cfg["owner_actor_id"], "tenant_id": cfg["owner_tenant_id"],
        "scope": "data:read", "iat": now, "nbf": now, "exp": now + 60,
        "jti": secrets.token_urlsafe(24),
    }
    signed = b64(json.dumps(header, separators=(",", ":")).encode()) + "." + b64(
        json.dumps(claims, separators=(",", ":")).encode())
    return signed + "." + b64(signer.sign(signed.encode("ascii")))

def run(real: bool) -> None:
    cfg = approved()
    if not real:
        print("PREFLIGHT_PASS=protected owner signer, key metadata, original tenant and active release")
        print("PRODUCTION_SEARCH_REQUESTS=0")
        return

    token = owner_token(cfg)
    key = check(KEY, 0o400, 0, read=True).decode("utf8").strip()
    if not 32 <= len(key) <= 256 or any(ch.isspace() for ch in key):
        raise ValueError("invalid_existing_owner_key")
    headers = {
        "X-Empire-Data-Session": token,
        "Authorization": "Bearer " + key,
        "Cache-Control": "no-store",
    }
    with httpx.Client(trust_env=False, follow_redirects=False, timeout=10) as client:
        before = client.get(API + "/v1/data/usage", headers=headers)
        if before.status_code != 200:
            raise ValueError("owner_authenticated_usage_denied_http_" + str(before.status_code))
        snapshot = before.json()
        if snapshot.get("billing_enabled") is not False:
            raise ValueError("live_billing_not_disabled")
        count = snapshot.get("request_count")
        if not isinstance(count, int) or count >= 3:
            raise ValueError("insufficient_existing_founder_search_quota")
        check_missing = client.post(API + "/v1/data/search")
        if check_missing.status_code != 401:
            raise ValueError("missing_credentials_not_rejected")
        request_headers = {
            **headers,
            "Idempotency-Key": "founder-real-search-" + secrets.token_hex(12),
        }
        response = client.post(API + "/v1/data/search",
                               json={"query": QUERY, "limit": LIMIT},
                               headers=request_headers)
        # Exactly one POST with legitimate credentials. NEVER retry on failure.
        if response.status_code != 200:
            print("ONE_REAL_SEARCH_HTTP=" + str(response.status_code))
            raise ValueError("authenticated_search_not_200")
        payload = response.json()
        results = payload.get("results")
        if payload.get("status") != "results" or not isinstance(results, list) or not results:
            raise ValueError("source_returned_no_verified_results")
        if payload.get("buyer_intent_verified") is not False:
            raise ValueError("source_incorrectly_claims_buyer_intent")
        summary = []
        for item in results:
            source = item.get("source") or {}
            host = urlsplit(str(item.get("url", ""))).hostname
            if (source.get("source_id") != "empire_search_fabric_public"
                    or source.get("upstream_engine") not in {"bing_html", "google_html", "brave_web"}
                    or not source.get("observed_at") or not host):
                raise ValueError("missing_verified_search_provenance")
            summary.append({"title": str(item.get("title", ""))[:110],
                            "host": host, "engine": source["upstream_engine"]})
        after = client.get(API + "/v1/data/usage", headers=headers)
        if after.status_code != 200:
            raise ValueError("post_search_usage_unavailable")
        new = after.json()
        if new.get("request_count") != count + 1 or new.get("billing_enabled") is not False:
            raise ValueError("canonical_usage_count_or_billing_changed")
        if response.headers.get("cache-control") != "no-store":
            raise ValueError("private_response_cache_control_missing")
    print("LIVE_DATA_CLOUD_AUTHENTICATED_SEARCH_PASS")
    print(json.dumps({
        "search_http_status": 200,
        "source": "empire_search_fabric_public",
        "results": summary,
        "usage_before": count,
        "usage_after": count + 1,
        "paid_provider_calls": 0,
        "billing_enabled": False,
        "authentication": "operator-signed owner token + existing protected API key",
        "founder_browser_origin_proven": False,
    }, sort_keys=True))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    x = parser.add_mutually_exclusive_group(required=True)
    x.add_argument("--preflight", action="store_true")
    x.add_argument("--apply-founder-approved", action="store_true")
    args = parser.parse_args()
    try:
        run(real=args.apply_founder_approved)
    except Exception as exc:
        print("CANARY_FAILED=" + str(exc), file=sys.stderr)
        raise SystemExit(1)
