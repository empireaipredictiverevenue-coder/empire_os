"""Existing Website & Growth guarded owner release of the post-V2 SaaS guide.

No new platform or agent. --preflight is GET/read-only; a separate signed-off
founder-specific scope approval is required before ANY production mutation.
The existing root-owned website lock, backup and atomic rollback are reused.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import stat
from typing import Any

from scripts.publish_industry_enquiry_v2_20261023 import (
    ReleaseHold, _get, _hash, _index, archive_full_site,
    _save_private_once, _locked_release,
)
from scripts.release_predictive_roofing_two_page_20261022 import (
    apply_four_pages_and_eight_assets,
)

ROOT = Path("/srv/empire_os")
LIVE = ROOT / "apps/empire-public-site/out"
PRIVATE = Path("/home/ubuntu/empire_releases/seo_saas_20261024_after_v2")
CANDIDATE = PRIVATE / "REBASED_CANDIDATE_RECEIPT.json"
BROWSER = PRIVATE / "BROWSER_SAAS_AFTER_V2_QA.json"
ROLLBACK_QA = PRIVATE / "SAAS_AFTER_V2_PRIVATE_ROLLBACK_QA.json"
CTA_QA = PRIVATE / "BROWSER_SAAS_FIRST_PARTY_CTA_20261024.json"
PINNED = {
    CANDIDATE: "f8d377850a508f0ecef2d1a15c43f70bc25b1c8fe40e2c34c2ea4996509b84a0",
    BROWSER: "e96b3d46da57233fd9988970f6b9cdbc1a7875ace066cf52999fb76a72d9bc09",
    ROLLBACK_QA: "2940a21d4edc68b52b2e4e2b634faaa26a1a93853607a18bd2f8a4d1bac56a3a",
    CTA_QA: "9819d069f9b259aa2dc920bba8580e18d522d67e8dacff7beac0fe21480abcdf",
}
ARCHIVE = Path("/var/backups/empire-website/saas_guide_post_v2_pre_659_20261024.tar")
BACKUP_RECEIPT = ARCHIVE.with_suffix(".receipt.json")
RELEASE_RECEIPT = ARCHIVE.with_suffix(".publication.json")
APPROVAL = ROOT / "docs/website/release_candidates/SAAS_GUIDE_RELEASE_APPROVAL_20261024.json"
# Unset deliberately. A separate, exact founder approval must precede
# an owner-issued code change pinning its immutable approval receipt digest.
APPROVAL_SHA256: str | None = None
EXACT_APPLY = "--apply-founder-approved-saas-guide-after-v2"
PAGE_FILES = ("predictive-revenue.html", "predictive-revenue.txt")
PROTECT = ("/", "/commercial", "/buy", "/privacy",
           "/industries/roofing", "/industries/solar",
           "/industries/hvac", "/industries/property")


def _read_pinned(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or _hash(path.read_bytes()) != PINNED[path]:
        raise ReleaseHold("PINNED_PRIVATE_EVIDENCE_DRIFT_" + path.name)
    return json.loads(path.read_text(encoding="utf-8"))


class _Markup(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms = 0
        self.consent = 0
        self.links: set[str] = set()
        self.assets: set[str] = set()
        self.external_scripts: set[str] = set()
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "form":
            self.forms += 1
        if tag == "input" and a.get("type") == "checkbox" and "required" in a:
            self.consent += 1
        if tag == "a" and a.get("href"):
            self.links.add(a["href"])
        for k in ("href", "src"):
            val = a.get(k) or ""
            if val.startswith("/_next/static/"):
                self.assets.add(val.split("?", 1)[0].lstrip("/"))
            if tag == "script" and val.startswith(("https://", "http://")):
                self.external_scripts.add(val)


def preflight(*, live: Path = LIVE) -> dict[str, Any]:
    p = _read_pinned(CANDIDATE)
    b = _read_pinned(BROWSER)
    q = _read_pinned(ROLLBACK_QA)
    cta = _read_pinned(CTA_QA)
    if (p.get("status") != "PRIVATE_659_TO_662_SAAS_SCOPED_OVERLAY_REBASED_NOT_PUBLISHED"
        or p.get("source_guide_commit") != "54601ed54"
        or p.get("live_v2_release_source_commit") != "758a5a31b"
        or p.get("original_live_file_count") != 659
        or p.get("private_candidate_file_count") != 662
        or p.get("all_v2_10_page_hashes_retained") is not True
        or p.get("all_v2_6_asset_hashes_retained") is not True
        or p.get("site_publication_authorized") is not False
        or p.get("separate_founder_approval_received") is not False
        or p.get("root_controlled_new_659_backup_established") is not False):
        raise ReleaseHold("UNTRUSTED_SAAS_CANDIDATE_CONTRACT")
    if (b.get("status") != "PRIVATE_DESKTOP_MOBILE_BROWSER_SMOKE_PASS_NOT_PUBLISHED"
        or b.get("widths") != [320, 390, 820, 1440]
        or len(b.get("route_checks", [])) != 8
        or len(b.get("navigation_checks", [])) != 2
        or any(c.get("http_status") != 200 or c.get("overflow")
               or not c.get("hasText") for c in b["route_checks"])
        or any(not row.get("passed") for row in b["navigation_checks"])
        or b.get("missing_local_assets") != []
        or b.get("page_errors") != []
        or any(b.get(k) != 0 for k in ("blocked_external", "blocked_non_get", "form_submissions"))
        or b.get("public_release_authorized") is not False):
        raise ReleaseHold("PRIVATE_POST_V2_BROWSER_QA_FAILED")
    if (q.get("status") != "PRIVATE_659_TO_662_TRANSACTION_AND_ROLLBACK_PASS_NOT_PUBLISHED"
        or q.get("actual_public_site_unchanged") is not True
        or q.get("live_659_hashes_preserved") is not True
        or len(q.get("scenarios", [])) != 2
        or any(not s.get("all_hashes_verified") for s in q["scenarios"])
        or {s.get("file_count") for s in q["scenarios"]} != {659, 662}):
        raise ReleaseHold("PRIVATE_POST_V2_ROLLBACK_QA_FAILED")
    expected_cta = {
        (390, "#deployment-request", "/predictive-revenue"),
        (390, "/commercial#commercial-enquiry", "/commercial"),
        (1440, "#deployment-request", "/predictive-revenue"),
        (1440, "/commercial#commercial-enquiry", "/commercial"),
    }
    cta_checks = cta.get("checks", [])
    if (cta.get("schema_version") != "empire.website.saas_first_party_cta_private_browser.v1"
        or cta.get("status") != "PRIVATE_SAAS_FIRST_PARTY_CTA_NAVIGATION_PASS"
        or cta.get("source_commit") != "54601ed54"
        or len(cta_checks) != 4
        or {(row.get("width"), row.get("clicked"), row.get("landed_path"))
            for row in cta_checks} != expected_cta
        or any(row.get("passed") is not True
            or row.get("source") != "/predictive-revenue#saas-revenue-diagnosis"
            or row.get("landed_anchor") !=
                ("#deployment-request" if row.get("landed_path") == "/predictive-revenue"
                 else "#commercial-enquiry")
            or any(row.get("form", {}).get(k) is not True for k in (
                "sectionExists", "formExists", "requiredConsentExists",
                "requiredConsentIsUnchecked", "requiredEmailExists",
                "siteContentExists",
            ))
            or row.get("form", {}).get("formCount") != 1 for row in cta_checks)
        or cta.get("page_errors") != []
        or cta.get("missing_local_assets") != []
        or any(cta.get(k) != 0 for k in (
            "rejected_non_get", "rejected_external", "form_submissions"))
        or cta.get("public_files_modified") is not False
        or cta.get("authority") != "NONE"):
        raise ReleaseHold("PRIVATE_FIRST_PARTY_CTA_BROWSER_QA_FAILED")
    root = Path(p["candidate_root"])
    if (root != PRIVATE / "out" or root.is_symlink() or not root.is_dir()
        or PRIVATE.is_symlink()):
        raise ReleaseHold("PRIVATE_STAGING_ROOT_CHANGED")
    original = p["live_source_sha256"]
    candidate = p["private_candidate_sha256"]
    replacements = {k: v["new_sha256"] for k, v in p["replacements"].items()}
    baseline = {k: v["baseline_sha256"] for k, v in p["replacements"].items()}
    additions = p["new_hashed_assets"]
    if (len(original) != 659 or len(candidate) != 662
        or set(replacements) != set(PAGE_FILES) or set(baseline) != set(PAGE_FILES)
        or len(additions) != 3 or set(replacements) & set(additions)
        or set(additions) & set(original)
        or not all(name.startswith("_next/static/") for name in additions)
        or any(original.get(k) != v for k, v in baseline.items())
        or candidate != {**original, **replacements, **additions}):
        raise ReleaseHold("EXACT_FIVE_FILE_RELEASE_SCOPE_DRIFT")
    if RELEASE_RECEIPT.exists() or RELEASE_RECEIPT.is_symlink():
        raise ReleaseHold("SAAS_RELEASE_ALREADY_RECORDED")
    if ARCHIVE.exists() or ARCHIVE.is_symlink() or BACKUP_RECEIPT.exists() or BACKUP_RECEIPT.is_symlink():
        raise ReleaseHold("SAAS_BACKUP_ALREADY_EXISTS_REVIEW_REQUIRED")
    current = _index(live)
    stage = _index(root)
    if current != original or stage != candidate:
        raise ReleaseHold("659_LIVE_OR_662_STAGED_FULL_HASH_DRIFT")
    staged_markup = _Markup()
    staged_markup.feed((root / "predictive-revenue.html").read_text(encoding="utf-8"))
    commercial = _Markup()
    commercial.feed((root / "commercial.html").read_text(encoding="utf-8"))
    if (staged_markup.forms != 1 or staged_markup.consent != 1
        or commercial.forms != 1 or commercial.consent != 1
        or "saas-revenue-diagnosis" not in staged_markup.ids
        or "deployment-request" not in staged_markup.ids
        or "commercial-enquiry" not in commercial.ids
        or "#deployment-request" not in staged_markup.links
        or "/commercial#commercial-enquiry" not in staged_markup.links
        or staged_markup.assets - set(candidate)
        or commercial.assets - set(candidate)):
        raise ReleaseHold("ORIGINAL_INTAKE_CONSENT_OR_ASSETS_NOT_PRESERVED")
    live_markup = _Markup()
    live_markup.feed((live / "predictive-revenue.html").read_text(encoding="utf-8"))
    if staged_markup.external_scripts - live_markup.external_scripts:
        raise ReleaseHold("EXTERNAL_SCRIPT_ADDED")
    # Served bytes must match this one precise immutable 659-file generation.
    previous_http = {r: _hash(_get(r)) for r in ("/predictive-revenue",) + PROTECT}
    for route, digest in previous_http.items():
        name = "index.html" if route == "/" else route.lstrip("/") + ".html"
        if name in original and digest != original[name]:
            raise ReleaseHold("SERVED_BASELINE_CHANGED_" + route)
    return {
        "status": "SAAS_659_TO_662_PREFLIGHT_PASS_PUBLICATION_NOT_APPROVED",
        "live_before_sha256": original, "candidate_sha256": candidate,
        "original_page_hashes": baseline,
        "new_page_hashes": replacements,
        "new_immutable_assets": additions,
        "staged_root": root, "protected_http_sha256": previous_http,
        "original_file_count": 659, "candidate_file_count": 662,
        "existing_page_replacements": 2, "new_asset_count": 3,
        "website_publication_authorized": False,
        "verified_root_backup_exists": False, "writes_performed": False,
    }


def require_separate_founder_approval() -> dict[str, Any]:
    """A CLI argument or the earlier V2 approval can never approve this release."""
    if not APPROVAL_SHA256:
        raise ReleaseHold("SEPARATE_SAAS_FOUNDER_APPROVAL_NOT_YET_RECORDED")
    if APPROVAL.is_symlink() or not APPROVAL.is_file():
        raise ReleaseHold("SAAS_APPROVAL_RECEIPT_NOT_PRESENT")
    if _hash(APPROVAL.read_bytes()) != APPROVAL_SHA256:
        raise ReleaseHold("SAAS_APPROVAL_RECEIPT_SHA_DRIFT")
    a = json.loads(APPROVAL.read_text(encoding="utf-8"))
    if (a.get("schema_version") != "empire.website.saas_guide_founder_release_approval.v1"
        or a.get("founder_explicit_approval") is not True
        or a.get("target_candidate_receipt_sha256") != PINNED[CANDIDATE]
        or a.get("approved_baseline_file_count") != 659
        or a.get("approved_candidate_file_count") != 662
        or a.get("scope") != list(PAGE_FILES) +
                sorted(json.loads(CANDIDATE.read_text())["new_hashed_assets"])):
        raise ReleaseHold("SAAS_FOUNDER_APPROVAL_WRONG_SCOPE")
    return a


def publish() -> dict[str, Any]:
    if os.geteuid() != 0:
        raise ReleaseHold("ORIGINAL_WEBSITE_ROOT_OWNER_AUTHORITY_REQUIRED")
    approval = require_separate_founder_approval()
    review = preflight()
    backup = archive_full_site(
        root=LIVE, dest=ARCHIVE, contents=review["live_before_sha256"]
    )
    if backup["files_readback_verified"] != 659 or backup["root_owned_private"] is not True:
        raise ReleaseHold("FRESH_659_FILE_ROOT_BACKUP_NOT_VERIFIED")
    _save_private_once(BACKUP_RECEIPT, {
        **backup, "schema_version": "empire.website.saas_post_v2_backup.v1",
        "founder_approved_receipt_sha256": APPROVAL_SHA256,
        "site_publication_occurred": False,
    })
    if _index(LIVE) != review["live_before_sha256"]:
        raise ReleaseHold("LIVE_659_CHANGED_AFTER_NEW_ROOT_BACKUP")
    expected = review["candidate_sha256"]
    issued: dict[str, Any] = {}

    def verify_post_release() -> None:
        if _index(LIVE) != expected:
            raise ReleaseHold("POST_RELEASE_662_FILE_TREE_DRIFT")
        if _hash(_get("/predictive-revenue")) != review["new_page_hashes"]["predictive-revenue.html"]:
            raise ReleaseHold("PUBLIC_SAAS_GUIDE_HTML_HASH_MISMATCH")
        for route, digest in review["protected_http_sha256"].items():
            if route == "/predictive-revenue":
                continue
            if _hash(_get(route)) != digest:
                raise ReleaseHold("UNRELATED_OR_V2_PUBLIC_ROUTE_CHANGED_" + route)
        for name, digest in review["new_immutable_assets"].items():
            if _hash(_get("/" + name)) != digest:
                raise ReleaseHold("PUBLIC_SAAS_HASHED_ASSET_MISMATCH_" + name)
        original_offers = json.loads(_get("/v1/checkout/commercial/offers"))
        if not isinstance(original_offers, dict):
            raise ReleaseHold("ORIGINAL_COMMERCIAL_OFFER_API_FAILED")
        receipt = {
            "schema_version": "empire.website.saas_guide_post_v2_publication.v1",
            "status": "FOUNDER_APPROVED_SAAS_GUIDE_659_TO_662_PUBLISHED_AND_GET_VERIFIED",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "source_commit": "54601ed54",
            "approved_candidate_sha256": PINNED[CANDIDATE],
            "founder_approval_sha256": APPROVAL_SHA256,
            "approved_scope": approval["scope"],
            "root_backup_sha256": backup["archive_sha256"],
            "verified_original_backup_file_count": 659,
            "public_file_count_after": 662,
            "modified_page_payload_files": 2,
            "added_hashed_assets": 3,
            "preserved_existing_files": 657,
            "client_submissions": 0,
            "crm_writes": False, "outbound_sent": False,
            "payment_activation": False, "model_training": False,
        }
        _save_private_once(RELEASE_RECEIPT, receipt)
        issued.update(receipt)

    try:
        apply_four_pages_and_eight_assets(
            live=LIVE, stage=review["staged_root"],
            baseline=review["original_page_hashes"],
            replacements=review["new_page_hashes"],
            additions=review["new_immutable_assets"],
            final_probe=verify_post_release,
        )
    except Exception:
        # Only a receipt from a failed in-flight attempt can be discarded;
        # the underlying helper handles exact five-file rollback or holds.
        if not issued and RELEASE_RECEIPT.exists():
            RELEASE_RECEIPT.unlink()
        raise
    if not issued:
        raise ReleaseHold("PUBLICATION_RECEIPT_NOT_WRITTEN")
    return issued


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--preflight", action="store_true")
    options.add_argument(EXACT_APPLY, action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.preflight:
            p = preflight()
            print(json.dumps({
                "status": p["status"], "live_file_count": p["original_file_count"],
                "staged_file_count": p["candidate_file_count"],
                "page_payload_replacements": p["existing_page_replacements"],
                "new_assets": p["new_asset_count"],
                "separate_founder_approval_recorded": False,
                "verified_root_backup_exists": False,
                "public_site_mutated": False,
            }, sort_keys=True))
        else:
            if os.geteuid() != 0:
                raise ReleaseHold("ORIGINAL_WEBSITE_ROOT_OWNER_AUTHORITY_REQUIRED")
            require_separate_founder_approval()  # BEFORE even acquiring the release lock
            with _locked_release():  # Original root-owned website lock; no new lock
                print(json.dumps(publish(), sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({
            "status": "SAAS_GUIDE_POST_V2_PUBLICATION_HELD",
            "reason": str(exc), "outbound_sent": False,
            "customer_submission": False, "crm_writes": False,
            "payment_activation": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
