"""Call loss is reason-coded only from approved original owner aggregates."""
import json
from datetime import datetime, timezone
from pathlib import Path
import pytest

from empire_os.competitor_call_loss_readiness import (
    SCHEMA, COUNTS, NO_CONNECT_REASONS, NO_PAYABLE_REASONS,
    summarize_readable_pulse, evaluate_approved_call_cohort,
)
from empire_os.competitor_intelligence_feed import build_feed_runtime

NOW = datetime(2026, 10, 27, 14, tzinfo=timezone.utc)

def pulse():
    return {
        "schema_version": "empire.lead_smart.commercial_pulse.v1",
        "buyer": "Lead Smart",
        "raw_call_identifiers_persisted": False,
        "caller_personal_data_persisted": False,
        "no_real_revenue_inferred_from_tracking": True,
        "qualified_billable_calls_verified": False,
        "settled_revenue_verified": False,
        "observed_at_utc": "2026-10-27T11:36:56+00:00",
        "campaign_expires_at": "2026-10-26T21:44:00+00:00",
        "ringba": {
            "status": "RESTRICTED_PROVIDER_ROWS_OBSERVED",
            "buyer_leg_connected_verified": False,
            "matching_rows_in_returned_window": 0,
        },
    }

def pilot():
    return {
        "schema_version": "empire.lead_smart.effective_pilot_state.v1",
        "buyer": "Lead Smart",
        "execution_authority": "NONE",
        "revenue_recognized": False,
        "mode": "PREACTIVATION",
        "routing_enabled": False,
        "traffic_enabled": False,
    }

def cohort(connected=60, human=50, accepted=30, settled=20, **flags):
    counts = {
        "provider_incoming_calls": 100,
        "provider_target_connected_calls": connected,
        "buyer_human_answered_calls": human,
        "buyer_accepted_payable_calls": accepted,
        "independently_settled_calls": settled,
    }
    reasons = {key: 0 for key in NO_CONNECT_REASONS}
    reasons["TARGET_NO_ANSWER"] = 40
    unpayable = {key: 0 for key in NO_PAYABLE_REASONS}
    unpayable["WRONG_GEOGRAPHY"] = 20
    return evaluate_approved_call_cohort(
        source_id="organic_search",
        cohort_ref="SYNTHETIC_COHORT_NO_REAL_REVENUE",
        counts=flags.get("counts", counts),
        no_connect_reasons=flags.get("no_connect_reasons", reasons),
        no_payable_reasons=flags.get("no_payable_reasons", unpayable),
        refs={key: "synthetic:receipt:" + key for key in COUNTS},
        original_owner_authorized=flags.get("original_owner_authorized", True),
        source_lineage_verified=flags.get("source_lineage_verified", True),
        buyer_acceptance_verified=flags.get("buyer_acceptance_verified", True),
        unique_inbound_terminal_dispositions_verified=flags.get(
            "unique_inbound_terminal_dispositions_verified", True),
    )

def test_live_pulse_zero_rows_is_not_zero_traffic_or_calls():
    result = summarize_readable_pulse(pulse(), pilot(), now=NOW)
    assert result["schema_version"] == SCHEMA
    assert result["original_commercial_pulse_fresh"]
    assert result["ringba_matching_rows_bounded_observation"] == 0
    assert result["bounded_rows_absence_is_proof_of_no_calls"] is False
    assert result["buyer_target_connection_verified"] is False
    assert result["buyer_human_answer_count_verified"] is None
    assert result["ringba_target_connected_count_verified"] is None
    assert result["accepted_payable_call_count_verified"] is None
    assert result["actual_cash_margin_cents"] is None
    assert result["campaign_expiry_in_pulse_is_past"]
    assert not result["campaign_expiry_is_provider_currently_confirmed"]
    assert result["pilot_mode"] == "PREACTIVATION"
    assert result["top_owner_action"] == "VERIFY_ORIGINAL_CAMPAIGN_EXPIRY_WITH_OWNER"
    assert not result["live_call_activation_authorized"]

def test_stale_pulse_does_not_derive_zero_calls():
    result = summarize_readable_pulse(
        pulse(), pilot(), now=datetime(2026, 11, 7, tzinfo=timezone.utc)
    )
    assert not result["original_commercial_pulse_fresh"]
    assert result["ringba_matching_rows_bounded_observation"] is None
    assert not result["campaign_expiry_in_pulse_is_past"]

def test_fake_or_privacy_invasive_pulse_is_rejected():
    bad = pulse()
    bad["raw_call_identifiers_persisted"] = True
    result = summarize_readable_pulse(bad, pilot(), now=NOW)
    assert not result["original_commercial_pulse_available"]
    assert result["ringba_matching_rows_bounded_observation"] is None

def test_real_owner_approved_reason_taxonomy_is_internally_consistent():
    result = cohort()
    assert result["authoritative_original_owner_cohort"]
    assert result["provider_incoming_calls"] == 100
    assert result["provider_target_connected_calls"] == 60
    assert result["buyer_human_answered_calls"] == 50
    assert result["buyer_accepted_payable_calls"] == 30
    assert result["not_payable_reasons_among_human_answered"]["WRONG_GEOGRAPHY"] == 20
    assert result["no_connect_reasons"]["TARGET_NO_ANSWER"] == 40
    assert not result["target_connected_is_human_answered"]
    assert not result["settled_revenue_inferred"]

@pytest.mark.parametrize("label", [
    "original_owner_authorized", "source_lineage_verified",
    "buyer_acceptance_verified", "unique_inbound_terminal_dispositions_verified",
])
def test_unverified_aggregate_never_shows_rejection_counts(label):
    result = cohort(**{label: False})
    assert result["provider_incoming_calls"] is None
    assert result["no_connect_reasons"] is None
    assert result["not_payable_reasons_among_human_answered"] is None
    assert result["status"] == "ORIGINAL_OWNER_LINEAGE_NOT_VERIFIED"

def test_disposition_reason_sum_must_equal_exact_nonconnects():
    with pytest.raises(ValueError):
        cohort(connected=61)
    bad = {key: 0 for key in NO_CONNECT_REASONS}
    with pytest.raises(ValueError):
        cohort(no_connect_reasons=bad)

def test_disposition_reason_sum_must_equal_human_answered_minus_accepted():
    with pytest.raises(ValueError):
        cohort(human=51)
    bad = {key: 0 for key in NO_PAYABLE_REASONS}
    with pytest.raises(ValueError):
        cohort(no_payable_reasons=bad)

def test_aggregate_stage_order_fails_closed():
    counts = {key: 10 for key in COUNTS}
    counts["buyer_accepted_payable_calls"] = 11
    with pytest.raises(ValueError):
        cohort(counts=counts)

def test_no_fake_reason_labels():
    bad = {key: 0 for key in NO_CONNECT_REASONS}
    bad.pop("NO_ELIGIBLE_TARGET")
    bad["PUBLISHER_FRAUD"] = 40
    with pytest.raises(ValueError):
        cohort(no_connect_reasons=bad)

def test_untrusted_owner_receipt_excluded_from_founder_feed(tmp_path):
    from empire_os.competitor_call_channel_atlas import SOURCE, build_atlas
    root = Path(__file__).resolve().parents[1]
    dst = tmp_path / "runtime/competitive_intelligence"
    dst.mkdir(parents=True)
    (dst / "competitor_intelligence_feed_latest.json").write_text(
        '{"canonical_company_count":14}')
    (dst / "call_acquisition_atlas_latest.json").write_text(json.dumps(
        build_atlas(json.loads((root / SOURCE).read_text()), now=NOW)))
    valid = summarize_readable_pulse(pulse(), pilot(), now=NOW)
    (dst / "call_loss_readiness_latest.json").write_text(json.dumps(valid))
    read = build_feed_runtime(tmp_path)
    assert read["canonical_company_count"] == 14
    item = read["call_acquisition_intelligence"]["call_loss_readiness"]
    assert item["available"]
    assert item["ringba_matching_rows_bounded_observation"] == 0
    assert item["accepted_payable_call_count_verified"] is None
    valid["live_call_activation_authorized"] = True
    (dst / "call_loss_readiness_latest.json").write_text(json.dumps(valid))
    bad = build_feed_runtime(tmp_path)
    assert bad["call_acquisition_intelligence"]["call_loss_readiness"]["available"] is False
