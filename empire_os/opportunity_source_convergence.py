"""Truth-preserving adapters from Empire intelligence into Opportunity Radar.

This module is intentionally transformation-only.

It does not:
- execute work,
- mutate commercial state,
- recognize revenue,
- grant authority,
- activate idle assets,
- send outreach,
- move funds.

V1 begins with canonical Revenue Pulse V3 observed conversion leaks.
Additional source families can be added only when their evidence contracts
are explicit enough to preserve source truth without inference.
"""

from __future__ import annotations

from hashlib import sha256
from math import isfinite
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "empire.opportunity_source_convergence.v1"
REVENUE_PULSE_SCHEMA = "empire.revenue-pulse.v3"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _refs(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []

    output: list[str] = []
    seen: set[str] = set()

    for value in values:
        ref = _text(value)
        if ref and ref not in seen:
            seen.add(ref)
            output.append(ref)

    return output


def _stable_key(parts: Sequence[str]) -> str:
    raw = "|".join(parts).encode("utf-8")
    return sha256(raw).hexdigest()[:24]


def _authority_none(candidate: dict[str, Any]) -> dict[str, Any]:
    """Radar-facing source evidence can never carry execution authority."""
    candidate.update(
        {
            "execution_authority": "none",
            "outreach_authority": "none",
            "calls_authority": "none",
            "traffic_authority": "none",
            "commercial_authority": "none",
            "payment_authority": "none",
            "revenue_recognition_authority": "none",
            "commercial_ready": False,
            "revenue_inferred": False,
        }
    )
    return candidate


def revenue_pulse_leak_candidates(
    payload: Mapping[str, Any] | None,
    *,
    tenant_id: str,
) -> list[dict[str, Any]]:
    """Adapt observed Revenue Pulse V3 conversion gaps into opportunities.

    Only `observed_zero_conversion` rows are accepted.

    Absence of conversion is preserved as an observed funnel condition.
    It is not converted into predicted lost revenue, customer intent,
    commercial readiness, or execution authority.
    """
    tenant = _text(tenant_id)
    if not tenant:
        raise ValueError("tenant_id required")

    if not isinstance(payload, Mapping):
        return []

    if payload.get("schema_version") != REVENUE_PULSE_SCHEMA:
        return []

    if payload.get("mode") != "OBSERVE":
        return []

    if payload.get("execution_authority") != "none":
        return []

    if payload.get("execution_allowed") is not False:
        return []

    leak_detection = payload.get("leak_detection")
    if not isinstance(leak_detection, Mapping):
        return []

    if leak_detection.get("method") != "observed_zero_conversion_only":
        return []

    if leak_detection.get("prediction") is not False:
        return []

    evidence_refs = _refs(payload.get("evidence_refs"))
    if not evidence_refs:
        return []

    raw_items = leak_detection.get("items")
    if not isinstance(raw_items, list):
        return []

    output: list[dict[str, Any]] = []

    for raw in raw_items:
        if not isinstance(raw, Mapping):
            continue

        from_stage = _text(raw.get("from_stage"))
        to_stage = _text(raw.get("to_stage"))

        try:
            entered = int(raw.get("entered"))
            converted = int(raw.get("converted"))
        except (TypeError, ValueError):
            continue

        if not from_stage or not to_stage:
            continue

        if entered <= 0 or converted != 0:
            continue

        if raw.get("state") != "observed_zero_conversion":
            continue

        if raw.get("prediction") is not False:
            continue

        key = (
            "revenue_leak_"
            + _stable_key(
                (
                    tenant,
                    from_stage,
                    to_stage,
                    str(entered),
                    str(converted),
                    *sorted(evidence_refs),
                )
            )
        )

        candidate = {
            "schema_version": SCHEMA_VERSION,
            "source": "revenue_pulse",
            "source_kind": "revenue_leak",
            "tenant_id": tenant,
            "opportunity_key": key,
            "evidence_refs": list(evidence_refs),
            "observed_condition": {
                "kind": "zero_conversion_gap",
                "from_stage": from_stage,
                "to_stage": to_stage,
                "entered": entered,
                "converted": converted,
                "conversion_rate": 0.0,
                "state": "observed_zero_conversion",
            },
            "prediction": False,
            "predicted_revenue_cents": None,
            "recognized_revenue_cents": None,
            "estimated_recovery_value_cents": None,
            "confidence": None,
            "opportunity_factory_ready": False,
            "requires_evidence_completion": True,
            "recommended_next_action": "investigate_observed_conversion_gap",
            "automatic_research_allowed": True,
            "automatic_analysis_allowed": True,
            "automatic_planning_allowed": True,
            "automatic_external_execution_allowed": False,
        }

        output.append(_authority_none(candidate))

    output.sort(key=lambda row: row["opportunity_key"])
    return output


def build_source_convergence_snapshot(
    *,
    tenant_id: str,
    revenue_pulse: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a bounded OBSERVE-only source-convergence snapshot."""
    tenant = _text(tenant_id)
    if not tenant:
        raise ValueError("tenant_id required")

    leak_candidates = revenue_pulse_leak_candidates(
        revenue_pulse,
        tenant_id=tenant,
    )

    candidates = list(leak_candidates)

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "OBSERVE",
        "tenant_id": tenant,
        "candidate_count": len(candidates),
        "source_counts": {
            "revenue_leak": len(leak_candidates),
        },
        "candidates": candidates,
        "automatic_research_allowed": True,
        "automatic_analysis_allowed": True,
        "automatic_planning_allowed": True,
        "automatic_external_execution_allowed": False,
        "execution_authority": "none",
        "outreach_authority": "none",
        "calls_authority": "none",
        "traffic_authority": "none",
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
    }



def _valid_score(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not isfinite(result) or not 0.6 <= result <= 1.0:
        return None
    return result



def _source_is_fresh(stamp: Any, *, now: datetime) -> bool:
    if not isinstance(stamp, str):
        return False
    try:
        observed = datetime.fromisoformat(
            stamp.replace("Z", "+00:00")
        )
        if observed.tzinfo is None or observed.utcoffset() is None:
            return False
        age = (now - observed).total_seconds()
        return 0 <= age <= 86400
    except (ValueError, TypeError, OverflowError):
        return False


def idle_asset_candidates(
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    tenant_id: str,
    evidence_scope: str,
) -> list[dict[str, Any]]:
    """Observe enriched idle assets; never promote or activate them."""
    tenant = _text(tenant_id)
    scope = _text(evidence_scope)
    if not tenant or not scope:
        raise ValueError("tenant_id and evidence_scope required")

    output = []
    seen: set[str] = set()
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        if row.get("tenant_id") != tenant:
            continue
        if not _source_is_fresh(
            row.get("observed_at"),
            now=datetime.now(timezone.utc),
        ):
            continue
        compound_id = _text(row.get("compound_id"))
        if not compound_id:
            continue
        score = _valid_score(row.get("lead_gen_score"))
        if score is None or compound_id in seen:
            continue
        seen.add(compound_id)

        key = "idle_asset_" + _stable_key(
            (tenant, compound_id)
        )
        output.append(_authority_none({
            "schema_version": SCHEMA_VERSION,
            "source": "idle_asset_enriched",
            "source_kind": "idle_asset",
            "tenant_id": tenant,
            "opportunity_key": key,
            "evidence_refs": [
                f"{scope}:idle_asset_enriched:{compound_id}"
            ],
            "observed_condition": {
                "compound_id": compound_id,
                "business_name": _text(row.get("business_name")),
                "industry": _text(row.get("industry")),
                "lead_gen_score": score,
            },
            "prediction": False,
            "predicted_revenue_cents": None,
            "recognized_revenue_cents": None,
            "estimated_recovery_value_cents": None,
            "opportunity_factory_ready": False,
            "requires_evidence_completion": True,
            "recommended_next_action": "review_idle_asset_evidence",
            "automatic_external_execution_allowed": False,
        }))
    return sorted(output, key=lambda x: x["opportunity_key"])



def _valid_gap_record(category: str, raw: Mapping[str, Any]) -> bool:
    """Reject unsupported, incomplete or invalid source measurements."""
    if category in ("hot_gaps", "unsaturated"):
        occupancy = raw.get("occupancy")
        leads = raw.get("leads")

        if type(occupancy) not in (int, float):
            return False
        if not isfinite(occupancy) or not 0 <= occupancy <= 1:
            return False

        if type(leads) is not int or leads < 0:
            return False

        return bool(_text(raw.get("niche_metro")))

    if category == "waste_lanes":
        return bool(_text(raw.get("lane_id")))

    if category == "waste_agents":
        return bool(_text(raw.get("agent")))

    if category == "waste_hotspots":
        return bool(_text(raw.get("scope")))

    return False


def predictive_cloud_gap_candidates(
    report: Mapping[str, Any] | None,
    *,
    tenant_id: str,
    evidence_ref: str,
) -> list[dict[str, Any]]:
    """Adapt observed market/waste indicators, never projected revenue."""
    tenant = _text(tenant_id)
    ref = _text(evidence_ref)
    if not tenant or not ref:
        raise ValueError("tenant_id and evidence_ref required")
    if not isinstance(report, Mapping):
        return []
    if report.get("schema_version") != "predictive_cloud.v2":
        return []
    if report.get("tenant_id") != tenant:
        return []
    if not _source_is_fresh(
        report.get("timestamp"),
        now=datetime.now(timezone.utc),
    ):
        return []

    intelligence = report.get("intelligence")
    if not isinstance(intelligence, Mapping):
        return []

    output = []
    seen: set[str] = set()

    for family, categories in (
        ("market_gap", ("hot_gaps", "unsaturated")),
        ("idle_waste", ("waste_lanes", "waste_agents", "waste_hotspots")),
    ):
        source = intelligence.get(
            "market_gaps" if family == "market_gap" else "waste"
        )
        if not isinstance(source, Mapping):
            continue

        for category in categories:
            records = source.get(category)
            if not isinstance(records, list):
                continue

            for raw in records:
                if not isinstance(raw, Mapping):
                    continue
                if not _valid_gap_record(category, raw):
                    continue
                if family == "market_gap":
                    identity = _text(raw.get("niche_metro"))
                    if not identity:
                        continue
                else:
                    identity = _text(
                        raw.get("lane_id")
                        or raw.get("agent")
                        or raw.get("scope")
                    )
                    if not identity:
                        continue

                key = family + "_" + _stable_key(
                    (tenant, category, identity)
                )
                if key in seen:
                    continue
                seen.add(key)

                output.append(_authority_none({
                    "schema_version": SCHEMA_VERSION,
                    "source": "predictive_cloud_v2",
                    "source_kind": family,
                    "tenant_id": tenant,
                    "opportunity_key": key,
                    "evidence_refs": [ref],
                    "observed_condition": {
                        "category": category,
                        "identity": identity,
                        "source_record": dict(raw),
                    },
                    "prediction": False,
                    "predicted_revenue_cents": None,
                    "recognized_revenue_cents": None,
                    "estimated_recovery_value_cents": None,
                    "opportunity_factory_ready": False,
                    "requires_evidence_completion": True,
                    "recommended_next_action": "verify_source_indicator",
                    "automatic_external_execution_allowed": False,
                }))

    return sorted(output, key=lambda x: x["opportunity_key"])

# ---------------------------------------------------------------------------
# Economic Signal Fabric -> Opportunity Convergence
# ---------------------------------------------------------------------------

_ECONOMIC_SIGNAL_OPPORTUNITY_TYPES = {
    "revenue_leak": "revenue_recovery",
    "idle_asset": "idle_asset_activation",
    "market_gap": "market_gap",
    "idle_waste": "waste_recovery",
}


def economic_signal_candidates(
    signals: Iterable[Mapping[str, Any]],
    *,
    tenant_id: str,
) -> list[dict[str, Any]]:
    """Convert validated Economic Signal Fabric evidence to opportunities.

    Input is expected to have already passed Economic Signal Fabric validation.
    This boundary still independently fails closed on provenance and authority.

    No economics are invented here. Evidence proves an observed condition,
    not buyer demand, commercial readiness, payout, revenue or permission.
    """

    tenant = str(tenant_id or "").strip()
    if not tenant:
        raise ValueError("tenant_id required")

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    for signal in signals:
        if not isinstance(signal, Mapping):
            continue

        if signal.get("schema_version") != "empire.economic-signal.v1":
            continue
        if signal.get("tenant_id") != tenant:
            continue
        if not str(signal.get("tenant_binding_ref") or "").strip():
            continue
        if signal.get("truth_class") != "OBSERVED":
            continue
        if signal.get("data_backend") != "empiredb":
            continue

        # Every authority must still be absent at this boundary.
        if any(
            signal.get(field) != "none"
            for field in (
                "execution_authority",
                "outreach_authority",
                "calls_authority",
                "traffic_authority",
                "commercial_authority",
                "payment_authority",
                "revenue_recognition_authority",
            )
        ):
            continue

        signal_type = str(signal.get("signal_type") or "").strip()
        opportunity_type = _ECONOMIC_SIGNAL_OPPORTUNITY_TYPES.get(
            signal_type
        )
        if opportunity_type is None:
            continue

        signal_id = str(signal.get("signal_id") or "").strip()
        entity_id = str(signal.get("entity_id") or "").strip()
        source_id = str(signal.get("source_id") or "").strip()
        observed_at = str(signal.get("observed_at") or "").strip()

        if not (
            signal_id.startswith("economic_signal_")
            and entity_id
            and source_id
            and observed_at
        ):
            continue

        refs = signal.get("evidence_refs")
        if (
            not isinstance(refs, list)
            or not refs
            or any(not str(ref or "").strip() for ref in refs)
        ):
            continue

        payload = signal.get("payload")
        if not isinstance(payload, Mapping):
            continue

        # Deterministic identity follows the canonical signal identity.
        candidate_key = f"economic_opportunity_{signal_id}"

        if candidate_key in seen:
            continue
        seen.add(candidate_key)

        candidates.append({
            "schema_version": "empire.opportunity-source.v1",
            "candidate_key": candidate_key,
            "tenant_id": tenant,
            "entity_id": entity_id,
            "source_id": source_id,
            "source_signal_id": signal_id,
            "source_family": "economic_signal_fabric",
            "source_signal_type": signal_type,
            "opportunity_type": opportunity_type,
            "observed_at": observed_at,
            "evidence_refs": list(dict.fromkeys(
                str(ref).strip() for ref in refs
            )),
            "strength": signal.get("strength"),
            "confidence": signal.get("confidence"),
            "source_payload": dict(payload),

            # Observation != economics.
            "buyer_demand_verified": False,
            "commercial_readiness_verified": False,
            "economics_verified": False,
            "payout_cents": None,
            "expected_revenue_cents": None,
            "recognized_revenue_cents": None,

            # Evidence is complete enough for opportunity research, not
            # autonomous commercial progression.
            "evidence_complete": True,
            "factory_ready": False,
            "review_required": True,

            "execution_authority": "none",
            "outreach_authority": "none",
            "calls_authority": "none",
            "traffic_authority": "none",
            "commercial_authority": "none",
            "payment_authority": "none",
            "revenue_recognition_authority": "none",
        })

    return candidates
