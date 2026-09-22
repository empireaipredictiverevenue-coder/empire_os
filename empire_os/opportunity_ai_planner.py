"""Automatically turn Opportunity Radar candidates into bounded AI planning work.

This is an internal planning bridge only. It does not perform outbound, accept
terms, move funds, recognize revenue, or create commercial authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from empire_os.coder import EmpireCoder
from empire_os.coder.jobs import JobKind, LocalJobQueue


RADAR_RELATIVE = Path("runtime/opportunity_radar/latest.json")
RESEARCH_RELATIVE = Path("runtime/opportunity_radar/research_latest.json")
FACTORY_INTAKE_RELATIVE = Path("runtime/opportunity_factory/intake_latest.json")
STATE_RELATIVE = Path("runtime/opportunity_radar/ai_planner_state.json")
OUTPUT_RELATIVE = Path("runtime/opportunity_radar/ai_planner_latest.json")


@dataclass(frozen=True)
class PlannedOpportunity:
    opportunity_key: str
    fingerprint: str
    coder_task_id: str
    coder_job_id: str
    priority: int
    queued_at: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _fingerprint(
    candidate: Mapping[str, Any],
    research: Mapping[str, Any] | None = None,
    factory_item: Mapping[str, Any] | None = None,
) -> str:
    material = {
        "opportunity_key": candidate.get("opportunity_key"),
        "opportunity_class": candidate.get("opportunity_class"),
        "trigger": candidate.get("trigger"),
        "observed_priority_score": candidate.get(
            "observed_priority_score"
        ),
        "evidence_refs": sorted(
            str(item)
            for item in (candidate.get("evidence_refs") or [])
            if str(item).strip()
        ),
        "factory_blockers": sorted(
            str(item)
            for item in (candidate.get("factory_blockers") or [])
            if str(item).strip()
        ),
        "recommended_next_actions": sorted(
            str(item)
            for item in (
                candidate.get("recommended_next_actions") or []
            )
            if str(item).strip()
        ),
        "research_evidence_urls": sorted(
            str(item)
            for item in ((research or {}).get("evidence_urls") or [])
            if str(item).strip()
        ),
        "research_observation_count": int(
            (research or {}).get("observation_count") or 0
        ),
        "factory_ready": bool(
            (factory_item or {}).get("factory_ready") is True
        ),
        "factory_blockers_actual": sorted(
            str(item)
            for item in ((factory_item or {}).get("blockers") or [])
            if str(item).strip()
        ),
    }
    raw = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _priority(candidate: Mapping[str, Any]) -> int:
    value = candidate.get("observed_priority_score")
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = 50.0
    return max(10, min(90, int(round(score))))


def _objective(
    candidate: Mapping[str, Any],
    research: Mapping[str, Any] | None = None,
    factory_item: Mapping[str, Any] | None = None,
) -> str:
    key = str(candidate.get("opportunity_key") or "").strip()
    klass = str(candidate.get("opportunity_class") or "").strip()
    title = str(candidate.get("title") or key).strip()
    blockers = [
        str(item).strip()
        for item in (candidate.get("factory_blockers") or [])
        if str(item).strip()
    ]
    actions = [
        str(item).strip()
        for item in (candidate.get("recommended_next_actions") or [])
        if str(item).strip()
    ]
    refs = [
        str(item).strip()
        for item in (candidate.get("evidence_refs") or [])
        if str(item).strip()
    ]
    research_urls = [
        str(item).strip()
        for item in ((research or {}).get("evidence_urls") or [])
        if str(item).strip()
    ]
    research_count = int(
        (research or {}).get("observation_count") or 0
    )
    actual_factory_blockers = [
        str(item).strip()
        for item in ((factory_item or {}).get("blockers") or [])
        if str(item).strip()
    ]
    factory_ready = bool(
        (factory_item or {}).get("factory_ready") is True
    )
    return (
        "PLAN ONLY: advance this existing Predictive Cloud opportunity toward "
        "the canonical Opportunity Factory without inventing evidence or "
        "creating a duplicate subsystem. Search the repo/docs/runtime contracts "
        "for reusable sensors, adapters, intelligence nodes, Search Fabric, "
        "Market Sweeps, Community Intent, Storm/Physical, TAM, Omega/Cortex, "
        "Quant, Astra, fulfilment and product contracts. Produce a bounded "
        "evidence-completion and implementation plan covering: missing evidence, "
        "which existing Empire components can collect it, canonical data writes, "
        "tests, observability, Opportunity Factory field mapping, economics "
        "evidence, distribution path, fulfilment readiness, automation path and "
        "Founder Console exposure. Safe reversible internal work may be proposed. "
        "Do NOT send outreach, accept terms, move funds, recognize revenue, "
        "fabricate buyer intent/demand/economics, or expand authority. "
        f"Opportunity key={key}; class={klass}; title={title}; "
        f"blockers={blockers}; recommended_actions={actions}; "
        f"evidence_refs={refs}; public_search_observation_count={research_count}; "
        f"public_search_evidence_urls={research_urls}; factory_ready={factory_ready}; "
        f"actual_factory_blockers={actual_factory_blockers}. Public search observations "
        "are research evidence candidates only and must not be treated as verified "
        "demand, buyer intent, economics or revenue."
    )


def plan_radar_opportunities(
    repo_root: str | Path,
    *,
    limit: int = 3,
    coder_factory: Callable[..., Any] = EmpireCoder,
    queue_factory: Callable[..., Any] = LocalJobQueue,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    radar = _read_json(root / RADAR_RELATIVE)
    research_batch = _read_json(root / RESEARCH_RELATIVE)
    factory_batch = _read_json(root / FACTORY_INTAKE_RELATIVE)
    candidates = radar.get("candidates")
    candidates = candidates if isinstance(candidates, list) else []
    research_actions = research_batch.get("actions")
    research_actions = (
        research_actions if isinstance(research_actions, list) else []
    )
    research_by_key = {
        str(row.get("opportunity_key") or "").strip(): row
        for row in research_actions
        if isinstance(row, Mapping)
        and str(row.get("opportunity_key") or "").strip()
    }
    factory_items = factory_batch.get("items")
    factory_items = (
        factory_items if isinstance(factory_items, list) else []
    )
    factory_by_key = {
        str(row.get("opportunity_key") or "").strip(): row
        for row in factory_items
        if isinstance(row, Mapping)
        and str(row.get("opportunity_key") or "").strip()
    }
    state_path = root / STATE_RELATIVE
    state = _read_json(state_path)
    fingerprints = state.get("fingerprints")
    fingerprints = (
        dict(fingerprints)
        if isinstance(fingerprints, dict)
        else {}
    )

    eligible: list[
        tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]
    ] = []
    skipped_unchanged = 0
    skipped_no_evidence = 0
    for raw in candidates:
        if not isinstance(raw, Mapping):
            continue
        key = str(raw.get("opportunity_key") or "").strip()
        refs = [
            str(item).strip()
            for item in (raw.get("evidence_refs") or [])
            if str(item).strip()
        ]
        if not key or not refs:
            skipped_no_evidence += 1
            continue
        research = research_by_key.get(key) or {}
        factory_item = factory_by_key.get(key) or {}
        fp = _fingerprint(raw, research, factory_item)
        if fingerprints.get(key) == fp:
            skipped_unchanged += 1
            continue
        eligible.append((raw, research, factory_item))

    eligible.sort(
        key=lambda item: (
            -_priority(item[0]),
            str(item[0].get("opportunity_key") or ""),
        )
    )

    now = datetime.now(timezone.utc).isoformat()
    planned: list[PlannedOpportunity] = []
    bounded = max(1, min(int(limit), 10))
    if eligible:
        coder_root = root / "runtime" / "coder"
        coder = coder_factory(root, runtime_root=coder_root)
        queue = queue_factory(root, runtime_root=coder_root)
    else:
        coder = None
        queue = None

    for candidate, research, factory_item in eligible[:bounded]:
        key = str(candidate.get("opportunity_key") or "").strip()
        fp = _fingerprint(candidate, research, factory_item)
        task = coder.create_task(
            _objective(candidate, research, factory_item)
        )
        job = queue.enqueue(
            task_id=task.id,
            kind=JobKind.PLAN,
            priority=_priority(candidate),
            payload={
                "terms": [
                    "Predictive Cloud",
                    "Opportunity Radar",
                    "Opportunity Factory",
                    "Astra",
                    "evidence",
                    str(candidate.get("opportunity_class") or ""),
                ],
                "budget_chars": 7000,
                "opportunity_key": key,
                "opportunity_fingerprint": fp,
                "execution_authority": "none",
            },
        )
        fingerprints[key] = fp
        planned.append(PlannedOpportunity(
            opportunity_key=key,
            fingerprint=fp,
            coder_task_id=task.id,
            coder_job_id=job.id,
            priority=_priority(candidate),
            queued_at=now,
        ))

    state_payload = {
        "schema_version": "empire.opportunity_ai_planner_state.v1",
        "updated_at": now,
        "fingerprints": fingerprints,
    }
    _write_json(state_path, state_payload)

    payload = {
        "schema_version": "empire.opportunity_ai_planner.v1",
        "mode": "OBSERVE",
        "generated_at": now,
        "radar_available": bool(radar),
        "radar_candidate_count": len(candidates),
        "research_available": bool(research_batch),
        "research_action_count": len(research_actions),
        "factory_intake_available": bool(factory_batch),
        "factory_intake_item_count": len(factory_items),
        "factory_ready_count": sum(
            row.get("factory_ready") is True
            for row in factory_items
            if isinstance(row, Mapping)
        ),
        "research_observation_count": sum(
            int(row.get("observation_count") or 0)
            for row in research_actions
            if isinstance(row, Mapping)
        ),
        "eligible_changed_count": len(eligible),
        "queued_count": len(planned),
        "skipped_unchanged": skipped_unchanged,
        "skipped_no_evidence": skipped_no_evidence,
        "planned": [row.as_dict() for row in planned],
        "automatic_research_planning": True,
        "automatic_production_execution": False,
        "outreach_authority": "none",
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
        "execution_authority": "none",
    }
    _write_json(root / OUTPUT_RELATIVE, payload)
    return payload
