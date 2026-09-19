"""Canonical read-only Lead Intelligence projection for EmpireOS."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from uuid import UUID


class LeadIntelligenceError(RuntimeError):
    """Canonical lead-intelligence state could not be read safely."""


Reader = Callable[[str, dict[str, str]], Any]


@dataclass(frozen=True)
class LeadIntelligenceLimits:
    signals: int = 50
    facts: int = 100
    scores: int = 30
    contact_points: int = 30
    employments: int = 30

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if not 1 <= int(value) <= 500:
                raise ValueError(
                    f"{name} limit must be between 1 and 500"
                )


def _uuid(value: str, *, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise LeadIntelligenceError(f"invalid {field}") from exc


def _rows(
    reader: Reader,
    path: str,
    params: dict[str, str],
    *,
    label: str,
) -> list[dict[str, Any]]:
    raw = reader(path, params)
    if not isinstance(raw, list):
        raise LeadIntelligenceError(
            f"{label} reader returned invalid payload"
        )
    if any(not isinstance(row, dict) for row in raw):
        raise LeadIntelligenceError(
            f"{label} reader returned invalid row"
        )
    return list(raw)


def _single(
    reader: Reader,
    path: str,
    params: dict[str, str],
    *,
    label: str,
    required: bool = False,
) -> dict[str, Any] | None:
    rows = _rows(reader, path, params, label=label)
    if len(rows) > 1:
        raise LeadIntelligenceError(
            f"{label} returned multiple rows"
        )
    if not rows:
        if required:
            raise LeadIntelligenceError(f"{label} not found")
        return None
    return rows[0]


def fetch_prospect(
    reader: Reader,
    prospect_id: str,
) -> dict[str, Any]:
    pid = _uuid(prospect_id, field="prospect_id")
    row = _single(
        reader,
        "/rest/v1/prospects",
        {
            "select": (
                "id,created_at,business_name,niche,metro,phone,website,"
                "address,rating,review_count,buy_signal_score,runs_ads,"
                "status,notes,contacted_at,contact_name,contact_title,"
                "contact_source,contacted_status"
            ),
            "id": f"eq.{pid}",
            "limit": "1",
        },
        label="prospect",
        required=True,
    )
    assert row is not None
    return row


def fetch_identity_link(
    reader: Reader,
    prospect_id: str,
) -> dict[str, Any] | None:
    pid = _uuid(prospect_id, field="prospect_id")
    return _single(
        reader,
        "/rest/v1/prospect_entity_links",
        {
            "select": (
                "prospect_id,entity_id,match_method,match_score,"
                "evidence,active,created_at"
            ),
            "prospect_id": f"eq.{pid}",
            "active": "eq.true",
            "limit": "2",
        },
        label="active prospect identity link",
    )


def fetch_business_entity(
    reader: Reader,
    entity_id: str,
) -> dict[str, Any]:
    eid = _uuid(entity_id, field="entity_id")
    row = _single(
        reader,
        "/rest/v1/business_entities",
        {
            "select": (
                "id,canonical_name,normalized_name,canonical_niche,"
                "canonical_metro,canonical_phone,canonical_website,"
                "identity_confidence,resolution_state,provenance,"
                "created_at,updated_at"
            ),
            "id": f"eq.{eid}",
            "limit": "1",
        },
        label="business entity",
        required=True,
    )
    assert row is not None
    return row


def fetch_latest_qualification(
    reader: Reader,
    prospect_id: str,
) -> dict[str, Any] | None:
    pid = _uuid(prospect_id, field="prospect_id")
    return _single(
        reader,
        "/rest/v1/prospect_qualifications",
        {
            "select": (
                "id,prospect_id,score,tier,status,recommended_action,"
                "scoring_engine,scoring_version,input_snapshot,"
                "result_payload,scored_at,updated_at"
            ),
            "prospect_id": f"eq.{pid}",
            "scoring_engine": "eq.empire_os.lead_scoring",
            "scoring_version": "eq.v1",
            "order": "scored_at.desc",
            "limit": "1",
        },
        label="latest qualification",
    )


def _entity_rows(
    reader: Reader,
    table: str,
    *,
    entity_id: str,
    select: str,
    order: str,
    limit: int,
    label: str,
) -> list[dict[str, Any]]:
    eid = _uuid(entity_id, field="entity_id")
    return _rows(
        reader,
        f"/rest/v1/{table}",
        {
            "select": select,
            "entity_id": f"eq.{eid}",
            "order": order,
            "limit": str(limit),
        },
        label=label,
    )


def fetch_entity_intelligence(
    reader: Reader,
    entity_id: str,
    *,
    limits: LeadIntelligenceLimits | None = None,
) -> dict[str, list[dict[str, Any]]]:
    limits = limits or LeadIntelligenceLimits()
    facts = _entity_rows(
        reader,
        "intelligence_facts",
        entity_id=entity_id,
        select=(
            "id,entity_type,entity_id,fact_key,fact_value,source_id,"
            "confidence,first_seen_at,last_seen_at,valid_from,valid_to,"
            "evidence_uri,evidence_hash,created_at"
        ),
        order="last_seen_at.desc",
        limit=limits.facts,
        label="intelligence facts",
    )
    signals = _entity_rows(
        reader,
        "intelligence_signals",
        entity_id=entity_id,
        select=(
            "id,entity_id,signal_type,signal_domain,observed_at,source_id,"
            "strength,confidence,expires_at,payload,created_at"
        ),
        order="observed_at.desc",
        limit=limits.signals,
        label="intelligence signals",
    )
    scores = _entity_rows(
        reader,
        "intelligence_scores",
        entity_id=entity_id,
        select=(
            "id,entity_type,entity_id,score_type,score,confidence,"
            "model_key,features,explanation,scored_at"
        ),
        order="scored_at.desc",
        limit=limits.scores,
        label="intelligence scores",
    )
    contact_points = _entity_rows(
        reader,
        "intelligence_contact_points",
        entity_id=entity_id,
        select=(
            "id,person_id,entity_id,contact_type,value,normalized_value,"
            "verification_state,source_id,first_seen_at,last_seen_at,"
            "verified_at,confidence"
        ),
        order="last_seen_at.desc",
        limit=limits.contact_points,
        label="intelligence contact points",
    )
    employments = _entity_rows(
        reader,
        "intelligence_employment",
        entity_id=entity_id,
        select=(
            "id,person_id,entity_id,title,normalized_title,seniority,"
            "department,buying_role,is_current,valid_from,valid_to,"
            "confidence,created_at"
        ),
        order="created_at.desc",
        limit=limits.employments,
        label="intelligence employment",
    )
    return {
        "facts": facts,
        "signals": signals,
        "scores": scores,
        "contact_points": contact_points,
        "employments": employments,
    }


def build_lead_intelligence(
    reader: Reader,
    prospect_id: str,
    *,
    limits: LeadIntelligenceLimits | None = None,
) -> dict[str, Any]:
    """Build one evidence-preserving canonical lead-intelligence view."""
    prospect = fetch_prospect(reader, prospect_id)
    pid = _uuid(prospect["id"], field="prospect.id")
    link = fetch_identity_link(reader, pid)
    qualification = fetch_latest_qualification(reader, pid)

    entity: dict[str, Any] | None = None
    intelligence: dict[str, list[dict[str, Any]]] = {
        "facts": [],
        "signals": [],
        "scores": [],
        "contact_points": [],
        "employments": [],
    }
    unknowns: list[str] = []

    if link is None:
        unknowns.append("canonical_entity_unresolved")
    else:
        entity_id = link.get("entity_id")
        if not entity_id:
            raise LeadIntelligenceError(
                "active identity link missing entity_id"
            )
        entity = fetch_business_entity(reader, str(entity_id))
        intelligence = fetch_entity_intelligence(
            reader,
            str(entity_id),
            limits=limits,
        )

    if qualification is None:
        unknowns.append("qualification_missing")
    if not intelligence["facts"]:
        unknowns.append("intelligence_facts_missing")
    if not intelligence["signals"]:
        unknowns.append("intelligence_signals_missing")
    if not intelligence["scores"]:
        unknowns.append("intelligence_scores_missing")

    return {
        "schema_version": "lead_intelligence.v1",
        "source_of_truth": "canonical_supabase",
        "read_only": True,
        "prospect_id": pid,
        "prospect": prospect,
        "identity": {"link": link, "entity": entity},
        "qualification": qualification,
        "intelligence": intelligence,
        "unknowns": unknowns,
    }
