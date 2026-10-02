from datetime import datetime, timezone
from types import SimpleNamespace

import scripts.run_buyer_deferred_enrichment as worker


NOW = datetime(2026, 10, 2, 22, 0, tzinfo=timezone.utc)


def _candidate():
    return SimpleNamespace(
        prospect_id="00000000-0000-0000-0000-000000000111"
    )


def _result():
    return {
        "decision_maker": {
            "name": "Jane Buyer",
            "title": "Owner",
            "decision_score": 1.0,
        },
        "review_ready": True,
        "outreach_ready": True,
        "preferred_email": "jane@example.com",
        "verified_contacts": [{"email": "jane@example.com"}],
        "person_bound": True,
    }


def test_review_key_is_daily_bounded_and_versioned():
    key = worker._review_idempotency_key(
        str(_candidate().prospect_id),
        "Jane@Example.com",
        now=NOW,
    )
    assert key.endswith(
        ":jane@example.com:reverified:2026-10-02:v2"
    )


def test_fresh_existing_review_is_reused_without_post(monkeypatch):
    calls = []

    def request(method, path, payload=None, **kwargs):
        calls.append((method, path, payload))
        if method == "GET":
            return [{
                "id": "review-fresh",
                "status": "approved",
                "proposed_at": "2026-10-01T20:00:00+00:00",
                "reviewed_at": "2026-10-01T20:02:00+00:00",
            }]
        raise AssertionError("fresh review must not be proposed again")

    monkeypatch.setattr(worker, "request_json", request)
    outcome = worker._propose_review(_candidate(), _result())

    assert outcome["decision"] == "existing_fresh"
    assert outcome["review_id"] == "review-fresh"
    assert [call[0] for call in calls] == ["GET"]


def test_stale_review_creates_new_reverification_review(monkeypatch):
    calls = []
    seen_key = {}

    def request(method, path, payload=None, **kwargs):
        calls.append((method, path, payload))
        if method == "GET":
            return [{
                "id": "review-stale",
                "status": "approved",
                "proposed_at": "2026-09-01T20:00:00+00:00",
                "reviewed_at": "2026-09-01T20:02:00+00:00",
            }]
        return {
            "decision": "proposed",
            "review_id": "review-new",
            "status": "pending",
        }

    def build(candidate, contact_plan, *, idempotency_key):
        seen_key["value"] = idempotency_key
        return {"params": {"p_evidence": {}}}

    monkeypatch.setattr(worker, "request_json", request)
    monkeypatch.setattr(worker, "build_candidate_review_plan", build)
    outcome = worker._propose_review(_candidate(), _result())

    assert outcome["decision"] == "proposed"
    assert outcome["review_id"] == "review-new"
    assert ":reverified:" in seen_key["value"]
    assert [call[0] for call in calls] == ["GET", "POST"]
