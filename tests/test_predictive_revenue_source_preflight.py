from datetime import datetime, timezone
import json

import pytest

from empire_os.predictive_revenue_source_preflight import review_authenticated_sources

NOW = datetime(2026, 11, 15, 15, tzinfo=timezone.utc)
TENANT = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _registered(**kwargs):
    return {
        "schema_version": "empire.predictive_revenue.tenant_registry_inspection.v1",
        "status": "TENANT_BOUND_REGISTRY_ROWS_OBSERVED_UNVERIFIED",
        "mode": "OBSERVE", "execution_authority": "none",
        "trusted_session_user_tenant_matched": True,
        "reader_nologin_noinherit_nobypassrls_verified": True,
        "forecast_registry_force_rls_verified": True,
        "original_forecast_immutable_registration_verified": False,
        "financial_actuals_verified": False,
        "observed_row_count": 4, **kwargs,
    }


def _census(**kwargs):
    return {
        "schema_version": "empire.predictive_revenue.daily_census_candidate.v1",
        "status": "DAY_SOURCE_CENSUS_CANDIDATE",
        "mode": "OBSERVE", "execution_authority": "none",
        "observed_utc_date": "2026-11-14",
        "database_session_tenant_identity_matched": True,
        "daily_revenue_census_verified": False,
        "ledger_backfill_finality_attested": False,
        "eligible_for_revenue_forecast_calibration": False,
        "tenant_event_count": 2, **kwargs,
    }


def test_no_auth_material_returns_hold_without_db_attempts():
    def forbidden(**kw):
        raise AssertionError("should not call credentialed source")
    got = review_authenticated_sources(
        tenant_id=None, registry_dsn=None, census_dsn=None,
        as_of=NOW, registry_reader=forbidden, census_reader=forbidden,
    )
    assert got["registry_source_status"] == "CANONICAL_TENANT_SCOPE_UNAVAILABLE"
    assert got["census_source_status"] == "CANONICAL_TENANT_SCOPE_UNAVAILABLE"
    assert got["registry_scoped_rows_observed"] is None
    assert got["original_restricted_registry_reader_reused"] is False
    assert got["registry_restricted_read_attempted"] is False
    assert got["census_restricted_read_attempted"] is False
    assert got["independently_verified_forecast_actual_pairs"] == 0


def test_missing_independent_reader_credentials_are_not_bypassed():
    got = review_authenticated_sources(
        tenant_id=TENANT, registry_dsn=None, census_dsn=None, as_of=NOW,
    )
    assert got["registry_source_status"] == "DEDICATED_REGISTRY_CREDENTIAL_UNAVAILABLE"
    assert got["census_source_status"] == "DEDICATED_CENSUS_CREDENTIAL_UNAVAILABLE"
    assert got["source_credentials_exposed"] is False
    assert TENANT not in json.dumps(got)


def test_positive_source_reads_do_not_authorize_calibration_or_revenue():
    registry_calls = []
    census_calls = []
    def registry(**kw):
        registry_calls.append(kw)
        return _registered()
    def census(**kw):
        census_calls.append(kw)
        return _census()
    got = review_authenticated_sources(
        tenant_id=TENANT, registry_dsn="secret:registry",
        census_dsn="secret:census", as_of=NOW,
        registry_reader=registry, census_reader=census,
    )
    assert len(registry_calls) == len(census_calls) == 1
    assert registry_calls[0]["tenant_id"] == TENANT
    assert registry_calls[0]["limit"] == 100
    assert census_calls[0]["day_utc"].isoformat() == "2026-11-14"
    assert census_calls[0]["require_session_tenant_binding"] is True
    assert got["registry_source_status"] == "INJECTED_READER_CONTRACT_TEST_ONLY"
    assert got["census_source_status"] == "INJECTED_READER_CONTRACT_TEST_ONLY"
    assert got["registry_scoped_rows_observed"] is None
    assert got["census_tenant_events_observed"] is None
    assert got["registry_reader_authenticated_session"] is False
    assert got["census_reader_authenticated_session"] is False
    assert got["model_calibration_ready"] is False
    assert got["independently_verified_forecast_actual_pairs"] == 0
    assert got["customer_revenue_amount_verified"] is False
    assert "secret" not in json.dumps(got)
    assert TENANT not in json.dumps(got)


def test_rejects_malicious_registry_or_census_overclaim():
    def registry(**kw):
        return _registered(original_forecast_immutable_registration_verified=True)
    def census(**kw):
        return _census(daily_revenue_census_verified=True)
    got = review_authenticated_sources(
        tenant_id=TENANT, registry_dsn="a", census_dsn="b",
        as_of=NOW, registry_reader=registry, census_reader=census,
    )
    assert got["registry_source_status"] == "REGISTRY_RESTRICTED_READ_OR_POLICY_FAILED"
    assert got["census_source_status"] == "CENSUS_RESTRICTED_READ_OR_POLICY_FAILED"
    assert not got["customer_release_authorized"]


def test_reader_failures_return_only_sanitized_status():
    def failed(**kw):
        raise RuntimeError("private_password=secret_key tenant=private")
    got = review_authenticated_sources(
        tenant_id=TENANT, registry_dsn="a", census_dsn="b",
        as_of=NOW, registry_reader=failed, census_reader=failed,
    )
    assert got["registry_source_status"] == "REGISTRY_RESTRICTED_READ_OR_POLICY_FAILED"
    assert got["census_source_status"] == "CENSUS_RESTRICTED_READ_OR_POLICY_FAILED"
    assert "private_password" not in json.dumps(got)


def test_wrong_tenant_and_time_rejected():
    got = review_authenticated_sources(
        tenant_id="not-uuid", registry_dsn="x", census_dsn="y", as_of=NOW,
    )
    assert got["registry_reader_authenticated_session"] is False
    with pytest.raises(ValueError, match="aware"):
        review_authenticated_sources(
            tenant_id=TENANT, registry_dsn=None, census_dsn=None,
            as_of=datetime(2026, 11, 15),
        )
