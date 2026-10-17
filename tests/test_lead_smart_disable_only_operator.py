"""Existing first-party pilot STOP: only a bounded disable mutation."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from empire_os.lead_smart_site_handoff import (
    CAMPAIGN, NUMBER, SCHEMA,
    verified_site_handoff_control, site_handoff_available,
)
from scripts.disable_lead_smart_pilot_control import stop_control

NOW = datetime(2026, 10, 12, 16, 15, tzinfo=timezone.utc)


def control():
    return {
        "schema_version": SCHEMA,
        "campaign_id": CAMPAIGN,
        "tracking_number": NUMBER,
        "enabled": True,
        "max_site_handoffs": 5,
        "monitoring_owner": "Founder supervision",
        "stop_method": "atomic_site_handoff_gate",
        "founder_authority_ref": "test_only",
        "starts_at": "2026-10-12T15:00:00+00:00",
        "ends_at": "2026-10-12T17:00:00+00:00",
    }


def write_protected(path: Path, data: str) -> None:
    path.write_text(data)
    path.chmod(0o600)


def readiness():
    return {
        "schema_version": "empire.lead_smart.launch_readiness.v1",
        "mode": "READY",
        "execution_authority": "LIVE_TRAFFIC",
        "launch_ready": True,
        "call_cta_enabled": True,
        "buyer_window_open_now": True,
        "gates": {"all_tests_only": True},
        "operating_hours": {"evaluated_at": NOW.isoformat()},
    }


def test_absent_control_remains_absent_even_with_apply(tmp_path):
    path = tmp_path / "pilot" / "approved_control.json"
    assert stop_control(control_path=path, apply=True)["status"] == "NO_CONTROL_HELD"
    assert not path.parent.exists()


def test_default_is_dry_run_zero_file_mutation(tmp_path):
    path = tmp_path / "approved_control.json"
    write_protected(path, json.dumps(control()))
    before = path.read_bytes()
    report = stop_control(control_path=path)
    assert report["status"] == "WOULD_DISABLE"
    assert report["state_changed"] is False
    assert report["pilot_activation_authorized"] is False
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_real_disable_holds_future_handoffs_and_preserves_ledger(tmp_path):
    path = tmp_path / "approved_control.json"
    ledger = tmp_path / "site_handoffs.json"
    write_protected(path, json.dumps(control()))
    ledger.write_text('{"site_handoffs":2}')
    before_ledger = ledger.read_bytes()
    assert verified_site_handoff_control(
        config_path=path, ledger_path=tmp_path / "unwritten.json", now=NOW
    )
    result = stop_control(control_path=path, apply=True)
    assert result["status"] == "DISABLED"
    assert result["state_changed"] is True
    assert result["buyer_routing_modified"] is False
    assert result["calls_in_progress_stopped"] is False
    assert json.loads(path.read_text())["enabled"] is False
    assert path.stat().st_mode & 0o777 == 0o600
    assert ledger.read_bytes() == before_ledger
    assert not verified_site_handoff_control(
        config_path=path, ledger_path=ledger, now=NOW
    )
    assert not site_handoff_available(
        "07001", config_path=path, ledger_path=ledger,
        readiness=readiness(), eligible_zip=True, now=NOW
    )


def test_disabled_control_idempotent_not_reactivated(tmp_path):
    path = tmp_path / "approved_control.json"
    write_protected(path, json.dumps({**control(), "enabled": False}))
    before = path.read_bytes()
    r = stop_control(control_path=path, apply=True)
    assert r["status"] == "ALREADY_DISABLED"
    assert not r["state_changed"]
    assert path.read_bytes() == before


@pytest.mark.parametrize("changes", [
    {"campaign_id": "someone-else"},
    {"tracking_number": "+15550000000"},
    {"schema_version": "invented"},
    {"stop_method": "other"},
    {"max_site_handoffs": 6},
    {"enabled": "true"},
])
def test_unrecognized_control_is_not_modified(tmp_path, changes):
    path = tmp_path / "approved_control.json"
    write_protected(path, json.dumps({**control(), **changes}))
    before = path.read_bytes()
    report = stop_control(control_path=path, apply=True)
    assert report["status"] == "UNTRUSTED_CONTROL_HELD"
    assert path.read_bytes() == before


def test_symlink_is_not_followed(tmp_path):
    target = tmp_path / "target.json"
    target.write_text(json.dumps(control()))
    path = tmp_path / "approved_control.json"
    path.symlink_to(target)
    result = stop_control(control_path=path, apply=True)
    assert result["status"] == "UNTRUSTED_CONTROL_HELD"
    assert json.loads(target.read_text())["enabled"] is True


def test_duplicate_keys_fail_closed(tmp_path):
    path = tmp_path / "approved_control.json"
    duplicate = json.dumps(control()).replace('"enabled": true',
        '"enabled": true, "enabled": false')
    write_protected(path, duplicate)
    assert stop_control(control_path=path, apply=True)["status"] == "UNTRUSTED_CONTROL_HELD"
    assert path.read_text() == duplicate



def test_writable_by_group_control_is_rejected(tmp_path):
    path = tmp_path / "approved_control.json"
    path.write_text(json.dumps(control()))
    path.chmod(0o660)
    assert stop_control(control_path=path, apply=True)["status"] == "UNTRUSTED_CONTROL_HELD"
    assert json.loads(path.read_text())["enabled"] is True


def test_stop_serializes_with_live_reservation_and_blocks_next(monkeypatch, tmp_path):
    """Stop cannot report success while an earlier reserve holds the lock."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from empire_os import lead_smart_site_handoff as handoff

    control_path = tmp_path / "approved_control.json"
    ledger = tmp_path / "site_handoffs.json"
    write_protected(control_path, json.dumps(control()))
    reservation_inside_lock = Event()
    release_reservation = Event()
    stop_started = Event()
    original_write = handoff._write_atomic

    def pause_before_commit(path, payload):
        reservation_inside_lock.set()
        assert release_reservation.wait(timeout=5), "Timed out waiting to release test reservation"
        return original_write(path, payload)

    monkeypatch.setattr(handoff, "_write_atomic", pause_before_commit)

    def reserve():
        return handoff.reserve_site_handoff(
            "07001", config_path=control_path, ledger_path=ledger,
            readiness=readiness(), eligible_zip=True, now=NOW,
        )

    def stop():
        stop_started.set()
        return stop_control(control_path=control_path, apply=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        existing_reservation = pool.submit(reserve)
        assert reservation_inside_lock.wait(timeout=5)
        stop_future = pool.submit(stop)
        assert stop_started.wait(timeout=5)
        try:
            # While the reservation is blocked inside the shared lock,
            # an emergency stop must not be able to change the config yet.
            assert not stop_future.done()
        finally:
            release_reservation.set()
        assert existing_reservation.result(timeout=5) == "tel:" + NUMBER
        assert stop_future.result(timeout=5)["status"] == "DISABLED"
    assert json.loads(ledger.read_text())["site_handoffs"] == 1
    assert json.loads(control_path.read_text())["enabled"] is False
    with pytest.raises(handoff.HandoffHeld):
        handoff.reserve_site_handoff(
            "07001", config_path=control_path, ledger_path=ledger,
            readiness=readiness(), eligible_zip=True, now=NOW,
        )
