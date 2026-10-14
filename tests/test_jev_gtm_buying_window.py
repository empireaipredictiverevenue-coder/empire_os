"""Observed momentum requires distinct non-overlapping evidence groups."""
from datetime import datetime, timedelta, timezone
import pytest

from empire_os.jev_gtm_v2 import review_gtm_signals, build_jev_gtm_decision
from empire_os.jev_gtm_buying_window import assess_buying_window

NOW = datetime(2026, 10, 14, 9, tzinfo=timezone.utc)


def signal(sid, kind, source, evidence, *, age_days=0, contradicted=False):
    return {
        "signal_id": sid, "signal_type": kind, "source_id": source,
        "observed_at": (NOW - timedelta(days=age_days)).isoformat(),
        "truth_class": "OBSERVED",
        "entity_id": "company:1", "tenant_id": "tenant:1",
        "evidence_refs": [evidence], "contradicted": contradicted,
    }


def assess(signals):
    validated = review_gtm_signals(
        signals, as_of=NOW, entity_id="company:1", tenant_id="tenant:1",
    )
    return assess_buying_window(validated)


def test_two_different_signal_types_and_sources_observed():
    result = assess([
        signal("1", "hiring", "jobs", "job-ref"),
        signal("2", "expansion", "filings", "filing-ref"),
    ])
    assert result["status"] == "MULTI_SIGNAL_WINDOW_OBSERVED"
    assert result["independent_evidence_group_count"] == 2
    assert result["buyer_purchase_intent_verified"] is False
    assert result["purchase_probability"] is None


def test_same_source_does_not_fake_convergence():
    result = assess([
        signal("1", "hiring", "jobs", "job-ref"),
        signal("2", "expansion", "jobs", "same-domain-other-ref"),
    ])
    assert result["status"] == "SINGLE_SOURCE_OR_SIGNAL_WATCH"
    assert result["independent_evidence_group_count"] == 1


def test_republished_same_document_does_not_fake_independence():
    result = assess([
        signal("1", "hiring", "feed:1", "same-source-ref"),
        signal("2", "expansion", "feed:2", "same-source-ref"),
    ])
    assert result["independent_evidence_group_count"] == 1


def test_two_distinct_sources_with_same_signal_type_are_insufficient():
    result = assess([
        signal("1", "hiring", "jobs:1", "proof:1"),
        signal("2", "hiring", "jobs:2", "proof:2"),
    ])
    assert result["status"] == "SINGLE_SOURCE_OR_SIGNAL_WATCH"


def test_old_signals_not_counted_as_current_buying_window():
    result = assess([
        signal("1", "hiring", "jobs", "proof:1", age_days=31),
        signal("2", "expansion", "filings", "proof:2", age_days=40),
    ])
    assert result["status"] == "NO_RECENT_SIGNAL"
    assert result["signal_count"] == 0


def test_contradiction_overrides_convergence():
    result = assess([
        signal("1", "hiring", "jobs", "proof:1", contradicted=True),
        signal("2", "expansion", "filings", "proof:2"),
    ])
    assert result["status"] == "CONTRADICTORY_REVIEW"


def test_cross_tenant_signal_excluded_before_momentum():
    bad = signal("bad", "expansion", "filings", "proof:2")
    bad["tenant_id"] = "tenant:other"
    result = assess([signal("ok", "hiring", "jobs", "proof:1"), bad])
    assert result["status"] == "SINGLE_SOURCE_OR_SIGNAL_WATCH"


def test_momentum_cannot_override_execution_gate():
    account = {
        "entity_id": "company:1", "tenant_id": "tenant:1",
        "opportunity_key": "op:1", "entity_verified": True,
        "tenant_binding_verified": True,
        "description": "roofing company hiring",
        "target_buyer_pools": ["local_and_smb_buyers"],
        "target_product_codes": ["managed_service"],
    }
    reviewed = build_jev_gtm_decision(
        account=account,
        signals=[
            signal("1", "hiring", "jobs", "proof:1"),
            signal("2", "expansion", "filings", "proof:2"),
        ],
        as_of=NOW,
        outreach={"suppression_checked": False, "suppression_state": "UNKNOWN"},
    )
    assert reviewed["buying_window"]["status"] == "MULTI_SIGNAL_WINDOW_OBSERVED"
    assert reviewed["action"] == "EVIDENCE_REVIEW"
    assert reviewed["outbound_approved"] is False


def test_rejects_invalid_clock_window():
    with pytest.raises(ValueError, match="bounded"):
        assess_buying_window({"fresh": [], "execution_authority": "none"}, recent_days=365)
