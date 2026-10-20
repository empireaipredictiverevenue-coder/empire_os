"""Metadata-only fixture checks for tenant-aware source admission."""
from __future__ import annotations
from copy import deepcopy
import json
import pytest

from empire_os.predictive_tenant_outcome_reader_preflight import (
    review_tenant_outcome_reader_policy,
    TenantEvidencePolicyHold,
    TABLE_POLICY,
    TABLE_SQL,
    POLICY_SQL,
    IDENTITY_SQL,
    ROLE_SQL,
)
import scripts.review_predictive_tenant_outcome_reader_preflight_20261020 as cli

TENANT = "4ec7c503-b78f-4201-ad2a-2a00f7b1b6f4"
LOGIN = "fixture_login_readonly"


def fixture_data():
    metadata = [
        (name, True, True, True)
        for name in TABLE_POLICY
    ]
    policies = [
        (name, policy, "SELECT", ["empiredb_tenant_reader"],
         "buyer_id IS NOT NULL AND public.empire_current_tenant_id() IS NOT NULL")
        for name, policy in TABLE_POLICY.items()
    ]
    return metadata, policies


class Cursor:
    def __init__(self, settings):
        self.settings = settings
        self.calls = []
        self.last = None

    def __enter__(self): return self
    def __exit__(self, *args): return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        self.last = (sql, params)

    def fetchone(self):
        sql, params = self.last
        if sql == IDENTITY_SQL:
            return self.settings.get(
                "identity", ("empiredb", "on", LOGIN,
                             "empiredb_tenant_reader", TENANT)
            )
        if sql == ROLE_SQL:
            if params == (LOGIN,):
                return self.settings.get("login_role", (True, False, False, False))
            if params == ("empiredb_tenant_reader",):
                return self.settings.get("reader_role", (False, False, False, False))
        raise AssertionError("unapproved scalar source")

    def fetchall(self):
        sql, params = self.last
        assert set(params[0]) == set(TABLE_POLICY)
        if sql == TABLE_SQL:
            return self.settings["tables"]
        if sql == POLICY_SQL:
            return self.settings["policies"]
        raise AssertionError("unapproved bulk source")


class Connection:
    def __init__(self, settings):
        self.cur = Cursor(settings)
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self.cur


def run(changes=None):
    tables, policies = fixture_data()
    state = {"tables": tables, "policies": policies}
    state.update(changes or {})
    calls = []
    def connect(dsn, *, connect_timeout):
        assert dsn == "test-credential-placeholder"
        assert connect_timeout == 5
        conn = Connection(state)
        calls.append(conn)
        return conn
    result = review_tenant_outcome_reader_policy(
        dsn="test-credential-placeholder", connect_factory=connect
    )
    return result, calls[0].cur.calls


def test_authentic_shape_is_only_policy_metadata_not_customer_evidence():
    report, calls = run()
    assert report["status"] == "TENANT_SOURCE_POLICY_METADATA_REVIEW_READY"
    assert report["policy_gap_codes"] == []
    assert report["session_tenant_resolved_by_db_role"] is True
    assert report["customer_forecast_eligible"] is False
    assert report["authenticated_terminal_outcomes_read"] is False
    assert report["original_conversion_prediction_registry_verified"] is False
    assert report["tenant_safe_data_reader_activated"] is False
    assert report["database_writes"] is False
    assert report["role_or_rls_changed"] is False
    assert report["execution_authority"] == "none"
    assert TENANT not in json.dumps(report)
    assert LOGIN not in json.dumps(report)
    assert calls[0][0] == "SET TRANSACTION READ ONLY"
    assert any(x[0] == IDENTITY_SQL for x in calls)
    assert any(x[0] == TABLE_SQL for x in calls)
    assert any(x[0] == POLICY_SQL for x in calls)
    assert all(
        (s.startswith("SELECT") or s.startswith("SET ")) for s, _ in calls
    )


def test_missing_outcome_policy_and_force_rls_never_pass():
    tables, policies = fixture_data()
    tables = [
        (n, enabled, False if n == "commercial_outcomes" else forced, granted)
        for n, enabled, forced, granted in tables
    ]
    policies = [x for x in policies if x[0] != "commercial_outcomes"]
    report, _ = run({"tables": tables, "policies": policies})
    assert report["status"] == "TENANT_SOURCE_POLICY_GAPS_OBSERVED"
    assert "commercial_outcomes.rls_forced" in report["policy_gap_codes"]
    assert "commercial_outcomes.expected_scoped_policy_found" in report["policy_gap_codes"]
    assert report["customer_forecast_eligible"] is False


def test_no_select_grant_still_has_gap():
    tables, policies = fixture_data()
    tables[2] = (tables[2][0], True, True, False)
    report, _ = run({"tables": tables, "policies": policies})
    assert any("reader_select_granted" in gap for gap in report["policy_gap_codes"])


@pytest.mark.parametrize("bad", [
    ("identity", ("empiredb", "on", LOGIN, "empiredb_tenant_reader", None)),
    ("identity", ("not_empiredb", "on", LOGIN, "empiredb_tenant_reader", TENANT)),
    ("identity", ("empiredb", "off", LOGIN, "empiredb_tenant_reader", TENANT)),
    ("identity", ("empiredb", "on", "postgres", "empiredb_tenant_reader", TENANT)),
    ("identity", ("empiredb", "on", LOGIN, "empiredb_app", TENANT)),
    ("login_role", (True, True, False, False)),
    ("login_role", (True, False, True, False)),
    ("login_role", (True, False, False, True)),
    ("reader_role", (False, False, True, False)),
    ("reader_role", (True, False, False, False)),
])
def test_bad_authority_cannot_inspect_original_source(bad):
    key, value = bad
    with pytest.raises(TenantEvidencePolicyHold):
        run({key: value})


def test_bogus_public_policy_is_not_counted_as_tenant_control():
    tables, policies = fixture_data()
    policies = [
        (name, policy, cmd, ["PUBLIC"] if name == "commercial_events" else roles, qual)
        for name, policy, cmd, roles, qual in policies
    ]
    report, _ = run({"policies": policies})
    assert "commercial_events.expected_scoped_policy_found" in report["policy_gap_codes"]


def test_repeated_metadata_name_refused():
    tables, _ = fixture_data()
    with pytest.raises(TenantEvidencePolicyHold):
        run({"tables": tables + [tables[0]]})


def test_missing_dsn_is_never_connected(monkeypatch, capsys):
    monkeypatch.delenv(cli.DSN_ENV, raising=False)
    assert cli.main(["--read-only"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "HELD_DEDICATED_TENANT_OUTCOME_READER_CREDENTIAL_MISSING"
    assert report["customer_forecast_eligible"] is False


def test_unavailable_or_bad_credential_redacts_private_error(monkeypatch, capsys):
    monkeypatch.setenv(cli.DSN_ENV, "fixture-private-secret")
    def fail(**kwargs):
        raise TenantEvidencePolicyHold("server with secret and private tenant")
    monkeypatch.setattr(cli, "review_tenant_outcome_reader_policy", fail)
    assert cli.main(["--read-only"]) == 0
    result = capsys.readouterr().out
    assert "secret" not in result
    assert "private tenant" not in result
    assert json.loads(result)["customer_forecast_eligible"] is False
