"""Tenant-scoped canonical reader: real SQL contract, synthetic DB fixtures."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import pytest

from empire_os.predictive_tenant_terminal_cohort_reader import (
    CANDIDATE_SQL, LIMIT, TenantCohortSourceHold,
    read_tenant_terminal_candidates,
)
from tests.test_predictive_tenant_outcome_reader_preflight import (
    Connection, Cursor, TENANT, LOGIN, fixture_data,
)
from empire_os.predictive_tenant_outcome_reader_preflight import (
    TABLE_POLICY, POLICY_SQL,
)
import scripts.review_predictive_tenant_terminal_cohort_20261020 as cli

NOW = datetime(2026, 10, 20, 20, 0, tzinfo=timezone.utc)


def uid(n):
    return f"00000000-0000-4000-8000-{n:012d}"


def candidate(n, *, outcome="lost", tenant=TENANT, verified="true",
              synthetic="false", derived="false", event_count=0):
    return (
        uid(n), uid(2000+n), uid(3000+n), tenant, uid(4000+n),
        outcome, NOW-timedelta(hours=1), verified, synthetic, derived,
        NOW-timedelta(days=2),
        NOW-timedelta(hours=2) if outcome=="won" else None,
        None, event_count,
    )


class CandidateCursor(Cursor):
    def fetchall(self):
        sql, params = self.last
        if sql == CANDIDATE_SQL:
            assert params == (NOW, NOW, LIMIT + 1)
            return self.settings.get("candidates", [])
        return super().fetchall()


class CandidateConnection(Connection):
    def __init__(self, state):
        self.cur = CandidateCursor(state)


def run(rows=(), *, mutate=None):
    tables, policies = fixture_data()
    state = {"tables": tables, "policies": policies, "candidates": list(rows)}
    state.update(mutate or {})
    connections = []
    def connect(dsn, *, connect_timeout):
        assert dsn=="fake-no-secrets" and connect_timeout==5
        conn=CandidateConnection(state)
        connections.append(conn)
        return conn
    report=read_tenant_terminal_candidates(
        dsn="fake-no-secrets",as_of=NOW,connect_factory=connect,
    )
    return report, connections[0].cur.calls


def test_tenant_read_sql_executes_after_session_identity_and_rls():
    out, calls=run([candidate(1),candidate(2,outcome="won",event_count=1)])
    assert out["status"]=="AUTHENTICATED_TENANT_TERMINAL_CANDIDATES_UNVERIFIED"
    assert out["candidate_rows_observed"]==2
    assert out["candidate_terminal_losses"]==1
    assert out["candidate_terminal_wins"]==1
    assert out["candidate_revenue_events_present"]==1
    assert out["source_rows_exported_to_scientific_training"] is False
    assert out["original_terminal_outcomes_independently_attested"] is False
    assert out["customer_forecast_eligible"] is False
    assert out["database_writes"] is False
    assert out["execution_authority"]=="none"
    assert all(x not in json.dumps(out) for x in (TENANT,LOGIN,uid(1),uid(2)))
    commands=[c[0] for c in calls]
    assert "SET TRANSACTION READ ONLY"==commands[0]
    assert POLICY_SQL in commands
    assert commands.index(POLICY_SQL) < commands.index(CANDIDATE_SQL)
    assert "ce.buyer_id=o.buyer_id" in CANDIDATE_SQL
    assert "ce.product_id=o.product_id" in CANDIDATE_SQL
    assert "ce.payload->>'actual_revenue'='true'" in CANDIDATE_SQL
    assert all(c.startswith(("SET ", "SELECT")) for c in commands)


@pytest.mark.parametrize("case", [
    [candidate(1,tenant=uid(900))],
    [candidate(1),candidate(1)],
    [candidate(1),candidate(2)[:-14]+tuple(candidate(1))], # malformed tuple
    [candidate(1,outcome="won",event_count=0)],
    [candidate(1,outcome="lost",event_count=1)],
    [candidate(1,verified=None)],
    [candidate(1,synthetic="true")],
    [candidate(1,derived="true")],
    [candidate(1,outcome="qualified")],
    [candidate(1)[:-7]+(NOW+timedelta(days=1),)+candidate(1)[-6:]],
])
def test_invalid_or_cross_tenant_outcomes_fail_entire_batch(case):
    with pytest.raises(TenantCohortSourceHold):
        run(case)


def test_bounded_reader_never_claims_complete_snapshot():
    out,_=run([candidate(n) for n in range(1,LIMIT+2)])
    assert out["status"]=="TENANT_SOURCE_COHORT_READ_BOUND_HOLD"
    assert out["candidate_terminal_wins"] is None
    assert out["source_census_complete"] is False
    assert out["customer_forecast_eligible"] is False


def test_absent_outcomes_still_not_authenticated_sales_truth():
    out,_=run([])
    assert out["candidate_rows_observed"]==0
    assert out["original_terminal_outcomes_independently_attested"] is False
    assert out["source_census_complete"] is False


def test_missing_commercial_outcomes_policy_stops_before_row_query():
    tables, policies=fixture_data()
    policies=[x for x in policies if x[0]!="commercial_outcomes"]
    with pytest.raises(TenantCohortSourceHold):
        run([candidate(1)],mutate={"policies":policies})


def test_extra_public_select_policy_stops_before_row_query():
    tables, policies=fixture_data()
    policies.append(("commercial_outcomes","extra_all_public","SELECT",
                     ["PUBLIC"], "true"))
    with pytest.raises(TenantCohortSourceHold):
        run([candidate(1)],mutate={"policies":policies})


def test_unsafe_role_or_login_session_rejected():
    with pytest.raises(TenantCohortSourceHold):
        run([candidate(1)],mutate={"reader_role":(False,False,True,False)})


def test_cli_reports_missing_credential_without_payload(monkeypatch,capsys):
    monkeypatch.delenv(cli.DSN_ENV,raising=False)
    assert cli.main(["--read-only"])==0
    out=json.loads(capsys.readouterr().out)
    assert out["status"]=="HELD_DEDICATED_TENANT_OUTCOME_READER_CREDENTIAL_MISSING"
    assert out["customer_forecast_eligible"] is False


def test_cli_never_leaks_db_exceptions(monkeypatch,capsys):
    monkeypatch.setenv(cli.DSN_ENV,"secret-dsn")
    def fail(*,dsn):
        raise TenantCohortSourceHold("secret private raw row")
    monkeypatch.setattr(cli,"read_tenant_terminal_candidates",fail)
    assert cli.main(["--read-only"])==0
    reply=capsys.readouterr().out
    assert "secret" not in reply
    assert json.loads(reply)["database_writes"] is False
