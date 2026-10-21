"""One real Jev decision receipt is not readiness, authority, or revenue."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from empire_os.search_intelligence.jev_pilot_receipt import (
    JevReceiptUnavailable, review_jev_private_pilot_receipt,
)
from empire_os.search_intelligence.service import build_search_intelligence_service


def sample_receipt():
    return {
        "schema_version": "empire.search.jev_real_one_shot_result.v1",
        "provider_key": "openrouter_typesafe_jev",
        "model": "typesafe/jev-1.13-20260917",
        "actual_jev_inference_calls": 1,
        "jev_decision_observed": True,
        "decision_label": "ABSTAIN",
        "decision_confidence": 0.46,
        "decision_probabilities": {
            "SOURCE_AUDIT": 0.33,
            "TECHNICAL_REPAIR_REVIEW": 0.01,
            "EDITORIAL_REVIEW": 0.08,
            "MONITOR": 0.01,
            "ABSTAIN": 0.57,
        },
        "review_priority_confidence": 0.23,
        "review_priority_score": 0.76,
        "human_review_yes_probability": 0.84,
        "input_tokens": 707,
        "cost_usd_reported": 0.000029694,
        "source_sha256": "f" * 64,
        "ground_truth_or_accuracy_verified": False,
        "decision_controls_live_traffic": False,
        "buyer_or_personal_data_sent": False,
        "database_writes": False,
        "publishing_authorized": False,
        "buyer_routing_authorized": False,
        "execution_authority": "NONE",
    }


def write_receipt(tmp_path, receipt):
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt))
    path.chmod(0o600)
    return path


def test_single_real_receipt_becomes_read_only_scalar_proof(tmp_path):
    fixture = sample_receipt()
    fixture["email"] = "sensitive@example.test"
    fixture["api_key"] = "DO_NOT_EXPOSE"
    receipt = review_jev_private_pilot_receipt(write_receipt(tmp_path, fixture))
    assert receipt["actual_jev_inference_calls_observed"] == 1
    assert receipt["decision_label"] == "ABSTAIN"
    assert receipt["human_review_yes_probability"] == 0.84
    assert receipt["provider_enabled_for_unattended_runs"] is False
    assert receipt["new_provider_calls_triggered"] == 0
    assert receipt["replay_billing_authorized"] is False
    assert receipt["publication_authorized"] is False
    assert receipt["execution_authority"] == "NONE"
    assert "DO_NOT_EXPOSE" not in str(receipt)
    assert "sensitive@" not in str(receipt)


@pytest.mark.parametrize("field,value", [
    ("actual_jev_inference_calls", 2),
    ("provider_key", "not_jev"),
    ("model", "other/model"),
    ("cost_usd_reported", 10),
    ("input_tokens", 99_999),
    ("ground_truth_or_accuracy_verified", True),
    ("database_writes", True),
    ("publishing_authorized", True),
    ("buyer_routing_authorized", True),
    ("execution_authority", "PUBLISH"),
    ("human_review_yes_probability", 1.5),
])
def test_false_or_dangerous_receipts_are_rejected(tmp_path, field, value):
    receipt = sample_receipt()
    receipt[field] = value
    with pytest.raises(JevReceiptUnavailable):
        review_jev_private_pilot_receipt(write_receipt(tmp_path, receipt))


def test_receipt_symlink_and_bad_permissions_rejected(tmp_path):
    path = write_receipt(tmp_path, sample_receipt())
    path.chmod(0o644)
    with pytest.raises(JevReceiptUnavailable):
        review_jev_private_pilot_receipt(path)
    path.chmod(0o600)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(JevReceiptUnavailable):
        review_jev_private_pilot_receipt(link)


def test_http_receipt_endpoint_read_only_and_fail_closed(monkeypatch, tmp_path):
    import empire_os.search_intelligence.api as api
    receipt = write_receipt(tmp_path, sample_receipt())
    monkeypatch.setattr(api, "review_jev_private_pilot_receipt",
                        lambda: review_jev_private_pilot_receipt(receipt))
    client = TestClient(build_search_intelligence_service())
    reply = client.get("/v1/search/jev/pilot/receipt")
    assert reply.status_code == 200
    assert reply.headers["cache-control"] == "no-store"
    assert reply.headers["x-content-type-options"] == "nosniff"
    assert reply.json()["new_provider_calls_triggered"] == 0
    monkeypatch.setattr(api, "review_jev_private_pilot_receipt",
                        lambda: (_ for _ in ()).throw(
                            JevReceiptUnavailable("secret internal path")))
    bad = client.get("/v1/search/jev/pilot/receipt")
    assert bad.status_code == 503
    assert bad.json()["detail"] == "jev_pilot_receipt_unavailable"
    assert "secret internal path" not in str(bad.json())
