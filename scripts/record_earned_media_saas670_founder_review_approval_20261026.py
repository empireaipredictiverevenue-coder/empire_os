"""Record founder's explicit review approval for one immutable SaaS670 packet.

Usage only after founder's direct, explicit approval in this conversation.
Creates a single *review-only* receipt at the original owner's expected path.
Does not approve publication, sign for ASTRA, or modify any public site file.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path

from empire_os.earned_media_saas670_owner_preflight import (
    FOUNDER, FOUNDER_SCHEMA, LIVE, CANDIDATE,
    PINNED_SOURCE_INDEX_SHA, PINNED_CANDIDATE_INDEX_SHA,
)
from empire_os.earned_media_saas_rebased_release import read_index, index_digest

DECISION = "FOUNDER_APPROVES_EXACT_REVISED_662_TO_670_PAYLOAD_FOR_ASTRA_REVIEW"
APPROVAL_QUOTE = "yes i approve"
APPROVAL_SOURCE = "USER_EXPLICIT_FOUNDER_APPROVAL_IN_CURRENT_CHAT_20261026"
APPROVED_CANDIDATE_SHA256 = (
    "2d37c7537329914fcecf531b34ff6fbeec42413da7dd42f5d5e4174f1411742b"
)


def verified_approval_payload(*, approved_at_utc: str) -> dict:
    """Pin the exact old and new site indexes BEFORE any approval recording."""
    source = read_index(LIVE)
    proposed = read_index(CANDIDATE)
    if (len(source) != 662 or len(proposed) != 670
            or index_digest(source) != PINNED_SOURCE_INDEX_SHA
            or index_digest(proposed) != APPROVED_CANDIDATE_SHA256
            or APPROVED_CANDIDATE_SHA256 != PINNED_CANDIDATE_INDEX_SHA
            or source.get("predictive-revenue.html") !=
            "7144c99317d5a38d2f44e94bdd992bb26a6544a1626a0cab8973d25b9e0c9e9a"):
        raise ValueError("EXACT_USER_APPROVED_CANDIDATE_OR_CURRENT_SITE_CHANGED")
    return {
        "schema_version": FOUNDER_SCHEMA,
        "decision": DECISION,
        "founder_direct_quote": APPROVAL_QUOTE,
        "founder_approval_source": APPROVAL_SOURCE,
        "recorded_at_utc": approved_at_utc,
        "approval_scope": "ASTRA_ORIGINAL_WEBSITE_OWNER_REVIEW_OF_THIS_EXACT_CANDIDATE_ONLY",
        "original_website_release_owner": "EXISTING_ASTRA_WEBSITE_RELEASE_OWNER",
        "source_live_file_count": 662,
        "candidate_file_count": 670,
        "source_live_inventory_sha256": PINNED_SOURCE_INDEX_SHA,
        "candidate_inventory_sha256": PINNED_CANDIDATE_INDEX_SHA,
        "replaced_existing_files": [
            "predictive-revenue.html", "predictive-revenue.txt"
        ],
        "added_new_hashed_static_assets": 8,
        "previous_672_file_approval_reused": False,
        "publication_performed": False,
        "immediate_publication_authorized": False,
        "independent_astra_owner_approval_verified": False,
        "root_protected_rollback_verified": False,
        "database_writes_authorized": False,
        "buyer_data_created": False,
        "outbound_or_payment_authorized": False,
        "actual_revenue_verified": False,
    }


def record_founder_approval(*, target: Path = FOUNDER) -> dict:
    """Create exactly one receipt; never replace a different agent's receipt."""
    if target.is_symlink() or target.exists():
        raise FileExistsError("ORIGINAL_FOUNDER_APPROVAL_RECEIPT_ALREADY_EXISTS_NO_OVERWRITE")
    receipt = verified_approval_payload(
        approved_at_utc=datetime.now(timezone.utc).isoformat()
    )
    if not target.parent.is_dir() or target.parent.is_symlink():
        raise ValueError("ORIGINAL_WEBSITE_OWNER_APPROVAL_DIRECTORY_NOT_READY")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(receipt, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        # Leave any partial receipt visibly invalid; never silently rewrite.
        raise
    return {
        "status": "EXACT_REVISED_670_FOUNDER_REVIEW_APPROVAL_RECORDED",
        "receipt_path": str(target),
        "receipt_sha256": sha256(target.read_bytes()).hexdigest(),
        "founder_review_approved": True,
        "candidate_inventory_sha256": PINNED_CANDIDATE_INDEX_SHA,
        "astra_approval_verified": False,
        "root_rollback_verified": False,
        "public_site_published": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--record-explicit-founder-review-approval-20261026",
        required=True, action="store_true",
    )
    parser.parse_args(argv)
    print(json.dumps(record_founder_approval(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
