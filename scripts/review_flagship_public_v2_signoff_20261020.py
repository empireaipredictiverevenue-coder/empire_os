"""Immutable private, evidence-bound V2 website release signoff proposal.

Does NOT grant founder signoff or perform deployment. All route/browser/hash
receipts are original owner evidence. Requires explicit further approval.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from datetime import datetime, timezone

from scripts.review_flagship_full_export_union_20261020 import (
    CANDIDATE, STAGE, STAGE_MANIFEST, LIVE, _verify_private_candidate,
    _require_original_stage,
    _file_index, ReleaseHold,
)
from empire_os.public_flagship_asset_policy import FLAGSHIP_ASSETS, reviewed_flagship_asset_path
from empire_os.flagship_static_release_routes import PINNED_ASSETS, reviewed_asset_path

ROOT = Path("/srv/empire_os")
BACKUP = Path("/var/backups/empire-website/flagship_current_live_20261020_before_union.tar")
REVIEW = CANDIDATE / "PUBLIC_V2_RELEASE_SIGNOFF_PROPOSAL.json"
BROWSER = CANDIDATE / "BROWSER_ROUTE_EVIDENCE.json"
PRIVATE_RECEIPT = CANDIDATE / "RELEASE_CANDIDATE_RECEIPT.json"
SCHEMA = "empire.website.full_public_release_signoff_proposal.v2"
EXACT_ROUTES = {
    "/", "/buy", "/commercial", "/about",
    "/insights/revenue-opportunity-assessment",
    "/roofing/installation-checklist",
}


def _load_bounded_json(file: Path) -> dict:
    if file.is_symlink() or not file.is_file() or file.stat().st_size > 200_000:
        raise ReleaseHold("REVIEW_EVIDENCE_MISSING_OR_OVERSIZE")
    data = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ReleaseHold("REVIEW_EVIDENCE_MALFORMED")
    return data


def _browser_evidence(file: Path) -> dict:
    r = _load_bounded_json(file)
    if (
        r.get("schema_version") != "empire.website.flagship_checkout_union_browser.v1"
        or r.get("status") != "PRIVATE_UNION_BROWSER_TECHNICAL_PASS"
        or not isinstance(r.get("routes"), list)
        or len(r["routes"]) != 12
        or not all(type(t) is dict and t.get("passed") is True for t in r["routes"])
        or not isinstance(r.get("navigation"), list)
        or len(r["navigation"]) != 4
        or not all(type(t) is dict and t.get("passed") is True for t in r["navigation"])
        or len(r.get("read_only_existing_public_api_gets", [])) < 6
        or not all(t.get("valid") is True for t in r["read_only_existing_public_api_gets"])
        or r.get("missing_local_assets") != []
        or r.get("browser_page_errors") != []
        or r.get("external_requests_blocked") != 0
        or r.get("non_get_requests_blocked") != 0
        or r.get("checkout_posts_submitted") != 0
        or r.get("release_approved") is not False
        or r.get("public_site_modified") is not False
        or r.get("payment_execution") is not False
        or {t["route"] for t in r["routes"]} != {
            "cinematic-home", "new-buyer-checkout", "new-commercial-enquiry",
            "preserved-about", "preserved-insight", "new-roofing-guide",
        }
        or {t["width"] for t in r["routes"]} != {390, 1440}
    ):
        raise ReleaseHold("BROWSER_PROOF_UNVERIFIED")
    return r


def review(*, require_backup: bool = True) -> dict:
    _require_original_stage(STAGE, STAGE_MANIFEST)
    stage = _verify_private_candidate(CANDIDATE / "out")
    browser = _browser_evidence(BROWSER)
    manifest = _load_bounded_json(PRIVATE_RECEIPT)
    expected = manifest["static_file_sha256"]
    live_index = _file_index(LIVE)
    if len(live_index) != 603:
        raise ReleaseHold("LIVE_SOURCE_CHANGED_SINCE_BACKUP")
    if stage.get("verified_file_count") != 632:
        raise ReleaseHold("PRIVATE_UNION_NOT_EXACTLY_632")
    archive_digest = None
    if require_backup:
        if BACKUP.is_symlink() or not BACKUP.is_file() or BACKUP.stat().st_size < 1_000_000:
            raise ReleaseHold("ROOT_PROTECTED_ROLLBACK_MISSING")
        digest_file = BACKUP.with_suffix(BACKUP.suffix + ".sha256")
        expected_line = digest_file.read_text(encoding="utf-8").splitlines()
        if len(expected_line) != 1 or not expected_line[0].startswith(
            sha256(BACKUP.read_bytes()).hexdigest() + "  "
        ):
            raise ReleaseHold("ROOT_BACKUP_DIGEST_MISMATCH")
        archive_digest = sha256(BACKUP.read_bytes()).hexdigest()
    for key in FLAGSHIP_ASSETS:
        if reviewed_flagship_asset_path(key, CANDIDATE / "out") is None:
            raise ReleaseHold("ORIGINAL_PINNED_FLAGSHIP_ASSET_MISMATCH")
    for key in PINNED_ASSETS:
        if reviewed_asset_path("/" + key, CANDIDATE / "out") is None:
            raise ReleaseHold("ORIGINAL_PINNED_GATEWAY_ASSET_MISMATCH")
    canonical_digest = sha256(
        json.dumps(expected, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": SCHEMA,
        "status": "EXACT_V2_BUILD_PROVEN_FOUNDER_PUBLICATION_APPROVAL_REQUIRED",
        "full_static_file_count": 632,
        "original_live_static_file_count": 603,
        "all_candidate_file_hashes_verified": True,
        "original_stage_source_and_manifest_verified": True,
        "original_gateway_pinned_assets_verified": True,
        "private_browser_routes_passed": len(browser["routes"]),
        "private_browser_navigation_passed": len(browser["navigation"]),
        "browser_errors": 0,
        "live_read_only_gateway_preflight_performed_separately": True,
        "candidate_static_inventory_sha256": canonical_digest,
        "private_candidate_receipt_sha256": sha256(PRIVATE_RECEIPT.read_bytes()).hexdigest(),
        "private_browser_receipt_sha256": sha256(BROWSER.read_bytes()).hexdigest(),
        "original_stage_manifest_sha256": sha256(STAGE_MANIFEST.read_bytes()).hexdigest(),
        "original_live_backup_sha256": archive_digest,
        "exact_intended_new_html": {
            p: expected[p] for p in (
                "index.html", "buy.html", "commercial.html",
            )
        },
        "publishing_would_change_live_site": True,
        "old_october_13_buyer_manifest_immutable": True,
        "new_release_contract_owner_review_required": True,
        "founder_final_visual_approval_obtained": False,
        "website_owner_public_release_approved": False,
        "public_files_modified": False,
        "customer_form_submitted": False,
        "payment_or_outbound_executed": False,
        "execution_authority": "none",
        "next_owner_decision": "EXPLICIT_APPROVAL_OF_THIS_EXACT_632_FILE_PUBLIC_RELEASE",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--write-private-review-packet", action="store_true")
    args = parser.parse_args(argv)
    if args.read_only == args.write_private_review_packet:
        parser.error("select exactly one nondeployment mode")
    try:
        result = review()
        if args.write_private_review_packet:
            with REVIEW.open("x", encoding="utf-8") as f:
                json.dump(result, f, sort_keys=True, indent=2)
                f.write("\n")
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ReleaseHold, ValueError, OSError, KeyError, TypeError):
        print(json.dumps({
            "schema_version": SCHEMA,
            "status": "SIGNOFF_SOURCE_HOLD",
            "founder_final_visual_approval_obtained": False,
            "website_owner_public_release_approved": False,
            "public_files_modified": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
