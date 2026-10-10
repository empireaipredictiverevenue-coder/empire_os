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
    attach_partner_inbound_requirements,
)

from empire_os.commercial_social_intent import build_social_intent_review
from empire_os.public_intent_affiliation import load_evidence as load_public_affiliation
from empire_os.buyer_pilot_assets import (
    build_partner_landing_review, render_partner_landing_review_html,
)
from hashlib import sha256

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
    # This evidence feed is optional until a *genuine* buyer response has
    # been examined through connected Gmail. A malformed file fails closed:
    # never discard it and silently claim that no partner terms arrived.
    terms = base / "partner_inbound_requirements_latest.json"
    if terms.exists():
        if terms.stat().st_mode & 0o077:
            raise RelationshipEvidenceError("inbound_requirement_evidence_not_private")
        reviewed = _read_private(terms, limit=18000, require_private=True)
    else:
        reviewed = {
            "schema_version": "empire.partner_inbound_requirements.v1",
            "origin": "connected_gmail_explicit_review",
            "observations": [],
        }
    attach_partner_inbound_requirements(result, reviewed)
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
        previous_social = previous.get("social_intent_review") or {}
        previous_research = previous_social.get("company_identity_research") or {}
        public_affiliation = load_public_affiliation(
            base / "intent_company_identity_evidence_latest.json"
        )
        result["social_intent_review"] = build_social_intent_review(
            inbox, result["relationships"],
            community=community, linkedin=linkedin,
            previous_research_tasks=previous_research.get(
                "identity_review_tasks", []
            ),
            public_affiliation_evidence=public_affiliation,
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
    # The 15-minute community cycle owns source-learning updates. The
    # 30-minute buyer scout only reads the same operational history and
    # surfaces the next safe research task beside founder relationships.
    try:
        from empire_os.community_intent_learning import SCHEMA, load_history
        learning_path = root / "runtime/community_intent/source_learning_latest.json"
        learning = _read_private(learning_path, limit=2_500_000)
        episodes = load_history(learning_path)
        if learning.get("schema_version") != SCHEMA:
            raise ValueError("unexpected_icp_learning_schema")
        result["icp_research_learning"] = {
            "status": "OBSERVE",
            "schema_version": SCHEMA,
            "generated_at": learning.get("generated_at"),
            "episode_count": len(episodes),
            "next_research_task": learning.get("next_research_task"),
            "next_research_source": learning.get("next_research_source"),
            "source_results": learning.get("source_results", [])[:35],
            "verified_buyer_conversions": 0,
            "recognized_revenue_cents": None,
            "outbound_authorized": False,
            "execution_authority": "NONE",
        }
    except (OSError, ValueError, TypeError):
        result["icp_research_learning"] = {
            "status": "UNAVAILABLE",
            "reason": "LEARNING_SNAPSHOT_MISSING_OR_INVALID",
            "verified_buyer_conversions": 0,
            "outbound_authorized": False,
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


def _atomic_private_bytes(path: Path, payload: bytes) -> None:
    if (path.is_symlink() or path.parent.is_symlink()
            or not path.parent.is_dir()):
        raise RelationshipEvidenceError("unsafe_private_preview_destination")
    fd, temporary = tempfile.mkstemp(prefix=".buyer_private_preview_", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as writer:
            writer.write(payload)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def materialize_partner_private_reviews(root: Path, registry: dict) -> dict:
    """Generate bounded static review files; no public web route or telephony.

    The existing buyer scout already calls this reconciler. The preview uses
    self-owned artwork, never partner-specific trading/approval assumptions.
    """
    pilots = registry.get("partner_pilot_readiness_queue")
    if not isinstance(pilots, list) or len(pilots) > 3:
        raise RelationshipEvidenceError("unexpected_partner_pilot_count")
    base = root / RELATIVE / "partner_private_reviews"
    if base.is_symlink():
        raise RelationshipEvidenceError("unsafe_private_preview_directory")
    artifact_data = []
    for pilot in pilots:
        review = build_partner_landing_review(pilot)
        key = review["entity_key"]
        html = render_partner_landing_review_html(review).encode("utf-8")
        packet = (json.dumps(review, indent=2, sort_keys=True) + "\n").encode()
        directory = base / key
        if directory.is_symlink():
            raise RelationshipEvidenceError("unsafe_partner_preview_directory")
        art = review.get("self_owned_illustration")
        media = None
        if art is not None:
            src = root / "templates/lead_smart/roofing/roofing-hero.webp"
            if src.is_symlink() or not src.is_file() or src.stat().st_size > 2_000_000:
                raise RelationshipEvidenceError("self_owned_review_media_not_available")
            media = src.read_bytes()
            if not media.startswith(b"RIFF") or media[8:12] != b"WEBP":
                raise RelationshipEvidenceError("unexpected_private_preview_media")
        artifact_data.append((key, directory, html, packet, media))
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    if base.stat().st_mode & 0o077:
        raise RelationshipEvidenceError("private_preview_base_permissions_unsafe")
    out = []
    for key, directory, html, packet, media in artifact_data:
        directory.mkdir(mode=0o700, exist_ok=True)
        if directory.stat().st_mode & 0o077:
            raise RelationshipEvidenceError("private_preview_partner_permissions_unsafe")
        _atomic_private_bytes(directory / "index.html", html)
        _atomic_private_bytes(directory / "review.json", packet)
        if media is not None:
            _atomic_private_bytes(directory / "roofing-hero.webp", media)
        out.append({
            "entity_key": key,
            "relative_private_html_path": str(
                (directory / "index.html").relative_to(root)
            ),
            "html_sha256": sha256(html).hexdigest(),
            "rendered_without_live_links": True,
            "source_page_or_route_deployed": False,
            "outbound_authorized": False,
        })
    return {
        "status": "PRIVATE_REVIEW_ONLY",
        "review_file_count": len(out),
        "rendered_at_runtime_only": True,
        "no_public_web_route_created": True,
        "call_routing_authorized": False,
        "execution_authority": "NONE",
        "artifacts": out,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        result = build()
        if args.write:
            result["partner_private_landing_reviews"] = (
                materialize_partner_private_reviews(ROOT, result)
            )
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
        "icp_learning_status": (
            result.get("icp_research_learning", {}).get("status", "UNAVAILABLE")
        ),
        "icp_next_research_task": (
            result.get("icp_research_learning", {}).get("next_research_task")
        ),
        "outbound_authorized": False, "execution_authority": "NONE",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
