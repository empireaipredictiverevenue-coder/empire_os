"""Read-only lead scoring coverage bridge for founder lead-supply observatory.

Never invokes scoring/enrichment workers or treats projections as realised outcomes.
Joins Omega score evidence to the current qualification and active identity link.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
import json

from empire_os.niche_taxonomy import niche_family
from empire_os.omega_buyer_readiness import omega_readiness_decision
from empire_os.omega_worker import SCORE_TYPE
from empire_os.intelligence.omega import MODEL_VERSION


ENGINE_REGISTER = (
    {
        "engine": "Lead Scoring v2",
        "files": ("empire_os/lead_scoring_v2.py", "empire_os/qualification_worker_v2.py"),
        "observed_connection": "canonical_prospect_qualifications",
        "commercial_authority": False,
    },
    {
        "engine": "Prospect Enrichment",
        "files": ("empire_os/prospect_enrichment.py", "empire_os/evidence_enrichment_planner.py"),
        "observed_connection": "qualification_v2_result_payload",
        "commercial_authority": False,
    },
    {
        "engine": "OMEGA 2",
        "files": ("empire_os/intelligence/omega.py", "empire_os/omega_worker.py"),
        "observed_connection": "intelligence_scores_omega_opportunity",
        "commercial_authority": False,
    },
    {
        "engine": "OMEGA Buyer Readiness",
        "files": ("empire_os/omega_buyer_readiness.py",),
        "observed_connection": "qualification_identity_omega_evidence_check",
        "commercial_authority": False,
    },
    {
        "engine": "CORTEX",
        "files": ("empire_os/cortex_learning_loop.py",),
        "observed_connection": "account_twin_outcome_learning_snapshot",
        "commercial_authority": False,
    },
    {
        "engine": "Legacy OMEGA / Enrichment",
        "files": ("empire_os/omega_os.py", "empire_os/enrichment.py"),
        "observed_connection": "legacy_hub_import_not_canonical_score_coverage",
        "commercial_authority": False,
    },
    {
        "engine": "Hunter & buyer enrichment",
        "files": ("empire_os/hunter/enrichment_worker.py", "empire_os/buyer_deferred_enrichment.py"),
        "observed_connection": "independent_evidence_workflows_not_qualification_receipt",
        "commercial_authority": False,
    },
)


def _niche(value: Any) -> str:
    return niche_family(value) or "unclassified"


def cortex_runtime_summary(path: Path, *, now: datetime | None = None) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"available": False, "connected_to_niche_aggregate": False}
    if not isinstance(value, dict) or value.get("schema_version") != "empire.cortex_learning_snapshot.v1":
        return {"available": False, "connected_to_niche_aggregate": False}
    stamp = str(value.get("generated_at") or "")
    current = now or datetime.now(timezone.utc)
    try:
        generated = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        freshness_seconds = max((current - generated).total_seconds(), 0)
    except (ValueError, TypeError):
        freshness_seconds = None
    return {
        "available": True,
        "generated_at": stamp or None,
        "freshness_seconds": int(freshness_seconds) if freshness_seconds is not None else None,
        "stale_older_than_24h": freshness_seconds is None or freshness_seconds > 86400,
        "packet_count": value.get("packet_count"),
        "learning_ready_count": value.get("learning_ready_count"),
        "verified_customer_learning_count": value.get("verified_customer_learning_count"),
        "model_weight_mutation_authorized": False,
        "connected_to_niche_aggregate": False,
        "execution_authority": "none",
    }


def build_scoring_coverage(
    *,
    prospects: Iterable[Mapping[str, Any]],
    qualifications: Iterable[Mapping[str, Any]],
    identity_links: Iterable[Mapping[str, Any]],
    intelligence_scores: Iterable[Mapping[str, Any]],
    cortex_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    people = {
        str(p["id"]): _niche(p.get("niche"))
        for p in prospects if p.get("id")
    }
    latest_qualification: dict[str, dict[str, Any]] = {}
    for record in qualifications:
        pid = str(record.get("prospect_id") or "")
        if pid not in people or str(record.get("scoring_engine") or "") != "empire_os.lead_scoring":
            continue
        ver = str(record.get("scoring_version") or "")
        if ver not in ("v1", "v2"):
            continue
        old = latest_qualification.get(pid)
        if old is None or (ver == "v2" and str(old.get("scoring_version")) == "v1") or (
            ver == str(old.get("scoring_version"))
            and str(record.get("scored_at") or "") > str(old.get("scored_at") or "")
        ):
            latest_qualification[pid] = dict(record)

    active_links: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in identity_links:
        pid = str(record.get("prospect_id") or "")
        if pid in people and record.get("active") is True:
            active_links[pid].append(dict(record))

    omega_candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_omega_score_rows = 0
    for score in intelligence_scores:
        if str(score.get("score_type") or "") != SCORE_TYPE or str(score.get("entity_type") or "") != "company":
            continue
        all_omega_score_rows += 1
        if str(score.get("model_key") or "") != MODEL_VERSION:
            continue
        features = score.get("features") or {}
        if not isinstance(features, Mapping):
            continue
        pid = str(features.get("prospect_id") or "")
        if pid in people:
            omega_candidates[pid].append(dict(score))

    per_niche: dict[str, Counter[str]] = defaultdict(Counter)
    matched: set[str] = set()
    for pid, name in people.items():
        counts = per_niche[name]
        q = latest_qualification.get(pid)
        if not q:
            counts["unscored"] += 1
            continue
        if str(q.get("scoring_version")) == "v1":
            counts["v1_only"] += 1
            continue
        counts["v2_scored_rows"] += 1
        if q.get("status") == "scored":
            counts["v2_scored_status"] += 1
        elif q.get("status") == "insufficient_evidence":
            counts["insufficient_evidence"] += 1
        tier = str(q.get("tier") or "unknown").lower()
        counts[f"tier_{tier}"] += 1

        payload = q.get("result_payload") or {}
        if isinstance(payload, Mapping):
            enriched = payload.get("enrichment") or {}
            if isinstance(enriched, Mapping):
                evidence = enriched.get("evidence")
                if isinstance(evidence, (list, tuple)) and bool(evidence):
                    counts["enrichment_evidence_present"] += 1
                elif enriched:
                    counts["enrichment_result_without_evidence"] += 1
        links = active_links.get(pid, [])
        if len(links) == 1 and str(links[0].get("entity_id")) == str(q.get("entity_id")):
            counts["active_qualified_identity_link"] += 1
        elif len(links) > 1:
            counts["ambiguous_identity_link"] += 1

        linked_omega = False
        for score in omega_candidates.get(pid, []):
            allowed, _reason = omega_readiness_decision(
                score, q, links[0] if len(links) == 1 else None
            )
            if allowed:
                linked_omega = True
                break
        if linked_omega:
            matched.add(pid)
            counts["omega_evidence_matched"] += 1
        elif omega_candidates.get(pid):
            counts["omega_stale_or_mismatched"] += 1

    fields = (
        "unscored", "v1_only", "v2_scored_rows",
        "v2_scored_status", "insufficient_evidence",
        "tier_hot", "tier_warm", "tier_cold", "tier_dead",
        "enrichment_evidence_present",
        "enrichment_result_without_evidence",
        "active_qualified_identity_link", "ambiguous_identity_link",
        "omega_evidence_matched", "omega_stale_or_mismatched",
    )
    overall = {field: sum(count[field] for count in per_niche.values()) for field in fields}
    return {
        "schema_version": "empire.lead_scoring_inventory_bridge.v1",
        "mode": "OBSERVE",
        "scoring_coverage_verified_against": "empiredb_qualification_identity_and_omega_rows",
        "prospect_count": len(people),
        "omega_score_rows_scanned": all_omega_score_rows,
        "omega_evidence_matched_unique_prospects": len(matched),
        "omega_probabilities_outcome_calibrated": False,
        "cortex": dict(cortex_snapshot or {"available": False}),
        "engine_registry": [dict(item) for item in ENGINE_REGISTER],
        "counts": overall,
        "by_niche": [
            {"niche": niche, **{field: counters[field] for field in fields}}
            for niche, counters in sorted(per_niche.items())
        ],
        "commercial_authority": "none",
        "model_weight_mutation_authorized": False,
        "outbound_authorized": False,
        "payment_authorized": False,
    }
