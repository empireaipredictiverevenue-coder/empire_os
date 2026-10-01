"""Prepare fail-closed canonical prospect promotion proposals.

This module does not write to Supabase. It converts REVIEW_READY buyer-scout
holding candidates into deterministic raw prospect proposals while explicitly
keeping buy_signal_score unknown and outreach disabled.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from empire_os.buyer_scout_review_readiness import reliable_business_name
from empire_os.buyer_acquisition_team import commercial_research_profile
from empire_os.buyer_deferred_enrichment import BuyerDeferredEnrichmentQueue
from empire_os.buyer_discovery import looks_like_person_name


OUTPUT = Path("runtime/buyer_acquisition/promotion_plan_latest.json")


def _corridor_market(
    keys: list[str],
) -> tuple[str | None, str | None]:
    parsed: list[tuple[str, str]] = []
    for key in keys:
        parts = str(key or "").split(":")
        if len(parts) != 6 or parts[0:2] != ["corridor", "v1"]:
            continue
        parsed.append((parts[2], parts[3]))
    unique = sorted(set(parsed))
    if len(unique) != 1:
        return None, None
    niche, metro = unique[0]
    return niche.replace("_", " "), metro.replace("_", " ")


def _primary_person(site_evidence: Mapping[str, Any]) -> dict[str, Any] | None:
    people = [
        dict(row)
        for row in (site_evidence.get("first_party_people") or [])
        if isinstance(row, Mapping)
    ]
    if len(people) != 1:
        return None
    person = people[0]
    if not str(person.get("name") or "").strip():
        return None
    return person


def _person_source(person: Mapping[str, Any] | None) -> str | None:
    if not person:
        return None
    for key in ("source", "identity_source"):
        value = str(person.get(key) or "").strip()
        if value:
            return value
    return "first_party_site"




def _source_prospect_ids(row: Mapping[str, Any]) -> list[str]:
    ids: list[str] = []
    for evidence in row.get("query_evidence") or []:
        if not isinstance(evidence, Mapping):
            continue
        prospect_id = str(evidence.get("prospect_id") or "").strip()
        if prospect_id and prospect_id not in ids:
            ids.append(prospect_id)
    return ids


def _target_people(site_evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    people: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in site_evidence.get("first_party_people") or []:
        if not isinstance(raw, Mapping):
            continue
        name = str(raw.get("name") or "").strip()
        title = str(raw.get("title") or "").strip()
        if not name or not title or not looks_like_person_name(name):
            continue
        key = (name.casefold(), title.casefold())
        if key in seen:
            continue
        seen.add(key)
        people.append({
            "name": name,
            "title": title,
            "source": str(
                raw.get("source")
                or raw.get("identity_source")
                or raw.get("source_kind")
                or "first_party_site"
            ).strip(),
            "evidence_url": str(
                raw.get("url") or raw.get("page_url") or ""
            ).strip() or None,
        })
    return people[:8]


def enqueue_priority_enrichment(
    payload: Mapping[str, Any],
    *,
    queue: BuyerDeferredEnrichmentQueue | None = None,
) -> dict[str, Any]:
    queue = queue or BuyerDeferredEnrichmentQueue()
    queued = 0
    skipped = 0
    prospect_ids: list[str] = []
    for proposal in payload.get("proposals") or []:
        if not isinstance(proposal, Mapping):
            continue
        pools = {
            str(value).strip()
            for value in (proposal.get("target_buyer_pools") or [])
            if str(value).strip()
        }
        source_ids = [
            str(value).strip()
            for value in (proposal.get("source_prospect_ids") or [])
            if str(value).strip()
        ]
        if (
            str(proposal.get("buyer_type") or "") != "qualified_end_buyer"
            or "enterprise_and_data_buyers" not in pools
            or not source_ids
        ):
            skipped += 1
            continue

        prospect = proposal.get("proposed_prospect_payload") or {}
        if not isinstance(prospect, Mapping):
            skipped += 1
            continue
        people = [
            dict(row)
            for row in (proposal.get("target_people_for_enrichment") or [])
            if isinstance(row, Mapping)
        ]
        product_codes = [
            str(value).strip()
            for value in (proposal.get("target_product_codes") or [])
            if str(value).strip()
        ]
        emails = [
            str(value).strip()
            for value in (
                proposal.get(
                    "first_party_emails_preserved_for_identity_resolution"
                )
                or []
            )
            if str(value).strip()
        ]
        domain = str(proposal.get("domain") or "").strip().lower()
        enqueued = queue.enqueue({
            "prospect_id": source_ids[0],
            "business_name": str(
                prospect.get("business_name") or ""
            ).strip(),
            "website": str(prospect.get("website") or "").strip(),
            "phone": str(prospect.get("phone") or "").strip(),
            "reason": (
                "no_bound_contact"
                if people or emails
                else "no_decision_maker"
            ),
            "account_key": (
                f"buyer_scout:{domain}" if domain else "buyer_scout:unknown"
            ),
            "wave": "buyer_scout_review_ready",
            "offer_key": (
                product_codes[0]
                if product_codes
                else "predictive_revenue_diagnostic"
            ),
            "target_people": people,
            "target_product_codes": product_codes,
            "priority_score": 92,
            "priority_reason": "buyer_scout_review_ready_enterprise",
        })
        if enqueued:
            queued += 1
            prospect_ids.append(source_ids[0])
        else:
            skipped += 1

    return {
        "queued_count": queued,
        "skipped_count": skipped,
        "prospect_ids": prospect_ids,
        "canonical_promotion_performed": False,
        "outbound_sent": False,
        "execution_authority": "internal_write",
    }


def build_promotion_plan(
    candidates: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    proposals: list[dict[str, Any]] = []
    blocked: dict[str, int] = {}

    for raw in candidates:
        row = dict(raw)
        if row.get("review_state") != "review_ready":
            blocked["not_review_ready"] = blocked.get(
                "not_review_ready", 0
            ) + 1
            continue
        if row.get("reconciliation_state") != "REVIEW_READY":
            blocked["reconciliation_not_ready"] = blocked.get(
                "reconciliation_not_ready", 0
            ) + 1
            continue

        candidate_id = str(row.get("id") or "").strip()
        business_name = str(row.get("business_name") or "").strip()
        website = str(row.get("website") or "").strip()
        if not candidate_id or not business_name or not website:
            blocked["identity_incomplete"] = blocked.get(
                "identity_incomplete", 0
            ) + 1
            continue
        site_for_identity = (
            dict(row.get("site_evidence"))
            if isinstance(row.get("site_evidence"), Mapping)
            else {}
        )
        if not reliable_business_name(
            business_name,
            source=site_for_identity.get("business_name_source"),
        ):
            blocked["business_name_not_verified"] = blocked.get(
                "business_name_not_verified", 0
            ) + 1
            continue

        corridors = [
            str(value)
            for value in (row.get("target_corridor_keys") or [])
            if str(value).strip()
        ]
        niche, metro = _corridor_market(corridors)

        site = (
            dict(row.get("site_evidence"))
            if isinstance(row.get("site_evidence"), Mapping)
            else {}
        )
        phones = [
            str(value).strip()
            for value in (site.get("first_party_phones") or [])
            if str(value).strip()
        ]
        emails = [
            str(value).strip()
            for value in (site.get("first_party_emails") or [])
            if str(value).strip()
        ]
        person = _primary_person(site)

        prospect_payload = {
            "business_name": business_name,
            "website": website,
            "phone": phones[0] if len(phones) == 1 else None,
            "niche": niche,
            "metro": metro,
            "buy_signal_score": None,
            "status": "new",
            "notes": (
                f"buyer_scout_candidate:{candidate_id}; "
                "research_evidence_only"
            ),
            "contact_name": (
                str(person.get("name") or "").strip()
                if person else None
            ),
            "contact_title": (
                str(person.get("title") or "").strip()
                if person else None
            ),
            "contact_source": _person_source(person),
        }

        proposals.append({
            "candidate_id": candidate_id,
            "source_prospect_ids": _source_prospect_ids(row),
            "target_people_for_enrichment": _target_people(site),
            "domain": row.get("domain"),
            "buyer_type": row.get("buyer_type"),
            "commercial_research_profile": commercial_research_profile(
                row.get("query_evidence") or []
            ),
            "target_buyer_pools": list(
                row.get("target_buyer_pools") or []
            ),
            "target_product_codes": list(
                row.get("target_product_codes") or []
            ),
            "target_corridor_keys": corridors,
            "proposed_prospect_payload": prospect_payload,
            "first_party_emails_preserved_for_identity_resolution": emails,
            "buy_signal_score_intentionally_unknown": True,
            "qualification_created": False,
            "buyer_created": False,
            "outreach_authorized": False,
        })

    proposals.sort(
        key=lambda row: (
            str(row.get("domain") or ""),
            str(row.get("candidate_id") or ""),
        )
    )

    return {
        "schema_version": "empire.buyer_scout_promotion_plan.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "proposal_count": len(proposals),
        "blocked_count": sum(blocked.values()),
        "blocked_reason_counts": dict(sorted(blocked.items())),
        "proposals": proposals,
        "database_write_performed": False,
        "canonical_promotion_performed": False,
        "buy_signal_score_policy": "UNKNOWN_NULL",
        "qualification_created": False,
        "buyer_created": False,
        "outbound_sent": False,
        "terms_accepted": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def write_promotion_plan(
    repo_root: str | Path,
    payload: Mapping[str, Any],
) -> Path:
    root = Path(repo_root).resolve()
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path
