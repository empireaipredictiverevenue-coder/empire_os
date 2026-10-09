from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import empire_os.storm_service as storm_service


NOW = datetime.now(timezone.utc)


def legacy_event(**overrides):
    row = {
        "event_id": "nws-test-1",
        "event_type": "Severe Thunderstorm Warning",
        "severity": 4,
        "area_description": "Test County",
        "headline": "Test warning",
        "occurred_at": (NOW - timedelta(minutes=10)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=50)).isoformat(),
    }
    row.update(overrides)
    return SimpleNamespace(**row)


def bare_service():
    service = object.__new__(storm_service.StormService)
    service.metrics = {"scans": 0, "strikes": 0, "started_at": 0}
    return service


def test_canonical_event_row_is_internal_observation_only():
    row = storm_service.StormService._canonical_event_row(legacy_event())

    assert row["tenant_id"] == "empire-internal"
    assert row["event_id"] == "nws-test-1"
    assert row["truth_class"] == "OBSERVED"
    assert row["severity"] == "severe"

    assert len(row["evidence"]) == 1
    ev = row["evidence"][0]

    assert ev["tenant_id"] == "empire-internal"
    assert ev["source"] == "nws_alert"
    assert ev["ref"] == "nws-test-1"


def test_severity_mapping_is_bounded():
    assert storm_service.StormService._severity_label(1) == "minor"
    assert storm_service.StormService._severity_label(2) == "moderate"
    assert storm_service.StormService._severity_label(3) == "moderate"
    assert storm_service.StormService._severity_label(4) == "severe"
    assert storm_service.StormService._severity_label(5) == "extreme"


def test_on_strike_only_observes_and_does_not_materialize(
    monkeypatch,
    tmp_path,
):
    calls = {"materialize": 0}

    def fake_materialize(repo_root, **kwargs):
        calls["materialize"] += 1
        return {
            "candidate_count": 0,
            "execution_authority": "none",
        }

    monkeypatch.setattr(
        storm_service,
        "materialize_storm_intelligence",
        fake_materialize,
    )
    monkeypatch.setattr(storm_service, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(storm_service, "LEGACY_HUB_FORWARD", False)

    service = bare_service()
    service._on_strike(legacy_event())

    assert service.metrics["strikes"] == 1
    assert calls["materialize"] == 0


def test_legacy_forward_flag_still_does_not_materialize_or_forward(
    monkeypatch,
    tmp_path,
):
    calls = {"materialize": 0}

    def fake_materialize(repo_root, **kwargs):
        calls["materialize"] += 1
        return {
            "candidate_count": 0,
            "execution_authority": "none",
        }

    monkeypatch.setattr(
        storm_service,
        "materialize_storm_intelligence",
        fake_materialize,
    )
    monkeypatch.setattr(storm_service, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(storm_service, "LEGACY_HUB_FORWARD", True)

    service = bare_service()
    service._on_strike(legacy_event())

    assert service.metrics["strikes"] == 1
    assert calls["materialize"] == 0



def test_scan_materializes_complete_deduped_event_set(monkeypatch, tmp_path):
    service = bare_service()

    first = legacy_event(event_id="nws-1")
    second = legacy_event(
        event_id="nws-2",
        area_description="Second County",
    )

    class Predictor:
        def __init__(self):
            self.events = []

        def scan(self):
            batch = [first, second]
            for event in batch:
                service._on_strike(event)
            self.events.extend(batch)
            return batch

    service.predictor = Predictor()

    captured = {}

    def fake_materialize(repo_root, **kwargs):
        captured.update(kwargs)
        return {
            "candidate_count": 0,
            "execution_authority": "none",
            "diagnostics": {"events_valid": len(kwargs["events"])},
        }

    monkeypatch.setattr(
        storm_service,
        "materialize_storm_intelligence",
        fake_materialize,
    )
    monkeypatch.setattr(storm_service, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(storm_service, "LEGACY_HUB_FORWARD", False)

    events, snapshot = service._scan_and_materialize()

    assert len(events) == 2
    assert service.metrics["strikes"] == 2
    assert len(captured["events"]) == 2
    assert {e["event_id"] for e in captured["events"]} == {"nws-1", "nws-2"}

    assert captured["subjects"] == ()
    assert captured["matches"] == ()
    assert captured["readiness"] == ()

    assert snapshot["candidate_count"] == 0
    assert snapshot["execution_authority"] == "none"


def test_scan_deduplicates_repeated_event_identity(monkeypatch, tmp_path):
    service = bare_service()

    repeated = legacy_event(event_id="nws-repeat")

    class Predictor:
        def __init__(self):
            self.events = [repeated]

        def scan(self):
            service._on_strike(repeated)
            self.events.append(repeated)
            return [repeated]

    service.predictor = Predictor()

    captured = {}

    def fake_materialize(repo_root, **kwargs):
        captured.update(kwargs)
        return {
            "candidate_count": 0,
            "execution_authority": "none",
            "diagnostics": {"events_valid": len(kwargs["events"])},
        }

    monkeypatch.setattr(
        storm_service,
        "materialize_storm_intelligence",
        fake_materialize,
    )
    monkeypatch.setattr(storm_service, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(storm_service, "LEGACY_HUB_FORWARD", False)

    service._scan_and_materialize()

    assert len(captured["events"]) == 1
    assert captured["events"][0]["event_id"] == "nws-repeat"
