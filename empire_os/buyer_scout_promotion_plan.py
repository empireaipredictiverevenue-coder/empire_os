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
            "contact_email": emails[0] if len(emails) == 1 else None,
            "contact_source": (
                "first_party_site"
                if person else None
            ),
        }

        proposals.append({
            "candidate_id": candidate_id,
            "domain": row.get("domain"),
            "buyer_type": row.get("buyer_type"),
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
