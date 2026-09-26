from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_os_api import create_revenue_os_router
from empire_os.revenue_os_feedback_registry import RevenueOsLearningRecord


class FakeFeedbackRegistry:
    def __init__(self):
        self.rows = {}

    def record_feedback(self, item: RevenueOsLearningRecord):
        item.validate()
        key = item.readiness.packet_key
        if key in self.rows:
            return {
                "status": "existing",
                "feedback_id": self.rows[key]["feedback_id"],
            }
        row = {
            "feedback_id": f"feedback-{len(self.rows) + 1}",
            "packet_key": key,
            "learning_ready": item.readiness.learning_ready,
            "realized_gross_profit_cents": (
                item.readiness.feedback.realized_gross_profit_cents
            ),
        }
        self.rows[key] = row
        return {"status": "recorded", **row}

    def list_feedback(self, *, limit):
        return list(self.rows.values())[:limit]


def client(registry=None):
    app = FastAPI()
    app.include_router(
        create_revenue_os_router(feedback_registry=registry)
    )
    return TestClient(app)


def body(**overrides):
    payload = {
        "packet_key": "packet-1",
        "outcome_observed": True,
        "revenue_recognized": True,
        "recognized_revenue_cents": 26000,
        "observed_cost_cents": 6000,
        "observed_at": "2026-09-20T16:00:00+00:00",
        "evidence_refs": ["outcome:1", "revenue:1", "cost:1"],
        "packet_created_at": "2026-09-20T12:00:00+00:00",
        "now_utc": "2026-09-20T18:00:00+00:00",
        "max_age_seconds": 21600,
        "evidence": {"source": "canonical_revenue_outcome"},
    }
    payload.update(overrides)
    return payload


def test_unbound_feedback_registry_fails_closed():
    response = client().post(
        "/v1/revenue-os/feedback/register",
        json=body(),
    )
    assert response.status_code == 503


def test_learning_ready_feedback_registers_without_mutation():
    response = client(FakeFeedbackRegistry()).post(
        "/v1/revenue-os/feedback/register",
        json=body(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recorded"
    assert data["mode"] == "OBSERVE"
    assert data["side_effects"] == "none"
    assert data["execution_authority"] == "none"
    assert data["model_weight_mutation"] is False
    assert data["capital_reallocation"] is False
    assert data["spend_execution"] is False
    assert data["outreach_execution"] is False
    assert data["payment_execution"] is False
    assert data["allocation_execution"] is False
    assert data["deployment_execution"] is False
    assert data["feedback_record"]["eligible_for_model_review"] is True
    assert (
        data["feedback_record"]["readiness"]["feedback"][
            "realized_gross_profit_cents"
        ]
        == 20000
    )


def test_blocked_feedback_can_be_audited_but_not_model_ready():
    response = client(FakeFeedbackRegistry()).post(
        "/v1/revenue-os/feedback/register",
        json=body(observed_cost_cents=None),
    )
    assert response.status_code == 200
    record = response.json()["feedback_record"]
    assert record["eligible_for_model_review"] is False
    assert "observed_cost_evidence_missing" in (
        record["readiness"]["blockers"]
    )


def test_feedback_registry_is_idempotent_and_history_is_read_only():
    repo = FakeFeedbackRegistry()
    c = client(repo)
    first = c.post("/v1/revenue-os/feedback/register", json=body())
    second = c.post("/v1/revenue-os/feedback/register", json=body())
    history = c.get("/v1/revenue-os/feedback/history")
    assert first.status_code == 200
    assert first.json()["status"] == "recorded"
    assert second.json()["status"] == "existing"
    assert history.status_code == 200
    payload = history.json()
    assert payload["read_only"] is True
    assert payload["side_effects"] == "none"
    assert payload["execution_authority"] == "none"
    assert payload["model_weight_mutation"] is False
    assert payload["capital_reallocation"] is False
    assert payload["count"] == 1


def test_registry_requires_provenance_evidence():
    response = client(FakeFeedbackRegistry()).post(
        "/v1/revenue-os/feedback/register",
        json=body(evidence={}),
    )
    assert response.status_code == 422
    assert "requires evidence" in response.json()["detail"]
