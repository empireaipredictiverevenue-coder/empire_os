"""Deterministic proposal-only projection of existing revenue runtime evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import tempfile
from typing import Any, Mapping

from empire_os.agent_web import public_capabilities
from empire_os.a2a_discovery import COMMERCE_CAPABILITIES
from empire_os.predictive_revenue_formula import CORE_FACTORS, predictive_revenue_formula
from empire_os.commercial_product_catalog import assess_catalog_item
from empire_os.revenue_distribution_review import REVIEW_SOURCES, build_human_review_queue
from empire_os.traffic_specialist import review_organic_traffic
from empire_os.conversion_intelligence import (
    CANONICAL_STAGES, ConversionStageEvidence, ConversionSpecialistReview,
    review_conversion_system,
)


OUTPUT = Path("runtime/revenue_distribution/latest.json")
SOURCES = {
    "conversion": "runtime/conversion/latest.json",
    "catalog": "runtime/commercial_catalog/latest.json",
    "radar": "runtime/opportunity_radar/latest.json",
    "buyer_acquisition": "runtime/buyer_acquisition/latest.json",
    "buyer_scout": "runtime/buyer_acquisition/scout_latest.json",
    "buyer_capacity": "runtime/buyer_capacity_readiness/latest.json",
    "exchange": "runtime/commercial_exchange/latest.json",
    "search": "runtime/agent_web/canonical_snapshot.json",
    "aeo": "runtime/search_intelligence/aeo_recovery/latest.json",
    "competitor": "runtime/competitive_intelligence/competitor_search_presence_latest.json",
    "crawler": "runtime/acquisition/latest.json",
}
SUMMARY_FIELDS = {
    "buyer_acquisition": ("demand_gap_count", "product_demand_count"),
    "buyer_scout": ("candidate_count", "verified_budget_candidate_count"),
    "buyer_capacity": ("buyers_seen", "capacity_verified", "fully_activated", "terms_verified"),
    "exchange": ("inventory_count", "overflow_count", "allocation_candidate_count", "buyer_seat_count"),
    "aeo": ("asset_count", "niche_count", "metro_count"),
    "competitor": ("observation_count", "company_with_search_presence_count"),
    "crawler": ("prospect_acquired", "signal_queued"),
}
AUTHORITY_KEYS = ("live_outbound", "paid_traffic", "binding_terms", "payment", "revenue_recognition")
ZERO_CASH_PREFERENCE = ("existing_inventory", "owned_crawlers", "organic_search", "direct_buyer_acquisition", "a2a_discovery", "webmcp_discovery")


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp required")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("timestamp timezone required")
    return stamp.astimezone(timezone.utc)


def _refs(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({v.strip() for v in value if isinstance(v, str) and v.strip()})


def _number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _source(name: str, payload: Any, now: datetime, max_age_seconds: int) -> dict[str, Any]:
    result: dict[str, Any] = {"path": SOURCES[name], "status": "missing_or_invalid", "evidence_refs": [], "observed_at": None}
    if not isinstance(payload, dict) or not payload:
        return result
    try:
        encoded = json.dumps(payload, sort_keys=True, allow_nan=False).encode()
    except (ValueError, TypeError):
        return result
    result["evidence_refs"] = [f"{SOURCES[name]}#sha256={hashlib.sha256(encoded).hexdigest()}"]
    stamp = payload.get("generated_at") or payload.get("observed_at") or payload.get("started_at")
    try:
        age = (now - _time(stamp)).total_seconds()
    except ValueError:
        result["status"] = "unknown_freshness"
        return result
    result["observed_at"] = stamp
    result["status"] = "future_dated" if age < 0 else "stale" if age > max_age_seconds else "available"
    if (payload.get("available") is False or payload.get("ok") is False
            or payload.get("error")
            or str(payload.get("status") or "").lower() in {
                "error", "failed", "unavailable", "producer_unavailable", "blocked",
            }
            or (name == "crawler" and payload.get("returncode", 0) != 0)):
        result["status"] = "producer_unavailable"
    return result


def _prediction(row: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    values = row.get("predictive_revenue_inputs")
    refs = row.get("predictive_revenue_evidence_refs")
    values = values if isinstance(values, dict) else {}
    refs = refs if isinstance(refs, dict) else {}
    inputs, evidence = {}, []
    for key in (*CORE_FACTORS, "ltv_cents"):
        value, links = values.get(key), _refs(refs.get(key))
        if links and _number(value) and (key == "ltv_cents" or value <= 1):
            inputs[key] = value
            evidence.extend(links)
    return predictive_revenue_formula(inputs), sorted(set(evidence))


def _conversion_projection(payload: Any, source: dict[str, Any]) -> dict[str, Any]:
    """Re-review canonical runtime counts, never trust serialized proposals/rates."""
    evidence = []
    blockers = []
    if source["status"] != "available":
        blockers.append(f"conversion:{source['status']}")
    elif payload.get("source") != "canonical_data":
        blockers.append("conversion:canonical_evidence_unavailable")
    else:
        counts, stages = payload.get("counts"), payload.get("stages")
        counts = counts if isinstance(counts, dict) else {}
        stages = stages if isinstance(stages, list) else []
        for stage in CANONICAL_STAGES:
            rows = [r for r in stages if isinstance(r, dict) and r.get("stage") == stage]
            row = counts.get(stage)
            refs = _refs(rows[0].get("evidence_refs")) if len(rows) == 1 else []
            if (not isinstance(row, dict) or not refs
                    or not all(ref.startswith("canonical_data:") for ref in refs)
                    or any(type(row.get(k)) is not int for k in ("entered", "converted"))
                    or not 0 <= row["converted"] <= row["entered"]):
                if row is not None:
                    blockers.append(f"conversion:{stage}:invalid_or_unreferenced_counts")
                continue
            evidence.append(ConversionStageEvidence(
                stage=stage, entered=row["entered"], converted=row["converted"],
                evidence_ref=refs[0], observed_at=source["observed_at"],
            ))
    review: ConversionSpecialistReview = review_conversion_system(evidence)
    result = json.loads(json.dumps(review.as_dict()))
    actions = []
    if review.experiment_candidate:
        stage_review = next(s for s in review.stages if s.stage == review.primary_bottleneck)
        actions.append({
            **review.experiment_candidate,
            "action_type": "review_conversion_bottleneck",
            "evidence_refs": sorted(set(stage_review.evidence_refs) | set(source["evidence_refs"])),
            "proposal_only": True, "execution_authority": "none",
            "total_action_cost_cents": None,
        })
    result.update(actions=actions, action_count=len(actions), blockers=blockers, source=source)
    return result


def build_revenue_distribution(
    snapshots: Mapping[str, Any], *, generated_at: str,
    acquisition_budget_cents: int | None = None, max_age_seconds: int = 86400,
) -> dict[str, Any]:
    """Pure projection; all evidence is input, and no action can be executed."""
    now = _time(generated_at)
    if acquisition_budget_cents is not None and (type(acquisition_budget_cents) is not int or acquisition_budget_cents < 0):
        raise ValueError("acquisition budget must be nonnegative integer cents or unknown")
    if type(max_age_seconds) is not int or max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be a positive integer")
    sources = {name: _source(name, snapshots.get(name), now, max_age_seconds) for name in SOURCES}
    blockers = [f"{name}:{source['status']}" for name, source in sources.items() if source["status"] != "available"]

    def summary(name: str) -> dict[str, Any]:
        source = sources[name]
        data = snapshots.get(name) if source["status"] == "available" else {}
        result = dict(source)
        for field in SUMMARY_FIELDS.get(name, ()):
            value = data.get(field)
            result[field] = value if _number(value) else None
        if name == "search":
            for field in ("markets", "seo_keywords"):
                rows = data.get(field)
                result[f"{field}_observed_count"] = len(rows) if isinstance(rows, list) else None
        return result

    opportunities = []
    catalog = snapshots.get("catalog") if sources["catalog"]["status"] == "available" else {}
    product_rows = catalog.get("products") or []
    product_rows = product_rows if isinstance(product_rows, list) else []
    products: dict[str, list[dict[str, Any]]] = {}
    for product in product_rows:
        if isinstance(product, Mapping) and isinstance(product.get("product_code"), str):
            assessed = assess_catalog_item(product)
            if product.get("binding_terms_ready") is None:
                assessed["binding_terms_ready"] = None
                assessed["readiness_blockers"].append("catalog_readiness_unknown")
            products.setdefault(product["product_code"], []).append(assessed)
    scout = snapshots.get("buyer_scout") if sources["buyer_scout"]["status"] == "available" else {}
    scout_rows = scout.get("candidates") or []
    scout_rows = scout_rows if isinstance(scout_rows, list) else []
    radar = snapshots.get("radar") if sources["radar"]["status"] == "available" else {}
    candidates = radar.get("candidates", [])
    if not isinstance(candidates, list):
        blockers.append("radar:invalid_candidates")
        candidates = []
    keys = [r.get("opportunity_key") for r in candidates if isinstance(r, dict) and isinstance(r.get("opportunity_key"), str)]
    for row in candidates:
        if not isinstance(row, dict):
            blockers.append("radar:invalid_candidate")
            continue
        key, refs = row.get("opportunity_key"), _refs(row.get("evidence_refs"))
        if not isinstance(key, str) or not key.strip() or not refs or keys.count(key) != 1:
            blockers.append("radar:missing_or_ambiguous_identity_or_evidence")
            continue
        prediction, factor_refs = _prediction(row)
        missing = list(prediction.get("missing_fields", []))
        codes = _refs(row.get("products"))
        if isinstance(row.get("offer_key"), str) and row["offer_key"].strip():
            codes = sorted(set(codes + [row["offer_key"].strip()]))
        product_matches = []
        for code in codes:
            matches = products.get(code, [])
            product = matches[0] if len(matches) == 1 else None
            product_matches.append({
                "product_code": code,
                "product_id": product.get("product_id") if product else None,
                "version": product.get("version") if product else None,
                "binding_terms_ready": product["binding_terms_ready"] if product else None,
                "price_basis": product.get("price_basis") if product else None,
                "readiness_blockers": product["readiness_blockers"] if product else ["catalog_product_missing_or_ambiguous"],
                "evidence_refs": sources["catalog"]["evidence_refs"] if product else [],
                "price_accepted": None,
            })
        research_matches = [
            {"domain": candidate.get("domain"),
             "canonical_seed_prospect_id": candidate.get("canonical_seed_prospect_id"),
             "product_codes": sorted(set(codes).intersection(_refs(candidate.get("target_product_codes")))),
             "match_classification": "RESEARCH_FIT_ONLY",
             "evidence_refs": sources["buyer_scout"]["evidence_refs"],
             "demand_verified": False}
            for candidate in scout_rows if isinstance(candidate, Mapping)
            and set(codes).intersection(_refs(candidate.get("target_product_codes")))
        ]
        opportunities.append({
            "opportunity_key": key,
            "product_matches": product_matches,
            "commercial_research_matches": research_matches,
            "product_link_state": "EXPLICIT_PRODUCT_REFERENCE" if codes else "UNKNOWN",
            "evidence_refs": sorted(set(refs + factor_refs + sources["radar"]["evidence_refs"])),
            "canonical_prediction": prediction,
            "expected_canonical_revenue_contribution_cents": prediction.get("predicted_revenue_cents"),
            "missing_evidence": missing,
            "buyer_capacity_verified_for_opportunity": None,
            "payout_cents": None,
        })
    opportunities.sort(key=lambda r: (r["expected_canonical_revenue_contribution_cents"] is None, -(r["expected_canonical_revenue_contribution_cents"] or 0), r["opportunity_key"]))
    actions = []

    def propose(kind: str, channel: str, reason: str, refs: list[str], missing: list[str], opportunity: dict | None = None) -> None:
        actions.append({
            "action_type": kind, "channel": channel, "reason": reason,
            "evidence_refs": refs, "missing_evidence": sorted(set(missing)),
            "expected_canonical_revenue_contribution_cents": opportunity["expected_canonical_revenue_contribution_cents"] if opportunity else None,
            "opportunity_key": opportunity["opportunity_key"] if opportunity else None,
            "authority_required": ["governed_review_before_execution"],
            "proposal_only": True, "execution_authority": "none",
        })

    for opportunity in opportunities:
        propose("complete_opportunity_evidence", "existing_inventory", "Review Radar evidence using the canonical formula; unknown factors require evidence.", opportunity["evidence_refs"], opportunity["missing_evidence"] + ["buyer_identity", "opportunity_buyer_capacity", "commercial_evidence"], opportunity)
    for source, kind, channel, reason, missing in (
        ("exchange", "review_owned_inventory", "existing_inventory", "Review observed Exchange supply without allocating it.", ["current_identity_quality", "opportunity_buyer_capacity"]),
        ("crawler", "prepare_demand_directed_crawler_review", "owned_crawlers", "Review existing crawler state before proposing verified demand targeting.", ["verified_demand_target", "source_provenance"]),
        ("search", "review_organic_search_evidence", "organic_search", "Review observed search coverage for SEO/AEO/GEO evidence gaps.", ["verified_search_gap"]),
        ("aeo", "review_aeo_evidence", "organic_search", "Review the existing AEO census.", ["current_indexation_evidence"]),
        ("competitor", "review_competitor_visibility", "organic_search", "Review observed visibility; visibility does not establish buyer demand.", ["verified_buyer_demand"]),
        ("buyer_acquisition", "prepare_buyer_research", "direct_buyer_acquisition", "Review existing buyer acquisition demand gaps without outreach.", ["verified_buyer_identity", "verified_buyer_demand"]),
    ):
        if sources[source]["status"] == "available":
            propose(kind, channel, reason, sources[source]["evidence_refs"], missing)
    if opportunities:
        for surface in ("a2a", "webmcp"):
            propose("prepare_discovery_review", f"{surface}_discovery", "Review existing discovery capabilities; commercial handoff remains governed.", sources["radar"]["evidence_refs"], ["verified_buyer_match", "commercial_evidence", "opportunity_buyer_capacity"])
    zero_cash = acquisition_budget_cents is None or acquisition_budget_cents == 0
    if zero_cash:
        actions.sort(key=lambda a: ZERO_CASH_PREFERENCE.index(a["channel"]))
    search_intelligence = {name: summary(name) for name in ("search", "aeo", "competitor")}
    organic_growth = {
        "schema_version": "empire.organic_growth.v1",
        "mode": "OBSERVE", "zero_cash_mode": True,
        "paid_traffic_authorized": False, "auto_publishing": False,
        "auto_indexation": False, "live_outbound": False,
        "execution_authority": "none",
        "traffic_specialist": review_organic_traffic(opportunities, search_intelligence),
        "conversion_specialist": _conversion_projection(snapshots.get("conversion"), sources["conversion"]),
    }
    return {
        "schema_version": "empire.revenue_distribution.v1",
        "generated_at": now.isoformat(), "mode": "OBSERVE", "zero_cash_mode": zero_cash,
        "acquisition_budget_cents": acquisition_budget_cents,
        "paid_acquisition_blockers": (["acquisition_budget_unknown"] if acquisition_budget_cents is None else ["acquisition_budget_zero"] if acquisition_budget_cents == 0 else []) + ["founder_authorization_required"],
        "zero_cash_research_ready": bool(actions),
        "demand": {name: summary(name) for name in ("buyer_acquisition", "buyer_scout")},
        "search_intelligence": search_intelligence,
        "organic_growth": organic_growth,
        "supply": {name: summary(name) for name in ("exchange", "crawler")},
        "buyer_capacity": summary("buyer_capacity"),
        "opportunities": opportunities, "distribution_actions": actions,
        "blockers": sorted(set(blockers)), "sources": sources,
        "authority": {key: False for key in AUTHORITY_KEYS},
        "execution_authority": "none", "proposal_only": True,
        "canonical_payment_rail": "USDT/BSC",
        "discovery_surfaces": {
            surface: [cap.key for cap in public_capabilities(surface) if cap.read_only and not cap.consequential]
            for surface in ("webmcp", "a2a")
        },
        "governed_commerce_capabilities": [cap.as_dict() for cap in COMMERCE_CAPABILITIES],
    }


def refresh_revenue_distribution(repo_root: Path, *, generated_at: str | None = None, acquisition_budget_cents: int | None = None) -> dict[str, Any]:
    """Read fixed producer artifacts and atomically write only our own snapshot."""
    snapshots = {}
    for name, relative in SOURCES.items():
        path = repo_root / relative
        try:
            snapshots[name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            snapshots[name] = None
    payload = build_revenue_distribution(snapshots, generated_at=generated_at or datetime.now(timezone.utc).isoformat(), acquisition_budget_cents=acquisition_budget_cents)
    review = {}
    for name, relative in REVIEW_SOURCES.items():
        try:
            review[name] = json.loads((repo_root / relative).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            review[name] = None
    payload.update(build_human_review_queue(snapshots, review, payload["opportunities"]))
    output = repo_root / OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, prefix=".latest-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return payload
