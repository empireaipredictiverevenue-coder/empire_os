"""Canonical buyer-state evidence stack for EmpireOS.

This module projects factual state only. It never promotes research, competitor
overlap, qualification scores, or model recommendations into buyer intent or
commercial intent. Unknown stages remain unknown.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from empire_os.intelligence_materializer_transport import (
    ROLE,
    PostgresIntelligenceMaterializer,
)


SNAPSHOT_RELATIVE_PATH = Path(
    "runtime/buyer_state/buyer_state_latest.json"
)

BUYER_STATES = (
    "DISCOVERED",
    "ICP_MATCH",
    "SIGNAL_ACTIVE",
    "RESEARCHED",
    "READY",
    "CONTACTED",
    "ENGAGED",
    "CONVERSATION",
    "COMMERCIAL_INTENT",
    "TERMS",
    "PAYMENT_PENDING",
    "PAID",
    "FULFILLED",
    "EXPANSION",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stage(
    name: str,
    observed: bool | None,
    *,
    evidence: Mapping[str, Any] | None = None,
    authority: str = "none",
) -> dict[str, Any]:
    return {
        "state": name,
        "observed": observed,
        "evidence": dict(evidence or {}),
        "authority": authority,
    }


def _qualification_state(row: Mapping[str, Any]) -> tuple[bool | None, bool | None]:
    status = _clean(row.get("qualification_status")).lower()
    tier = _clean(row.get("qualification_tier")).lower()
    action = _clean(row.get("recommended_action")).lower()

    if not status:
        return None, None

    if status == "insufficient_evidence" or tier == "insufficient_evidence":
        return None, None

    if status != "scored":
        return None, None

    icp_match = True
    ready = (
        "immediate governed contact" in action
        or "review for immediate" in action
    )
    return icp_match, ready


def build_buyer_state_for_entity(
    row: Mapping[str, Any],
    *,
    account_brief: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    entity_id = _clean(row.get("entity_id"))
    company_name = _clean(row.get("canonical_name"))
    prospect_id = _clean(row.get("prospect_id"))

    discovered = bool(entity_id and prospect_id and row.get("link_active") is True)
    icp_match, ready = _qualification_state(row)

    signal_count = int(row.get("competitive_signal_count") or 0)
    signal_active = True if signal_count > 0 else None

    brief = dict(account_brief or {})
    critic = brief.get("claim_critic")
    researched = None
    if isinstance(critic, Mapping):
        if (
            brief.get("entity_id") == entity_id
            and critic.get("all_published_claims_supported") is True
            and int(critic.get("supported_count") or 0) > 0
        ):
            researched = True

    contacted_status = _clean(row.get("contacted_status")).lower()
    contacted_at = _clean(row.get("contacted_at"))
    if contacted_at:
        contacted = True
    elif contacted_status == "not_contacted":
        contacted = False
    elif contacted_status:
        contacted = True
    else:
        contacted = None

    qualification_evidence = {
        "prospect_id": prospect_id or None,
        "qualification_score": row.get("qualification_score"),
        "qualification_tier": row.get("qualification_tier"),
        "qualification_status": row.get("qualification_status"),
        "recommended_action": row.get("recommended_action"),
        "scored_at": row.get("scored_at"),
    }

    stages = [
        _stage(
            "DISCOVERED",
            discovered,
            evidence={
                "entity_id": entity_id or None,
                "prospect_id": prospect_id or None,
                "entity_link_active": row.get("link_active") is True,
                "entity_match_score": row.get("match_score"),
            },
        ),
        _stage(
            "ICP_MATCH",
            icp_match,
            evidence=qualification_evidence,
        ),
        _stage(
            "SIGNAL_ACTIVE",
            signal_active,
            evidence={
                "competitive_signal_count": signal_count,
                "signal_type": (
                    "competitor_audience_evidence"
                    if signal_count > 0
                    else None
                ),
            },
        ),
        _stage(
            "RESEARCHED",
            researched,
            evidence={
                "account_brief_available": bool(brief),
                "supported_claim_count": (
                    critic.get("supported_count")
                    if isinstance(critic, Mapping)
                    else None
                ),
                "blocked_claim_count": (
                    critic.get("blocked_count")
                    if isinstance(critic, Mapping)
                    else None
                ),
            },
        ),
        _stage(
            "READY",
            ready,
            evidence=qualification_evidence,
            authority="governed_internal_review",
        ),
        _stage(
            "CONTACTED",
            contacted,
            evidence={
                "contacted_status": row.get("contacted_status"),
                "contacted_at": row.get("contacted_at"),
            },
            authority="governed_external",
        ),
    ]

    # These states require canonical downstream commercial/conversation evidence.
    # Absence of a reader path is UNKNOWN, never false and never inferred.
    for state in BUYER_STATES[6:]:
        stages.append(_stage(state, None))

    true_states = [
        stage["state"]
        for stage in stages
        if stage["observed"] is True
    ]
    current_state = true_states[-1] if true_states else None

    return {
        "schema_version": "empire.buyer_state_evidence.v1",
        "entity_id": entity_id,
        "company_name": company_name,
        "prospect_id": prospect_id or None,
        "current_factual_state": current_state,
        "states": stages,
        "unknown_states": [
            stage["state"] for stage in stages
            if stage["observed"] is None
        ],
        "observed_true_states": true_states,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "qualification_score_is_commercial_intent": False,
        "competitor_evidence_is_buyer_intent": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


def build_buyer_state_snapshot(
    rows: Iterable[Mapping[str, Any]],
    *,
    account_briefs: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    briefs = {
        _clean(brief.get("entity_id")): brief
        for brief in account_briefs
        if isinstance(brief, Mapping) and _clean(brief.get("entity_id"))
    }

    entities = [
        build_buyer_state_for_entity(
            row,
            account_brief=briefs.get(_clean(row.get("entity_id"))),
        )
        for row in rows
        if isinstance(row, Mapping) and _clean(row.get("entity_id"))
    ]
    entities.sort(
        key=lambda item: (
            BUYER_STATES.index(item["current_factual_state"])
            if item["current_factual_state"] in BUYER_STATES
            else -1,
            item["company_name"].casefold(),
        ),
        reverse=True,
    )

    return {
        "schema_version": "empire.buyer_state_evidence_snapshot.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entity_count": len(entities),
        "states": list(BUYER_STATES),
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
        "entities": entities,
    }


def load_early_buyer_state_rows(
    writer: PostgresIntelligenceMaterializer,
) -> list[dict[str, Any]]:
    with writer._connect(writer.dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SET LOCAL ROLE {ROLE}")
            cursor.execute(
                """
                SELECT
                  be.id AS entity_id,
                  be.canonical_name,
                  pel.prospect_id,
                  pel.match_score,
                  pel.active AS link_active,
                  p.status AS prospect_status,
                  p.contacted_status,
                  p.contacted_at,
                  pq.score AS qualification_score,
                  pq.tier AS qualification_tier,
                  pq.status AS qualification_status,
                  pq.recommended_action,
                  pq.scored_at,
                  (
                    SELECT count(*)
                    FROM public.intelligence_signals s
                    WHERE s.entity_id=be.id
                      AND s.signal_type='competitor_audience_evidence'
                      AND s.signal_domain='competitive_intelligence'
                  ) AS competitive_signal_count
                FROM public.business_entities be
                JOIN public.prospect_entity_links pel
                  ON pel.entity_id=be.id
                 AND pel.active=true
                JOIN public.prospects p
                  ON p.id=pel.prospect_id
                LEFT JOIN LATERAL (
                  SELECT q.*
                  FROM public.prospect_qualifications q
                  WHERE q.entity_id=be.id
                  ORDER BY q.scored_at DESC NULLS LAST,
                           q.created_at DESC
                  LIMIT 1
                ) pq ON true
                WHERE EXISTS (
                  SELECT 1
                  FROM public.intelligence_signals s
                  WHERE s.entity_id=be.id
                    AND s.signal_type='competitor_audience_evidence'
                    AND s.signal_domain='competitive_intelligence'
                )
                ORDER BY be.canonical_name, pel.prospect_id
                """
            )
            names = [item.name for item in cursor.description]
            return [
                dict(zip(names, row, strict=True))
                for row in cursor.fetchall()
            ]


def _load_account_briefs(repo_root: Path) -> list[dict[str, Any]]:
    path = (
        repo_root
        / "runtime/competitive_intelligence/"
        / "competitor_account_briefs_latest.json"
    )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    briefs = payload.get("briefs") if isinstance(payload, Mapping) else []
    return [
        row for row in (briefs or [])
        if isinstance(row, Mapping)
    ]


def write_buyer_state_snapshot(
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


def refresh_buyer_state_snapshot(
    repo_root: Path,
    writer: PostgresIntelligenceMaterializer,
) -> dict[str, Any]:
    payload = build_buyer_state_snapshot(
        load_early_buyer_state_rows(writer),
        account_briefs=_load_account_briefs(repo_root),
    )
    write_buyer_state_snapshot(repo_root, payload)
    return payload


def build_buyer_state_runtime(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "available": False,
            "schema_version": "empire.buyer_state_evidence_snapshot.v1",
            "mode": "OBSERVE",
            "entity_count": 0,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "outreach_enabled": False,
            "execution_authority": "none",
        }
    return {"available": True, **payload}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh canonical buyer-state evidence snapshot"
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
            build_buyer_state_runtime(repo_root),
            indent=2,
            sort_keys=True,
            default=str,
        ))
        return 0

    writer = PostgresIntelligenceMaterializer.from_env()
    payload = refresh_buyer_state_snapshot(repo_root, writer)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
