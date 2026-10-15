"""V16 production read-only inspector: exact genesis pin and zero mutations."""
from datetime import timedelta
import json
from pathlib import Path

import pytest

from empire_os.data_exchange_temporal_quality import PILOT_IDS
from scripts import inspect_data_exchange_v16_live as inspector
from tests.test_data_exchange_temporal_quality import NOW, custody, snap


def fake_store(rows, *, expected_dsn="fixture-only"):
    class Reader:
        def __init__(self, dsn):
            assert dsn == expected_dsn
        def read_window(self):
            return rows
        def append_once(self, *args, **kwargs):
            raise AssertionError("never write from read-only live inspector")
    return Reader


def with_genesis(monkeypatch, rows):
    monkeypatch.setattr(inspector, "RELEASED_GENESIS_SHA256", rows[0]["chain_sha256"])


def test_genesis_readonly_receipt_and_due_gate_hold(monkeypatch):
    rows = custody((NOW - timedelta(hours=2), "non-permissioned"))
    with_genesis(monkeypatch, rows)
    report = inspector.inspect_live(
        now=NOW, dsn="fixture-only", store_factory=fake_store(rows))
    assert report["status"] == "CANONICAL_CUSTODY_READONLY_VERIFIED"
    assert report["production_genesis_receipt_matched"] is True
    assert report["history_observation_count_in_window"] == 1
    assert report["canonical_head_sequence"] == 0
    assert report["second_capture_eligible_now"] is False
    assert report["capture_gate_status"] == "HOLD_MINIMUM_24H_SEPARATION"
    assert report["seconds_until_eligible"] == 22 * 3600
    assert report["v14_board_status"] == "HOLD_NEED_TWO_CANONICAL_OBSERVATIONS"
    assert report["temporal_quality_status"] == "HOLD_REVIEW_REQUIRED"
    assert "SECOND_CANONICAL_OBSERVATION_REQUIRED" in report["temporal_quality_holds"]
    assert report["pinned_three_entity_sample_complete"] is True
    assert report["v14_observed_field_change_count"] == 0
    assert report["database_writes"] is False
    assert report["customer_delivery_enabled"] is False


def test_exactly_24h_after_genesis_eligible_but_no_write(monkeypatch):
    rows = custody((NOW - timedelta(days=1), "non-permissioned"))
    with_genesis(monkeypatch, rows)
    report = inspector.inspect_live(
        now=NOW, dsn="fixture-only", store_factory=fake_store(rows))
    assert report["second_capture_eligible_now"] is True
    assert report["seconds_until_eligible"] == 0
    assert report["canonical_head_sequence"] == 0
    assert report["v14_observed_field_change_count"] == 0
    assert report["database_writes"] is False


def test_wrong_genesis_hash_holds_before_recheck():
    rows = custody((NOW - timedelta(hours=2), "non-permissioned"))
    def forbidden_recheck(*, now):
        raise AssertionError("forged genesis should prevent recheck")
    with pytest.raises(inspector.InspectionHold,
                       match="PRODUCTION_GENESIS_RECEIPT_MISMATCH"):
        inspector.inspect_live(
            now=NOW, dsn="fixture-only", recheck_official=True,
            store_factory=fake_store(rows), fetch_snapshot=forbidden_recheck)


def test_live_source_recheck_same_origin_not_independent_proof(monkeypatch):
    rows = custody((NOW - timedelta(hours=25), "non-permissioned"))
    with_genesis(monkeypatch, rows)
    seen = []
    def fetch(*, now):
        seen.append(now)
        return snap(now - timedelta(seconds=5))
    report = inspector.inspect_live(
        now=NOW, dsn="fixture-only", recheck_official=True,
        store_factory=fake_store(rows), fetch_snapshot=fetch)
    assert seen == [NOW]
    assert report["source_recheck"] == "REPEAT_SAME_SOURCE_MATCH"
    assert report["second_capture_eligible_now"] is True
    assert report["source_authenticity"] == "NOT_INDEPENDENTLY_VERIFIED"
    assert report["external_anchor_verified"] is False
    assert report["regional_market_coverage_percent"] is None
    assert report["database_writes"] is False


def test_changed_official_source_is_not_a_committed_signal(monkeypatch):
    rows = custody((NOW - timedelta(hours=25), "non-permissioned"))
    with_genesis(monkeypatch, rows)
    report = inspector.inspect_live(
        now=NOW, dsn="fixture-only", recheck_official=True,
        store_factory=fake_store(rows),
        fetch_snapshot=lambda *, now: snap(
            now - timedelta(seconds=5), status="permissioned"))
    assert report["source_recheck"] == "RECHECK_DIFFERS_FROM_STORED_SOURCE"
    assert report["source_mismatched_field_record_count"] == 3
    assert report["v14_observed_field_change_count"] == 0
    assert report["buyer_intent_verified"] is False
    assert report["database_writes"] is False


def test_true_two_snapshot_field_transition_seen_by_v14(monkeypatch):
    rows = custody((NOW - timedelta(hours=51), "non-permissioned"),
                   (NOW - timedelta(hours=25), "permissioned"))
    with_genesis(monkeypatch, rows)
    report = inspector.inspect_live(
        now=NOW, dsn="fixture-only", store_factory=fake_store(rows))
    assert report["canonical_head_sequence"] == 1
    assert report["v14_board_status"] == "OBSERVED_CHANGES_REVIEW_ONLY"
    assert report["v14_observed_field_change_count"] == 3
    assert report["v14_review_queue_count"] == 3
    assert report["customer_delivery_enabled"] is False
    assert report["payment_execution"] is False


def test_empty_custody_fails_closed():
    with pytest.raises(inspector.InspectionHold,
                       match="NO_PERSISTED_CUSTODY_OBSERVATIONS"):
        inspector.inspect_live(
            now=NOW, dsn="fixture-only", store_factory=fake_store([]))


def test_never_rechecks_when_not_selected(monkeypatch):
    rows = custody((NOW - timedelta(hours=1), "non-permissioned"))
    with_genesis(monkeypatch, rows)
    report=inspector.inspect_live(
        now=NOW, dsn="fixture-only", store_factory=fake_store(rows),
        fetch_snapshot=lambda **kw: (_ for _ in ()).throw(
            AssertionError("no unrequested network fetch")))
    assert report["source_recheck"]=="NOT_PERFORMED"


def test_root_required_before_accessing_secret(monkeypatch, capsys):
    monkeypatch.setattr(inspector.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(inspector, "protected_dsn", lambda: (_ for _ in ()).throw(
        AssertionError("secret must not be read")))
    assert inspector.main(["--read-only"]) == 2
    report=json.loads(capsys.readouterr().out)
    assert report["reason_code"]=="AUTHORISED_ROOT_READ_ACCESS_REQUIRED"
    assert report["database_writes"] is False


def test_readonly_flag_mandatory_without_secret_access(monkeypatch, capsys):
    monkeypatch.setattr(inspector.os, "geteuid", lambda: 0)
    monkeypatch.setattr(inspector, "protected_dsn", lambda: (_ for _ in ()).throw(
        AssertionError("secret must not be read")))
    assert inspector.main([])==2
    assert json.loads(capsys.readouterr().out)["reason_code"]=="EXPLICIT_READ_ONLY_FLAG_REQUIRED"


def test_exception_does_not_print_libpq_secret(monkeypatch, capsys):
    monkeypatch.setattr(inspector.os, "geteuid", lambda: 0)
    monkeypatch.setattr(inspector, "CANONICAL_ROOT", Path.cwd())
    monkeypatch.setattr(inspector, "protected_dsn",lambda: "fixture-password")
    monkeypatch.setattr(inspector,"inspect_live",
        lambda **kw: (_ for _ in ()).throw(
            RuntimeError("connection password=verysecret token private@invalid.test")))
    assert inspector.main(["--read-only"]) == 2
    output=capsys.readouterr().out
    assert "verysecret" not in output and "private@" not in output
    assert json.loads(output)["reason_code"]=="SOURCE_OR_CANONICAL_HISTORY_UNVERIFIED"


def test_root_main_outputs_only_safe_observation_metadata(monkeypatch, capsys):
    monkeypatch.setattr(inspector.os, "geteuid", lambda: 0)
    monkeypatch.setattr(inspector,"CANONICAL_ROOT",Path.cwd())
    monkeypatch.setattr(inspector,"protected_dsn",lambda:"opaque-root-secret")
    rows = custody((NOW - timedelta(hours=3), "non-permissioned"))
    with_genesis(monkeypatch, rows)
    original = inspector.inspect_live
    def fixture_inspect(**kwargs):
        kwargs["store_factory"] = fake_store(rows, expected_dsn="opaque-root-secret")
        return original(**kwargs)
    monkeypatch.setattr(inspector,"inspect_live", fixture_inspect)
    assert inspector.main(["--read-only"]) == 0
    output = capsys.readouterr().out
    assert "opaque-root-secret" not in output
    result = json.loads(output)
    assert result["status"]=="CANONICAL_CUSTODY_READONLY_VERIFIED"
    assert result["canonical_head_sequence"]==0
    assert result["customer_delivery_enabled"] is False
    assert result["database_writes"] is False
