"""Phase 18 Full Autonomous Revenue OS observe-only integration packet."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any, Mapping

from empire_os.buyer_allocation import (
    fetch_active_identity_link,
    fetch_latest_qualification,
)
from empire_os.canonical_data_gateway import gateway_from_environment
from empire_os.engineering_gauntlet import (
    GauntletCandidate,
    evaluate_gauntlet,
)
from empire_os.execution_bus_data_repository import ExecutionBusDataRepository
from empire_os.qualification_worker_v2 import run_cycle as run_qualification_cycle
from empire_os.revenue_architecture_critic import review_revenue_architecture
from empire_os.revenue_inventory import (
    BOOKED_APPOINTMENT,
    CPA_OUTCOME,
    PREQUALIFIED_LEAD,
    QUALIFIED_CALL,
    RAW_LEAD,
    classify_revenue_inventory,
)
from empire_os.runtime_env import load_runtime_env


@dataclass(frozen=True)
class RevenueDecisionPacket:
    packet_key: str
    recommended_workstream: str | None
    recommended_job_type: str | None
    forecast_direction: str | None
    capital_candidate_id: str | None
    demand_plan_ref: str | None
    enterprise_blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    mode: str = "OBSERVE"
    side_effects: str = "none"
    execution_authority: str = "none"

    def validate(self) -> None:
        if not self.packet_key.strip():
            raise ValueError("packet_key required")
        if self.mode != "OBSERVE":
            raise ValueError("Phase 18 integration packet must remain OBSERVE")
        if self.side_effects != "none":
            raise ValueError("Phase 18 integration packet cannot have side effects")
        if self.execution_authority != "none":
            raise ValueError("Phase 18 integration packet cannot grant execution authority")
        if not self.evidence_refs:
            raise ValueError("integration packet requires evidence")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)
def compose_revenue_decision_packet(
    *,
    packet_key: str,
    astra_decision: Mapping[str, Any] | None,
    predictive_forecast: Mapping[str, Any] | None,
    capital_recommendation: Mapping[str, Any] | None,
    demand_plan_ref: str | None,
    enterprise_blockers: tuple[str, ...] = (),
    evidence_refs: tuple[str, ...],
) -> RevenueDecisionPacket:
    astra = dict(astra_decision or {})
    forecast = dict(predictive_forecast or {})
    capital = dict(capital_recommendation or {})

    packet = RevenueDecisionPacket(
        packet_key=str(packet_key or "").strip(),
        recommended_workstream=(
            str(astra["workstream"]).strip()
            if astra.get("workstream") is not None
            else None
        ),
        recommended_job_type=(
            str(astra["recommended_job_type"]).strip()
            if astra.get("recommended_job_type") is not None
            else None
        ),
        forecast_direction=(
            str(forecast["direction"]).strip()
            if forecast.get("direction") is not None
            else None
        ),
        capital_candidate_id=(
            str(capital["candidate_id"]).strip()
            if capital.get("candidate_id") is not None
            else None
        ),
        demand_plan_ref=(
            str(demand_plan_ref).strip()
            if demand_plan_ref is not None
            else None
        ),
        enterprise_blockers=tuple(
            sorted({str(item).strip() for item in enterprise_blockers if str(item).strip()})
        ),
        evidence_refs=tuple(
            str(item).strip() for item in evidence_refs if str(item).strip()
        ),
    )
    packet.validate()
    return packet


ENV_PATH = os.environ.get("EMPIRE_ENV_PATH", "/etc/empire_os.env")
RUNTIME_ROOT = Path(os.environ.get("EMPIRE_RUNTIME_ROOT", "/srv/empire_os/runtime"))
REVENUE_RUNTIME_DIR = RUNTIME_ROOT / "autonomous_revenue_os"
LATEST_STATE_PATH = REVENUE_RUNTIME_DIR / "latest.json"

RELEASE_ID = "autonomous-revenue-os-v1"
DEFAULT_INVENTORY_LIMIT = int(os.environ.get("EMPIRE_REVENUE_INVENTORY_LIMIT", "100"))
DEFAULT_QUALIFICATION_LIMIT = int(os.environ.get("EMPIRE_REVENUE_QUALIFICATION_LIMIT", "10"))
MIN_IDLE_SLEEP_SECONDS = int(os.environ.get("EMPIRE_REVENUE_IDLE_SLEEP_SECONDS", "30"))
ACTIVE_SLEEP_SECONDS = int(os.environ.get("EMPIRE_REVENUE_ACTIVE_SLEEP_SECONDS", "3"))
FAILURE_SLEEP_SECONDS = int(os.environ.get("EMPIRE_REVENUE_FAILURE_SLEEP_SECONDS", "60"))
INVENTORY_FLOOR = int(os.environ.get("EMPIRE_REVENUE_INVENTORY_FLOOR", "250"))
LEAD_GENERATION_BATCH = int(os.environ.get("EMPIRE_REVENUE_LEAD_GENERATION_BATCH", "25"))
LEAD_GENERATION_COOLDOWN_SECONDS = int(
    os.environ.get("EMPIRE_REVENUE_LEAD_GENERATION_COOLDOWN_SECONDS", "900")
)
CONTINUOUS_LEAD_GENERATION = (
    os.environ.get("EMPIRE_REVENUE_CONTINUOUS_LEAD_GENERATION", "0").strip()
    == "1"
)
OPPORTUNITY_RADAR_PATH = Path("/srv/empire_os/runtime/opportunity_radar/latest.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    tmp.replace(path)


def _repository() -> ExecutionBusDataRepository:
    env = load_runtime_env(ENV_PATH)
    return ExecutionBusDataRepository(gateway_from_environment(env))


def build_inventory_snapshot(
    *,
    repository: ExecutionBusDataRepository | None = None,
    limit: int = DEFAULT_INVENTORY_LIMIT,
) -> dict[str, Any]:
    repo = repository or _repository()
    rows = repo.inventory_prospects(limit=max(1, int(limit)))
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for prospect in rows:
        prospect_id = str(prospect.get("id") or "").strip()
        if not prospect_id:
            continue
        try:
            qualification = fetch_latest_qualification(
                repo.buyer_allocation,
                prospect_id,
            )
            identity_link = fetch_active_identity_link(
                repo.buyer_allocation,
                prospect_id,
            )
            events = repo.prospect_conversation_events(prospect_id)
            outcomes = repo.prospect_commercial_outcomes(prospect_id)
            classification = classify_revenue_inventory(
                prospect=prospect,
                qualification=qualification,
                identity_link=identity_link,
                conversation_events=events,
                commercial_outcomes=outcomes,
            )
            items.append({
                **classification.as_dict(),
                "business_name": prospect.get("business_name"),
                "niche": prospect.get("niche"),
                "metro": prospect.get("metro"),
                "qualification_score": (
                    qualification.get("score")
                    if isinstance(qualification, dict)
                    else None
                ),
                "qualification_tier": (
                    qualification.get("tier")
                    if isinstance(qualification, dict)
                    else None
                ),
            })
        except Exception as exc:
            errors.append({
                "prospect_id": prospect_id,
                "error": f"{type(exc).__name__}:{str(exc)[:300]}",
            })

    counts = Counter(item["stage"] for item in items)
    return {
        "schema_version": "empire.autonomous-revenue.inventory.v1",
        "observed_at": _utc_now(),
        "inventory_limit": max(1, int(limit)),
        "prospects_observed": len(rows),
        "classified": len(items),
        "errors": errors,
        "counts": {
            RAW_LEAD: counts.get(RAW_LEAD, 0),
            PREQUALIFIED_LEAD: counts.get(PREQUALIFIED_LEAD, 0),
            QUALIFIED_CALL: counts.get(QUALIFIED_CALL, 0),
            BOOKED_APPOINTMENT: counts.get(BOOKED_APPOINTMENT, 0),
            CPA_OUTCOME: counts.get(CPA_OUTCOME, 0),
        },
        "items": items,
        "price_truth": "unknown_until_verified_buyer_or_product_economics",
        "actual_revenue": False,
        "execution_authority": "none",
    }


def diagnose_next_revenue_action(
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    counts = dict(snapshot.get("counts") or {})

    if int(counts.get(RAW_LEAD, 0)) > 0:
        return {
            "action": "qualify_raw_leads",
            "authority": "internal_write",
            "component": "qualification_worker_v2",
            "reason": "raw_inventory_available",
        }
    if int(counts.get(PREQUALIFIED_LEAD, 0)) > 0:
        return {
            "action": "match_prequalified_leads_to_verified_buyers",
            "authority": "founder_gate",
            "component": "buyer_allocation",
            "reason": "ppl_inventory_available",
        }
    if int(counts.get(QUALIFIED_CALL, 0)) > 0:
        return {
            "action": "route_or_convert_qualified_calls",
            "authority": "founder_gate",
            "component": "conversation_closer",
            "reason": "pay_per_call_inventory_available",
        }
    if int(counts.get(BOOKED_APPOINTMENT, 0)) > 0:
        return {
            "action": "match_booked_appointments_to_verified_demand",
            "authority": "founder_gate",
            "component": "commercial_exchange",
            "reason": "appointment_inventory_available",
        }
    if int(counts.get(CPA_OUTCOME, 0)) > 0:
        return {
            "action": "record_and_learn_from_cpa_outcomes",
            "authority": "internal_write",
            "component": "economic_memory",
            "reason": "verified_conversion_outcomes_available",
        }
    return {
        "action": "generate_more_leads",
        "authority": "internal_write",
        "component": "lead_generation",
        "reason": "no_classified_inventory",
    }




def _architecture_critic_review() -> dict[str, Any]:
    return review_revenue_architecture({
        "single_control_plane": "autonomous_revenue_os",
        "timer_driven": False,
        "unknown_price_stays_null": True,
        "real_sources_only": True,
        "usdt_bsc_only": True,
        "lead_generation_batch": max(1, LEAD_GENERATION_BATCH),
        "qualification_batch": max(1, DEFAULT_QUALIFICATION_LIMIT),
        "external_send": False,
        "call_execution": False,
        "booking_execution": False,
        "binding_terms": False,
        "fund_movement": False,
        "revenue_recognition": False,
        "inventory_stages": (
            RAW_LEAD,
            PREQUALIFIED_LEAD,
            QUALIFIED_CALL,
            BOOKED_APPOINTMENT,
            CPA_OUTCOME,
        ),
    }).as_dict()

def _qualification_gauntlet(attested: bool) -> dict[str, Any]:
    decision = evaluate_gauntlet(GauntletCandidate(
        action_key="revenue-loop:qualification:v1",
        component="qualification_worker_v2",
        authority="internal_write",
        evidence_refs=(
            "docs/architecture/revenue_inventory_ladder_v1.md",
            "docs/AUTONOMOUS_SYSTEM_STITCHING_ARCHITECTURE.md",
        ),
        architecture_contract=True,
        fresh_context_critic_passed=bool(
            _architecture_critic_review().get("passed")
        ),
        tests_policy_passed=bool(attested),
        independent_verify_ready=bool(attested),
        diff_clean=bool(attested),
        reversible=True,
        consequential=False,
    ))
    return decision.as_dict()




def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _select_lead_generation_target(
    snapshot: Mapping[str, Any],
) -> dict[str, Any] | None:
    radar = _read_json(OPPORTUNITY_RADAR_PATH) or {}
    for row in radar.get("candidates") or []:
        if not isinstance(row, dict):
            continue
        niche = str(row.get("niche") or "").strip()
        metro = str(row.get("metro") or "").strip()
        refs = [
            str(value).strip()
            for value in (row.get("evidence_refs") or [])
            if str(value).strip()
        ]
        if niche and metro and refs:
            return {
                "niche": niche,
                "metro": metro,
                "evidence_refs": refs,
                "opportunity_key": row.get("opportunity_key"),
            }

    # Fallback: replenish an already-observed market rather than invent one.
    for item in snapshot.get("items") or []:
        if not isinstance(item, dict):
            continue
        niche = str(item.get("niche") or "").strip()
        metro = str(item.get("metro") or "").strip()
        if niche and metro:
            return {
                "niche": niche,
                "metro": metro,
                "evidence_refs": tuple(item.get("evidence_refs") or ()),
                "opportunity_key": f"inventory:{niche}:{metro}".lower(),
            }
    return None


def _lead_generation_gauntlet(
    *,
    attested: bool,
    target: Mapping[str, Any],
) -> dict[str, Any]:
    refs = tuple(
        str(value).strip()
        for value in (target.get("evidence_refs") or ())
        if str(value).strip()
    )
    decision = evaluate_gauntlet(GauntletCandidate(
        action_key=(
            "revenue-loop:lead-generation:"
            f"{target.get('niche')}:{target.get('metro')}"
        ),
        component="crawler_runner",
        authority="internal_write",
        evidence_refs=refs + (
            "docs/architecture/revenue_inventory_ladder_v1.md",
        ),
        architecture_contract=True,
        fresh_context_critic_passed=bool(
            refs and _architecture_critic_review().get("passed")
        ),
        tests_policy_passed=bool(attested),
        independent_verify_ready=bool(attested),
        diff_clean=bool(attested),
        reversible=True,
        consequential=False,
    ))
    return decision.as_dict()


def _lead_generation_due(previous: Mapping[str, Any] | None) -> bool:
    if not isinstance(previous, Mapping):
        return True
    lead_generation = previous.get("lead_generation")
    if not isinstance(lead_generation, Mapping):
        return True
    raw = str(lead_generation.get("attempted_at") or "").strip()
    if not raw:
        return True
    try:
        observed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return True
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - observed).total_seconds()
    return age >= LEAD_GENERATION_COOLDOWN_SECONDS


def _run_lead_generation(
    target: Mapping[str, Any],
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "empire_os.crawler_runner",
        "--metro",
        str(target["metro"]),
        "--niche",
        str(target["niche"]),
        "--max-candidates",
        str(max(1, LEAD_GENERATION_BATCH)),
    ]
    completed = subprocess.run(
        command,
        cwd="/srv/empire_os",
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    return {
        "attempted_at": _utc_now(),
        "target": {
            "niche": target.get("niche"),
            "metro": target.get("metro"),
            "opportunity_key": target.get("opportunity_key"),
        },
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout_tail": (completed.stdout or "")[-4000:],
        "stderr_tail": (completed.stderr or "")[-4000:],
        "max_candidates": max(1, LEAD_GENERATION_BATCH),
        "actual_revenue": False,
    }


def build_revenue_review_queue(
    snapshot: Mapping[str, Any],
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for item in snapshot.get("items") or []:
        if not isinstance(item, dict):
            continue
        stage = str(item.get("stage") or "")
        if stage == RAW_LEAD:
            continue
        if stage == PREQUALIFIED_LEAD:
            action = "ppl_buyer_match_review"
        elif stage == QUALIFIED_CALL:
            action = "pay_per_call_or_appointment_conversion_review"
        elif stage == BOOKED_APPOINTMENT:
            action = "appointment_buyer_match_review"
        elif stage == CPA_OUTCOME:
            action = "cpa_outcome_learning_review"
        else:
            continue
        queue.append({
            "prospect_id": item.get("prospect_id"),
            "business_name": item.get("business_name"),
            "niche": item.get("niche"),
            "metro": item.get("metro"),
            "stage": stage,
            "monetization_model": item.get("monetization_model"),
            "action": action,
            "evidence_refs": item.get("evidence_refs") or (),
            "founder_gate_required": stage in {
                PREQUALIFIED_LEAD,
                QUALIFIED_CALL,
                BOOKED_APPOINTMENT,
            },
            "external_execution": False,
        })
        if len(queue) >= max(1, int(limit)):
            break
    return queue

def run_agentic_cycle(
    *,
    repository: ExecutionBusDataRepository | None = None,
    inventory_limit: int = DEFAULT_INVENTORY_LIMIT,
    qualification_limit: int = DEFAULT_QUALIFICATION_LIMIT,
    internal_write: bool | None = None,
    gauntlet_attested: bool | None = None,
) -> dict[str, Any]:
    if internal_write is None:
        internal_write = (
            os.environ.get("EMPIRE_REVENUE_LOOP_INTERNAL_WRITE", "0").strip()
            == "1"
        )
    if gauntlet_attested is None:
        gauntlet_attested = (
            os.environ.get("EMPIRE_REVENUE_GAUNTLET_ATTESTED", "0").strip()
            == "1"
            and os.environ.get("EMPIRE_REVENUE_RELEASE_ID", "").strip()
            == RELEASE_ID
        )

    qualification_result: dict[str, Any] | None = None
    qualification_gate = _qualification_gauntlet(bool(gauntlet_attested))

    if (
        internal_write
        and qualification_gate["decision"] == "READY_FOR_INTERNAL_EXECUTION"
    ):
        qualification_result = run_qualification_cycle(
            limit=max(1, int(qualification_limit))
        )

    previous_state = _read_json(LATEST_STATE_PATH)
    snapshot = build_inventory_snapshot(
        repository=repository,
        limit=inventory_limit,
    )

    lead_generation: dict[str, Any] | None = None
    lead_generation_gate: dict[str, Any] | None = None
    target = _select_lead_generation_target(snapshot)
    should_generate = bool(
        target
        and _lead_generation_due(previous_state)
        and (
            CONTINUOUS_LEAD_GENERATION
            or int(snapshot.get("classified") or 0) < INVENTORY_FLOOR
        )
    )
    if should_generate:
        lead_generation_gate = _lead_generation_gauntlet(
            attested=bool(gauntlet_attested),
            target=target or {},
        )
        if (
            internal_write
            and lead_generation_gate["decision"]
            == "READY_FOR_INTERNAL_EXECUTION"
        ):
            lead_generation = _run_lead_generation(target or {})

    next_action = diagnose_next_revenue_action(snapshot)
    review_queue = build_revenue_review_queue(snapshot)

    payload = {
        "schema_version": "empire.autonomous-revenue.loop.v1",
        "cycle_at": _utc_now(),
        "loop": [
            "OBSERVE",
            "DIAGNOSE",
            "PLAN",
            "GAUNTLET",
            "ACT",
            "VERIFY",
            "RECORD",
            "REPEAT",
        ],
        "qualification_gauntlet": qualification_gate,
        "qualification_result": qualification_result,
        "lead_generation_gauntlet": lead_generation_gate,
        "lead_generation": lead_generation,
        "continuous_lead_generation": CONTINUOUS_LEAD_GENERATION,
        "inventory_floor": INVENTORY_FLOOR,
        "inventory": snapshot,
        "review_queue": review_queue,
        "next_action": next_action,
        "communications_execution": False,
        "booking_execution": False,
        "binding_terms": False,
        "fund_movement": False,
        "revenue_recognition": False,
        "actual_revenue": False,
        "execution_authority": (
            "bounded_internal"
            if qualification_result is not None or lead_generation is not None
            else "observe"
        ),
    }
    _atomic_json(LATEST_STATE_PATH, payload)
    return payload


class AutonomousRevenueLoop:
    def __init__(
        self,
        *,
        inventory_limit: int = DEFAULT_INVENTORY_LIMIT,
        qualification_limit: int = DEFAULT_QUALIFICATION_LIMIT,
    ) -> None:
        self.inventory_limit = max(1, int(inventory_limit))
        self.qualification_limit = max(1, int(qualification_limit))
        self._stop = False

    def stop(self, *_args: Any) -> None:
        self._stop = True

    def run_forever(self) -> None:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        failure_backoff = FAILURE_SLEEP_SECONDS

        while not self._stop:
            try:
                result = run_agentic_cycle(
                    inventory_limit=self.inventory_limit,
                    qualification_limit=self.qualification_limit,
                )
                qualification = result.get("qualification_result")
                lead_generation = result.get("lead_generation")
                did_work = bool(
                    (
                        isinstance(qualification, dict)
                        and int(qualification.get("attempted") or 0) > 0
                    )
                    or isinstance(lead_generation, dict)
                )
                sleep_for = (
                    ACTIVE_SLEEP_SECONDS
                    if did_work
                    else MIN_IDLE_SLEEP_SECONDS
                )
                failure_backoff = FAILURE_SLEEP_SECONDS
            except Exception as exc:
                _atomic_json(LATEST_STATE_PATH, {
                    "schema_version": "empire.autonomous-revenue.loop.v1",
                    "cycle_at": _utc_now(),
                    "status": "DEGRADED",
                    "error": f"{type(exc).__name__}:{str(exc)[:1000]}",
                    "actual_revenue": False,
                    "execution_authority": "none",
                })
                sleep_for = failure_backoff
                failure_backoff = min(failure_backoff * 2, 900)

            deadline = time.monotonic() + max(1, sleep_for)
            while not self._stop and time.monotonic() < deadline:
                time.sleep(min(1.0, deadline - time.monotonic()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--inventory-limit", type=int, default=DEFAULT_INVENTORY_LIMIT)
    parser.add_argument("--qualification-limit", type=int, default=DEFAULT_QUALIFICATION_LIMIT)
    args = parser.parse_args()

    if args.once:
        print(json.dumps(
            run_agentic_cycle(
                inventory_limit=args.inventory_limit,
                qualification_limit=args.qualification_limit,
            ),
            indent=2,
            sort_keys=True,
            default=str,
        ))
        return 0

    AutonomousRevenueLoop(
        inventory_limit=args.inventory_limit,
        qualification_limit=args.qualification_limit,
    ).run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
