from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.data_plane_api import create_data_plane_router


def client():
    app = FastAPI()
    app.include_router(create_data_plane_router())
    return TestClient(app)


def test_health_is_observe_only():
    body = client().get("/v1/data-plane/health").json()
    assert body["canonical_operational_truth"] == "supabase_postgresql"
    assert body["deployment_enabled"] is False
    assert body["schema_mutation"] is False
    assert body["execution_authority"] == "none"


def test_readiness_preview_never_deploys():
    body = client().post(
        "/v1/data-plane/readiness/preview",
        json={"evidence": {
            "raw_gb_per_day": 20,
            "raw_retention_days": 90,
            "multimodal_objects_per_day": 5000,
            "event_backlog": 100000,
            "independent_consumers": 8,
            "p95_ingest_lag_seconds": 120,
            "analytical_rows": 500000000,
            "p95_analytical_query_seconds": 12,
            "postgres_analytics_cpu_pct": 80,
            "search_documents": 50000000,
            "p95_search_latency_ms": 1200,
            "search_qps": 250,
            "multi_hop_graph_queries_per_minute": 2000,
            "p95_graph_query_ms": 2500,
            "required_regions": 3,
            "monthly_unavailability_minutes": 45,
            "cross_region_users_pct": 60,
        }},
    ).json()
    assert len(body["review_recommended"]) == 6
    assert body["deployment_enabled"] is False
    assert body["migration_execution"] is False


def test_replay_endpoint_is_preview_only():
    body = client().post(
        "/v1/data-plane/replay/plan/preview",
        json={"request": {
            "source_key": "storm.nws",
            "partition": "2026-09-19",
            "start_at": "2026-09-19T00:00:00Z",
            "end_at": "2026-09-19T23:59:59Z",
            "max_records": 10000,
        }},
    ).json()
    assert body["ready_for_operator_review"] is True
    assert body["replay_execution"] is False
    assert body["execution_authority"] == "none"


def test_event_preview_validates_contract_and_never_persists():
    response = client().post(
        "/v1/data-plane/event/preview",
        json={"data": {
            "event_id": "evt-1",
            "event_type": "permit.observed",
            "aggregate_type": "permit",
            "aggregate_id": "permit-1",
            "schema_version": "v1",
            "source_key": "permit.miami",
            "observed_at": "2026-09-20T00:00:00+00:00",
            "emitted_at": "2026-09-20T00:00:01+00:00",
            "correlation_id": "corr-1",
            "idempotency_key": "permit:1",
            "evidence_refs": ["raw.permit.1"],
            "payload": {"permit_id": "permit-1"},
        }},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["persisted"] is False
    assert body["execution_authority"] == "none"

    invalid = client().post(
        "/v1/data-plane/event/preview",
        json={"data": {"event_id": "evt-1"}},
    )
    assert invalid.status_code == 422
