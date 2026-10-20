"""CLI end-to-end checks using only isolated test fixtures."""
import json
from pathlib import Path
import subprocess
import sys

from empire_os.inbound_recovery_store import OfflineRecoveryStore
from empire_os.inbound_revenue_recovery import RecoveryEvent

DATE = "2026-10-20T13:00:00+00:00"


def _call(path, *args):
    return subprocess.run(
        [sys.executable, "-B", "-m",
         "scripts.review_inbound_revenue_recovery_20261020",
         "--events-jsonl", str(path), "--tenant-id", "business-a",
         "--read-only", *args],
        capture_output=True, text=True,
    )


def _fixture(tmp_path):
    path = tmp_path / "fixture.jsonl"
    rows = [
        {"tenant_id": "business-a", "event_id": "A1", "call_id": "call-1",
         "occurred_at": DATE, "kind": "unanswered", "origin": "provider",
         "verified": True, "synthetic": False},
        {"tenant_id": "business-a", "event_id": "A2", "call_id": "call-1",
         "occurred_at": "2026-10-20T13:05:00+00:00",
         "kind": "booking_requested", "origin": "operator",
         "synthetic": False},
        {"tenant_id": "business-b", "event_id": "B1", "call_id": "call-9",
         "occurred_at": DATE, "kind": "unanswered", "origin": "provider",
         "verified": True, "synthetic": False},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return path


def test_cli_opportunity_review_and_tenant_scope(tmp_path):
    fixture = _fixture(tmp_path)
    result = _call(
        fixture, "--opportunities", "--as-of", "2026-10-20T13:25:00Z"
    )
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["queue_total"] == 1
    assert body["tickets"][0]["call_id"] == "call-1"
    assert body["tickets"][0]["priority"] == "urgent_review"
    assert body["customer_contact_authorized"] is False


def test_cli_source_attribution_requires_evidence(tmp_path):
    fixture = _fixture(tmp_path)
    result = _call(
        fixture, "--source-attribution", "--as-of", "2026-10-20T13:25:00Z"
    )
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["recovered_calls"] == 0
    assert body["last_touch_channels"] == {}


def test_cli_missing_clock_or_invalid_mode_rejected(tmp_path):
    fixture = _fixture(tmp_path)
    assert _call(fixture, "--opportunities").returncode != 0
    assert _call(fixture, "--source-touches-jsonl", str(fixture)).returncode != 0
    assert _call(
        fixture, "--source-attribution", "--as-of", "2026-10-20"
    ).returncode != 0


def test_sqlite_queue_read_is_scoped_and_nonmutating(tmp_path):
    fixture = _fixture(tmp_path)
    path = tmp_path / "call-evidence.db"
    with OfflineRecoveryStore(path) as store:
        for row in fixture.read_text().splitlines():
            store.append_offline(RecoveryEvent(**json.loads(row)))
    before = path.stat().st_size
    proc = subprocess.run(
        [sys.executable, "-B", "-m",
         "scripts.review_inbound_revenue_recovery_20261020",
         "--sqlite-db", str(path), "--tenant-id", "business-a",
         "--read-only", "--opportunities", "--as-of", "2026-10-20T13:25:00Z"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["queue_total"] == 1
    assert path.stat().st_size == before


def test_cli_patterns_reject_missing_timezone(tmp_path):
    fixture = _fixture(tmp_path)
    assert _call(fixture, "--patterns", "--as-of", "2026-10-20T13:25:00Z").returncode != 0


def test_cli_patterns_reports_no_fake_insights_from_small_sample(tmp_path):
    fixture = _fixture(tmp_path)
    result = _call(
        fixture, "--patterns", "--as-of", "2026-10-20T13:25:00Z",
        "--timezone", "Europe/London",
    )
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["sample_size"] == 1
    assert body["cohort_sufficient"] is False
    assert body["alerts"] == []
    assert body["revenue_estimated"] is False
