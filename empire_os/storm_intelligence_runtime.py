"""Predictive Storm Intelligence runtime.

Canonical OBSERVE-only materializer for evidence-grounded storm intelligence.

Pipeline:
    real source observation
    -> canonical StormEvent
    -> evidenced AffectedSubject
    -> evidenced BuyerProductMatch
    -> assess_storm_product
    -> Storm opportunity
    -> atomic runtime/storm_opportunity/latest.json

This runtime does not infer damage, demand, buyer intent, pricing, economics,
revenue or execution authority. Missing evidence remains missing.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from empire_os.storm_opportunity_bridge import (
    build_storm_opportunity_snapshot,
    storm_assessment_to_opportunity,
)
from empire_os.storm_product_integration import (
    AffectedSubject,
    BuyerProductMatch,
    Evidence,
    ReadinessGate,
    ReadinessProof,
    StormEvent,
    SubjectKind,
    TruthClass,
    assess_storm_product,
)


SNAPSHOT_RELATIVE_PATH = Path("runtime/storm_opportunity/latest.json")
SCHEMA_VERSION = "empire.storm_intelligence_runtime.v1"

_SEVERITIES = {"minor", "moderate", "severe", "extreme"}


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None and value.utcoffset() is not None else None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def _unit(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if 0.0 <= number <= 1.0 else None


def _truth(value: Any) -> TruthClass | None:
    try:
        return TruthClass(_text(value).upper())
    except ValueError:
        return None


def _kind(value: Any) -> SubjectKind | None:
    try:
        return SubjectKind(_text(value).lower())
    except ValueError:
        return None


def _evidence(
    rows: Any,
    *,
    tenant_id: str,
) -> tuple[Evidence, ...]:
    if not isinstance(rows, (list, tuple)):
        return ()

    items: list[Evidence] = []
    identities: set[tuple[str, str]] = set()

    for row in rows:
        if not isinstance(row, Mapping):
            continue

        row_tenant = _text(row.get("tenant_id"))
        ref = _text(row.get("ref") or row.get("evidence_ref"))
        source = _text(row.get("source"))
        observed_at = _time(row.get("observed_at"))
        valid_until = _time(row.get("valid_until"))

        if (
            row_tenant != tenant_id
            or not ref
            or not source
            or observed_at is None
            or valid_until is None
            or valid_until <= observed_at
        ):
            continue

        identity = (source.casefold(), ref)
        if identity in identities:
            continue
        identities.add(identity)

        items.append(
            Evidence(
                tenant_id=tenant_id,
                ref=ref,
                source=source,
                observed_at=observed_at,
                valid_until=valid_until,
            )
        )

    return tuple(items)


def canonical_event_from_row(row: Mapping[str, Any]) -> StormEvent:
    tenant_id = _text(row.get("tenant_id"))
    event_id = _text(row.get("event_id"))
    event_type = _text(row.get("event_type"))
    severity = _text(row.get("severity")).lower()
    starts_at = _time(row.get("starts_at"))
    ends_at = _time(row.get("ends_at"))
    truth_class = _truth(row.get("truth_class"))
    evidence = _evidence(row.get("evidence"), tenant_id=tenant_id)

    if not tenant_id or not event_id or not event_type:
        raise ValueError("storm event identity required")
    if severity not in _SEVERITIES:
        raise ValueError("supported storm severity required")
    if starts_at is None or ends_at is None:
        raise ValueError("timezone-aware event interval required")
    if truth_class not in (TruthClass.OBSERVED, TruthClass.FORECAST):
        raise ValueError("storm event truth class required")
    if not evidence:
        raise ValueError("storm event evidence required")

    return StormEvent(
        tenant_id=tenant_id,
        event_id=event_id,
        event_type=event_type,
        severity=severity,
        starts_at=starts_at,
        ends_at=ends_at,
        truth_class=truth_class,
        evidence=evidence,
    )


def canonical_subject_from_row(
    row: Mapping[str, Any],
    *,
    event: StormEvent,
) -> AffectedSubject:
    tenant_id = _text(row.get("tenant_id"))
    event_id = _text(row.get("event_id"))
    canonical_id = _text(row.get("canonical_id"))
    niche = _text(row.get("niche"))
    territory_id = _text(row.get("territory_id"))
    kind = _kind(row.get("kind"))
    confidence = _unit(row.get("confidence"))
    territory_overlap = _unit(row.get("territory_overlap"))
    evidence = _evidence(row.get("evidence"), tenant_id=tenant_id)

    if tenant_id != event.tenant_id:
        raise ValueError("subject tenant mismatch")
    if event_id != event.event_id:
        raise ValueError("subject event mismatch")
    if not canonical_id or not niche or not territory_id or kind is None:
        raise ValueError("canonical subject identity required")
    if confidence is None or territory_overlap is None:
        raise ValueError("subject confidence and territory overlap required")
    if not evidence:
        raise ValueError("subject evidence required")

    return AffectedSubject(
        tenant_id=tenant_id,
        event_id=event_id,
        canonical_id=canonical_id,
        kind=kind,
        niche=niche,
        territory_id=territory_id,
        confidence=confidence,
        territory_overlap=territory_overlap,
        evidence=evidence,
    )


def canonical_match_from_row(
    row: Mapping[str, Any],
    *,
    event: StormEvent,
) -> BuyerProductMatch:
    tenant_id = _text(row.get("tenant_id"))
    buyer_id = _text(row.get("buyer_id"))
    product_id = _text(row.get("product_id"))
    niche = _text(row.get("niche"))
    territory_id = _text(row.get("territory_id"))
    evidence = _evidence(row.get("evidence"), tenant_id=tenant_id)

    if tenant_id != event.tenant_id:
        raise ValueError("buyer product tenant mismatch")
    if not buyer_id or not product_id or not niche or not territory_id:
        raise ValueError("buyer product identity required")
    if not evidence:
        raise ValueError("buyer product evidence required")

    return BuyerProductMatch(
        tenant_id=tenant_id,
        buyer_id=buyer_id,
        product_id=product_id,
        niche=niche,
        territory_id=territory_id,
        evidence=evidence,
    )


def readiness_from_rows(
    rows: Any,
    *,
    scope: tuple[str, str, str, str, str],
) -> tuple[ReadinessProof, ...]:
    if not isinstance(rows, (list, tuple)):
        return ()

    proofs: list[ReadinessProof] = []
    seen: set[ReadinessGate] = set()

    for row in rows:
        if not isinstance(row, Mapping):
            continue

        try:
            gate = ReadinessGate(_text(row.get("gate")))
        except ValueError:
            continue

        supplied_scope = row.get("scope")
        if (
            not isinstance(supplied_scope, (list, tuple))
            or tuple(_text(v) for v in supplied_scope) != scope
            or gate in seen
        ):
            continue

        evidence = _evidence(row.get("evidence"), tenant_id=scope[0])
        if not evidence:
            continue

        seen.add(gate)
        proofs.append(
            ReadinessProof(
                gate=gate,
                scope=scope,
                evidence=evidence,
            )
        )

    return tuple(proofs)


def _next_best_evidence(reason: str) -> str:
    mapping = {
        "invalid_event": "canonical_event_evidence_required",
        "invalid_subject": "canonical_subject_evidence_required",
        "invalid_match": "buyer_product_evidence_required",
        "subject_missing": "canonical_subject_evidence_required",
        "match_missing": "buyer_product_evidence_required",
    }
    return mapping.get(reason, "readiness_evidence_required")


def build_storm_intelligence_runtime(
    *,
    events: Iterable[Mapping[str, Any]] = (),
    subjects: Iterable[Mapping[str, Any]] = (),
    matches: Iterable[Mapping[str, Any]] = (),
    readiness: Iterable[Mapping[str, Any]] = (),
    source_rejections: Iterable[Mapping[str, Any]] = (),
    impact_evidence: Iterable[Mapping[str, Any]] = (),
    impact_policy=None,
    future_state_forecasts=(),
    forecast_origin_policy=None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware runtime clock required")

    event_rows = list(events)
    subject_rows = list(subjects)
    match_rows = list(matches)
    readiness_rows = list(readiness)

    diagnostics: dict[str, Any] = {
        "events_seen": len(event_rows),
        "events_valid": 0,
        "events_rejected": 0,
        "events_deduplicated": 0,
        "subjects_considered": 0,
        "subjects_supported": 0,
        "matches_considered": 0,
        "assessments_completed": 0,
        "opportunities_emitted": 0,
        "blocked_count": 0,
        "evidence_conflict_count": 0,
        "source_health": "UNKNOWN",
        "rejections": [],
        "next_best_evidence": [],
    }

    from empire_os.real_world_event_intelligence import (
        replay_source_evidence, normalized_event_evidence, assess_event_truth,
    )
    normalized = {}
    truth_rejections = list(source_rejections)[:100]
    for index, row in enumerate(event_rows):
        if not isinstance(row, Mapping) or "event_truth_evidence" not in row:
            continue
        try:
            ev = replay_source_evidence(row["event_truth_evidence"])
            key = (ev.source, ev.source_record_id, ev.raw_evidence_hash)
            existing = normalized.get(key)
            if existing is None or ev.retrieved_at < existing.retrieved_at:
                normalized[key] = ev
        except (ValueError, TypeError, KeyError, AttributeError):
            truth_rejections.append({"index": index, "reason": "invalid_normalized_evidence"})
    retained = [normalized[key] for key in sorted(normalized)[-100:]]
    canonical_events: dict[tuple[str, str], StormEvent] = {}
    conflicted_events = set()
    event_hashes = {}

    for index, row in enumerate(event_rows):
        if not isinstance(row, Mapping):
            diagnostics["events_rejected"] += 1
            diagnostics["rejections"].append(
                {"kind": "event", "index": index, "reason": "invalid_event"}
            )
            continue

        try:
            if "event_truth_evidence" in row:
                replay_source_evidence(row["event_truth_evidence"])
            event = canonical_event_from_row(row)
        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            diagnostics["events_rejected"] += 1
            diagnostics["rejections"].append(
                {
                    "kind": "event",
                    "index": index,
                    "reason": "invalid_event",
                    "detail": str(exc),
                }
            )
            continue

        identity = (event.tenant_id, event.event_id)
        if identity in conflicted_events:
            continue
        existing = canonical_events.get(identity)

        if existing is not None:
            diagnostics["events_deduplicated"] += 1
            evidence_hash = row.get("event_truth_evidence", {}).get("raw_evidence_hash")
            if existing != event or event_hashes.get(identity) != evidence_hash:
                diagnostics["evidence_conflict_count"] += 1
                canonical_events.pop(identity, None)
                conflicted_events.add(identity)
                diagnostics["rejections"].append(
                    {
                        "kind": "event",
                        "event_id": event.event_id,
                        "reason": "conflicting_event_evidence",
                    }
                )
            continue

        canonical_events[identity] = event
        event_hashes[identity] = row.get("event_truth_evidence", {}).get("raw_evidence_hash")

    diagnostics["events_valid"] = len(canonical_events)

    subjects_by_event: dict[tuple[str, str], list[AffectedSubject]] = {}
    for index, row in enumerate(subject_rows):
        diagnostics["subjects_considered"] += 1
        if not isinstance(row, Mapping):
            diagnostics["rejections"].append(
                {"kind": "subject", "index": index, "reason": "invalid_subject"}
            )
            continue

        identity = (_text(row.get("tenant_id")), _text(row.get("event_id")))
        event = canonical_events.get(identity)
        if event is None:
            diagnostics["rejections"].append(
                {"kind": "subject", "index": index, "reason": "subject_missing_event"}
            )
            continue

        try:
            subject = canonical_subject_from_row(row, event=event)
        except (TypeError, ValueError) as exc:
            diagnostics["rejections"].append(
                {
                    "kind": "subject",
                    "index": index,
                    "reason": "invalid_subject",
                    "detail": str(exc),
                }
            )
            continue

        subjects_by_event.setdefault(identity, []).append(subject)
        diagnostics["subjects_supported"] += 1

    matches_by_tenant: dict[str, list[BuyerProductMatch]] = {}
    for index, row in enumerate(match_rows):
        diagnostics["matches_considered"] += 1
        if not isinstance(row, Mapping):
            diagnostics["rejections"].append(
                {"kind": "match", "index": index, "reason": "invalid_match"}
            )
            continue

        tenant_id = _text(row.get("tenant_id"))
        event = next(
            (item for (tenant, _), item in canonical_events.items() if tenant == tenant_id),
            None,
        )
        if event is None:
            diagnostics["rejections"].append(
                {"kind": "match", "index": index, "reason": "match_missing_event"}
            )
            continue

        try:
            match = canonical_match_from_row(row, event=event)
        except (TypeError, ValueError) as exc:
            diagnostics["rejections"].append(
                {
                    "kind": "match",
                    "index": index,
                    "reason": "invalid_match",
                    "detail": str(exc),
                }
            )
            continue

        matches_by_tenant.setdefault(tenant_id, []).append(match)

    opportunities: list[dict[str, Any]] = []
    seen_scopes: set[tuple[str, str, str, str, str]] = set()

    for identity in sorted(canonical_events):
        event = canonical_events[identity]
        event_subjects = subjects_by_event.get(identity, [])

        if not event_subjects:
            diagnostics["blocked_count"] += 1
            diagnostics["next_best_evidence"].append(
                {
                    "tenant_id": event.tenant_id,
                    "event_id": event.event_id,
                    "required": "canonical_subject_evidence_required",
                }
            )
            continue

        tenant_matches = matches_by_tenant.get(event.tenant_id, [])

        for subject in event_subjects:
            compatible = [
                match
                for match in tenant_matches
                if match.niche == subject.niche
                and match.territory_id == subject.territory_id
            ]

            if not compatible:
                diagnostics["blocked_count"] += 1
                diagnostics["next_best_evidence"].append(
                    {
                        "tenant_id": event.tenant_id,
                        "event_id": event.event_id,
                        "subject_id": subject.canonical_id,
                        "required": "buyer_product_evidence_required",
                    }
                )
                continue

            for match in compatible:
                scope = (
                    event.tenant_id,
                    event.event_id,
                    subject.canonical_id,
                    match.buyer_id,
                    match.product_id,
                )

                if scope in seen_scopes:
                    continue
                seen_scopes.add(scope)

                proofs = readiness_from_rows(readiness_rows, scope=scope)

                try:
                    assessment = assess_storm_product(
                        event,
                        subject,
                        match,
                        now=now,
                        proofs=proofs,
                    )
                    opportunity = storm_assessment_to_opportunity(
                        event,
                        subject,
                        assessment,
                    )
                except (TypeError, ValueError) as exc:
                    diagnostics["blocked_count"] += 1
                    diagnostics["rejections"].append(
                        {
                            "kind": "assessment",
                            "scope": list(scope),
                            "reason": "assessment_rejected",
                            "detail": str(exc),
                        }
                    )
                    continue

                opportunity["event_importance"] = {
                    "state": (
                        "MODELED"
                        if assessment.score is not None
                        else "BLOCKED"
                    ),
                    "truth_class": "INFERRED",
                }
                opportunity["economic_opportunity"] = {
                    "state": "UNKNOWN",
                    "expected_revenue_value_cents": None,
                }
                opportunity["commercial_readiness"] = {
                    "state": "BLOCKED",
                    "commercial_ready": False,
                }
                opportunity["exposure"] = {
                    "state": "INFERRED",
                    "damage_verified": False,
                    "confidence": subject.confidence,
                    "territory_overlap": subject.territory_overlap,
                }

                opportunities.append(opportunity)
                diagnostics["assessments_completed"] += 1

                if assessment.blockers:
                    diagnostics["blocked_count"] += 1
                    diagnostics["next_best_evidence"].append(
                        {
                            "tenant_id": event.tenant_id,
                            "event_id": event.event_id,
                            "subject_id": subject.canonical_id,
                            "buyer_id": match.buyer_id,
                            "product_id": match.product_id,
                            "required": "readiness_evidence_required",
                            "blockers": list(assessment.blockers),
                        }
                    )

    snapshot = build_storm_opportunity_snapshot(
        opportunities,
        generated_at=now.isoformat(),
    )

    diagnostics["opportunities_emitted"] = snapshot["candidate_count"]
    diagnostics["source_health"] = (
        "HEALTHY"
        if diagnostics["events_valid"] > 0
        else ("DEGRADED" if diagnostics["events_seen"] > 0 else "NO_DATA")
    )
    diagnostics["last_successful_run"] = now.isoformat()

    groups = {}
    for ev in retained:
        groups.setdefault((ev.source, ev.source_record_id), []).append(ev)
    from dataclasses import asdict
    snapshot["event_truth"] = {
        "schema_version": "empire.event_truth.v1",
        "evidence": [normalized_event_evidence(ev) for ev in retained],
        "assessments": [asdict(assess_event_truth(tuple(groups[key]))) for key in sorted(groups)],
        "rejections": truth_rejections[:100],
        "retention_limit": 100,
        "omitted_count": max(0, len(normalized) - 100),
    }
    from empire_os.real_world_exposure_graph import build_exposure_graph
    def exposure_rows(rows, field, identity):
        for row in rows:
            if not isinstance(row, Mapping) or field not in row:
                continue
            item = row[field]
            if (not isinstance(item, Mapping)
                    or item.get("tenant_id") != row.get("tenant_id")
                    or item.get(identity) != row.get(identity)):
                yield {}  # Bounded generic rejection, without leaking source data.
            else:
                yield item

    exposure_graph = build_exposure_graph(
        exposure_rows(event_rows, "geographic_footprint", "event_id"),
        exposure_rows(subject_rows, "exposure_subject", "subject_id"),
    )
    snapshot["exposure_graph"] = exposure_graph.as_dict()
    from empire_os.real_world_impact_intelligence import assess_impact, MAX_EVIDENCE
    from itertools import islice
    # Alerts/intersections never become impact evidence. Only explicit normalized records enter.
    impact_rows = list(islice(iter(impact_evidence), MAX_EVIDENCE + 1))
    impact_rejections = set()
    if len(impact_rows) > MAX_EVIDENCE:
        impact_rows = []
        impact_rejections.add("evidence_batch_limit")
    by_tenant = {}
    for row in impact_rows:
        if (not isinstance(row, Mapping)
                or (_text(row.get("tenant_id")), _text(row.get("event_id"))) not in canonical_events):
            impact_rejections.add("impact_missing_canonical_event")
            continue
        by_tenant.setdefault(row["tenant_id"], []).append(row)
    impact_tenants = sorted({tenant for tenant, _ in canonical_events})
    if len(impact_tenants) > MAX_EVIDENCE:
        impact_tenants = []
        impact_rejections.add("tenant_batch_limit")
    impact_assessments = [assess_impact(
        by_tenant.get(tenant, ()), tenant_id=tenant, now=now, policy=impact_policy,
        exposures=(edge for edge in exposure_graph.relationships if edge.tenant_id == tenant),
    ).as_dict() for tenant in impact_tenants]
    snapshot["impact_intelligence"] = {
        "schema_version": "empire.real_world_impact.v1",
        "impact_evidence_count": sum(a["impact_evidence_count"] for a in impact_assessments),
        "assessments": impact_assessments,
        "rejections": sorted(impact_rejections),
    }
    from empire_os.real_world_future_state_intelligence import (
        build_future_state_snapshot, ForecastOriginPolicy, MAX_FORECASTS,
    )
    # Explicit model outputs only. NWS severity/exposure never synthesizes forecasts.
    future_rows = list(islice(iter(future_state_forecasts), MAX_FORECASTS + 1))
    future_rejections = set()
    if len(future_rows) > MAX_FORECASTS:
        future_rows = []
        future_rejections.add("forecast_batch_limit")
    future_by_tenant = {}
    for row in future_rows:
        if (not isinstance(row, Mapping)
                or not isinstance(row.get("tenant_id"), str)
                or not isinstance(row.get("event_id"), str)
                or (row.get("tenant_id"), row.get("event_id")) not in canonical_events):
            future_rejections.add("forecast_missing_canonical_event")
            continue
        future_by_tenant.setdefault(row["tenant_id"], []).append(row)
    future_snapshots = []
    for tenant in impact_tenants:
        upstream = assess_impact(
            by_tenant.get(tenant, ()), tenant_id=tenant, now=now, policy=impact_policy,
            exposures=(edge for edge in exposure_graph.relationships if edge.tenant_id == tenant),
        )
        future_snapshots.append(build_future_state_snapshot(
            future_by_tenant.get(tenant, ()), assessment=upstream, generated_at=now,
            policy=forecast_origin_policy or ForecastOriginPolicy(),
        ))
    snapshot["future_state_intelligence"] = {
        "schema_version": "empire.real_world_future_state.v1",
        "forecast_count": sum(s["forecast_count"] for s in future_snapshots),
        "assessments": future_snapshots,
        "rejections": sorted(future_rejections),
    }
    from empire_os.real_world_decision_intelligence import build_storm_decision_surface
    snapshot["decision_intelligence"] = build_storm_decision_surface(
        future_snapshots, canonical_events.keys(), as_of=now,
    )
    from empire_os.storm_opportunity_bridge import decision_opportunity_provenance
    decision_sources = {}
    for decision_snapshot in snapshot["decision_intelligence"]["decisions"]:
        context = decision_snapshot["decision"]["context"]
        key = (context["tenant_id"], context["event_id"])
        if key in decision_sources:
            raise ValueError("ambiguous storm decision provenance")
        decision_sources[key] = decision_snapshot
    for opportunity in snapshot["candidates"]:
        source = decision_sources.get((opportunity["tenant_id"], opportunity["event_id"]))
        if source is not None:
            opportunity["decision_provenance"] = decision_opportunity_provenance(
                source, tenant_id=opportunity["tenant_id"], event_id=opportunity["event_id"],
                subject_id=opportunity["subject_id"], as_of=now,
            )
    snapshot["runtime_schema_version"] = SCHEMA_VERSION
    snapshot["diagnostics"] = diagnostics
    snapshot["unknown_stays_unknown"] = True
    snapshot["damage_inferred"] = False
    snapshot["buyer_intent_inferred"] = False
    snapshot["demand_inferred"] = False
    snapshot["pricing_inferred"] = False
    snapshot["economics_inferred"] = False

    return snapshot


def write_storm_opportunity_snapshot(
    repo_root: Path,
    snapshot: Mapping[str, Any],
) -> Path:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        dict(snapshot),
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
    ) + "\n"

    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass

    return path


def materialize_storm_intelligence(
    repo_root: Path,
    *,
    events: Iterable[Mapping[str, Any]] = (),
    subjects: Iterable[Mapping[str, Any]] = (),
    matches: Iterable[Mapping[str, Any]] = (),
    readiness: Iterable[Mapping[str, Any]] = (),
    source_rejections: Iterable[Mapping[str, Any]] = (),
    impact_evidence: Iterable[Mapping[str, Any]] = (),
    impact_policy=None,
    now: datetime | None = None,
) -> dict[str, Any]:
    snapshot = build_storm_intelligence_runtime(
        events=events,
        subjects=subjects,
        matches=matches,
        readiness=readiness,
        source_rejections=source_rejections,
        impact_evidence=impact_evidence,
        impact_policy=impact_policy,
        now=now,
    )
    write_storm_opportunity_snapshot(repo_root, snapshot)
    return snapshot
