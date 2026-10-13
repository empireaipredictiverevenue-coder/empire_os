#!/usr/bin/env python3
"""Founder-approved, narrowly scoped enterprise-consent release.

--check is read only. --apply needs the exact named founder approval token
and root execution in the local Ubuntu console. Remote execution policy is
not to be circumvented. Never makes a valid prospect request or payment.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import stat
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = Path("/srv/empire_os")
STAGE = Path("/var/tmp/empire_predictive_consent_release_20261013")
LIVE = REPO / "apps/empire-public-site/out"
PAGE = "predictive-revenue.html"
SERVICE = "empire-self-serve-checkout.service"
SERVICE_URL = "http://127.0.0.1:8098"
PUBLIC_URL = "https://empire-ai.co.uk"
REQUIRED_COMMIT = "223c932c"
APPROVAL = "--approved-single-predictive-consent-page-and-checkout-restart"


class ReleaseHeld(RuntimeError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
        raise ReleaseHeld("UNSAFE_OR_MISSING_RELEASE_FILE")
    return path.read_bytes()


def http(path: str, *, method: str = "GET", payload: dict | None = None,
         origin: bool = False) -> tuple[int, bytes]:
    if not path.startswith("/"):
        raise ReleaseHeld("INVALID_HTTP_PATH")
    # Use the first-party public gateway loopback for negative POST tests; the
    # independent external CDN/origin readback uses curl after publication.
    url = ("http://127.0.0.1:80" if origin else SERVICE_URL) + path
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
        if origin:
            headers["Origin"] = PUBLIC_URL
            headers["Sec-Fetch-Site"] = "same-origin"
    req = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=7) as response:
            return response.status, response.read(262144)
    except HTTPError as exc:
        return exc.code, exc.read(262144)


def current_health() -> dict:
    code, body = http("/health")
    if code != 200:
        raise ReleaseHeld("CHECKOUT_HEALTH_NOT_200")
    data = json.loads(body)
    if not isinstance(data, dict) or data.get("status") != "online":
        raise ReleaseHeld("CHECKOUT_UNHEALTHY")
    for key in ("payment_proposal_authorized", "binding_order_creation_authorized",
                "payment_execution", "revenue_recognition"):
        if type(data.get(key)) is not bool:
            raise ReleaseHeld("CHECKOUT_HEALTH_SHAPE_CHANGED")
    if data["payment_execution"] or data["revenue_recognition"]:
        raise ReleaseHeld("UNEXPECTED_MONEY_AUTHORITY_STATE")
    return data


def eligible_manifest() -> dict:
    if STAGE.is_symlink() or not STAGE.is_dir() or LIVE.is_symlink():
        raise ReleaseHeld("INVALID_STAGE_OR_LIVE_ROOT")
    manifest_path = STAGE / "manifest.json"
    raw = checked_file(manifest_path)
    m = json.loads(raw)
    if (m.get("schema_version") != "empire.predictive_revenue_consent_release.v1"
            or m.get("mode") != "PREPARED_NOT_LIVE"
            or m.get("main_source_commit") != REQUIRED_COMMIT
            or m.get("new_route_page") != PAGE
            or m.get("new_assets") != 2
            or m.get("no_other_pages_touched") is not True
            or m.get("backend_restart_required") is not True
            or m.get("backend_restart_authorized") is not False
            or m.get("public_page_promotion_authorized") is not False):
        raise ReleaseHeld("STAGED_RELEASE_SCOPE_CHANGED")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", REQUIRED_COMMIT, "HEAD"],
        cwd=REPO, capture_output=True, check=False
    ).returncode != 0:
        raise ReleaseHeld("REQUIRED_SOURCE_COMMIT_NOT_LOADED")
    source = (REPO / "empire_os/self_serve_checkout_api.py").read_text(encoding="utf-8")
    if "if req.contact_consent is not True or req.website:" not in source:
        raise ReleaseHeld("CANONICAL_BACKEND_SOURCE_DOES_NOT_MATCH_RELEASE")
    old = checked_file(STAGE / "before" / PAGE)
    new = checked_file(STAGE / "after" / PAGE)
    live = checked_file(LIVE / PAGE)
    if (sha(old) != m["old_page_sha256"] or sha(new) != m["new_page_sha256"]
            or sha(live) != m["old_page_sha256"]):
        raise ReleaseHeld("EXISTING_PAGE_OR_BACKUP_HASH_MISMATCH")
    rendered = new.decode("utf-8")
    if (rendered.count('type="checkbox"') != 1
            or "I consent to Empire AI" not in rendered
            or 'href="https://empire-ai.co.uk/predictive-revenue"' not in rendered):
        raise ReleaseHeld("CANDIDATE_CONSENT_MARKUP_CHANGED")
    assets = m.get("assets")
    if not isinstance(assets, dict) or not 2 <= len(assets) <= 20:
        raise ReleaseHeld("INVALID_ASSET_SET")
    new_keys = []
    for key, details in assets.items():
        if (not isinstance(key, str) or not key.startswith("_next/static/")
                or ".." in Path(key).parts or Path(key).is_absolute()
                or not isinstance(details, dict)):
            raise ReleaseHeld("UNSAFE_ASSET_PATH")
        target = LIVE / key
        if target.parent.is_symlink() or target.is_symlink():
            raise ReleaseHeld("SYMLINK_ASSET")
        if details.get("live_present") is True:
            if sha(checked_file(target)) != details["sha256"]:
                raise ReleaseHeld("IMMUTABLE_SHARED_ASSET_CHANGED")
        elif details.get("live_present") is False:
            candidate = STAGE / "assets" / key
            if sha(checked_file(candidate)) != details["sha256"]:
                raise ReleaseHeld("STAGED_ASSET_HASH_MISMATCH")
            if target.exists():
                raise ReleaseHeld("NEW_ASSET_PATH_ALREADY_OCCUPIED")
            new_keys.append(key)
        else:
            raise ReleaseHeld("UNKNOWN_ASSET_CLASS")
    if len(new_keys) != 2:
        raise ReleaseHeld("UNEXPECTED_NEW_ASSET_COUNT")
    return m


def existing_catalog_proofs() -> dict:
    results = {}
    for path, expected, key in (
        ("/v1/catalog", 4, "count"),
        ("/v1/predictive-revenue/products", 5, "product_count"),
    ):
        code, raw = http(path)
        if code != 200:
            raise ReleaseHeld("CATALOG_HEALTH_FAILED")
        value = json.loads(raw)
        if (not isinstance(value, dict) or value.get(key) != expected
                or len(value.get("products", [])) != expected):
            raise ReleaseHeld("CURRENT_REVENUE_CATALOG_CHANGED")
        results[path] = expected
    return results


def invalid_api_proofs() -> dict:
    # OpenAPI is deliberately disabled on the live service. Use a deliberately
    # unknown offer code so this NEVER becomes a valid prospect even if an old
    # process was accidentally loaded. Verify *specific* consent errors.
    example = {
        "product_code": "not-an-empire-offer-consent-negative-20261013",
        "business_name": "Offline Negative Test",
        "email": "never-send@example.invalid",
        "domain": "example.invalid",
        "industry": "test",
        "geography": "test",
        "desired_outcome": "This request must be rejected without prospect ingestion",
        "idempotency_key": "invalid-consent-contract-test-20261013",
    }
    outcomes = {}
    for name, payload in (
        ("missing_consent", example),
        ("false_consent", {**example, "contact_consent": False}),
        ("bot_honeypot", {**example, "contact_consent": True, "website": "bots.example.invalid"}),
    ):
        code, raw = http("/v1/predictive-revenue/interests", method="POST", payload=payload)
        outcomes[name] = code
        if code != 422:
            raise ReleaseHeld("BACKEND_NEGATIVE_GATE_FAILED:" + name)
        response = json.loads(raw)
        detail = response.get("detail") if isinstance(response, dict) else None
        if name == "missing_consent":
            if "contact_consent" not in str(detail):
                raise ReleaseHeld("BACKEND_REQUIRED_CONSENT_SCHEMA_NOT_LOADED")
        elif detail != "specific_contact_consent_required":
            raise ReleaseHeld("BACKEND_CONSENT_REJECTION_REASON_INCORRECT:" + name)
    # Exactly one public negative-path request, never a valid buyer.
    code, raw = http("/v1/checkout/predictive-revenue/interests", method="POST",
                     payload={**example, "contact_consent": False}, origin=True)
    outcomes["gateway_false_consent"] = code
    if (code != 422 or json.loads(raw).get("detail") != "specific_contact_consent_required"):
        raise ReleaseHeld("PUBLIC_GATEWAY_NEGATIVE_GATE_FAILED")
    return outcomes


def atomic_new_asset(source: Path, destination: Path, expected: str, uid: int, gid: int):
    data = checked_file(source)
    if sha(data) != expected:
        raise ReleaseHeld("STAGED_ASSET_CHANGED")
    dest_dir = destination.parent
    if not dest_dir.is_dir() or dest_dir.is_symlink():
        raise ReleaseHeld("STATIC_ASSET_PARENT_UNSAFE_OR_MISSING")
    fd, temporary = tempfile.mkstemp(prefix=".consent-static-", dir=dest_dir)
    try:
        with os.fdopen(fd, "wb") as fp:
            fp.write(data)
            fp.flush()
            os.fsync(fp.fileno())
        os.chmod(temporary, 0o644)
        os.chown(temporary, uid, gid)
        if sha(checked_file(Path(temporary))) != expected:
            raise ReleaseHeld("ASSET_COPY_FAILED")
        os.link(temporary, destination)  # Fails closed: never overwrite shared assets.
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_page(data: bytes, expected_before: str, expected_after: str):
    target = LIVE / PAGE
    if sha(checked_file(target)) != expected_before or sha(data) != expected_after:
        raise ReleaseHeld("CONCURRENT_PAGE_CHANGE_BLOCKED")
    original_stat = target.stat()
    fd, temporary = tempfile.mkstemp(prefix=".consent-release-", dir=LIVE)
    try:
        with os.fdopen(fd, "wb") as fp:
            fp.write(data)
            fp.flush()
            os.fsync(fp.fileno())
        os.chmod(temporary, stat.S_IMODE(original_stat.st_mode))
        os.chown(temporary, original_stat.st_uid, original_stat.st_gid)
        if sha(checked_file(target)) != expected_before:
            raise ReleaseHeld("CONCURRENT_PAGE_CHANGE_BLOCKED")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def public_readback(m: dict):
    # Use the same public origin verified in the earlier six-page release.
    expected = m["new_page_sha256"]
    with tempfile.TemporaryDirectory(prefix="empire-consent-check-") as directory:
        targets = [("/predictive-revenue", expected)] + [
            ("/" + key, details["sha256"])
            for key, details in m["assets"].items()
            if details.get("live_present") is False
        ]
        for idx, (uri, digest) in enumerate(targets):
            out = str(Path(directory) / str(idx))
            proc = subprocess.run(
                ["curl", "--noproxy", "*", "--silent", "--show-error", "--location",
                 "--max-time", "12", "--output", out, "--write-out", "%{http_code}",
                 PUBLIC_URL + uri],
                capture_output=True, text=True, check=False
            )
            if proc.returncode != 0 or proc.stdout.strip() != "200":
                raise ReleaseHeld("PUBLIC_ASSET_OR_PAGE_HTTP_FAILED")
            if sha(checked_file(Path(out))) != digest:
                raise ReleaseHeld("PUBLIC_CONTENT_HASH_MISMATCH")
    return {"new_page": 200, "new_assets": 2, "sha256_verified": True}


def apply(m: dict) -> dict:
    if os.geteuid() != 0:
        raise ReleaseHeld("ROOT_OPERATOR_REQUIRED_FOR_EXACT_SERVICE_RESTART")
    if (STAGE / "receipt.json").exists():
        raise ReleaseHeld("PRIOR_RELEASE_RECEIPT_EXISTS")
    health_before = current_health()
    catalog_before = existing_catalog_proofs()
    proc = subprocess.run(
        ["systemctl", "restart", SERVICE], capture_output=True, text=True,
        check=False, timeout=30
    )
    if proc.returncode != 0:
        raise ReleaseHeld("EXACT_CHECKOUT_RESTART_FAILED_PAGE_UNCHANGED")
    health_after = None
    for _ in range(16):
        try:
            health_after = current_health()
            break
        except (ReleaseHeld, URLError, OSError, ValueError):
            time.sleep(0.5)
    if health_after is None:
        raise ReleaseHeld("CHECKOUT_DID_NOT_RETURN_HEALTHY_PAGE_UNCHANGED")
    for field in (
        "payment_proposal_authorized", "binding_order_creation_authorized",
        "payment_execution", "revenue_recognition", "checkout_settlement_mode",
        "bsc_payment_configuration_status", "founder_led_commercial_interest_enabled"
    ):
        if health_after.get(field) != health_before.get(field):
            raise ReleaseHeld("CHECKOUT_AUTHORITY_DRIFT_PAGE_UNCHANGED")
    if existing_catalog_proofs() != catalog_before:
        raise ReleaseHeld("CHECKOUT_CATALOG_DRIFT_PAGE_UNCHANGED")
    negative = invalid_api_proofs()
    # Revalidate source/static state *after* the service restart, before writing.
    eligible_manifest()
    original = checked_file(LIVE / PAGE)
    old_sha = sha(original)
    if old_sha != m["old_page_sha256"]:
        raise ReleaseHeld("CONCURRENT_PAGE_CHANGE_PAGE_UNCHANGED")
    original_stat = (LIVE / PAGE).stat()
    published = False
    try:
        for key, details in m["assets"].items():
            if details["live_present"] is False:
                atomic_new_asset(STAGE / "assets" / key, LIVE / key,
                                 details["sha256"], original_stat.st_uid,
                                 original_stat.st_gid)
        atomic_page(checked_file(STAGE / "after" / PAGE),
                    m["old_page_sha256"], m["new_page_sha256"])
        published = True
        verification = public_readback(m)
        if sha(checked_file(LIVE / PAGE)) != m["new_page_sha256"]:
            raise ReleaseHeld("POST_PUBLICATION_LOCAL_HASH_MISMATCH")
    except Exception:
        # Restore *only* the exact page we published. No unrelated route touched.
        if published and sha(checked_file(LIVE / PAGE)) == m["new_page_sha256"]:
            atomic_page(original, m["new_page_sha256"], m["old_page_sha256"])
        raise
    receipt = {
        "status": "PREDICTIVE_REVENUE_CONSENT_LIVE_VERIFIED",
        "published_utc": datetime.now(timezone.utc).isoformat(),
        "page_only": "/predictive-revenue",
        "original_page_sha256": m["old_page_sha256"],
        "published_page_sha256": m["new_page_sha256"],
        "new_immutable_assets": 2,
        "checkout_service_restarted": True,
        "payment_authority_unchanged": True,
        "checkout_catalogs": catalog_before,
        "live_negative_api_proofs": negative,
        "public_readback": verification,
        "synthetic_prospects_written": False,
        "outbound_sent": False,
        "payment_execution": False,
    }
    dest = STAGE / "receipt.json"
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fp:
        json.dump(receipt, fp, indent=2, sort_keys=True)
        fp.write("\n")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(APPROVAL, action="store_true")
    args = parser.parse_args()
    try:
        m = eligible_manifest()
        health = current_health()
        if not args.apply:
            print(json.dumps({
                "status": "READ_ONLY_RELEASE_PREFLIGHT_PASS",
                "mode": "OBSERVE",
                "existing_checkout_payment_execution": health["payment_execution"],
                "staged_new_assets": m["new_assets"],
                "live_page_unchanged": True,
                "restart_performed": False,
                "outbound_sent": False,
            }, sort_keys=True))
            return 0
        if not getattr(args, APPROVAL.lstrip("-").replace("-", "_")):
            raise ReleaseHeld("EXACT_FOUNDER_APPROVAL_FLAG_REQUIRED")
        lock = STAGE / "operator_release.lock"
        if lock.is_symlink():
            raise ReleaseHeld("UNSAFE_RELEASE_LOCK")
        with lock.open("a+") as fp:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = apply(m)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        # Deliberately exclude sensitive process or SQL errors from release output.
        code = str(exc) if isinstance(exc, ReleaseHeld) else type(exc).__name__
        print(json.dumps({"status": "RELEASE_HELD", "reason": code,
                          "no_new_outbound": True, "no_payment_execution": True},
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
