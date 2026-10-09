"""Flow meter must measure evidence transitions without fabricating conversion."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os

from empire_os.revenue_flow_meter import (
    RECEIPTS, HISTORY, OUTPUT, build_flow_meter, refresh_flow_meter,
)

NOW = datetime(2026, 10, 9, 19, 45, tzinfo=timezone.utc)
STAMP = NOW.isoformat()


def receipts(*, historical_commercial=False):
    commercial_at = (
        (NOW - timedelta(days=17)).isoformat() if historical_commercial else STAMP
    )
    return {
        "scout": {
            "schema_version": "empire.buyer_acquisition_scout.v1",
            "generated_at": STAMP, "candidate_count": 2,
            "probed_domain_count": 2,
            "observed_first_party_buyer_claim_receipt_count": 6,
            "candidates": [
                {"domain": "alpha.example", "website": "https://alpha.example/",
                 "canonical_identity_verified": True,
                 "canonical_seed_identity_corroborated": True,
                 "canonical_seed_prospect_id": "some-prospect",
                 "canonical_seed_website": "https://alpha.example"},
                {"domain": "beta.example", "website": "https://beta.example/"},
            ],
        },
        "reconciliation": {
            "schema_version": "empire.buyer_scout_reconciliation.v1",
            "generated_at": (NOW + timedelta(seconds=2)).isoformat(),
            "candidate_count": 2,
            "results": [
                {"domain": "alpha.example", "reconciliation_state": "EXISTING"},
                {"domain": "beta.example", "reconciliation_state": "NEW"},
            ],
        },
        "persistence": {
            "schema_version": "empire.buyer_scout_persistence.v1",
            "generated_at": (NOW + timedelta(seconds=3)).isoformat(),
            "persisted_candidate_count": 2,
        },
        "review": {
            "schema_version": "empire.buyer_scout_review_readiness.v1",
            "generated_at": (NOW + timedelta(seconds=5)).isoformat(),
            "candidate_count": 198, "review_ready_count": 1,
            "blocked_reason_counts": {
                "site_evidence_below_floor": 92,
                "direct_buyer_evidence_missing": 44,
            },
        },
        "quality": {
            "schema_version": "empire.buyer_evidence_quality.v1",
            "generated_at": (NOW + timedelta(seconds=6)).isoformat(),
            "stage_receipts_time_aligned": True,
            "scout_receipt_fresh": True,
            "source_generated_at": {
                "scout": STAMP,
                "reconciliation": (NOW + timedelta(seconds=2)).isoformat(),
                "persistence": (NOW + timedelta(seconds=3)).isoformat(),
                "holding_review": (NOW + timedelta(seconds=5)).isoformat(),
            },
            "candidate_with_valid_direct_purchase_receipt": 1,
            "candidate_with_strict_named_person_email_binding": 0,
        },
        "astra": {
            "schema_version": "empire.astra.executive.v2",
            "generated_at": STAMP, "canonical_company_binding_count": 0,
        },
        "commercial_funnel": {
            "schema_version": "empire.founder_commercial_funnel.v1",
            "generated_at": commercial_at,
            "counts": {
                "outbound_delivered": 25,
                "commercial_replies": 0,
                "recognized_revenue_events": 0,
            },
        },
        "revenue_pulse": {
            "schema_version": "empire.revenue-pulse.v3",
            "generated_at": STAMP,
            "recognized_revenue_truth": {"recognized_revenue_cents": 0},
        },
    }


def test_exact_scout_reconciliation_join_and_independent_holding():
    report = build_flow_meter(receipts(), now=NOW + timedelta(seconds=7))
    assert report["handoffs"]["scout_to_reconciliation"]["status"] == "exact_domain_same_cycle"
    assert report["handoffs"]["scout_to_reconciliation"]["joined_count"] == 2
    assert report["handoffs"]["scout_to_reconciliation"]["coverage_ratio"] == 1.0
    assert report["handoffs"]["scout_to_reconciliation"]["causal_conversion_rate"] is None
    assert report["handoffs"]["reconciliation_to_holding"]["causal_conversion_rate"] is None
    assert report["handoffs"]["holding_to_review"]["causal_conversion_rate"] is None
    assert report["stages"]["discovered"]["current_count"] == 2
    assert report["stages"]["holding_persisted"]["current_count"] == 2
    assert report["stages"]["holding_review_scanned"]["current_count"] == 198
    assert report["stages"]["holding_review_ready_transitions"]["current_count"] == 1
    assert report["stages"]["verified_purchasing_statements"]["current_count"] == 1
    assert report["stages"]["strict_named_email_bindings"]["current_count"] == 0
    assert report["stages"]["corroborated_canonical_candidates"]["current_count"] == 1
    assert report["stages"]["astra_canonical_bindings"]["current_count"] == 0
    assert report["verified_end_to_end_conversion_rate"] is None
    assert report["database_read_performed"] is False
    assert report["database_write_performed"] is False
    assert report["outbound_sent"] is False


def test_stale_commercial_cannot_be_presented_as_current_outbound():
    report = build_flow_meter(
        receipts(historical_commercial=True), now=NOW + timedelta(seconds=8),
    )
    assert report["source_health"]["commercial_funnel"]["status"] == "stale"
    stage = report["stages"]["outbound_delivered"]
    assert stage["observed_count"] == 25
    assert stage["current_count"] is None
    assert report["health_checks"]["commercial_truth_fresh"] is False
    assert any(
        x["reason"] == "untrusted_commercial_funnel_snapshot"
        for x in report["blockers"]
    )
    assert report["stages"]["recognized_revenue_cents"]["current_count"] == 0


def test_unknown_missing_or_corrupted_data_never_converts_to_zero():
    payload = receipts()
    payload["quality"] = None
    payload["revenue_pulse"] = None
    out = build_flow_meter(payload, now=NOW)
    assert out["stages"]["verified_purchasing_statements"]["current_count"] is None
    assert out["stages"]["recognized_revenue_cents"]["observed_count"] is None
    assert out["source_health"]["revenue_pulse"]["status"] == "unavailable"


def test_duplicate_and_mismatched_domains_are_not_joined():
    payload = receipts()
    payload["reconciliation"]["results"][1]["domain"] = "alpha.example"
    out = build_flow_meter(payload, now=NOW)
    assert out["handoffs"]["scout_to_reconciliation"]["status"] == "duplicate_domain_conflict"
    assert out["handoffs"]["scout_to_reconciliation"]["coverage_ratio"] is None
    payload["reconciliation"]["results"][1]["domain"] = "gamma.example"
    out = build_flow_meter(payload, now=NOW)
    assert out["handoffs"]["scout_to_reconciliation"]["joined_count"] == 1
    assert out["handoffs"]["scout_to_reconciliation"]["coverage_ratio"] == 0.5
    assert out["handoffs"]["scout_to_reconciliation"]["unmatched_scout_domains"] == 1


def test_lookalike_url_blocks_exact_domain_coverage():
    payload = receipts()
    payload["scout"]["candidates"][0]["website"] = "https://alpha.example.evil.test/"
    result = build_flow_meter(payload, now=NOW)
    assert result["handoffs"]["scout_to_reconciliation"]["status"] == "invalid_scout_domain"
    assert result["handoffs"]["scout_to_reconciliation"]["joined_count"] is None


def test_unaligned_receipts_never_claim_same_run():
    payload = receipts()
    payload["reconciliation"]["generated_at"] = (NOW + timedelta(minutes=17)).isoformat()
    result = build_flow_meter(payload, now=NOW + timedelta(minutes=18))
    assert result["handoffs"]["scout_to_reconciliation"]["status"] == "source_stale_or_not_same_run"
    assert result["handoffs"]["scout_to_reconciliation"]["coverage_ratio"] is None


def test_quality_must_be_fresh_and_time_aligned():
    payload = receipts()
    payload["quality"]["stage_receipts_time_aligned"] = False
    result = build_flow_meter(payload, now=NOW)
    assert result["stages"]["verified_purchasing_statements"]["current_count"] is None
    payload["quality"]["stage_receipts_time_aligned"] = True
    payload["quality"]["scout_receipt_fresh"] = False
    result = build_flow_meter(payload, now=NOW)
    assert result["stages"]["verified_purchasing_statements"]["current_count"] is None


def test_future_source_cannot_be_current():
    payload = receipts()
    payload["scout"]["generated_at"] = (NOW + timedelta(hours=2)).isoformat()
    result = build_flow_meter(payload, now=NOW)
    assert result["source_health"]["scout"]["status"] == "future_dated"
    assert result["stages"]["discovered"]["current_count"] is None


def test_schema_mismatch_is_not_authoritative():
    payload = receipts()
    payload["revenue_pulse"]["schema_version"] = "unknown-schema"
    result = build_flow_meter(payload, now=NOW)
    assert result["source_health"]["revenue_pulse"]["status"] == "schema_mismatch"
    assert result["stages"]["recognized_revenue_cents"]["current_count"] is None


def test_latest_and_history_are_private_bounded_and_idempotent(tmp_path):
    test_data = receipts()
    for name, rel in RECEIPTS.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(test_data[name]), encoding="utf-8")
    one = refresh_flow_meter(tmp_path, now=NOW + timedelta(seconds=8))
    two = refresh_flow_meter(tmp_path, now=NOW + timedelta(seconds=9))
    assert one["tracking"]["history_count"] == 1
    assert two["tracking"]["history_count"] == 1
    latest = tmp_path / OUTPUT
    history = tmp_path / HISTORY
    assert latest.exists() and history.exists()
    assert os.stat(latest).st_mode & 0o777 == 0o600
    assert os.stat(history).st_mode & 0o777 == 0o600
    samples = json.loads(history.read_text())["samples"]
    assert samples[0]["discovered"] == 2
    assert samples[0]["joined_by_exact_domain"] == 2
    assert "email" not in json.dumps(samples)
    assert "first_party_people" not in json.dumps(samples)


def test_missing_runtime_is_explicit_not_a_successful_funnel(tmp_path):
    report = refresh_flow_meter(tmp_path, now=NOW)
    assert report["source_health"]["scout"]["status"] == "unavailable"
    assert report["stages"]["discovered"]["current_count"] is None
    assert report["verified_end_to_end_conversion_rate"] is None
    assert report["tracking"]["history_count"] == 0
    assert not (tmp_path / HISTORY).exists()


def test_history_corruption_fails_closed_instead_of_erasing_samples(tmp_path):
    data = receipts()
    for key, rel in RECEIPTS.items():
        file = tmp_path / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(data[key]))
    history = tmp_path / HISTORY
    history.write_text("{not-valid-json")
    try:
        refresh_flow_meter(tmp_path, now=NOW)
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("expected corrupt history to fail")
    assert history.read_text() == "{not-valid-json"


def test_persisted_count_does_not_mean_verified_identity():
    payload = receipts()
    payload["scout"]["candidates"][0]["canonical_identity_verified"] = False
    out = build_flow_meter(payload, now=NOW)
    assert out["stages"]["holding_persisted"]["current_count"] == 2
    assert out["stages"]["corroborated_canonical_candidates"]["current_count"] == 0
    assert out["stages"]["astra_canonical_bindings"]["current_count"] == 0


def test_wrong_scout_quality_receipt_cannot_claim_same_cohort():
    payload = receipts()
    payload["quality"]["source_generated_at"] = {
        "scout": (NOW - timedelta(minutes=35)).isoformat(),
    }
    report = build_flow_meter(payload, now=NOW)
    assert report["stages"]["verified_purchasing_statements"]["current_count"] is None
    assert report["stages"]["strict_named_email_bindings"]["current_count"] is None



def test_report_counts_raw_source_observations_separately_from_verified_proof():
    report = build_flow_meter(receipts(), now=NOW)
    assert report["stages"]["sites_probed"]["current_count"] == 2
    assert report["stages"]["first_party_source_receipts"]["current_count"] == 6
    assert report["stages"]["verified_purchasing_statements"]["current_count"] == 1
    assert "not_buyer_proof" in report["stages"]["first_party_source_receipts"]["scope"]


def test_mismatched_quality_review_ref_cannot_claim_verified_buyer():
    payload = receipts()
    payload["quality"]["source_generated_at"]["holding_review"] = (
        NOW - timedelta(minutes=20)
    ).isoformat()
    report = build_flow_meter(payload, now=NOW)
    assert report["stages"]["verified_purchasing_statements"]["current_count"] is None


def test_reconciliation_count_mismatch_cannot_claim_exact_join():
    payload = receipts()
    payload["reconciliation"]["candidate_count"] = 18
    report = build_flow_meter(payload, now=NOW)
    assert report["handoffs"]["scout_to_reconciliation"]["status"] == "count_and_records_mismatch"
    assert report["handoffs"]["scout_to_reconciliation"]["joined_count"] is None
