"""Commercial-source readiness guards: no invented buyer identity or demand."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

import pytest

from empire_os.opportunity_commercial_source_health import (
    assess_sources, diagnostic_for_claim,
)


NOW = datetime(2026, 10, 9, 13, 45, tzinfo=timezone.utc)


def _write(root, rel, payload):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    return path


def _sources(root, *, market_time=None):
    _write(root, "runtime/conversations_replies_control/latest.json", {
        "generated_at": NOW.isoformat(),
        "canonical_messages": [],
        "quarantine": {
            "quarantine_count": 3096,
            "records": [
                {"reasons": ["MISSING_STABLE_THREAD_ID", "MISSING_CANONICAL_CONTACT_IDENTITY"]},
                {"reasons": ["MISSING_STABLE_MESSAGE_ID", "MISSING_STABLE_THREAD_ID"]},
            ],
        },
    })
    _write(root, "runtime/conversations_replies_control/passive_reply_db_observer_latest.json", {
        "generated_at": (NOW - timedelta(days=2)).isoformat(),
        "candidate_count": 0,
        "status": "NO_CANONICAL_REPLY_ROWS",
    })
    _write(root, "runtime/conversations_replies_control/founder_mailbox_inprocess_observer_latest.json", {
        "status": "OBSERVER_ERROR", "error": "secret value must not appear",
        "error_type": "HTTPException",
    })
    _write(root, "runtime/market_sweeps/revenue_gps_latest.json", {
        "generated_at": (market_time or (NOW - timedelta(days=10))).isoformat(),
        "market_count": 100, "commercial_demand_market_count": 0,
        "buyer_intent_inferred": False,
    })


def test_observe_exact_quarantine_causes_and_stale_market_without_pii(tmp_path):
    _sources(tmp_path)
    result = assess_sources(tmp_path, NOW)
    conv = result["sources"]["conversation_os"]
    market = result["sources"]["market_gps_and_commercial_outcomes"]
    assert conv["status"] == "BLOCKED"
    assert conv["quarantined_record_count"] == 3096
    assert conv["quarantine_reason_counts"]["MISSING_STABLE_THREAD_ID"] == 2
    assert conv["quarantine_reason_counts"]["MISSING_CANONICAL_CONTACT_IDENTITY"] == 1
    assert conv["reply_observer_candidate_count"] is None
    assert conv["reply_observer_status"] == "STALE_OBSERVER_NOT_CURRENT_TRUTH"
    assert "CANONICAL_REPLY_OBSERVER_NOT_CURRENT" in conv["reason_codes"]
    assert "CANONICAL_RECORDS_QUARANTINED" in conv["reason_codes"]
    assert market["snapshot_age_days"] == 10
    assert "MARKET_GPS_STALE" in market["reason_codes"]
    assert "NO_OBSERVED_COMMERCIAL_DEMAND" in market["reason_codes"]
    assert result["commercial_claims_auto_verified"] == 0
    assert result["normalized_scores_written"] == 0
    assert result["mailbox_read_attempted"] is False
    assert result["market_gps_refresh_attempted"] is False
    assert "secret value" not in json.dumps(result)
    assert diagnostic_for_claim(result, "buyer_intent")["status"] == "BLOCKED"
    assert diagnostic_for_claim(result, "demand")["status"] == "BLOCKED"


def test_missing_sources_fail_closed(tmp_path):
    result = assess_sources(tmp_path, NOW)
    assert result["sources"]["conversation_os"]["status"] == "BLOCKED"
    assert result["sources"]["market_gps_and_commercial_outcomes"]["status"] == "BLOCKED"
    assert "MARKET_GPS_SOURCE_MISSING" in result["sources"]["market_gps_and_commercial_outcomes"]["reason_codes"]
    assert result["execution_authority"] == "none"


def test_fresh_zero_demand_still_is_not_positive_evidence(tmp_path):
    _sources(tmp_path, market_time=NOW)
    result = assess_sources(tmp_path, NOW)
    market = result["sources"]["market_gps_and_commercial_outcomes"]
    assert market["status"] == "BLOCKED"
    assert "MARKET_GPS_STALE" not in market["reason_codes"]
    assert market["reported_commercial_demand_market_count"] == 0
    assert market["fresh_authenticated_demand_proved"] is False


def test_future_market_timestamp_is_rejected(tmp_path):
    _sources(tmp_path, market_time=NOW + timedelta(days=2))
    result = assess_sources(tmp_path, NOW)
    assert "MARKET_GPS_FUTURE_DATED" in result["sources"]["market_gps_and_commercial_outcomes"]["reason_codes"]


def test_undated_or_naive_clock_never_counts_as_fresh(tmp_path):
    with pytest.raises(ValueError, match="timezone"):
        assess_sources(tmp_path, datetime(2026, 10, 9, 13, 45))
    _sources(tmp_path)
    f = tmp_path / "runtime/market_sweeps/revenue_gps_latest.json"
    data = json.loads(f.read_text())
    data["generated_at"] = "2026-10-09T13:45:00"
    f.write_text(json.dumps(data))
    result = assess_sources(tmp_path, NOW)
    assert "MARKET_GPS_UNDATED" in result["sources"]["market_gps_and_commercial_outcomes"]["reason_codes"]


def test_source_profile_distinguishes_outbound_history_from_true_reply_candidates(tmp_path):
    _sources(tmp_path)
    path = tmp_path / "runtime/conversations_replies_control/latest.json"
    canonical = json.loads(path.read_text())
    canonical["source_summary"] = {
        "database_tables": [
            "public.outbound_events", "public.outbound_replies",
            "public.empire_conversations"
        ]
    }
    def sid(table):
        return "source:" + sha256(table.encode()).hexdigest()
    canonical["quarantine"]["records"] = [
        {"source_id": sid("public.outbound_events"),
         "reasons": ["MISSING_STABLE_THREAD_ID"]},
        {"source_id": sid("public.outbound_events"),
         "reasons": ["MISSING_STABLE_THREAD_ID"]},
        {"source_id": sid("public.outbound_replies"),
         "reasons": ["MISSING_CANONICAL_CONTACT_IDENTITY"]},
        {"source_id": sid("public.empire_conversations"),
         "reasons": ["MISSING_STABLE_MESSAGE_ID"]},
    ]
    path.write_text(json.dumps(canonical))
    result = assess_sources(tmp_path, NOW)
    source = result["sources"]["conversation_os"]
    assert source["quarantine_sample_source_kind_counts"] == {
        "CONVERSATION_CANDIDATE": 1,
        "OUTBOUND_EVENT_TABLE": 2,
        "REPLY_CANDIDATE": 1,
    }
    assert source["quarantine_sample_is_not_population_distribution"] is True
    assert source["next_remediation"][0]["no_synthetic_message_or_contact_identity"] is True
    assert source["quarantined_record_count"] == 3096
    assert result["commercial_claims_auto_verified"] == 0


def test_source_health_reads_actual_admission_totals_without_claiming_reply_proof(tmp_path):
    _sources(tmp_path)
    canonical_path = tmp_path / "runtime/conversations_replies_control/latest.json"
    data = json.loads(canonical_path.read_text())
    data["source_admission"] = {
        "admitted_conversation_candidate_rows": 6,
        "excluded_nonmessage_rows": 3090,
        "admission_does_not_authenticate_buyer_intent": True,
        "tenant_binding_established": False,
        "execution_authority": "none",
    }
    data["quarantine"]["quarantine_count"] = 6
    canonical_path.write_text(json.dumps(data))
    result = assess_sources(tmp_path, NOW)
    conversation = result["sources"]["conversation_os"]
    assert conversation["message_source_rows_admitted"] == 6
    assert conversation["nonmessage_source_rows_excluded"] == 3090
    assert conversation["quarantined_record_count"] == 6
    assert conversation["authenticated_buyer_intent_proved"] is False
    assert conversation["source_admission_does_not_prove_buyer_intent"] is True
    data["source_admission"]["tenant_binding_established"] = True
    canonical_path.write_text(json.dumps(data))
    malformed = assess_sources(tmp_path, NOW)
    assert malformed["sources"]["conversation_os"]["message_source_rows_admitted"] is None
    assert malformed["commercial_claims_auto_verified"] == 0


def test_reply_observer_zero_only_current_when_fresh(tmp_path):
    """A 48h-old zero cannot override today's quarantined inbound rows."""
    _sources(tmp_path, market_time=NOW)
    snapshot = tmp_path / "runtime/conversations_replies_control/passive_reply_db_observer_latest.json"
    stale = assess_sources(tmp_path, NOW)["sources"]["conversation_os"]
    assert stale["reply_observer_candidate_count"] is None
    assert "CANONICAL_REPLY_OBSERVER_NOT_CURRENT" in stale["reason_codes"]
    source = json.loads(snapshot.read_text())
    source["generated_at"] = NOW.isoformat()
    snapshot.write_text(json.dumps(source))
    current = assess_sources(tmp_path, NOW)["sources"]["conversation_os"]
    assert current["reply_observer_candidate_count"] == 0
    assert "CANONICAL_REPLY_OBSERVER_NOT_CURRENT" not in current["reason_codes"]
    # Fresh observation is not original provider authentication.
    assert current["authenticated_buyer_intent_proved"] is False


def test_invalid_future_and_undated_reply_observations_are_not_current(tmp_path):
    _sources(tmp_path, market_time=NOW)
    observer = tmp_path / "runtime/conversations_replies_control/passive_reply_db_observer_latest.json"
    for timestamp in (None, "2026-10-09T13:45:00",
                      (NOW + timedelta(days=1)).isoformat()):
        value = json.loads(observer.read_text())
        value["generated_at"] = timestamp
        observer.write_text(json.dumps(value))
        health = assess_sources(tmp_path, NOW)["sources"]["conversation_os"]
        assert health["reply_observer_candidate_count"] is None
        assert "CANONICAL_REPLY_OBSERVER_NOT_CURRENT" in health["reason_codes"]
        assert health["authenticated_buyer_intent_proved"] is False


def test_stale_conversation_capture_is_flagged_despite_existing_message_count(tmp_path):
    _sources(tmp_path)
    path = tmp_path / "runtime/conversations_replies_control/latest.json"
    original = json.loads(path.read_text())
    original["generated_at"] = (NOW - timedelta(days=3)).isoformat()
    path.write_text(json.dumps(original))
    observed = assess_sources(tmp_path, NOW)["sources"]["conversation_os"]
    assert "CANONICAL_CONVERSATION_SNAPSHOT_NOT_CURRENT" in observed["reason_codes"]
    assert observed["authenticated_buyer_intent_proved"] is False


def _stage3_linkage_contract():
    return {
        "schema": "empire.conversation_reply_linkage_plan.v1",
        "generated_at": NOW.isoformat(),
        "mode": "OBSERVE",
        "schema_join_path_available": True,
        "verification_status": "SCHEMA_PATH_FOUND_DATA_PROOF_REQUIRED",
        "join_edges": [
            {"join_cardinality_verified": False},
            {"join_cardinality_verified": False},
        ],
        "actual_joined_rows_proven": 0,
        "buyer_intent_verified": False,
        "canonical_messages_promoted": 0,
        "normalized_scores_written": 0,
        "database_access_attempted": False,
        "controlled_identity_review": None,
        "controlled_identity_review_not_live_evidence": True,
        "external_execution_authority": "none",
    }


def test_stage3_current_planner_is_only_code_ready_not_buyer_ready(tmp_path):
    _sources(tmp_path, market_time=NOW)
    _write(
        tmp_path, "runtime/conversations_replies_control/reply_linkage_plan_latest.json",
        _stage3_linkage_contract(),
    )
    result = assess_sources(tmp_path, NOW)
    health = result["sources"]["conversation_os"]["reply_identity_integration_health"]
    assert health["status"] == "CODE_PATH_CURRENT_ORIGINAL_EVIDENCE_PENDING"
    assert health["structural_review_integration_available"] is True
    assert health["tenant_authority_verified"] is False
    assert health["original_provider_authentication_verified"] is False
    assert health["buyer_intent_verified"] is False
    assert health["production_structural_matches_verified"] == 0
    diag = diagnostic_for_claim(result, "buyer_intent")
    assert diag["reply_identity_integration_status"] == health["status"]
    assert "ORIGINAL_REPLY_CONTACT_AND_TENANT_PROOF_REQUIRED" in diag["reasons"]
    assert diag["commercial_claim_verified"] is False
    assert result["normalized_scores_written"] == 0
    assert result["execution_authority"] == "none"


@pytest.mark.parametrize("fault", [
    {"buyer_intent_verified": True},
    {"canonical_messages_promoted": 1},
    {"normalized_scores_written": 1},
    {"actual_joined_rows_proven": 1},
    {"external_execution_authority": "send"},
    {"database_access_attempted": True},
    {"controlled_identity_review": {"structurally_reviewable_count": 1}},
    {"controlled_identity_review_not_live_evidence": False},
    {"schema_join_path_available": False},
    {"verification_status": "VERIFIED_BUYER"},
    {"join_edges": [{"join_cardinality_verified": True}]},
])
def test_stage3_unsafe_or_test_evidence_never_becomes_live_proof(tmp_path, fault):
    _sources(tmp_path, market_time=NOW)
    incoming = _stage3_linkage_contract()
    incoming.update(fault)
    _write(
        tmp_path, "runtime/conversations_replies_control/reply_linkage_plan_latest.json",
        incoming,
    )
    result = assess_sources(tmp_path, NOW)
    profile = result["sources"]["conversation_os"]["reply_identity_integration_health"]
    assert profile["status"] == "BLOCKED_PLANNER_EVIDENCE_INVALID"
    assert "REPLY_IDENTITY_PLANNER_CONTRACT_UNTRUSTED" in profile["reason_codes"]
    assert profile["tenant_authority_verified"] is False
    assert profile["buyer_intent_verified"] is False
    assert result["commercial_claims_auto_verified"] == 0


def test_stage3_missing_future_and_stale_planner_cannot_override_quarantine(tmp_path):
    _sources(tmp_path, market_time=NOW)
    missing = assess_sources(tmp_path, NOW)
    assert missing["sources"]["conversation_os"]["reply_identity_integration_health"]["status"] == (
        "BLOCKED_PLANNER_EVIDENCE_INVALID"
    )
    for stamped in (
        (NOW - timedelta(days=2)).isoformat(),
        (NOW + timedelta(days=2)).isoformat(),
        "2026-10-09T13:45:00",
    ):
        entry = _stage3_linkage_contract()
        entry["generated_at"] = stamped
        _write(tmp_path, "runtime/conversations_replies_control/reply_linkage_plan_latest.json", entry)
        result = assess_sources(tmp_path, NOW)
        assert "REPLY_IDENTITY_PLANNER_NOT_CURRENT" in result["sources"]["conversation_os"]["reason_codes"]
        assert result["sources"]["conversation_os"]["quarantined_record_count"] == 3096
        assert result["commercial_claims_auto_verified"] == 0


def test_stage3_private_planner_values_do_not_leak_to_resolver(tmp_path):
    _sources(tmp_path, market_time=NOW)
    record = _stage3_linkage_contract()
    record["private_contact"] = "private_user@do-not-emit.test"
    record["hidden_reasoning"] = "DO NOT EMIT PRIVATE CONTRACT"
    _write(tmp_path, "runtime/conversations_replies_control/reply_linkage_plan_latest.json", record)
    result = assess_sources(tmp_path, NOW)
    assert "private_user@do-not-emit.test" not in json.dumps(result)
    assert "DO NOT EMIT PRIVATE CONTRACT" not in json.dumps(result)
    assert result["sources"]["conversation_os"]["reply_identity_integration_health"]["buyer_intent_verified"] is False
