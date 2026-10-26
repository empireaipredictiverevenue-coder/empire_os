"""Record one explicitly approved immutable SaaS708 *review* receipt.

Never confers independent ASTRA owner approval or publication authority.
Only accepts the exact 700-live to 708-private candidate validated in Stage 13.
The file is exclusively created at the existing EmpireOS approval directory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path

from empire_os.earned_media_saas700_reconciliation import (
    LIVE, DESTINATION, RECEIPT, verify,
)
from empire_os.earned_media_saas_rebased_release import read_index, index_digest

SCHEMA = "empire.website.saas708_founder_exact_approval.v1"
DECISION = "FOUNDER_APPROVES_EXACT_REVISED_700_TO_708_PAYLOAD_FOR_ASTRA_REVIEW"
ORIGINAL_OWNER = "EXISTING_ASTRA_WEBSITE_RELEASE_OWNER"
APPROVAL_TEXT = "yes i approve"
SOURCE = "FOUNDER_EXPLICIT_REPLY_TO_EXACT_708_FILE_REVIEW_SCOPE_20261026"
PINNED_SOURCE_SHA = "f6cb9f0f541b041ebd5ca397c3c87268d89a70e086e26a16c1d2534dc13315df"
PINNED_CANDIDATE_SHA = "62b62b184d5597ffc806a825723c4638f2953702c823561233d30058e398dab2"
FILE = Path(
    "/srv/empire_os/docs/website/release_candidates/"
    "SAAS708_FOUNDER_EXACT_APPROVAL_20261026.json"
)


def build_receipt(*, recorded_at_utc: str) -> dict:
    # Recheck all 700 + 708 current bytes. The candidate itself is unmodified.
    status = verify()
    old = read_index(LIVE)
    new = read_index(DESTINATION)
    if (len(old) != 700 or len(new) != 708
            or index_digest(old) != PINNED_SOURCE_SHA
            or index_digest(new) != PINNED_CANDIDATE_SHA
            or status["original_index_sha256"] != PINNED_SOURCE_SHA
            or status["candidate_index_sha256"] != PINNED_CANDIDATE_SHA):
        raise ValueError("FOUNDER_EXACT_708_CANDIDATE_NO_LONGER_MATCHES_APPROVED_BYTES")
    manifest = json.loads(RECEIPT.read_text("utf-8"))
    if (manifest.get("source_live_inventory_sha256") != PINNED_SOURCE_SHA
            or manifest.get("candidate_inventory_sha256") != PINNED_CANDIDATE_SHA
            or manifest.get("new_founder_approval_verified") is not False
            or manifest.get("site_publication_authorized") is not False
            or len(manifest.get("added_files", [])) != 8):
        raise ValueError("STAGED_708_INTEGRITY_OR_APPROVAL_CONTRACT_CHANGED")
    return {
        "schema_version": SCHEMA,
        "decision": DECISION,
        "founder_quote": APPROVAL_TEXT,
        "founder_approval_source": SOURCE,
        "recorded_at_utc": recorded_at_utc,
        "scope": "EXACT_708_FILE_CANDIDATE_FOR_ASTRA_FINAL_REVIEW_ONLY",
        "original_website_release_owner": ORIGINAL_OWNER,
        "live_file_count": 700,
        "candidate_file_count": 708,
        "source_live_inventory_sha256": PINNED_SOURCE_SHA,
        "candidate_inventory_sha256": PINNED_CANDIDATE_SHA,
        "replaced_existing_files": ["predictive-revenue.html", "predictive-revenue.txt"],
        "added_immutable_assets": 8,
        "commercial_page_preserved": True,
        "older_670_approval_not_transferred": True,
        "immediate_publication_authorized": False,
        "website_owner_independent_signoff_verified": False,
        "root_protected_rollback_verified": False,
        "publication_performed": False,
        "crm_writes_authorized": False,
        "outbound_or_payment_authorized": False,
        "genuine_buyer_enquiry_verified": False,
        "actual_revenue_verified": False,
    }


def record(*, target: Path = FILE) -> dict:
    if target.is_symlink() or target.exists():
        raise FileExistsError("EXISTING_FOUNDER_APPROVAL_RECEIPT_NO_OVERWRITE")
    if target.parent.is_symlink() or not target.parent.is_dir():
        raise ValueError("ORIGINAL_APPROVAL_DESTINATION_MISSING")
    item = build_receipt(recorded_at_utc=datetime.now(timezone.utc).isoformat())
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(item, f, sort_keys=True, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    return {
        "status": "FOUNDER_EXACT_708_FINAL_REVIEW_APPROVAL_RECORDED",
        "receipt_path": str(target),
        "receipt_sha256": sha256(target.read_bytes()).hexdigest(),
        "candidate_inventory_sha256": PINNED_CANDIDATE_SHA,
        "original_astra_owner_approved": False,
        "root_rollback_verified": False,
        "publication_performed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record-explicit-708-founder-review-approval", required=True,
                        action="store_true")
    parser.parse_args(argv)
    print(json.dumps(record(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
