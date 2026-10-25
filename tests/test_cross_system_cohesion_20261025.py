"""No synthetic commercial fixture enters any production store: tmp_path only."""
from __future__ import annotations
from datetime import datetime, timezone
import json

from empire_os.cross_system_cohesion import SOURCES, build_cohesion_snapshot

NOW = datetime(2026, 10, 25, 23, 20, tzinfo=timezone.utc)

def write_source(tmp_path, key, *, extra=None, age="2026-10-25T23:18:00+00:00"):
    path, schema, _ = SOURCES[key]
    target = tmp_path / path
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": schema, "mode": "OBSERVE",
               "generated_at": age, "execution_authority": "none"}
    payload.update(extra or {})
    target.write_text(json.dumps(payload))
    return target

def test_missing_sources_fail_closed_without_guessing_counts(tmp_path):
    result = build_cohesion_snapshot(tmp_path, now=NOW)
    assert all(x["status"] == "UNAVAILABLE" for x in result["sources"].values())
    assert all(v is None for v in result["evidence_population_counts"].values())
    assert not result["fully_verified_commercial_loop"]
    assert result["canonical_entity_id_join_verified"] is False
    assert result["dispatched_tasks"] == 0
    assert result["db_writes"] is False
    assert result["emails_sent"] is False
    assert result["payments_executed"] is False

def test_independent_realistic_observations_never_infer_verified_buyer(tmp_path):
    payload = {
        "buyer_scout": {"candidate_count": 11},
        "jev": {"observations_submitted": 59},
        "opportunity_factory": {"candidate_count": 21, "factory_ready_count": 0},
        "buyer_relationships": {"warm_business_relationship_count": 5},
        "buyer_capacity": {"buyers_seen": 1057, "fully_activated": 0},
        "predictive_revenue": {"candidate_count": 218, "passed_count": 0},
        "orders_payments": {"semantic_truth": {"real_payment_observed": False}},
        "revenue_pulse": {"recognized_revenue_truth": {"recognized_revenue_cents": 0}},
        "economic_memory": {"outcome_conditioned_memories": []},
    }
    for key, extra in payload.items():
        write_source(tmp_path, key, extra=extra)
    result = build_cohesion_snapshot(tmp_path, now=NOW)
    assert result["system_connected_for_observation"] is True
    facts = result["evidence_population_counts"]
    assert facts["scout_research_candidates"] == 11
    assert facts["jev_observations"] == 59
    assert facts["factory_ready_opportunities"] == 0
    assert facts["fully_activated_buyers"] == 0
    assert facts["recognized_revenue_cents"] == 0
    assert result["population_counts_are_independent_not_a_conversion_funnel"]
    assert not result["fully_verified_commercial_loop"]
    tasks = {x["task"]:x["owner"] for x in result["proposed_next_work"]}
    assert tasks["VERIFY_ONE_BUYER_CONTRACT_BUYBOX_TERMS_CAPACITY"] == "BuyerAcquisition"
    assert tasks["ATTEST_ONE_CANONICAL_TENANT_LINK_FROM_PRIVILEGED_READER"] == "SmartCRM"
    assert all(x["automatic_execution_authorized"] is False
               for x in result["proposed_next_work"])

def test_stale_poison_and_symlink_do_not_masquerade_as_connected(tmp_path):
    f = write_source(tmp_path, "buyer_scout", extra={"candidate_count": 999999},
                     age="2026-10-20T00:00:00+00:00")
    assert build_cohesion_snapshot(tmp_path, now=NOW)["sources"]["buyer_scout"]["status"] == "STALE_OR_FUTURE"
    f.unlink()
    f.symlink_to(tmp_path / "missing")
    assert build_cohesion_snapshot(tmp_path, now=NOW)["sources"]["buyer_scout"]["status"] == "UNAVAILABLE"
    f.unlink()
    write_source(tmp_path, "buyer_scout", extra={
        "outbound_sent": True, "candidate_count": 12})
    r = build_cohesion_snapshot(tmp_path, now=NOW)
    assert r["sources"]["buyer_scout"]["status"] == "UNSAFE_EXECUTION_AUTHORITY"
    assert r["evidence_population_counts"]["scout_research_candidates"] is None

def test_cannot_close_commercial_loop_by_mixing_unrelated_positive_aggregates(tmp_path):
    for key in SOURCES:
        write_source(tmp_path, key)
    write_source(tmp_path, "buyer_capacity",
                 extra={"fully_activated": 1})
    write_source(tmp_path, "opportunity_factory",
                 extra={"factory_ready_count": 1})
    write_source(tmp_path, "orders_payments",
                 extra={"semantic_truth": {"real_payment_observed": True}})
    write_source(tmp_path, "revenue_pulse",
                 extra={"recognized_revenue_truth": {"recognized_revenue_cents": 90000}})
    write_source(tmp_path, "economic_memory",
                 extra={"outcome_conditioned_memories": [{"outcome_id": "unlinked"}]})
    result = build_cohesion_snapshot(tmp_path, now=NOW)
    assert result["canonical_entity_id_join_verified"] is False
    assert result["fully_verified_commercial_loop"] is False
    assert result["outbound_authorized"] is False
    assert result["payments_executed"] is False
    assert result["execution_authority"] == "NONE"


def test_entire_chain_requires_entity_proof_even_with_current_snapshots(tmp_path):
    for key in SOURCES:
        write_source(tmp_path, key)
    report = build_cohesion_snapshot(tmp_path, now=NOW)
    chain = report["lifecycle_handoff_gates"]
    assert len(chain) == 12
    assert chain[0]["stage"] == "DATA"
    assert chain[-1]["stage"] == "ECONOMIC_MEMORY"
    assert {row["stage"] for row in chain} == {
        "DATA", "SOURCE_RIGHTS", "OPPORTUNITY", "PERSON_COMPANY",
        "TENANT_CRM", "BUYER_ACCEPTANCE", "APPROVED_OUTBOUND",
        "ACCEPTED_ORDER", "SETTLEMENT", "FULFILMENT",
        "REALISED_REVENUE", "ECONOMIC_MEMORY",
    }
    assert all(row["canonical_record_handoff_verified"] is False for row in chain)
    assert report["buyer_evidence_brain_in_registry"] == (
        "NOT_PRESENT_IN_CURRENT_RECONCILED_SOURCE"
    )
