"""Bounded production qualification cycle for canonical Lead Scoring v2."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from empire_os.canonical_data_gateway import gateway_from_environment
from empire_os.commercial_event_repository import CommercialEventRepository
from empire_os.prospect_enrichment import enrich_prospect_for_scoring
from empire_os.qualification_data_repository import QualificationDataRepository
from empire_os.qualification_v2 import build_v2_qualification_payload
from empire_os.runtime_env import load_runtime_env
from empire_os.singleton_identity_plan import (
    SingletonIdentityPlanError,
    build_singleton_identity_plan,
)

ENV_PATH = "/etc/empire_os.env"
SCORING_ENGINE = "empire_os.lead_scoring"
SCORING_VERSION = "v2"

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _qualification_repository() -> QualificationDataRepository:
    env = load_runtime_env(ENV_PATH)
    return QualificationDataRepository(gateway_from_environment(env))


def _commercial_event_repository() -> CommercialEventRepository:
    env = load_runtime_env(ENV_PATH)
    return CommercialEventRepository(gateway_from_environment(env))


def fetch_prospect(prospect_id: str) -> dict[str, Any]:
    return _qualification_repository().fetch_prospect(prospect_id)


def fetch_pending_prospects(limit: int = 10) -> list[dict[str, Any]]:
    return _qualification_repository().fetch_pending_prospects(
        limit=limit,
        scoring_engine=SCORING_ENGINE,
        scoring_version=SCORING_VERSION,
    )


def fetch_unlinked_allocatable_prospects(
    limit: int = 10,
) -> list[dict[str, Any]]:
    return _qualification_repository().fetch_unlinked_allocatable_prospects(
        limit=limit,
        scoring_engine=SCORING_ENGINE,
        scoring_version=SCORING_VERSION,
    )


def fetch_latest_acquisition(
    prospect_id: str,
) -> dict[str, Any] | None:
    return _qualification_repository().fetch_latest_acquisition(prospect_id)


def acquisition_website(acquisition: dict[str, Any] | None) -> str:
    evidence = (
        acquisition.get("evidence")
        if isinstance(acquisition, dict)
        else None
    )
    raw = evidence.get("raw") if isinstance(evidence, dict) else None
    if not isinstance(raw, dict):
        return ""
    return str(
        raw.get("business_website")
        or (raw.get("osm_tags") or {}).get("website")
        or ""
    ).strip()


def resolve_acquisition_website(
    prospect: dict[str, Any],
    acquisition: dict[str, Any] | None,
) -> str:
    """Resolve the strongest current acquisition website evidence.

    Stored evidence wins when present. For sources with a bounded official
    member/detail page resolver, the live source may refresh missing website
    evidence in memory before Search Fabric is needed. This function does not
    mutate the acquisition ledger.
    """
    stored = acquisition_website(acquisition)
    if stored:
        return stored

    if not isinstance(acquisition, dict):
        return ""

    source = str(acquisition.get("source") or "").strip()
    source_url = str(acquisition.get("source_url") or "").strip()
    business_name = str(prospect.get("business_name") or "").strip()

    if (
        source != "recc_solar"
        or not source_url
        or not business_name
    ):
        return ""

    try:
        from empire_os.lead_sources.recc_solar import _detail
        candidate = _detail(business_name, source_url)
    except Exception:
        return ""

    raw = getattr(candidate, "raw", None) if candidate is not None else None
    if not isinstance(raw, dict):
        return ""
    return str(raw.get("business_website") or "").strip()


def fetch_active_identity_link(
    prospect_id: str,
) -> dict[str, Any] | None:
    return _qualification_repository().fetch_active_identity_link(prospect_id)


def _insert_identity_entity(payload: dict[str, Any]) -> None:
    _qualification_repository().insert_identity_entity(payload)


def _insert_identity_link(payload: dict[str, Any]) -> None:
    _qualification_repository().insert_identity_link(payload)


def resolve_identity(
    prospect: dict[str, Any],
    acquisition: dict[str, Any] | None,
    enrichment: dict[str, Any],
) -> str | None:
    prospect_id = str(prospect["id"])
    existing = fetch_active_identity_link(prospect_id)
    if existing:
        entity_id = str(existing.get("entity_id") or "").strip()
        if not entity_id:
            raise RuntimeError("active identity link missing entity id")
        return entity_id

    if not acquisition:
        return None

    try:
        plan = build_singleton_identity_plan(
            prospect=prospect,
            acquisition=acquisition,
            enrichment=enrichment,
        )
    except SingletonIdentityPlanError:
        return None

    entity_id = str(plan["entity_id_candidate"])
    entity_payload = {
        "id": entity_id,
        "canonical_name": plan["canonical_name_candidate"],
        "normalized_name": str(
            plan["canonical_name_candidate"]
        ).strip().lower(),
        "canonical_niche": plan["canonical_niche_candidate"],
        "canonical_metro": plan["canonical_metro_candidate"],
        "canonical_phone": plan["canonical_phone_candidate"],
        "canonical_website": plan["canonical_website_candidate"],
        "identity_confidence": plan["association_confidence"],
        "resolution_state": plan["resolution_state"],
        "provenance": {
            "resolver": "singleton_identity_plan.v1",
            "confidence_basis": plan["confidence_basis"],
            "evidence_assertions": plan["evidence_assertions"],
            "source": plan["source"],
        },
    }
    _insert_identity_entity(entity_payload)

    link_payload = {
        "prospect_id": prospect_id,
        "entity_id": entity_id,
        "match_method": "singleton_evidence_v1",
        "match_score": plan["association_confidence"],
        "evidence": {
            "confidence_basis": plan["confidence_basis"],
            "evidence_assertions": plan["evidence_assertions"],
            "source": plan["source"],
        },
        "active": True,
    }
    _insert_identity_link(link_payload)

    verified = fetch_active_identity_link(prospect_id)
    verified_id = str(
        (verified or {}).get("entity_id") or ""
    ).strip()
    if verified_id != entity_id:
        raise RuntimeError("identity promotion verification failed")
    return entity_id


def verified_enrichment_website(
    prospect: dict[str, Any],
    enrichment: dict[str, Any],
) -> str:
    """Return only an identity-accepted discovered first-party website."""
    if str(prospect.get("website") or "").strip():
        return ""

    fields = enrichment.get("fields")
    if not isinstance(fields, dict):
        return ""
    website = str(fields.get("website") or "").strip()
    if not website:
        return ""

    evidence = enrichment.get("evidence")
    evidence = evidence if isinstance(evidence, list) else []
    guard_ok = any(
        isinstance(item, dict)
        and item.get("source") == "identity_guard"
        and item.get("accepted") is True
        for item in evidence
    )
    site_ok = any(
        isinstance(item, dict)
        and item.get("source") == "website"
        and item.get("accepted") is True
        for item in evidence
    )
    return website if guard_ok and site_ok else ""


def promote_verified_website(
    prospect: dict[str, Any],
    enrichment: dict[str, Any],
) -> str:
    """Persist a verified first-party site without overwriting canonical data."""
    website = verified_enrichment_website(prospect, enrichment)
    if not website:
        return ""

    prospect_id = str(prospect.get("id") or "").strip()
    if not prospect_id:
        raise RuntimeError("prospect id required for website promotion")

    return _qualification_repository().promote_verified_website(
        prospect_id,
        website,
    )


def build_evidence_backed_payload(
    prospect: dict[str, Any],
    *,
    acquisition_website: str = "",
    enrichment: dict[str, Any] | None = None,
    entity_id: str | None = None,
) -> dict[str, Any]:
    if enrichment is None:
        enrichment_input = dict(prospect)
        if acquisition_website:
            enrichment_input["_acquisition_website"] = acquisition_website
        enrichment = enrich_prospect_for_scoring(enrichment_input)

    scoring_input = dict(prospect)
    scoring_input.update(enrichment.get("fields") or {})
    scoring_input["enrichment_score"] = enrichment.get("enrichment_score", 0)

    evidence = list(enrichment.get("evidence") or [])
    presence_checked = any(
        item.get("source") in {"website", "identity_guard"}
        for item in evidence
        if isinstance(item, dict)
    )

    payload = build_v2_qualification_payload(
        scoring_input,
        entity_id=entity_id,
        buy_signal_observed=False,
        enrichment_observed=True,
        business_presence_checked=presence_checked,
    )
    payload["result_payload"] = {
        **payload["result_payload"],
        "enrichment": enrichment,
    }
    return payload


def upsert_qualification(payload: dict[str, Any]) -> dict[str, Any]:
    return _qualification_repository().upsert_qualification(payload)


def emit_event(
    *,
    prospect_id: str,
    qualification_id: str,
    payload: dict[str, Any],
) -> None:
    event = {
        "event_type": "prospect_qualified_v2",
        "prospect_id": prospect_id,
        "channel": "qualification",
        "actor": "qualification_worker_v2",
        "payload": {
            "qualification_id": qualification_id,
            "score": payload.get("score"),
            "tier": payload.get("tier"),
            "evidence_confidence": payload.get("evidence_confidence"),
            "scoring_version": SCORING_VERSION,
        },
        "occurred_at": _now(),
        "idempotency_key": f"prospect:{prospect_id}:qualified:v2",
    }
    _commercial_event_repository().append_idempotent(event)


def qualify_prospect(prospect: dict[str, Any]) -> dict[str, Any]:
    prospect_id = str(prospect["id"])
    acquisition = fetch_latest_acquisition(prospect_id)
    website = resolve_acquisition_website(
        prospect,
        acquisition,
    )

    enrichment_input = dict(prospect)
    if website:
        enrichment_input["_acquisition_website"] = website
    enrichment = enrich_prospect_for_scoring(enrichment_input)

    promoted_website = promote_verified_website(
        prospect,
        enrichment,
    )
    if promoted_website:
        prospect = {
            **prospect,
            "website": promoted_website,
        }

    entity_id = resolve_identity(
        prospect,
        acquisition,
        enrichment,
    )
    payload = build_evidence_backed_payload(
        prospect,
        acquisition_website=website,
        enrichment=enrichment,
        entity_id=entity_id,
    )
    payload["result_payload"] = {
        **payload["result_payload"],
        "identity_resolution": {
            "attempted": True,
            "resolved": bool(entity_id),
            "entity_id": entity_id,
            "method": (
                "canonical_link_or_singleton_evidence"
                if entity_id
                else "singleton_evidence_unresolved"
            ),
            "attempted_at": _now(),
        },
    }
    row = upsert_qualification(payload)
    emit_event(
        prospect_id=prospect_id,
        qualification_id=str(row["id"]),
        payload=payload,
    )
    return {
        "prospect_id": prospect_id,
        "qualification_id": str(row["id"]),
        "score": payload.get("score"),
        "tier": payload.get("tier"),
        "evidence_confidence": payload.get("evidence_confidence"),
        "entity_id": entity_id,
        "identity_resolved": bool(entity_id),
        "verified_website_promoted": promoted_website or None,
    }


def _run_prospects(
    prospects: list[dict[str, Any]],
    *,
    schema_version: str,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for prospect in prospects:
        try:
            results.append(qualify_prospect(prospect))
        except Exception as exc:
            errors.append(
                {
                    "prospect_id": str(prospect.get("id") or ""),
                    "error": f"{type(exc).__name__}:{str(exc)[:300]}",
                }
            )
    return {
        "schema_version": schema_version,
        "ok": not errors,
        "attempted": len(prospects),
        "qualified": len(results),
        "failed": len(errors),
        "identity_resolved": sum(
            1 for row in results if row.get("identity_resolved")
        ),
        "results": results,
        "errors": errors,
        "real_data_only": True,
        "outreach_enabled": False,
        "payment_enabled": False,
        "finished_at": _now(),
    }


def run_cycle(limit: int = 10) -> dict[str, Any]:
    return _run_prospects(
        fetch_pending_prospects(limit),
        schema_version="qualification_cycle.v2",
    )


def run_identity_catchup(limit: int = 10) -> dict[str, Any]:
    return _run_prospects(
        fetch_unlinked_allocatable_prospects(limit),
        schema_version="qualification_identity_catchup.v1",
    )
