from datetime import datetime, timezone
import json

import pytest

from empire_os.outbound_observer_heartbeat import (
    evaluate_observer_heartbeat,
    write_observer_heartbeat,
)


NOW = datetime(2026, 10, 3, 21, 0, tzinfo=timezone.utc)


def result():
    return {
        "mode": "OBSERVE",
        "scope_key": "empire",
        "ringleader": {
            "posture": "READY",
            "telemetry_sla": {"posture": "CURRENT"},
        },
        "mutation_authorized": False,
    }


def test_successful_observer_cycle_writes_non_authorizing_heartbeat(tmp_path):
    path = tmp_path / "heartbeat.json"
    payload = write_observer_heartbeat(result(), path=path, now=NOW)

    assert path.exists()
    assert payload["mode"] == "OBSERVE"
    assert payload["ringleader_posture"] == "READY"
    assert payload["telemetry_posture"] == "CURRENT"
    assert payload["mutation_authorized"] is False
    assert payload["send_authorized"] is False

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk == payload


def test_current_heartbeat_is_current(tmp_path):
    path = tmp_path / "heartbeat.json"
    write_observer_heartbeat(result(), path=path, now=NOW)

    status = evaluate_observer_heartbeat(
        path=path,
        now=datetime(2026, 10, 3, 21, 10, tzinfo=timezone.utc),
        max_age_minutes=15,
    )
    assert status["status"] == "CURRENT"
    assert status["age_seconds"] == 600


def test_old_heartbeat_is_stale(tmp_path):
    path = tmp_path / "heartbeat.json"
    write_observer_heartbeat(result(), path=path, now=NOW)

    status = evaluate_observer_heartbeat(
        path=path,
        now=datetime(2026, 10, 3, 21, 20, tzinfo=timezone.utc),
        max_age_minutes=15,
    )
    assert status["status"] == "STALE"


def test_missing_heartbeat_is_missing(tmp_path):
    status = evaluate_observer_heartbeat(
        path=tmp_path / "missing.json",
        now=NOW,
    )
    assert status["status"] == "MISSING"


def test_invalid_or_authorizing_heartbeat_is_invalid(tmp_path):
    path = tmp_path / "heartbeat.json"
    path.write_text(
        json.dumps({
            "observed_at": NOW.isoformat(),
            "mutation_authorized": True,
        }),
        encoding="utf-8",
    )
    status = evaluate_observer_heartbeat(path=path, now=NOW)
    assert status["status"] == "INVALID"


def test_writer_rejects_mutating_observer_result(tmp_path):
    bad = result()
    bad["mutation_authorized"] = True
    with pytest.raises(RuntimeError, match="non_mutating"):
        write_observer_heartbeat(
            bad,
            path=tmp_path / "heartbeat.json",
            now=NOW,
        )
