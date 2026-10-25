"""Deterministic diagnostics tests; no live services or business records."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from empire_os.predictive_cloud_runtime_diagnostics import (
    inspect_runtime_diagnostics, SCHEMA, UNKNOWN_METRICS,
)

NOW = datetime(2026, 10, 25, 23, 20, tzinfo=timezone.utc)
SHOW = ("Result=success\nExecMainStatus=0\n"
        "ExecMainStartTimestamp=Sun 2026-10-25 23:17:48 UTC\n"
        "ExecMainExitTimestamp=Sun 2026-10-25 23:17:49 UTC\n"
        "ExecMainStartTimestampMonotonic=3510000000000\n"
        "ExecMainExitTimestampMonotonic=3510001000000\n")
MEM = "MemTotal:       100000 kB\nMemAvailable:    40000 kB\n"
DISK = {"total": 1000, "used": 300, "free": 650}
SOURCES = {
    "cloud": {"schema_version": "empire.predictive_cloud.status.v2",
              "mode": "OBSERVE", "execution_authority": "none",
              "generated_at": "2026-10-25T23:00:00+00:00"},
    "predictive": {"schema_version": "empire.predictive_intelligence.v1",
                   "mode": "OBSERVE", "execution_authority": "none",
                   "generated_at": "2026-10-25T22:00:00+00:00"},
    "jev": {"schema_version": "empire.jev.client_pain_production_observe.v1",
            "mode": "OBSERVE", "execution_authority": "none",
            "generated_at_utc": "2026-10-24T23:20:00+00:00"},
}


def inspect(**changes):
    data = dict(now=NOW, systemd_show=SHOW, meminfo=MEM,
                disk=DISK, snapshots={k: dict(v) for k, v in SOURCES.items()},
                load_one=4.5, cpu_count=8)
    data.update(changes)
    return inspect_runtime_diagnostics(**data)


def test_current_service_and_host_pressure_are_observations_only():
    report = inspect()
    assert report["schema_version"] == SCHEMA
    assert report["materializer_last_run"] == {
        "status": "LAST_RUN_SUCCESS", "duration_ms": 1000
    }
    assert report["system_memory"]["used_pct"] == 60.0
    assert report["repo_filesystem"]["used_pct"] == 30.0
    assert report["system_load_1m_per_core"] == 0.562
    assert report["source_snapshot_age_seconds"]["cloud"] == 1200
    assert report["blockers"] == []
    assert report["execution_authority"] == "none"
    assert report["database_writes"] is False
    assert report["payment_authorized"] is False
    assert report["model_training_authorized"] is False
    assert report["historical_run_counts"] is None
    assert report["materializer_journal_24h"] is None
    assert "inference_request_latency" in UNKNOWN_METRICS


@pytest.mark.parametrize("result,status", [
    ("exit-code", "1"), ("success", "3"), ("failed", "0"),
])
def test_failed_last_run_is_not_admitted_as_healthy(result, status):
    raw = SHOW.replace("Result=success", f"Result={result}").replace(
        "ExecMainStatus=0", f"ExecMainStatus={status}")
    report = inspect(systemd_show=raw)
    assert report["materializer_last_run"]["status"] == "LAST_RUN_FAILED"
    assert "MATERIALIZER_LAST_RUN_NOT_VERIFIED_SUCCESS" in report["blockers"]


def test_forged_duplicate_systemd_properties_fail_closed():
    report = inspect(systemd_show=SHOW + "Result=success\n")
    assert report["materializer_last_run"]["status"] == "UNKNOWN"
    assert report["materializer_last_run"]["duration_ms"] is None


def test_missing_monotonic_duration_does_not_fabricate_zero():
    raw = SHOW.replace("ExecMainStartTimestampMonotonic=3510000000000\n", "").replace(
        "ExecMainExitTimestampMonotonic=3510001000000\n", "")
    report = inspect(systemd_show=raw)
    assert report["materializer_last_run"]["status"] == "LAST_RUN_SUCCESS"
    assert report["materializer_last_run"]["duration_ms"] is None


def test_broken_monotonic_counter_rejected_without_hiding_last_result():
    raw = SHOW.replace("3510001000000", "3509999999999")
    report = inspect(systemd_show=raw)
    assert report["materializer_last_run"]["status"] == "LAST_RUN_SUCCESS"
    assert report["materializer_last_run"]["duration_ms"] is None


def test_subsecond_monotonic_duration():
    raw = SHOW.replace("3510001000000", "3510000368486")
    report = inspect(systemd_show=raw)
    assert report["materializer_last_run"]["duration_ms"] == 368.486


def test_future_exit_timestamp_rejected():
    raw = SHOW.replace("Sun 2026-10-25 23:17:49 UTC",
                       "Sun 2026-10-26 23:17:49 UTC")
    report = inspect(systemd_show=raw)
    assert report["materializer_last_run"]["status"] == "UNKNOWN"


def test_expired_and_forged_jev_evidence_fails_closed():
    rows = {k: dict(v) for k, v in SOURCES.items()}
    rows["jev"]["generated_at_utc"] = "2026-10-22T00:00:00Z"
    rows["jev"]["execution_authority"] = "spend"
    report = inspect(snapshots=rows)
    assert report["source_snapshot_age_seconds"]["jev"] is None
    assert "JEV_SNAPSHOT_STALE_OR_UNTRUSTED" in report["blockers"]


def test_source_clock_cannot_be_in_the_future():
    rows = {k: dict(v) for k, v in SOURCES.items()}
    rows["cloud"]["generated_at"] = "2026-10-26T01:00:00Z"
    report = inspect(snapshots=rows)
    assert report["source_snapshot_age_seconds"]["cloud"] is None
    assert "CLOUD_SNAPSHOT_STALE_OR_UNTRUSTED" in report["blockers"]


def test_missing_telemetry_is_unknown_not_zero():
    report = inspect(systemd_show="", meminfo="", disk={},
                     load_one=None, cpu_count=None)
    assert report["materializer_last_run"]["status"] == "UNKNOWN"
    assert report["system_memory"] is None
    assert report["repo_filesystem"] is None
    assert report["system_load_1m_per_core"] is None
    assert "MEMORY_TELEMETRY_UNKNOWN" in report["blockers"]
    assert "DISK_TELEMETRY_UNKNOWN" in report["blockers"]


@pytest.mark.parametrize("mem,disk", [
    ("MemTotal:       0 kB\nMemAvailable: 0 kB\n", DISK),
    ("MemTotal:       100 kB\nMemAvailable: 200 kB\n", DISK),
    (MEM, {"total": 100, "used": 101, "free": 0}),
    (MEM, {"total": 100, "used": True, "free": 0}),
])
def test_malformed_pressure_inputs_never_become_valid(mem, disk):
    report = inspect(meminfo=mem, disk=disk)
    assert (report["system_memory"] is None or
            report["repo_filesystem"] is None)
    assert report["execution_authority"] == "none"


def test_high_resource_pressure_is_flagged_without_service_action():
    report = inspect(meminfo="MemTotal: 100 kB\nMemAvailable: 5 kB\n",
                     disk={"total": 1000, "used": 980, "free": 10})
    assert "MEMORY_PRESSURE_HIGH" in report["blockers"]
    assert "DISK_PRESSURE_HIGH" in report["blockers"]
    assert report["service_restarts"] == 0


def test_missing_and_wrong_source_inventory_rejected():
    with pytest.raises(ValueError, match="EXACT_SNAPSHOT_CONTRACT_REQUIRED"):
        inspect(snapshots={})
    with pytest.raises(ValueError, match="EXPLICIT_AWARE_CLOCK_REQUIRED"):
        inspect(now=NOW.replace(tzinfo=None))


def test_cli_does_not_probe_host_without_explicit_read_only(capsys, monkeypatch):
    from scripts import review_predictive_cloud_runtime_diagnostics_20261025 as cli
    def reject(*args, **kwargs):
        raise AssertionError("live host probe was executed without permission")
    monkeypatch.setattr(cli, "_service_show", reject)
    code = cli.main([], root=Path("/path/not/to/read"))
    output = capsys.readouterr().out
    assert code == 2
    assert "EXPLICIT_READ_ONLY_REQUIRED" in output


def _journal_event(message: str, *, pid: str = "1",
                   minutes_ago: int = 5) -> str:
    timestamp = NOW - timedelta(minutes=minutes_ago)
    return json.dumps({
        "_PID": pid, "_COMM": "systemd",
        "UNIT": "empire-predictive-cloud-materializer.service",
        "_BOOT_ID": "f" * 32,
        "__REALTIME_TIMESTAMP": str(int(timestamp.timestamp() * 1_000_000)),
        "MESSAGE": message,
    })


def test_visible_journal_completion_counts_not_historical_totals():
    success = "empire-predictive-cloud-materializer.service: Deactivated successfully."
    failure = ("empire-predictive-cloud-materializer.service: "
               "Failed with result 'exit-code'.")
    data = "\n".join((_journal_event(success), _journal_event(success),
                      _journal_event(failure)))
    report = inspect(journal_jsonl=data)
    assert report["materializer_journal_24h"] == {
        "scope": "VISIBLE_JOURNAL_COMPLETIONS_ONLY",
        "window_hours": 24,
        "success_messages_seen": 2,
        "failure_messages_seen": 1,
        "visible_completion_messages": 3,
        "sample_limit_reached": False,
        "full_history_verified": False,
    }
    assert report["historical_run_counts"] is None
    assert report["model_training_authorized"] is False


def test_missing_journal_is_unknown_and_empty_journal_is_zero_visible_only():
    assert inspect(journal_jsonl=None)["materializer_journal_24h"] is None
    value = inspect(journal_jsonl="")["materializer_journal_24h"]
    assert value["visible_completion_messages"] == 0
    assert value["full_history_verified"] is False


@pytest.mark.parametrize("raw", [
    "not json",
    _journal_event(
        "empire-predictive-cloud-materializer.service: Deactivated successfully.",
        pid="999"
    ),
    _journal_event(
        "empire-predictive-cloud-materializer.service: Deactivated successfully.",
        minutes_ago=25*60
    ),
    ("{}\n" * 1025),
])
def test_untrusted_or_truncated_journal_does_not_prove_health(raw):
    assert inspect(journal_jsonl=raw)["materializer_journal_24h"] is None


def test_unrelated_journal_message_cannot_inflate_counts():
    report = inspect(journal_jsonl=_journal_event("A random log entry"))
    assert report["materializer_journal_24h"]["visible_completion_messages"] == 0


def test_maximum_journal_window_discloses_sampling_limit():
    success = "empire-predictive-cloud-materializer.service: Deactivated successfully."
    raw = "\n".join(_journal_event(success) for _ in range(1024))
    result = inspect(journal_jsonl=raw)["materializer_journal_24h"]
    assert result["visible_completion_messages"] == 1024
    assert result["sample_limit_reached"] is True
    assert result["full_history_verified"] is False
