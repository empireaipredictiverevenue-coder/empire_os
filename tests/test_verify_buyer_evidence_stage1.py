"""One-shot, read-only Stage 1 completion gate.

No real database, provider, SMTP, systemd change, or external action.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util
import json

NOW = datetime(2026, 10, 9, 18, tzinfo=timezone.utc)


def loader():
    p = Path(__file__).resolve().parents[1] / "scripts/verify_buyer_evidence_stage1.py"
    spec = importlib.util.spec_from_file_location("stage1_evidence_check_test", p)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save(root, rel, value):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value))


def ready(tmp_path):
    save(tmp_path, "runtime/conversations_replies_control/collector_health_latest.json", {
        "observed_at": NOW.isoformat(),
        "status": "READ_SUCCESS", "source_query_completed": True,
        "database_table_count": 2,
    })
    save(tmp_path, "runtime/conversations_replies_control/latest.json", {
        "generated_at": (NOW-timedelta(seconds=1)).isoformat(),
        "quarantine": {"quarantine_count": 5},
    })
    save(tmp_path, "runtime/market_sweeps/revenue_gps_latest.json", {
        "generated_at": NOW.isoformat(),
        "execution_authority": "none", "market_count": 12,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "raw_reply_records_are_commercial_proof": False,
        "inbound_reply_authenticity_verified": False,
        "restricted_reply_lineage": {
            "schema": "empire.market_gps_restricted_reply_lineage.v1",
            "window_days": 90,
            "reply_records_observed": 5,
            "reply_records_with_intent_pointer": 4,
            "reply_records_matched_to_intent": 3,
            "reply_records_matched_to_prospect": 2,
            "reply_records_missing_intent_pointer": 1,
            "reply_records_with_unmatched_intent": 1,
            "reply_records_with_unmatched_prospect": 1,
            "positive_classification_records_unverified": 1,
            "original_provider_message_id_checked": False,
            "canonical_contact_identity_verified": False,
            "provider_thread_binding_verified": False,
            "tenant_binding_verified": False,
            "buyer_intent_verified": False,
            "commercial_demand_inferred": False,
            "read_only_aggregate": True,
            "execution_authority": "none",
        },
    })
    save(tmp_path, "runtime/opportunity_factory/evidence_resolution_latest.json", {
        "execution_authority": "none", "normalized_scores_written": 0,
        "factory_promotion_authorized": False,
    })
    save(tmp_path, "runtime/opportunity_factory/intake_latest.json", {
        "execution_authority": "none", "factory_ready_count": 0,
    })


def check(root, **kwargs):
    return loader().assess(root, now=NOW, market_service_healthy=True,
                           root_timer_active=True, masked_collector_post=False,
                           **kwargs)


def test_all_stage1_readiness_requirements_can_pass(tmp_path):
    ready(tmp_path)
    result = check(tmp_path)
    assert result["status"] == "PASS"
    assert result["blockers"] == []
    assert result["live_lineage_status"] == "CURRENT_STRUCTURAL_COUNTS_ONLY"
    assert result["quarantined_message_count"] == 5
    assert result["authenticated_buyer_messages_proven"] is False
    assert result["changes_applied"] is False


def test_existing_masked_optional_step_blocks_completion(tmp_path):
    ready(tmp_path)
    result = loader().assess(
        tmp_path, now=NOW,
        market_service_healthy=True,
        root_timer_active=True, masked_collector_post=True,
    )
    assert result["status"] == "BLOCKED"
    assert result["blockers"] == ["COLLECTOR_SYSTEMD_FAILURE_STILL_MASKED"]


def test_missing_lineage_is_pending_not_zero(tmp_path):
    ready(tmp_path)
    gps = tmp_path / "runtime/market_sweeps/revenue_gps_latest.json"
    doc = json.loads(gps.read_text())
    doc.pop("restricted_reply_lineage")
    gps.write_text(json.dumps(doc))
    result = check(tmp_path)
    assert "LIVE_MARKET_REPLY_LINEAGE_NOT_VERIFIED" in result["blockers"]
    assert result["live_lineage_status"] == "PENDING_RESTRICTED_LINEAGE_SNAPSHOT"
    assert result["live_lineage_counts"] is None


def test_stale_collector_health_and_snapshot_cannot_pass(tmp_path):
    ready(tmp_path)
    name = tmp_path / "runtime/conversations_replies_control/collector_health_latest.json"
    health = json.loads(name.read_text())
    health["observed_at"] = (NOW-timedelta(hours=5)).isoformat()
    name.write_text(json.dumps(health))
    result = check(tmp_path)
    assert "COLLECTOR_HEALTH_NOT_CURRENT" in result["blockers"]
    assert "COLLECTOR_SNAPSHOT_HEALTH_NOT_CORRELATED" in result["blockers"]


def test_verification_refuses_factory_promotion_and_failed_collector(tmp_path):
    ready(tmp_path)
    health = tmp_path / "runtime/conversations_replies_control/collector_health_latest.json"
    row = json.loads(health.read_text())
    row["status"] = "DATABASE_SOURCE_READ_FAILED"
    row["source_query_completed"] = False
    health.write_text(json.dumps(row))
    resolver = tmp_path / "runtime/opportunity_factory/evidence_resolution_latest.json"
    data = json.loads(resolver.read_text())
    data["factory_promotion_authorized"] = True
    resolver.write_text(json.dumps(data))
    result = check(tmp_path)
    assert "COLLECTOR_READ_NOT_VERIFIED" in result["blockers"]
    assert "FACTORY_EXECUTION_GATES_UNVERIFIED" in result["blockers"]


def test_no_files_mutated(tmp_path):
    ready(tmp_path)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    check(tmp_path)
    after = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after


def test_independent_healthy_systemd_monitor_closes_masked_error_gap(tmp_path):
    ready(tmp_path)
    result = loader().assess(
        tmp_path, now=NOW, market_service_healthy=True, root_timer_active=True,
        masked_collector_post=True, independent_health_monitor_ready=True,
    )
    assert result["status"] == "PASS"
    assert result["independent_health_monitor_ready"] is True
    assert result["execution_authority"] == "none"
