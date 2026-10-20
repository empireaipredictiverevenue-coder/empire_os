"""Scorecard and CLI read-only guarantees; no contacts or payments are made."""
import json
import subprocess
import sys

import pytest

from empire_os.inbound_recovery_scorecard import build_inbound_recovery_scorecard
from empire_os.inbound_recovery_store import OfflineRecoveryStore
from empire_os.inbound_revenue_recovery import RecoveryEvent


def event(tenant="test-tenant", *, synthetic=False):
    return RecoveryEvent(
        tenant_id=tenant, event_id="missed-1", call_id="call-1",
        occurred_at="2026-10-20T09:00:00+00:00", kind="unanswered",
        origin="provider", verified=True, synthetic=synthetic,
    )


def test_empty_scorecard_has_no_fabricated_conversion_rate():
    from empire_os.inbound_revenue_recovery import RecoveryLedger

    output = build_inbound_recovery_scorecard(RecoveryLedger().report("empty"))
    assert output["calls_observed"] == 0
    assert output["missed_call_rate_percent"] is None
    assert output["verified_missed_recovery_rate_percent"] is None
    assert output["revenue_estimates_included"] is False
    assert output["verified_paid_recovery_minor_by_currency"] == {}


def test_scorecard_tracks_unrecovered_calls_without_claiming_money():
    from empire_os.inbound_revenue_recovery import RecoveryLedger

    ledger = RecoveryLedger()
    ledger.append(event())
    output = build_inbound_recovery_scorecard(ledger.report("test-tenant"))
    assert output["missed_calls"] == 1
    assert output["open_missed_opportunities"] == 1
    assert output["missed_call_rate_percent"] == 100.0
    assert output["verified_missed_recovery_rate_percent"] == 0.0
    assert output["actions"]
    assert output["pricing_activated"] is False


def test_incomplete_or_lying_aggregate_rejected():
    with pytest.raises(ValueError, match="incomplete"):
        build_inbound_recovery_scorecard({"tenant_id": "a"})
    from empire_os.inbound_revenue_recovery import RecoveryLedger

    wrong = RecoveryLedger().report("test-tenant")
    wrong["verified_recovered_calls"] = 9
    with pytest.raises(ValueError, match="inconsistent"):
        build_inbound_recovery_scorecard(wrong)


def test_sqlite_report_read_only_mode_never_creates_file(tmp_path):
    path = tmp_path / "not-there.db"
    with pytest.raises(ValueError, match="existing_sqlite"):
        OfflineRecoveryStore(path, read_only=True)
    assert not path.exists()


def test_sqlite_read_only_db_rejects_writes(tmp_path):
    path = tmp_path / "proof.db"
    with OfflineRecoveryStore(path) as store:
        store.append_offline(event())
    with OfflineRecoveryStore(path, read_only=True) as store:
        assert store.report("test-tenant")["missed_calls"] == 1
        with pytest.raises(ValueError, match="read_only"):
            store.append_offline(event(tenant="another-tenant"))


def test_cli_sqlite_readonly_scorecard(tmp_path):
    path = tmp_path / "store.db"
    with OfflineRecoveryStore(path) as store:
        store.append_offline(event())
    script = "scripts.review_inbound_revenue_recovery_20261020"
    result = subprocess.run(
        [sys.executable, "-B", "-m", script, "--sqlite-db", str(path),
         "--tenant-id", "test-tenant", "--read-only", "--scorecard"],
        check=True, capture_output=True, text=True,
    )
    report = json.loads(result.stdout)
    assert report["missed_calls"] == 1
    assert report["evidence_level"] == "offline_not_a_live_revenue_claim"
    assert report["environment"] == "offline_sqlite_persisted"
    missing = subprocess.run(
        [sys.executable, "-B", "-m", script, "--sqlite-db",
         str(tmp_path / "missing.db"), "--tenant-id", "test-tenant", "--read-only"],
        capture_output=True, text=True,
    )
    assert missing.returncode != 0
    assert not (tmp_path / "missing.db").exists()


def test_cli_jsonl_readonly_scorecard_excludes_synthetic(tmp_path):
    fixture = tmp_path / "events.jsonl"
    fixture.write_text(json.dumps({
        "tenant_id": "a", "event_id": "synthetic-1", "call_id": "s1",
        "occurred_at": "2026-10-20T09:00:00+00:00",
        "kind": "unanswered", "origin": "provider",
    }) + "\n")
    result = subprocess.run(
        [sys.executable, "-B", "-m", "scripts.review_inbound_revenue_recovery_20261020",
         "--events-jsonl", str(fixture), "--tenant-id", "a", "--read-only",
         "--scorecard"],
        check=True, capture_output=True, text=True,
    )
    report = json.loads(result.stdout)
    assert report["calls_observed"] == 0
    assert report["missed_call_rate_percent"] is None
