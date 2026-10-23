"""Revenue-first GPU freeze and no-mutation edge planning regressions."""
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.predictive_edge_depin_governance import (
    REVENUE_GATED_COMPUTE_SPEND_CAP_CENTS,
    review_gpu_candidate,
    review_replica_candidate,
    review_edge_expansion,
)

NOW = datetime(2026, 10, 24, 9, tzinfo=timezone.utc)


def gpu(**updates):
    row = {
        "provider": "io.net",
        "region": "eu-central",
        "workload": "private_llm_inference",
        "gpu_count": 2,
        "hours": 4,
        "currency": "USD",
        "quoted_gpu_hour_cents": 50,
        "monthly_spend_cap_cents": 0,
        "quote_ref": "research-only-no-real-quote",
        "quote_valid_until": (NOW + timedelta(days=1)).isoformat(),
        "container_digest": "sha256:" + ("a" * 64),
        "approved_data_classification": "public_or_synthetic",
        "data_residency_approved": True,
        "private_network_verified": True,
        "egress_cost_cents": 100,
        "total_non_gpu_cost_cents": 200,
        "founder_spend_approved": True,
    }
    row.update(updates)
    return row


def replica(**updates):
    row = {
        "region": "eu-central",
        "replication_mode": "logical_publication",
        "purpose": "analytics_read_only",
        "replicated_table_count": 3,
        "inventory_source_ref": "inventory:source-only",
        "data_owner_approved": True,
        "regional_processing_rights_verified": True,
        "tenant_isolation_evaluated": True,
        "encrypted_transport_verified": True,
        "read_only_access_verified": True,
        "restore_drill_verified": True,
        "schema_sequence_consistency_verified": True,
        "slot_wal_retention_limit_verified": True,
        "lag_monitoring_verified": True,
        "backup_chain_preserved": True,
        "rollback_procedure_reviewed": True,
        "release_owner_approved": True,
    }
    row.update(updates)
    return row


def test_zero_spend_is_immutable_policy_no_access_to_compute():
    assert REVENUE_GATED_COMPUTE_SPEND_CAP_CENTS == 0
    output = review_edge_expansion(
        as_of=NOW, gpu_candidates=[gpu()], replica_candidates=[replica()]
    )
    assert output["mode"] == "OBSERVE"
    assert output["compute_spend_cap_minor_units"] == 0
    assert output["zero_paid_gpu_until_realized_revenue"] is True
    assert output["revenue_verified"] is False
    assert output["payments_made"] is False
    assert output["new_gpu_nodes_provisioned"] == 0
    assert output["new_replicas_created"] == 0
    assert output["existing_astra_and_prime_unchanged"] is True
    assert output["existing_empiredb_primary_unchanged"] is True
    assert output["existing_local_inference_preserved"] is True
    assert output["database_wal_configuration_modified"] is False
    assert output["database_mutation"] is False
    assert output["services_changed"] is False
    assert output["dns_modified"] is False
    assert output["execution_authority"] == "none"


def test_even_fake_founder_approval_and_provider_quote_dont_unlock():
    result = review_gpu_candidate(gpu(), as_of=NOW)
    assert result["quoted_total_cost_minor_units"] == 700
    assert result["paid_gpu_work_allowed"] is False
    assert result["monthly_spend_cap_minor_units"] == 0
    assert result["cluster_provisioned"] is False
    assert result["external_request_sent"] is False
    assert result["provider_price_verified"] is False
    assert "GPU_COST_EXCEEDS_SPEND_CAP" in result["blockers"]
    assert "VERIFIED_REALIZED_REVENUE_REQUIRED_BEFORE_GPU_SPENDING" in result["blockers"]
    assert "SEPARATE_FOUNDER_GPU_RELEASE_APPROVAL_REQUIRED" in result["blockers"]


@pytest.mark.parametrize("amount", [1, 5, 1000, 10000000])
def test_no_caller_can_expand_founder_spend_cap(amount):
    with pytest.raises(ValueError, match="stays at zero"):
        review_edge_expansion(as_of=NOW, founder_spend_cap_cents=amount)


def test_no_caller_can_override_per_candidate_spend_cap():
    with pytest.raises(ValueError, match="budget is frozen"):
        review_gpu_candidate(gpu(monthly_spend_cap_cents=1), as_of=NOW)


def test_synthetic_claimed_revenue_injection_is_rejected():
    raw = gpu()
    raw["revenue_verified"] = True
    with pytest.raises(ValueError, match="exact approved fields"):
        review_gpu_candidate(raw, as_of=NOW)


def test_fake_claimed_payment_injection_is_rejected():
    raw = gpu()
    raw["closed_won_revenue"] = 1_000_000
    with pytest.raises(ValueError, match="exact approved fields"):
        review_gpu_candidate(raw, as_of=NOW)


def test_no_execution_can_be_requested_even_without_gpu():
    with pytest.raises(ValueError, match="cannot request execution"):
        review_edge_expansion(as_of=NOW, observe_only=False)


def test_no_provider_source_can_be_used_directly():
    with pytest.raises(ValueError, match="provider/region"):
        review_gpu_candidate(gpu(provider="unknown-provider"), as_of=NOW)


def test_replica_all_true_still_never_creates_slot_or_primary():
    result = review_replica_candidate(replica())
    assert result["publication_created"] is False
    assert result["replication_slot_created"] is False
    assert result["source_primary_relocated"] is False
    assert result["reader_authority"] == "none"
    assert "REPLICA_TOPOLOGY_AND_LSN_NOT_INDEPENDENTLY_VERIFIED" in result["blockers"]
    assert "LOGICAL_DDL_SEQUENCE_AND_CONFLICT_POLICY_REVIEW_REQUIRED" in result["blockers"]


def test_replica_requires_read_only_purpose():
    with pytest.raises(ValueError, match="only read-only"):
        review_replica_candidate(replica(purpose="multimaster_write"))


def test_logical_and_physical_replica_are_not_equivalent():
    result = review_replica_candidate(replica(replication_mode="physical_standby"))
    assert "LOGICAL_DDL_SEQUENCE_AND_CONFLICT_POLICY_REVIEW_REQUIRED" not in result["blockers"]
    assert "REPLICA_TOPOLOGY_AND_LSN_NOT_INDEPENDENTLY_VERIFIED" in result["blockers"]


def test_quote_missing_stays_unknown_and_never_cost_zero():
    row = review_gpu_candidate(gpu(
        quoted_gpu_hour_cents=None, quote_ref=None, quote_valid_until=None,
        egress_cost_cents=None, total_non_gpu_cost_cents=None,
    ), as_of=NOW)
    assert row["quoted_total_cost_minor_units"] is None
    assert "INDEPENDENT_PROVIDER_QUOTE_REQUIRED" in row["blockers"]


@pytest.mark.parametrize("override", [
    {"gpu_count": 0},
    {"hours": -1},
    {"currency": "AKT"},
    {"container_digest": "latest"},
    {"quote_valid_until": (NOW - timedelta(minutes=1)).isoformat()},
])
def test_gpu_candidate_is_blocked_or_invalid(override):
    if "quote_valid_until" in override:
        result = review_gpu_candidate(gpu(**override), as_of=NOW)
        assert "GPU_QUOTE_EXPIRED" in result["blockers"]
    elif "container_digest" in override:
        result = review_gpu_candidate(gpu(**override), as_of=NOW)
        assert "PINNED_SIGNED_IMAGE_REVIEW_REQUIRED" in result["blockers"]
    else:
        with pytest.raises(ValueError):
            review_gpu_candidate(gpu(**override), as_of=NOW)


def test_revenue_first_zero_input_still_returns_no_spend():
    row = review_edge_expansion(as_of=NOW)
    assert row["gpu_candidates"] == []
    assert row["compute_spend_cap_minor_units"] == 0
    assert row["provider_calls"] == 0
    assert row["independently_verified_realized_revenue_available"] is False
    assert "NO_GPU_OR_EDGE_SPENDING_BEFORE_VERIFIED_REALIZED_REVENUE" in row["blockers"]
