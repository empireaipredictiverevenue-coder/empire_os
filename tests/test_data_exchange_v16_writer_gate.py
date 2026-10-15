"""Enforce V16 24-hour cadence under V15 custody transaction lock."""
from datetime import timedelta
import pytest

from empire_os.data_exchange_observation_custody import (
    CustodyIntegrityError, plan_custody_append,
)
from empire_os.data_exchange_custody_transport import EmpireDBConstructionCustody
from test_data_exchange_observation_custody import Cursor, Connection, db_row
from test_data_exchange_temporal_quality import NOW, snap


def writer_at(hours_ago):
    old_at = NOW - timedelta(hours=hours_ago)
    old_snapshot = snap(old_at)
    old = plan_custody_append(
        old_snapshot, previous=None, assessed_at=NOW)["row"]
    cur = Cursor(head=db_row(old))
    store = EmpireDBConstructionCustody(
        "isolated-fixture", connector=lambda *a, **k: Connection(cur))
    return store, cur, old_snapshot


@pytest.mark.parametrize("elapsed_minutes", [1, 60, 360, 1439])
def test_early_reobservation_rejected_inside_serialised_transport(elapsed_minutes):
    old_hours=24
    store, cur, _ = writer_at(old_hours)
    latest = snap(
        NOW - timedelta(hours=old_hours) + timedelta(minutes=elapsed_minutes))
    with pytest.raises(CustodyIntegrityError,
                       match="CANONICAL_NEXT_OBSERVATION_NOT_DUE_24H"):
        store.append_once(latest, now=NOW)
    assert cur.writes == 0
    assert any("pg_advisory_xact_lock" in sql for sql, _ in cur.queries)
    assert not any(sql.startswith("INSERT") for sql, _ in cur.queries)


def test_exact_24h_later_is_allowed_by_existing_writer():
    store, cur, _ = writer_at(26)
    result = store.append_once(snap(NOW - timedelta(hours=2)), now=NOW)
    assert result["mode"] == "CANONICAL_APPEND_COMMITTED"
    assert result["database_writes"] is True
    assert result["sequence"] == 1
    assert cur.writes == 1


def test_exact_same_timestamp_replay_remains_noop():
    store, cur, old_snapshot = writer_at(2)
    result = store.append_once(old_snapshot, now=NOW)
    assert result["mode"] == "ALREADY_OBSERVED"
    assert result["database_writes"] is False
    assert result["sequence"] == 0
    assert cur.writes == 0


def test_under_24h_real_field_change_still_cannot_bypass_gate():
    store, cur, _ = writer_at(10)
    newer = snap(NOW, status="permissioned")
    with pytest.raises(CustodyIntegrityError,
                       match="CANONICAL_NEXT_OBSERVATION_NOT_DUE_24H"):
        store.append_once(newer, now=NOW)
    assert cur.writes == 0
