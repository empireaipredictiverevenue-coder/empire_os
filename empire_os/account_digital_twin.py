"""Account / Buyer Digital Twin read model for EmpireOS.

The twin composes already-governed runtime evidence into one account view.
Unknown commercial, conversation, payment, fulfilment, outcome, and revenue
state stays unknown. This module performs no writes outside its local snapshot
and grants no execution authority.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from empire_os.intelligence_materializer_transport import (
    ROLE,
    PostgresIntelligenceMaterializer,
)


SNAPSHOT_RELATIVE_PATH = Path(
    "runtime/account_twin/account_twin_latest.json"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _index(rows: list[Any], key: str = "entity_id") -> dict[str, Mapping[str, Any]]:
    return {
        _clean(row.get(key)): row
        for row in rows
        if isinstance(row, Mapping) and _clean(row.get(key))
    }


def _state_map(entity: Mapping[str, Any]) -> dict[str, bool | None]:
    result: dict[str, bool | None] = {}
    for row in entity.get("states", []) or []:
        if not isinstance(row, Mapping):
            continue
        name = _clean(row.get("state"))
        if not name:
            continue
        observed = row.get("observed")
        result[name] = observed if isinstance(observed, bool) else None
    return result


def _stage_evidence(
    entity: Mapping[str, Any],
    *names: str,
) -> dict[str, Any]:
    for row in entity.get("states", []) or []:
        if not isinstance(row, Mapping):
            continue
        if _clean(row.get("state")) in names:
            evidence = row.get("evidence")
            return dict(evidence) if isinstance(evidence, Mapping) else {}
    return {}


def build_account_twin(
    entity: Mapping[str, Any],
    *,
    audience: Mapping[str, Any] | None = None,
    research: Mapping[str, Any] | None = None,
    brief: Mapping[str, Any] | None = None,
    next_action: Mapping[str, Any] | None = None,
    qualification_history: list[Mapping[str, Any]] | None = None,
    commercial_history: Mapping[str, Any] | None = None,
    revenue_truth: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    audience = dict(audience or {})
    research = dict(research or {})
    brief = dict(brief or {})
    next_action = dict(next_action or {})
    qualification_history = list(qualification_history or [])
    commercial_history_loaded = commercial_history is not None
    commercial_history = dict(commercial_history or {})
    revenue_truth_loaded = revenue_truth is not None
    revenue_truth = dict(revenue_truth or {})

    states = _state_map(entity)
    unknown_states = list(entity.get("unknown_states", []) or [])

    qualification = _stage_evidence(entity, "READY", "ICP_MATCH")
    contacted = _stage_evidence(entity, "CONTACTED")

    competitor_evidence = [
        item
        for item in audience.get("evidence", []) or []
        if isinstance(item, Mapping)
    ]
    claims = [
        item
        for item in brief.get("claims", []) or []
        if isinstance(item, Mapping)
    ]
    observations = [
        item
        for item in research.get("observations", []) or []
        if isinstance(item, Mapping)
    ]

    downstream = {
        name: states.get(name)
        for name in (
            "ENGAGED",
            "CONVERSATION",
            "COMMERCIAL_INTENT",
            "TERMS",
            "PAYMENT_PENDING",
            "PAID",
            "FULFILLED",
            "EXPANSION",
        )
    }

    uncertainties: list[str] = []
    if not qualification:
        uncertainties.append("qualification_evidence_unavailable")
    if not claims:
        uncertainties.append("supported_account_claims_unavailable")
    if not observations:
        uncertainties.append("research_observations_unavailable")
    if not competitor_evidence:
        uncertainties.append("competitor_relationship_evidence_unavailable")
    if not commercial_history_loaded:
        uncertainties.append("commercial_history_unavailable")
        if not _clean(contacted.get("contacted_at")):
            uncertainties.append("outreach_history_not_observed")

    for state_name, observed in downstream.items():
        if observed is None:
            uncertainties.append(
                f"{state_name.lower()}_not_observed"
            )

    return {
        "schema_version": "empire.account_buyer_digital_twin.v1",
        "mode": "OBSERVE",
        "entity_id": _clean(entity.get("entity_id")),
        "prospect_id": _clean(entity.get("prospect_id")) or None,
        "identity": {
            "company_name": _clean(entity.get("company_name")),
            "company_website": _clean(brief.get("company_website")) or None,
            "entity_id": _clean(entity.get("entity_id")),
            "prospect_id": _clean(entity.get("prospect_id")) or None,
        },
        "buyer_state": {
            "current_factual_state": entity.get("current_factual_state"),
            "observed_true_states": list(
                entity.get("observed_true_states", []) or []
            ),
            "unknown_states": unknown_states,
            "states": list(entity.get("states", []) or []),
        },
        "qualification": {
            "history_available": bool(qualification_history),
            "history": [
                dict(item)
                for item in qualification_history
                if isinstance(item, Mapping)
            ],
            "latest_evidence": qualification or None,
            "score_is_commercial_intent": False,
        },
        "public_evidence": {
            "supported_claim_count": len(claims),
            "claims": claims,
            "canonical_competitor_evidence_count": len(
                competitor_evidence
            ),
            "canonical_competitor_evidence": competitor_evidence,
        },
        "competitor_relationships": {
            "competitors": list(audience.get("competitors", []) or []),
            "competitor_count": int(audience.get("competitor_count") or 0),
            "evidence_count": int(
                audience.get("unique_evidence_count") or 0
            ),
            "buyer_intent_inferred": False,
        },
        "research": {
            "requested_action": research.get("requested_action"),
            "next_step": research.get("next_step"),
            "observation_count": int(
                research.get("observation_count") or 0
            ),
            "observations": observations,
            "claim_critic": (
                brief.get("claim_critic")
                if isinstance(brief.get("claim_critic"), Mapping)
                else {}
            ),
        },
        "next_best_action": next_action or None,
        "outreach": {
            "contacted_state": states.get("CONTACTED"),
            "contacted_status": contacted.get("contacted_status"),
            "contacted_at": contacted.get("contacted_at"),
            "history_available": commercial_history_loaded,
            "intent_count": len(
                commercial_history.get("outbound_intents", []) or []
            ),
            "intents": list(
                commercial_history.get("outbound_intents", []) or []
            ),
        },
        "conversation": {
            "engaged": states.get("ENGAGED"),
            "conversation": states.get("CONVERSATION"),
            "history_available": commercial_history_loaded,
            "source": (
                "outbound_replies"
                if commercial_history_loaded
                else None
            ),
            "reply_count": len(
                commercial_history.get("outbound_replies", []) or []
            ),
            "replies": list(
                commercial_history.get("outbound_replies", []) or []
            ),
            "conversation_state_authoritative": False,
        },
        "commercial": {
            "commercial_intent": states.get("COMMERCIAL_INTENT"),
            "terms": states.get("TERMS"),
            "payment_pending": states.get("PAYMENT_PENDING"),
            "paid": states.get("PAID"),
            "fulfilled": states.get("FULFILLED"),
            "expansion": states.get("EXPANSION"),
            "history_available": commercial_history_loaded,
            "terms_reviews": list(
                commercial_history.get("terms_reviews", []) or []
            ),
            "payment_requests": list(
                commercial_history.get("payment_requests", []) or []
            ),
            "payment_evidence": list(
                commercial_history.get("payment_evidence", []) or []
            ),
            "fulfilment_orders": list(
                commercial_history.get("fulfilment_orders", []) or []
            ),
            "unknown_stays_unknown": True,
        },
        "outcomes": {
            "available": commercial_history_loaded,
            "history": list(
                commercial_history.get("commercial_outcomes", []) or []
            ),
            "verified_outcome": (
                list(commercial_history.get("commercial_outcomes", []) or [])[-1]
                if commercial_history.get("commercial_outcomes")
                else None
            ),
        },
        "revenue_truth": {
            "available": revenue_truth_loaded,
            "recognized_order_count": (
                int(revenue_truth.get("recognized_order_count") or 0)
                if revenue_truth_loaded else None
            ),
            "recognized_revenue_cents": (
                int(revenue_truth.get("recognized_revenue_cents") or 0)
                if revenue_truth_loaded else None
            ),
            "actual_cost_cents": (
                int(revenue_truth.get("actual_cost_cents") or 0)
                if revenue_truth_loaded else None
            ),
            "realized_gp_cents": (
                int(revenue_truth.get("realized_gp_cents") or 0)
                if revenue_truth_loaded else None
            ),
            "latest_recognized_at": (
                revenue_truth.get("latest_recognized_at")
                if revenue_truth_loaded else None
            ),
            "forecast_included_in_truth": False,
            "actual_revenue": (
                bool(int(revenue_truth.get("recognized_revenue_cents") or 0) > 0)
                if revenue_truth_loaded else False
            ),
            "recognition_authority": "none",
        },
        "uncertainty": {
            "explicit": True,
            "items": sorted(set(uncertainties)),
        },
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_authorized": False,
        "payment_authorized": False,
        "execution_authority": "none",
    }


def build_account_twin_snapshot(
    *,
    buyer_state: Mapping[str, Any],
    audience: Mapping[str, Any],
    research: Mapping[str, Any],
    briefs: Mapping[str, Any],
    next_actions: Mapping[str, Any],
    qualification_history_by_entity: Mapping[
        str, list[Mapping[str, Any]]
    ] | None = None,
    commercial_history_by_entity: Mapping[
        str, Mapping[str, Any]
    ] | None = None,
    revenue_truth_by_entity: Mapping[
        str, Mapping[str, Any]
    ] | None = None,
) -> dict[str, Any]:
    audience_by_id = _index(list(audience.get("companies", []) or []))
    research_by_id = _index(list(research.get("actions", []) or []))
    brief_by_id = _index(list(briefs.get("briefs", []) or []))
    next_by_id = _index(list(next_actions.get("actions", []) or []))
    qualification_history_by_entity = dict(
        qualification_history_by_entity or {}
    )
    commercial_history_by_entity = dict(
        commercial_history_by_entity or {}
    )
    revenue_truth_by_entity = dict(
        revenue_truth_by_entity or {}
    )

    twins = []
    for entity in buyer_state.get("entities", []) or []:
        if not isinstance(entity, Mapping):
            continue
        entity_id = _clean(entity.get("entity_id"))
        if not entity_id:
            continue
        twins.append(build_account_twin(
            entity,
            audience=audience_by_id.get(entity_id),
            research=research_by_id.get(entity_id),
            brief=brief_by_id.get(entity_id),
            next_action=next_by_id.get(entity_id),
            qualification_history=qualification_history_by_entity.get(
                entity_id,
                [],
            ),
            commercial_history=commercial_history_by_entity.get(
                entity_id
            ),
            revenue_truth=revenue_truth_by_entity.get(entity_id),
        ))

    twins.sort(
        key=lambda row: (
            _clean(row["identity"].get("company_name")).casefold()
        )
    )

    return {
        "schema_version": "empire.account_buyer_digital_twin_snapshot.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "twin_count": len(twins),
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_authorized": False,
        "payment_authorized": False,
        "execution_authority": "none",
        "twins": twins,
    }


def load_qualification_history(
    writer: PostgresIntelligenceMaterializer,
    entity_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    if not entity_ids:
        return {}

    with writer._connect(writer.dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SET LOCAL ROLE {ROLE}")
            cursor.execute(
                """
                SELECT
                  q.id,
                  q.entity_id,
                  q.prospect_id,
                  q.score,
                  q.tier,
                  q.status,
                  q.evidence_confidence,
                  q.observed_dimensions,
                  q.unknown_dimensions,
                  q.recommended_action,
                  q.scoring_engine,
                  q.scoring_version,
                  q.scored_at,
                  q.created_at
                FROM public.prospect_qualifications q
                WHERE q.entity_id = ANY(%s::uuid[])
                ORDER BY q.entity_id,
                         q.scored_at ASC NULLS LAST,
                         q.created_at ASC
                """,
                (entity_ids,),
            )
            names = [item.name for item in cursor.description]
            rows = [
                dict(zip(names, row, strict=True))
                for row in cursor.fetchall()
            ]

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        entity_id = _clean(row.get("entity_id"))
        grouped.setdefault(entity_id, []).append(row)
    return grouped


def load_commercial_history(
    writer: PostgresIntelligenceMaterializer,
    entity_ids: list[str],
) -> dict[str, dict[str, Any]]:
    if not entity_ids:
        return {}

    with writer._connect(writer.dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SET LOCAL ROLE {ROLE}")
            cursor.execute(
                """
                SELECT entity_id, history
                FROM public.empire_account_twin_history(%s::uuid[])
                ORDER BY entity_id
                """,
                (entity_ids,),
            )
            rows = cursor.fetchall()

    result: dict[str, dict[str, Any]] = {}
    for entity_id, history in rows:
        key = _clean(entity_id)
        result[key] = dict(history) if isinstance(history, Mapping) else {}
    return result


def load_account_revenue_truth(
    writer: PostgresIntelligenceMaterializer,
    entity_ids: list[str],
) -> dict[str, dict[str, Any]]:
    if not entity_ids:
        return {}

    with writer._connect(writer.dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SET LOCAL ROLE {ROLE}")
            cursor.execute(
                """
                SELECT
                  entity_id,
                  recognized_order_count,
                  recognized_revenue_cents,
                  actual_cost_cents,
                  realized_gp_cents,
                  latest_recognized_at
                FROM public.empire_account_revenue_truth(%s::uuid[])
                ORDER BY entity_id
                """,
                (entity_ids,),
            )
            names = [item.name for item in cursor.description]
            rows = [
                dict(zip(names, row, strict=True))
                for row in cursor.fetchall()
            ]

    return {
        _clean(row.get("entity_id")): row
        for row in rows
        if _clean(row.get("entity_id"))
    }


def refresh_account_twin_snapshot(repo_root: Path) -> dict[str, Any]:
    runtime = repo_root / "runtime"
    buyer_state = _load_json(
        runtime / "buyer_state/buyer_state_latest.json"
    )
    entity_ids = [
        _clean(row.get("entity_id"))
        for row in buyer_state.get("entities", []) or []
        if isinstance(row, Mapping) and _clean(row.get("entity_id"))
    ]

    qualification_history: dict[
        str, list[dict[str, Any]]
    ] = {}
    commercial_history: dict[str, dict[str, Any]] = {}
    revenue_truth: dict[str, dict[str, Any]] = {}
    try:
        writer = PostgresIntelligenceMaterializer.from_env()
    except Exception:
        writer = None
    if writer is not None:
        qualification_history = load_qualification_history(
            writer,
            entity_ids,
        )
        commercial_history = load_commercial_history(
            writer,
            entity_ids,
        )
        revenue_truth = load_account_revenue_truth(
            writer,
            entity_ids,
        )

    payload = build_account_twin_snapshot(
        buyer_state=buyer_state,
        audience=_load_json(
            runtime
            / "competitive_intelligence/"
            / "competitor_audience_latest.json"
        ),
        research=_load_json(
            runtime
            / "competitive_intelligence/"
            / "competitor_account_research_latest.json"
        ),
        briefs=_load_json(
            runtime
            / "competitive_intelligence/"
            / "competitor_account_briefs_latest.json"
        ),
        next_actions=_load_json(
            runtime
            / "next_best_action/"
            / "next_best_action_latest.json"
        ),
        qualification_history_by_entity=qualification_history,
        commercial_history_by_entity=commercial_history,
        revenue_truth_by_entity=revenue_truth,
    )
    write_account_twin_snapshot(repo_root, payload)
    return payload


def write_account_twin_snapshot(
    repo_root: Path,
    payload: Mapping[str, Any],
) -> Path:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def build_account_twin_runtime(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    try:
        payload = _load_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return {
            "available": False,
            "schema_version": (
                "empire.account_buyer_digital_twin_snapshot.v1"
            ),
            "mode": "OBSERVE",
            "twin_count": 0,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "outreach_authorized": False,
            "payment_authorized": False,
            "execution_authority": "none",
        }
    return {"available": True, **payload}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build read-only Account / Buyer Digital Twins"
    )
    parser.add_argument(
        "--repo-root",
        default=os.getenv("EMPIRE_REPO_ROOT", "/srv/empire_os"),
    )
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()

    if not args.refresh:
        print(json.dumps(
            build_account_twin_runtime(repo_root),
            indent=2,
            sort_keys=True,
            default=str,
        ))
        return 0

    payload = refresh_account_twin_snapshot(repo_root)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
