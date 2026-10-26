"""Reconcile the already-built CTA route against the newer owned 700-file site.

Offline only. Does not revise the old founder approval, modify source, or
grant ASTRA authority. The new 708-file inventory requires separate approval.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import shutil
import os

from empire_os.earned_media_saas_rebased_release import (
    ReleaseHeld, REPLACE, LINK, OLD_LINK, read_index, index_digest,
    route_static_references,
)

SCHEMA = "empire.website.earned_media_saas700_source_reconciliation.v1"
LIVE = Path("/srv/empire_os/apps/empire-public-site/out")
PREVIOUS = Path("/home/ubuntu/empire_releases/earned_media_saas_union_20261026/rebased_candidate")
OUTPUT_ROOT = Path("/home/ubuntu/empire_releases/earned_media_saas_union_20261026")
DESTINATION = OUTPUT_ROOT / "rebased_from_700_candidate"
RECEIPT = OUTPUT_ROOT / "rebased_from_700_receipt.json"
LIVE_700_PIN = "f6cb9f0f541b041ebd5ca397c3c87268d89a70e086e26a16c1d2534dc13315df"
OLD_670_PIN = "2d37c7537329914fcecf531b34ff6fbeec42413da7dd42f5d5e4174f1411742b"
LATEST_COMMERCIAL_PIN = "304605ef015372b24ccbf3274313476a3aa7ec06c32c10337c76f860f609d190"


def validate_inputs() -> tuple[dict[str, str], dict[str, str], list[str]]:
    if LIVE.is_symlink() or PREVIOUS.is_symlink():
        raise ReleaseHeld("UNTRUSTED_SITE_OR_PREVIOUS_CANDIDATE_SYMLINK")
    before = read_index(LIVE)
    prev = read_index(PREVIOUS)
    if (len(before) != 700 or index_digest(before) != LIVE_700_PIN
            or len(prev) != 670 or index_digest(prev) != OLD_670_PIN
            or before.get("commercial.html") != LATEST_COMMERCIAL_PIN):
        raise ReleaseHeld("EXACT_NEWER_ORIGINAL_SITE_OR_APPROVED_OLD_CANDIDATE_CHANGED")
    html = (PREVIOUS / "predictive-revenue.html").read_text("utf8")
    rsc = (PREVIOUS / "predictive-revenue.txt").read_text("utf8")
    if (html.count(LINK) != 1 or OLD_LINK in html
            or 'id="deployment-request"' not in html
            or 'id="free-evidence-sample"' not in html):
        raise ReleaseHeld("CTA_OR_CONSENTED_SAAS_FUNNEL_CHANGED")
    refs = route_static_references(html, rsc)
    additions = sorted(path for path in refs if path not in before)
    if len(additions) != 8:
        raise ReleaseHeld("EXPECTED_EIGHT_UNIQUE_STATIC_ASSETS_NOT_AVAILABLE")
    if any(path not in prev for path in refs):
        raise ReleaseHeld("STAGED_SAAS_REFERENCED_ASSET_MISSING")
    if any(before[path] != prev[path] for path in refs if path in before):
        raise ReleaseHeld("STATIC_ASSET_COLLISION_WITH_CURRENT_LIVE_SITE")
    return before, prev, additions


def verify() -> dict:
    if RECEIPT.is_symlink() or not RECEIPT.is_file():
        raise ReleaseHeld("PRIVATE_700_REBASE_RECEIPT_MISSING")
    source, prev, additions = validate_inputs()
    final = read_index(DESTINATION)
    doc = json.loads(RECEIPT.read_text())
    if (not isinstance(doc, dict) or doc.get("schema_version") != SCHEMA
            or doc.get("site_publication_authorized") is not False
            or doc.get("root_backup_verified") is not False
            or len(final) != 708 or
            doc.get("candidate_inventory_sha256") != index_digest(final)):
        raise ReleaseHeld("REBASED_708_RECEIPT_OR_INVENTORY_INVALID")
    changed = {k for k in source if source[k] != final.get(k)}
    added = sorted(set(final)-set(source))
    if changed != REPLACE or added != additions or set(source)-set(final):
        raise ReleaseHeld("REBASE_708_CHANGED_UNRELATED_LIVE_FILE")
    if any(final[k] != source[k] for k in source if k not in REPLACE):
        raise ReleaseHeld("RECENT_SEO_OWNER_FILES_NOT_PRESERVED")
    if (final["predictive-revenue.html"] != prev["predictive-revenue.html"]
            or final["predictive-revenue.txt"] != prev["predictive-revenue.txt"]
            or any(final[k] != prev[k] for k in additions)):
        raise ReleaseHeld("ORIGINAL_SAAS_PAYLOAD_CHANGED_DURING_REBASE")
    return {
        "schema_version": SCHEMA,
        "status": "PRIVATE_708_FILE_REBASE_INTEGRITY_PASS_REVIEW_ONLY",
        "original_live_file_count": len(source),
        "new_candidate_file_count": len(final),
        "replaced_existing_files": sorted(REPLACE),
        "new_static_assets_count": len(additions),
        "other_original_files_preserved_exactly": len(source) - len(REPLACE),
        "original_index_sha256": index_digest(source),
        "candidate_index_sha256": index_digest(final),
        "founder_previous_670_approval_applies_to_new_708": False,
        "website_owner_independent_release_signoff": False,
        "root_backup_verified": False,
        "site_publication_authorized": False,
        "site_publication_performed": False,
        "actual_customer_enquiry_verified": False,
        "actual_revenue_verified": False,
    }


def prepare() -> dict:
    if (DESTINATION.exists() or DESTINATION.is_symlink()
            or RECEIPT.exists() or RECEIPT.is_symlink()):
        raise ReleaseHeld("REBASED_708_CANDIDATE_ALREADY_EXISTS_NO_REPLACE")
    source, prev, additions = validate_inputs()
    scratch = OUTPUT_ROOT / "rebased_from_700_candidate.incomplete"
    if scratch.exists() or scratch.is_symlink():
        raise ReleaseHeld("UNTRUSTED_EXISTING_TEMP_REBASE")
    try:
        shutil.copytree(LIVE, scratch, symlinks=False)
        for item in sorted(REPLACE | set(additions)):
            src = PREVIOUS / item
            dst = scratch / item
            if src.is_symlink() or not src.is_file() or dst.is_symlink():
                raise ReleaseHeld("UNSAFE_REBASED_FILE_PATH")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        final = read_index(scratch)
        if (len(final) != 708 or
                {k for k in source if source[k] != final.get(k)} != REPLACE or
                sorted(set(final)-set(source)) != additions or
                read_index(LIVE) != source or read_index(PREVIOUS) != prev):
            raise ReleaseHeld("SOURCE_CHANGED_OR_RELEASE_SCOPE_INVALID")
        payload = {
            "schema_version": SCHEMA,
            "status": "OFFLINE_708_SAAS_ON_700_LIVE_OWNER_BASELINE_PENDING_REVIEW",
            "source_live_inventory_sha256": index_digest(source),
            "previous_670_candidate_inventory_sha256": index_digest(prev),
            "candidate_inventory_sha256": index_digest(final),
            "current_live_file_count": len(source),
            "candidate_file_count": len(final),
            "added_files": additions,
            "replaced_files": sorted(REPLACE),
            "preserved_original_file_count": len(source)-len(REPLACE),
            "preserved_recent_commercial_sha256": final["commercial.html"],
            "old_founder_approval_does_not_cover_new_candidate": True,
            "new_founder_approval_verified": False,
            "astra_owner_authority_verified": False,
            "root_backup_verified": False,
            "site_publication_authorized": False,
            "site_publication_performed": False,
            "db_writes": False,
            "new_buyer_enquiry_submitted": False,
            "payment_or_outbound": False,
        }
        os.replace(scratch, DESTINATION)
        with RECEIPT.open("x", encoding="utf8") as f:
            json.dump(payload,f,sort_keys=True,indent=2)
            f.write("\n")
    except Exception:
        if scratch.exists() and scratch.is_dir():
            shutil.rmtree(scratch)
        raise
    return verify()
