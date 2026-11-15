"""V4 native EmpireDB census: source-observation contract, not cash finality."""
from datetime import date, datetime, timedelta, timezone

import pytest

from empire_os.predictive_revenue_canonical_reader import (
    CanonicalRevenueEvidenceUnavailable,
)
from empire_os.predictive_revenue_daily_census import (
    read_daily_revenue_census,
    verify_daily_census_row,
)

TENANT = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
DAY = date(2026, 11, 10)


def _row(*, snapshot_at, broken=0, valid=1, amount=12345):
    return (
        DAY, TENANT, valid + broken, valid, amount, broken, 0, snapshot_at,
    )


def test_original_row_verifier_remains_strict_about_future_source_time():
    as_of = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
    with pytest.raises(CanonicalRevenueEvidenceUnavailable,
                       match="SNAPSHOT_TIME_INVALID"):
        verify_daily_census_row(
            _row(snapshot_at=as_of + timedelta(milliseconds=5)),
            day_utc=DAY, tenant_id=TENANT, as_of=as_of,
        )


def test_source_candidate_never_claims_settlement_or_model_calibration():
    as_of = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
    got = verify_daily_census_row(
        _row(snapshot_at=as_of), day_utc=DAY, tenant_id=TENANT, as_of=as_of,
    )
    assert got["status"] == "DAY_SOURCE_CENSUS_CANDIDATE"
    assert got["tenant_candidate_amount_cents"] == 12345
    assert got["daily_revenue_census_verified"] is False
    assert got["ledger_backfill_finality_attested"] is False
    assert got["tenant_authorization_proven"] is False
    assert got["eligible_for_revenue_forecast_calibration"] is False
    assert got["execution_authority"] == "none"


def test_global_orphan_revenue_event_holds_even_valid_tenant():
    as_of = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
    got = verify_daily_census_row(
        _row(snapshot_at=as_of, broken=1),
        day_utc=DAY, tenant_id=TENANT, as_of=as_of,
    )
    assert got["status"] == "DAY_CENSUS_INCOMPLETE_HOLD"
    assert got["tenant_candidate_amount_cents"] is None
    assert got["unknown_or_invalid_global_event_count"] == 1
    assert got["eligible_for_revenue_forecast_calibration"] is False


class _Cursor:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        return (TENANT,)

    def fetchall(self):
        return [self.row]


class _Conn:
    def __init__(self, cursor):
        self.cur = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self.cur


def test_reader_verifies_at_read_completion_not_before_query():
    # A real database query finishes after its caller's as_of timestamp.
    # Regression: before the fix, a millisecond-newer DB snapshot failed.
    actual_snapshot = datetime.now(timezone.utc)
    reader = _Cursor(_row(snapshot_at=actual_snapshot))
    got = read_daily_revenue_census(
        day_utc=DAY, tenant_id=TENANT,
        as_of=actual_snapshot - timedelta(milliseconds=5),
        dsn="fixture-only", connect_factory=lambda *_a, **_k: _Conn(reader),
        require_session_tenant_binding=True,
    )
    assert got["status"] == "DAY_SOURCE_CENSUS_CANDIDATE"
    assert got["database_session_tenant_identity_matched"] is True
    assert got["eligible_for_revenue_forecast_calibration"] is False
    assert any("SET TRANSACTION READ ONLY" in sql for sql, _ in reader.calls)
    assert any("SET LOCAL ROLE empire_predictive_revenue_evidence_reader" in sql
               for sql, _ in reader.calls)


def test_read_completion_does_not_accept_far_future_snapshot():
    reader = _Cursor(_row(
        snapshot_at=datetime.now(timezone.utc) + timedelta(days=1)
    ))
    with pytest.raises(CanonicalRevenueEvidenceUnavailable,
                       match="SNAPSHOT_TIME_INVALID"):
        read_daily_revenue_census(
            day_utc=DAY, tenant_id=TENANT,
            as_of=datetime.now(timezone.utc),
            dsn="fixture-only", connect_factory=lambda *_a, **_k: _Conn(reader),
            require_session_tenant_binding=True,
        )
