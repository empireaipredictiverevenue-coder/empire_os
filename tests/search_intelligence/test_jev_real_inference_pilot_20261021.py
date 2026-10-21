"""No network test: typed real-provider adapter and spending/privacy fail-closed."""
from copy import deepcopy

import pytest

import empire_os.search_intelligence.jev_live_pilot as mod


def safe_department():
    return {
        "gsc_returned_page_rows": 32,
        "gsc_final_page_window": ["2026-10-07", "2026-10-19"],
    }


def stub_portfolio(**kwargs):
    return {
        "schema_version": "empire.search.jev_department_portfolio.v1",
        "execution_authority": "NONE",
        "jev_inference_calls": 0,
        "database_writes": False,
        "publication_authority": False,
        "source_sample_window": ["2026-10-07", "2026-10-19"],
        "task_board": [{
            "task_id": "GSC_404_RECOVERY",
            "evidence_state": "AGGREGATE_REVIEW_AVAILABLE",
            "risk_class": "medium",
            "automatic_execution_authorized": False,
            "aggregate_scalar_evidence": {
                "legacy_missing_404_count_in_returned_page_sample": 30,
                "legacy_missing_404_impressions_in_returned_page_sample": 44,
                "legacy_404_core_topic_editorial_review_count": 15,
            },
        }],
    }


def valid_plan(monkeypatch):
    monkeypatch.setattr(mod, "review_jev_department_portfolio", stub_portfolio)
    return mod.build_jev_one_shot_plan(department=safe_department())


def sample_vendor_response():
    return {
        "model": "typesafe/jev-1.13-20260917",
        "answers": {
            "next_review": {
                "type": "choice",
                "choice": "TECHNICAL_REPAIR_REVIEW",
                "probabilities": {
                    "SOURCE_AUDIT": 0.03,
                    "TECHNICAL_REPAIR_REVIEW": 0.8,
                    "EDITORIAL_REVIEW": 0.12,
                    "MONITOR": 0.04,
                    "ABSTAIN": 0.01,
                },
                "confidence": 0.8,
            },
            "investigation_priority": {
                "type": "score",
                "score": 2.5,
                "confidence": 0.7,
            },
            "requires_human": {"type": "noul", "noul": 0.99},
        },
        "usage": {"input_tokens": 640, "output_tokens": 50,
                  "cost": 0.00002688},
    }


class FakeReply:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def test_one_shot_follows_original_department_and_excludes_sensitive_rows(monkeypatch):
    p = valid_plan(monkeypatch)
    assert p["expected_endpoint"] == "https://openrouter.ai/api/alpha/decisions"
    assert p["request"]["model"] == "typesafe/jev-1.13"
    assert p["max_expected_request_count"] == 1
    assert set(p["request"]["questions"]) == {
        "next_review", "investigation_priority", "requires_human"
    }
    assert p["request"]["questions"]["next_review"]["type"] == "choice"
    assert p["request"]["questions"]["investigation_priority"]["type"] == "score"
    assert p["request"]["questions"]["requires_human"]["type"] == "noul"
    assert p["state"]["sample_page_rows"] == 32
    assert p["state"]["missing_page_rows_in_sample"] == 30
    assert p["state"]["core_topic_editorial_candidates"] == 15
    assert p["raw_query_or_customer_data_sent"] is False
    assert "email" not in str(p)
    assert p["execution_authority"] == "NONE"


def test_mock_jev_contract_validates_actual_provider_output(monkeypatch):
    p = valid_plan(monkeypatch)
    recorded = []

    def fake_post(url, **kw):
        recorded.append((url, kw))
        return FakeReply(sample_vendor_response())

    result = mod.evaluate_jev_one_shot(
        p, key="sk-" + "x"*30, post=fake_post)
    assert len(recorded) == 1
    url, kw = recorded[0]
    assert url == mod.ENDPOINT
    assert kw["timeout"] == 12 and kw["allow_redirects"] is False
    assert kw["json"]["model"] == "typesafe/jev-1.13"
    assert result["provider_key"] == "openrouter_typesafe_jev"
    assert result["actual_jev_inference_calls"] == 1
    assert result["decision_label"] == "TECHNICAL_REPAIR_REVIEW"
    assert result["cost_usd_reported"] < mod.MAX_COST_USD
    assert result["publishing_authorized"] is False
    assert result["buyer_routing_authorized"] is False
    assert result["execution_authority"] == "NONE"


@pytest.mark.parametrize("modification", [
    lambda a: a["answers"]["next_review"].update(choice="PUBLISH_NOW"),
    lambda a: a["answers"]["next_review"].update(confidence=2),
    lambda a: a["answers"]["requires_human"].update(noul=-0.2),
    lambda a: a["answers"]["investigation_priority"].update(score=999),
    lambda a: a["usage"].update(cost=20),
    lambda a: a["usage"].pop("cost"),
    lambda a: a.update(model="untrusted/chat"),
    lambda a: a["answers"]["next_review"]["probabilities"].update(MONITOR=8.0),
])
def test_unsafe_vendor_output_fails_closed(monkeypatch, modification):
    p = valid_plan(monkeypatch)
    payload = sample_vendor_response()
    modification(payload)
    with pytest.raises(mod.JevPilotHeld):
        mod.evaluate_jev_one_shot(p, key="sk-"+"x"*30,
                                  post=lambda *_a, **_kw: FakeReply(payload))


def test_no_network_on_scope_mutation_and_missing_key(monkeypatch):
    p = valid_plan(monkeypatch)

    def reject(*args, **kwargs):
        pytest.fail("No external request allowed")

    changed = deepcopy(p)
    changed["request"]["state"]["customer_email"] = "test@example.test"
    with pytest.raises(mod.JevPilotHeld):
        mod.evaluate_jev_one_shot(changed, key="sk-"+"x"*30, post=reject)
    with pytest.raises(mod.JevPilotHeld, match="key_not_configured"):
        mod.evaluate_jev_one_shot(p, key="missing", post=reject)


def test_no_error_response_body_logged(monkeypatch):
    p = valid_plan(monkeypatch)
    reply = FakeReply({"secret": "NEVER_OUTPUT"})
    reply.status_code = 401
    with pytest.raises(mod.JevPilotHeld) as exc:
        mod.evaluate_jev_one_shot(p, key="sk-"+"x"*30,
                                  post=lambda *_a, **_kw: reply)
    assert str(exc.value) == "jev_http_401"
    assert "NEVER_OUTPUT" not in str(exc.value)
