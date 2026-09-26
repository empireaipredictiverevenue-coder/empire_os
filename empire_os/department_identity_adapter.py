"""Targeted decision-maker evidence adapter for department work.

Given one canonical entity_id, find linked prospects and recover a decision
maker using existing first-party/authoritative Empire intelligence. It never
performs outreach and never guesses a person or email.
"""
from __future__ import annotations

import urllib.parse
from typing import Any, Callable, Mapping

from empire_os.identity_recovery import recover_identity


Request = Callable[..., Any]
Recover = Callable[..., Mapping[str, Any]]


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _get(
    request: Request,
    path: str,
    params: Mapping[str, Any],
) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({
        key: str(value)
        for key, value in params.items()
        if value is not None
    })
    rows = request("GET", f"{path}?{query}") or []
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def resolve_entity_decision_maker(
    *,
    entity_id: str,
    request: Request,
    recoverer: Recover = recover_identity,
) -> dict[str, Any]:
    entity_id = _clean(entity_id)
    if not entity_id:
        raise ValueError("entity_id required")

    links = _get(
        request,
        "/rest/v1/prospect_entity_links",
        {
            "select": "prospect_id,entity_id,active,match_score,created_at",
            "entity_id": f"eq.{entity_id}",
            "active": "eq.true",
            "order": "match_score.desc,created_at.desc",
            "limit": 10,
        },
    )
    prospect_ids = [
        _clean(row.get("prospect_id"))
        for row in links
        if _clean(row.get("prospect_id"))
    ]
    if not prospect_ids:
        return {
            "status": "UNAVAILABLE",
            "entity_id": entity_id,
            "reason": "entity_has_no_active_prospect_link",
            "decision_maker": None,
            "evidence_refs": [],
            "outreach_executed": False,
            "execution_authority": "none",
        }

    rows = _get(
        request,
        "/rest/v1/prospects",
        {
            "select": (
                "id,business_name,metro,website,contact_name,"
                "contact_title,contact_source"
            ),
            "id": f"in.({','.join(prospect_ids)})",
            "limit": max(1, len(prospect_ids)),
        },
    )
    by_id = {
        _clean(row.get("id")): row
        for row in rows
        if _clean(row.get("id"))
    }

    for prospect_id in prospect_ids:
        row = by_id.get(prospect_id) or {}
        name = _clean(row.get("contact_name"))
        title = _clean(row.get("contact_title"))
        if name and title:
            return {
                "status": "AVAILABLE",
                "entity_id": entity_id,
                "prospect_id": prospect_id,
                "decision_maker": {
                    "name": name,
                    "title": title,
                    "source": _clean(row.get("contact_source"))
                    or "canonical_prospect",
                },
                "new_identity_persisted": False,
                "evidence_refs": [
                    f"canonical:prospects:{prospect_id}",
                ],
                "outreach_executed": False,
                "execution_authority": "none",
            }

    for prospect_id in prospect_ids:
        row = by_id.get(prospect_id) or {}
        business_name = _clean(row.get("business_name"))
        website = _clean(row.get("website"))
        metro = _clean(row.get("metro"))
        if not business_name or not website:
            continue

        recovered = recoverer(
            business_name=business_name,
            website=website,
            metro=metro,
        )
        identity = (
            recovered.get("identity")
            if isinstance(recovered, Mapping)
            else None
        )
        if not isinstance(identity, Mapping):
            continue

        name = _clean(identity.get("name"))
        title = _clean(identity.get("title"))
        source = _clean(identity.get("source"))
        source_url = _clean(identity.get("source_url"))
        try:
            confidence = float(identity.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0

        first_party = identity.get("first_party") is True
        registry = identity.get("authoritative_registry") is True
        acceptable = bool(
            name
            and title
            and (
                (first_party and confidence >= 0.70)
                or (registry and confidence >= 0.90)
            )
        )
        if not acceptable:
            continue

        params = urllib.parse.urlencode({"id": f"eq.{prospect_id}"})
        request(
            "PATCH",
            f"/rest/v1/prospects?{params}",
            payload={
                "contact_name": name,
                "contact_title": title,
                "contact_source": source
                or "targeted_identity_recovery",
            },
            prefer="return=minimal",
        )
        refs = [f"canonical:prospects:{prospect_id}"]
        if source_url:
            refs.append(source_url)
        return {
            "status": "AVAILABLE",
            "entity_id": entity_id,
            "prospect_id": prospect_id,
            "decision_maker": {
                "name": name,
                "title": title,
                "source": source,
                "source_url": source_url or None,
                "confidence": confidence,
                "first_party": first_party,
                "authoritative_registry": registry,
            },
            "new_identity_persisted": True,
            "evidence_refs": refs,
            "outreach_executed": False,
            "guessed_identity": False,
            "guessed_email": False,
            "execution_authority": "none",
        }

    return {
        "status": "UNAVAILABLE",
        "entity_id": entity_id,
        "reason": "decision_maker_not_resolved_from_bounded_evidence",
        "decision_maker": None,
        "evidence_refs": [
            f"canonical:prospect_entity_links:{entity_id}",
        ],
        "outreach_executed": False,
        "guessed_identity": False,
        "guessed_email": False,
        "execution_authority": "none",
    }
