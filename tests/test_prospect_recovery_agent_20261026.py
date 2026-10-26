"""Single Prospect Recovery Agent: bounded supervision, no invented commerce."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

import pytest

from empire_os.prospect_recovery_agent import (
    SOURCES, _buyer_briefs, _atomic_write, _read_json,
    build_recovery_plan, run_agent,
)

NOW = datetime(2026, 10, 26, 12, 30, tzinfo=timezone.utc)


def iso(minutes=0):
    return (NOW - timedelta(minutes=minutes)).isoformat()


def snapshots(*, age=2, overflow=4):
    return {
        "exchange": {
            "observed_at": iso(age),
            "qualification_population_census": {
                "state": "CANONICAL_COUNT_AVAILABLE",
                "canonical_prospect_total": 33653,
                "v2_qualification_record_total": 3947,
                "v2_scored_prospect_total": 236,
                "prospects_without_v2_record": 29706,
                "v2_hot_tier_total": 170,
                "v2_warm_tier_total": 47,
            },
            "selection_window": {"limit_reached": True},
            "inventory_count": 200,
            "overflow_count": overflow,
            "supply_gate_diagnostics": {
                "identity_ready_count": 87,
                "identity_blocker_counts": {"missing_active_identity_link": 111},
            },
            "omega_scoring": {"scores_with_exact_qualification_and_identity": 87},
        },
        "buyer_plan": {
            "generated_at": iso(age),
            "demand_gap_queue": [
                {
                    "corridor_key": "corridor:v1:roofing:denver_co:qualified_lead:lead",
                    "niche_family": "roofing",
                    "territory": "denver_co",
                    "overflow_count": overflow,
                    "buyer_hunt_required": True,
                    "priority_score": 650,
                    "active_remaining_capacity": 0,
                }
            ],
        },
        "buyer_scout": {
            "generated_at": iso(age),
            "candidate_count": 11,
            "verified_budget_candidate_count": 0,
            "explicit_direct_buyer_candidate_count": 0,
        },
        "qualification": {"updated_at": iso(age), "next_offset": 60},
        "linked_qualification": {"updated_at": iso(age), "next_offset": 15},
    }


def test_healthy_live_mission_uses_existing_workers_and_prioritises_real_overflow():
    plan = build_recovery_plan(snapshots(), None, now=NOW)
    assert plan["metrics"]["canonical_prospects"] == 33653
    assert plan["metrics"]["without_v2_record"] == 29706
    assert plan["metrics"]["chronological_cursor"] == 60
    assert plan["metrics"]["identity_linked_cursor"] == 15
    assert plan["metrics"]["exchange_missing_active_identity_in_selection"] == 111
    assert len(plan["buyer_recruitment_worklist"]) == 1
    assert plan["buyer_recruitment_worklist"][0]["owner"] == "existing_buyer_acquisition_scout"
    assert plan["next_actions"] == []
    assert plan["new_database"] is False
    assert plan["outbound_sent"] is False
    assert plan["payments_changed"] is False


def test_stale_sources_produce_at_most_two_allowlisted_repair_requests():
    plan = build_recovery_plan(snapshots(age=130), None, now=NOW)
    assert len(plan["next_actions"]) == 2
    assert [row["service"] for row in plan["next_actions"]] == [
        "empire-qualification.service", "empire-commercial-exchange.service",
    ]
    assert plan["repair_requests_held_for_next_cycle"] == 2


def test_service_cooldown_prevents_duplicate_restart():
    prior = {"restart_requests": {
        "empire-qualification.service": iso(4),
        "empire-commercial-exchange.service": iso(3),
    }}
    plan = build_recovery_plan(snapshots(age=120), prior, now=NOW)
    assert [row["service"] for row in plan["next_actions"]] == [
        "empire-buyer-acquisition-team.service",
        "empire-buyer-acquisition-scout.service",
    ]


def test_corrupt_or_future_source_does_not_trigger_repair():
    src = snapshots(age=130)
    src["qualification"]["updated_at"] = iso(-90)
    src["exchange"]["observed_at"] = "invalid"
    plan = build_recovery_plan(src, None, now=NOW)
    assert "empire-qualification.service" not in [r["service"] for r in plan["next_actions"]]
    assert "empire-commercial-exchange.service" not in [r["service"] for r in plan["next_actions"]]


def test_missing_unknown_census_is_not_safely_inferred_as_zero():
    src = snapshots()
    src["exchange"]["qualification_population_census"] = {"state": "COUNT_UNAVAILABLE"}
    plan = build_recovery_plan(src, None, now=NOW)
    assert plan["metrics"]["without_v2_record"] is None
    assert plan["metrics"]["canonical_prospects"] is None
    assert plan["metrics"]["verified_saleable_total"] is None


def test_buyer_worklist_requires_observed_overflow_and_buyer_hunt():
    plan = _buyer_briefs({
        "demand_gap_queue": [
            {"corridor_key": "c1", "niche_family": "hvac", "territory": "a",
             "overflow_count": 2, "buyer_hunt_required": True},
            {"corridor_key": "c2", "niche_family": "plumbing", "territory": "b",
             "overflow_count": 0, "buyer_hunt_required": True},
            {"corridor_key": "c3", "niche_family": "roofing", "territory": "c",
             "overflow_count": 5, "buyer_hunt_required": False},
        ]
    })
    assert len(plan) == 1 and plan[0]["corridor_key"] == "c1"


def test_read_only_agent_does_not_write_any_files(tmp_path):
    for key, relative in SOURCES.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snapshots()[key]))
    result = run_agent(tmp_path, now=NOW)
    assert result["execution_mode"] == "DRY_RUN"
    assert result["unit_requests"] == []
    assert not (tmp_path / "runtime/prospect_recovery_agent").exists()


def test_private_atomic_output_and_unsafe_source_hold(tmp_path):
    path = tmp_path / "private" / "state.json"
    _atomic_write(path, {"score": 1})
    assert (path.stat().st_mode & 0o077) == 0
    assert _read_json(path) == {"score": 1}
    target = tmp_path / "target.json"
    target.write_text("{}")
    link = tmp_path / "symlink.json"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="symlink|unsafe"):
        _read_json(link)


def test_inconsistent_census_never_becomes_claim():
    src = snapshots()
    src["exchange"]["qualification_population_census"]["prospects_without_v2_record"] = 100
    plan = build_recovery_plan(src, None, now=NOW)
    assert plan["metrics"]["canonical_prospects"] is None
    assert plan["metrics"]["without_v2_record"] is None


def test_progress_delta_requires_two_comparable_census_receipts():
    plan = build_recovery_plan(snapshots(), {"metrics": {"v2_records": 3930}}, now=NOW)
    assert plan["metrics"]["v2_records_delta_since_prior_agent_cycle"] == 17


def test_agent_distinguishes_degraded_search_from_service_failure():
    src = snapshots()
    src["buyer_scout"]["search_query_domain_coverage"] = {
        "state": "LOW_ELIGIBLE_SEARCH_YIELD",
        "distinct_queries_submitted": 12,
        "queries_with_eligible_domains": 1,
    }
    plan = build_recovery_plan(src, None, now=NOW)
    health = plan["buyer_research_source_health"]
    assert health["state"] == "LOW_ELIGIBLE_SEARCH_YIELD"
    assert health["queries_submitted"] == 12
    assert health["queries_with_eligible_domains"] == 1
    assert health["automatic_additional_search_requests"] == 0
    assert health["automated_search_restart_authorized_by_degradation"] is False
    assert health["recovery_owner"] == "existing_buyer_acquisition_scout"
    assert plan["next_actions"] == []
    assert plan["outbound_sent"] is False


def test_stale_or_missing_search_coverage_stays_unknown():
    src = snapshots()
    src["buyer_scout"]["search_query_domain_coverage"] = {
        "state": "NO_ELIGIBLE_SEARCH_RESULTS",
        "distinct_queries_submitted": 12,
        "queries_with_eligible_domains": 0,
    }
    src["buyer_scout"]["generated_at"] = iso(120)
    stale = build_recovery_plan(src, None, now=NOW)
    assert stale["buyer_research_source_health"]["state"] == "STALE_SCOUT_SEARCH_EVIDENCE"
    assert stale["buyer_research_source_health"]["queries_submitted"] is None

    fresh = snapshots()
    uninstrumented = build_recovery_plan(fresh, None, now=NOW)
    assert uninstrumented["buyer_research_source_health"]["state"] == "SEARCH_COVERAGE_NOT_INSTRUMENTED"
    assert uninstrumented["buyer_research_source_health"]["queries_with_eligible_domains"] is None
