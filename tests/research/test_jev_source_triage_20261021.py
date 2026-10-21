"""Jev/Laya may only suggest a human review lane."""
import json
from copy import deepcopy
from pathlib import Path
import pytest

from empire_os.research.jev_source_triage import triage_original_sources
from empire_os.typed_decision_provider import TypedDecisionResult

LEDGER = Path(__file__).resolve().parents[2] / "docs/commercial/RESEARCH_SOLAR_HVAC_LEGAL_PROPERTY_UK_US_OFFICIAL_SOURCES_20261021.json"


def source():
    return json.loads(LEDGER.read_text())


class LocalProvider:
    def __init__(self, *, label="RIGHTS_REVIEW", confidence=.9, fail=False, key="laya_http", shadow=True):
        self.calls = []
        self.label, self.confidence, self.fail = label, confidence, fail
        self.key, self.shadow = key, shadow

    def evaluate(self, request):
        assert set(request.state) == {
            "sector", "market", "observed_shape", "topic_anchor_count",
            "source_kind", "licensed_for_reuse", "editorial_approved"
        }
        assert request.state["licensed_for_reuse"] is False
        assert request.state["editorial_approved"] is False
        assert "http" not in json.dumps(request.state)
        self.calls.append(request)
        if self.fail:
            raise RuntimeError("local provider unavailable")
        return TypedDecisionResult(
            provider_key=self.key, model_key="laya-local-fixture",
            task_key=request.task_key, decision_schema_ref=request.decision_schema_ref,
            state_ref=request.state_ref, label=self.label,
            confidence=self.confidence, latency_ms=2,
            source_ref="local:shadow:fixture", shadow_only=self.shadow,
            execution_authority="none",
        )


def test_deterministic_original_source_review():
    result = triage_original_sources(source())
    assert result["original_sources_reviewed"] == 15
    assert result["deterministic_review_lane_counts"] == {
        "HOLD": 4, "REINSPECT_SOURCE": 2,
        "RIGHTS_REVIEW": 1, "EDITORIAL_REVIEW": 8
    }
    assert result["shadow_model_calls_attempted"] == 0
    assert result["trusted_research_sources_admitted"] == 0
    assert result["database_writes"] is False
    assert result["outbound_authorized"] is False


def test_bounded_local_shadow_never_overrides_review_authority():
    provider = LocalProvider(label="EDITORIAL_REVIEW")
    result = triage_original_sources(source(), provider=provider, max_shadow_calls=3)
    assert len(provider.calls) == 3
    assert result["shadow_model_calls_attempted"] == 3
    assert all(x["source_admitted"] is False for x in result["review_items"])
    assert result["deterministic_review_lane_counts"]["HOLD"] == 4
    assert result["execution_authority"] == "none"
    assert result["external_paid_jev_api_called"] is False


def test_sidecar_down_retains_deterministic_result():
    provider = LocalProvider(fail=True)
    result = triage_original_sources(source(), provider=provider, max_shadow_calls=2)
    assert len(provider.calls) == 2
    assert sum(x["model_advisory_status"] == "SHADOW_UNAVAILABLE_HELD"
               for x in result["review_items"]) == 2
    assert result["trusted_research_sources_admitted"] == 0


@pytest.mark.parametrize("kwargs", [
    {"label": "SOURCE_APPROVED"},
    {"key": "external_provider"},
    {"shadow": False},
    {"confidence": float("nan")},
])
def test_malformed_or_untrusted_model_output_is_held(kwargs):
    provider = LocalProvider(**kwargs)
    result = triage_original_sources(source(), provider=provider, max_shadow_calls=1)
    assert result["review_items"][0]["model_advisory_status"] == "SHADOW_UNAVAILABLE_HELD"
    assert result["trusted_research_sources_admitted"] == 0


@pytest.mark.parametrize("field,value", [
    ("source_admitted", True),
    ("source_license_or_reuse_rights_verified", True),
    ("customer_demand_verified", True),
    ("editorial_owner_signed_off", True),
    ("source_body_sha256", "bogus"),
    ("individual_property_or_person_records_fetched", 1),
])
def test_forged_original_source_rejected(field, value):
    evidence = source()
    evidence["rows"][0][field] = value
    with pytest.raises(ValueError):
        triage_original_sources(evidence)


def test_held_only_rows_never_call_model():
    evidence = source()
    evidence["rows"] = [x for x in evidence["rows"]
                        if x["status"] == "ORIGINAL_SOURCE_FETCH_OR_TOPIC_HELD"]
    evidence["total_exact_sources_checked"] = len(evidence["rows"])
    provider = LocalProvider()
    result = triage_original_sources(evidence, provider=provider, max_shadow_calls=4)
    assert result["shadow_model_calls_attempted"] == 0
    assert not provider.calls


def test_explicit_local_shadow_budget_required():
    with pytest.raises(ValueError):
        triage_original_sources(source(), max_shadow_calls=1)
    with pytest.raises(ValueError):
        triage_original_sources(source(), max_shadow_calls=9)


def test_late_row_tampering_stops_all_provider_calls():
    evidence = source()
    evidence["rows"][-1]["source_admitted"] = True
    provider = LocalProvider()
    with pytest.raises(ValueError):
        triage_original_sources(evidence, provider=provider, max_shadow_calls=2)
    assert not provider.calls


def test_low_confidence_model_has_escalation_without_changing_lane():
    provider = LocalProvider(label="HOLD", confidence=.51)
    result = triage_original_sources(source(), provider=provider, max_shadow_calls=1)
    first = result["review_items"][0]
    assert first["model_advisory_status"] == "SHADOW_ESCALATE"
    assert first["deterministic_review_lane"] == "EDITORIAL_REVIEW"
    assert first["proposed_model_lane"] == "HOLD"
    assert first["source_admitted"] is False


def test_pinned_local_shadow_receipt_matches_original_ledger_without_rights():
    import hashlib
    from scripts.review_empire_research_jev_alignment_20261021 import LEDGER as SOURCE_NAME, RECEIPT as RECEIPT_NAME
    folder = LEDGER.parent
    receipt = json.loads((folder / RECEIPT_NAME).read_text())
    original = json.loads((folder / SOURCE_NAME).read_text())
    fingerprint = hashlib.sha256(json.dumps(original, sort_keys=True).encode()).hexdigest()
    assert receipt["input_sha256"] == fingerprint
    assert receipt["status"] == "RESEARCH_LOCAL_SHADOW_COMPARISON_REVIEW_ONLY"
    assert receipt["original_source_count"] == 15
    assert receipt["local_shadow_attempts"] == 2
    assert receipt["trusted_source_admissions"] == 0
    assert receipt["human_editorial_signoff_present"] is False
    assert receipt["model_disagreements_with_deterministic"] == 2
    assert receipt["external_paid_jev_api_called"] is False
    assert receipt["db_writes"] is False
    assert receipt["messages_sent"] == 0
    assert receipt["execution_authority"] == "none"
