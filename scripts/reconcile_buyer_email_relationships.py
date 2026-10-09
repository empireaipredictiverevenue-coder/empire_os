#!/usr/bin/env python3
"""Unify buyer discovery and imported Gmail thread metadata, OBSERVE only.

This program CANNOT log into Gmail: the separately connected Gmail connector is
not accessible as a server mailbox. The owned IMAP readiness must be independently
proven before ongoing mailbox collection can be marked automated.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from empire_os.commercial_relationship_registry import (
    RelationshipEvidenceError, reconcile,
)

from empire_os.commercial_social_intent import build_social_intent_review

ROOT = Path("/srv/empire_os")
RELATIVE = Path("runtime/buyer_network_intelligence")
SOURCE_NAME = "gmail_relationship_evidence_latest.json"
OUTPUT_NAME = "commercial_relationship_registry_latest.json"


def _read_private(
    path: Path, *, limit: int = 2_500_000, require_private: bool = False
) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise RelationshipEvidenceError("missing_or_unsafe_relationship_source")
    if require_private and path.stat().st_mode & 0o077:
        raise RelationshipEvidenceError("gmail_source_not_private")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RelationshipEvidenceError("invalid_relationship_json")
    return payload


def build(root: Path = ROOT) -> dict:
    base = Path(root).resolve() / RELATIVE
    src = _read_private(base / SOURCE_NAME, require_private=True)
    queue = _read_private(base / "candidate_queue_latest.json")
    qualification = _read_private(base / "founder_qualification_actions_latest.json")
    prior_path = base / OUTPUT_NAME
    previous = _read_private(prior_path) if prior_path.exists() else {}
    result = reconcile(src, queue, qualification, previous=previous)
    # This is evidence-only enrichment. A missing collector must not block
    # an already valid Gmail/relationship registry.
    try:
        inbox = _read_private(
            root / "runtime/acquisition/signal_inbox.json",
            limit=45_000_000,
        )
        community = _read_private(
            root / "runtime/community_intent/latest.json", limit=2_000_000
        )
        linkedin = _read_private(
            root / "runtime/buyer_acquisition/linkedin_revenue_department_latest.json",
            limit=2_000_000,
        )
        result["social_intent_review"] = build_social_intent_review(
            inbox, result["relationships"],
            community=community, linkedin=linkedin,
        )
    except (OSError, ValueError, TypeError):
        result["social_intent_review"] = {
            "schema_version": "empire.commercial_social_intent_review.v1",
            "status": "UNAVAILABLE",
            "reason": "INTENT_EVIDENCE_MISSING_OR_INVALID",
            "verified_poster_to_company_identity_count": 0,
            "verified_commercial_buying_intent_count": 0,
            "outbound_sent": False,
            "execution_authority": "NONE",
        }
    return result


def atomic_private_write(path: Path, result: dict) -> None:
    if path.parent.is_symlink() or not path.parent.is_dir() or path.is_symlink():
        raise RelationshipEvidenceError("unsafe_relationship_destination")
    data = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
    fd, temporary = tempfile.mkstemp(prefix=".buyer_rel_", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as writer:
            writer.write(data)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        result = build()
        if args.write:
            atomic_private_write(ROOT / RELATIVE / OUTPUT_NAME, result)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        # Never leak contact data or source text through errors.
        print(json.dumps({"status": "BLOCKED", "error_code": type(exc).__name__,
                          "outbound_authorized": False, "execution_authority": "NONE"}))
        return 2
    print(json.dumps({
        "status": "PASS", "written": args.write,
        "relationship_count": result["relationship_count"],
        "linked_gmail_thread_count": result["linked_gmail_thread_count"],
        "gmail_snapshot_fresh": result["gmail_snapshot_fresh"],
        "stage_counts": result["stage_counts"],
        "founder_review_required_count": result['founder_review_required_count'],
        "warm_business_relationship_count": result['warm_business_relationship_count'],
        "founder_action_queue_truncated": result['founder_action_queue_truncated'],
        "new_inbound_relationships_since_prior_snapshot":
            result["new_inbound_relationships_since_prior_snapshot"],
        "automatic_live_gmail_ingest_configured": False,
        "social_intent_review_status": (
            result.get("social_intent_review", {}).get("status", "OBSERVE")
        ),
        "social_intent_linked_company_candidates": (
            result.get("social_intent_review", {}).get(
                "signals_with_potential_company_link_count", 0
            )
        ),
        "social_intent_verified_buyers": 0,
        "outbound_authorized": False, "execution_authority": "NONE",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
