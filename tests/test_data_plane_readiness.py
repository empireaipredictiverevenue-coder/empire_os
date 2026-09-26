from empire_os.data_plane_readiness import (
    assess_data_contract_readiness,
    assess_data_plane_readiness,
    assess_replay_plan,
)


def full_low_scale_evidence():
    return {
        "raw_gb_per_day": 0.5,
        "raw_retention_days": 14,
        "multimodal_objects_per_day": 100,
        "event_backlog": 50,
        "independent_consumers": 2,
        "p95_ingest_lag_seconds": 3,
        "analytical_rows": 1_000_000,
        "p95_analytical_query_seconds": 0.5,
        "postgres_analytics_cpu_pct": 15,
        "search_documents": 100_000,
        "p95_search_latency_ms": 80,
        "search_qps": 5,
        "multi_hop_graph_queries_per_minute": 10,
        "p95_graph_query_ms": 100,
        "required_regions": 1,
        "monthly_unavailability_minutes": 1,
        "cross_region_users_pct": 5,
    }


def test_current_stack_remains_sufficient_at_low_scale():
    result = assess_data_plane_readiness(full_low_scale_evidence())
    assert result["review_recommended"] == []
    assert result["insufficient_evidence"] == []
    assert all(
        item["state"] == "CURRENT_STACK_SUFFICIENT"
        for item in result["components"]
    )
    assert result["deployment_enabled"] is False
    assert result["execution_authority"] == "none"


def test_measured_bottlenecks_recommend_review_not_deployment():
    evidence = full_low_scale_evidence()
    evidence.update({
        "raw_gb_per_day": 8,
        "event_backlog": 50000,
        "independent_consumers": 6,
        "analytical_rows": 250_000_000,
        "p95_analytical_query_seconds": 8,
        "search_documents": 20_000_000,
    })
    result = assess_data_plane_readiness(evidence)
    assert "durable_raw_object_storage" in result["review_recommended"]
    assert "event_backbone_kafka_redpanda" in result["review_recommended"]
    assert "analytical_engine_clickhouse" in result["review_recommended"]
    assert "dedicated_search_engine" in result["review_recommended"]
    assert result["deployment_enabled"] is False


def test_missing_workload_metrics_remain_unknown():
    result = assess_data_plane_readiness({})
    assert result["review_recommended"] == []
    assert len(result["insufficient_evidence"]) == 6
    assert all(
        item["state"] == "INSUFFICIENT_EVIDENCE"
        for item in result["components"]
    )


def test_data_contract_requires_identity_privacy_and_time_semantics():
    result = assess_data_contract_readiness({
        "namespace": "empire.permit",
        "schema_name": "observation",
        "schema_version": "v1",
        "owner": "data-platform",
        "compatibility_mode": "backward",
        "privacy_class": "PUBLIC",
        "idempotency_semantics": "source-record-id",
        "retention_class": "raw-365d",
        "fields": [{"name": "permit_id", "type": "string"}],
        "time_semantics": {
            "event_time_field": "observed_at",
            "processing_time_field": "fetched_at",
        },
    })
    assert result["ready_for_review"] is True
    assert result["registry_mutation"] is False

    bad = assess_data_contract_readiness({
        "namespace": "x",
        "privacy_class": "MAGIC",
        "fields": [],
    })
    assert bad["ready_for_review"] is False
    assert "unsupported_privacy_class" in bad["blockers"]


def test_replay_plan_is_bounded_dry_run_only():
    result = assess_replay_plan({
        "source_key": "permit.miami",
        "partition": "2026-09-19",
        "start_at": "2026-09-19T00:00:00Z",
        "end_at": "2026-09-20T00:00:00Z",
        "max_records": 5000,
    })
    assert result["ready_for_operator_review"] is True
    assert result["replay_execution"] is False
    assert result["production_write"] is False

    too_big = assess_replay_plan({
        "source_key": "permit.miami",
        "partition": "2026-09",
        "start_at": "2026-09-01T00:00:00Z",
        "end_at": "2026-10-01T00:00:00Z",
        "max_records": 1000000,
    })
    assert too_big["ready_for_operator_review"] is False
    assert "max_records_exceeds_preview_limit" in too_big["blockers"]
