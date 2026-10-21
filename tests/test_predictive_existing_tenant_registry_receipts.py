"""Authenticated forecast registry policy and bounded candidate evidence."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest

from empire_os.predictive_existing_tenant_registry_receipts import (
    REGISTRY_META_SQL, REGISTRY_POLICY_SQL, ROWS_SQL, MAX_ROWS,
    METRIC, RegistrySourceHeld, _admitted_metadata,
    read_existing_tenant_registry_receipts,
)
from empire_os.predictive_tenant_outcome_reader_preflight import (
    IDENTITY_SQL, ROLE_SQL, READER_ROLE,
)

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
TENANT = "4ec7c503-b78f-4201-ad2a-2a00f7b1b6f4"
LOGIN = "source_login_readonly"
EXAMPLE_POLICY = (
    "tenant_registry_select", "SELECT", [READER_ROLE],
    "dimension_key = ('tenant:'::text || public.empire_current_tenant_id()::text)"
)
META = (True, True, True, False, False)


def record(number=1, *, tenant=TENANT, at=NOW, value=Decimal("123")):
    return (
        f"00000000-0000-4000-8000-{number:012d}",
        f"original_registry_ref_{number}",
        "tenant:" + tenant, METRIC, value, at - timedelta(minutes=5),
    )


class Cursor:
    def __init__(self, state):
        self.state=state
        self.calls=[]
        self.last=None
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def execute(self, sql, params=None):
        self.calls.append((sql,params))
        self.last=(sql,params)
    def fetchone(self):
        sql,params=self.last
        if sql==IDENTITY_SQL:
            return self.state.get("identity",("empiredb","on",LOGIN,READER_ROLE,TENANT))
        if sql==ROLE_SQL:
            if params==(LOGIN,):
                return self.state.get("login_role",(True,False,False,False,False,False,False))
            if params==(READER_ROLE,):
                return self.state.get("reader_role",(False,False,False,False,False,False,False))
        if sql==REGISTRY_META_SQL:
            return self.state.get("meta",META)
        raise AssertionError("unexpected metadata source")
    def fetchall(self):
        sql,params=self.last
        if sql==REGISTRY_POLICY_SQL:
            return self.state.get("policies",[EXAMPLE_POLICY])
        if sql==ROWS_SQL:
            assert params==(METRIC,MAX_ROWS+1)
            return self.state.get("rows",[])
        raise AssertionError("unexpected row source")


class Connection:
    def __init__(self,state): self.cur=Cursor(state)
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def cursor(self): return self.cur


def run(**overrides):
    state={"rows":[record()]}
    state.update(overrides)
    connections=[]
    def connect(credential,*,connect_timeout):
        assert credential=="fixture-not-a-secret"
        assert connect_timeout==5
        conn=Connection(state)
        connections.append(conn)
        return conn
    result=read_existing_tenant_registry_receipts(
        dsn="fixture-not-a-secret",now=NOW,connect_factory=connect,
    )
    return result,connections[0].cur.calls


def test_scoped_registry_rows_are_never_immutable_or_training_proof():
    report,calls=run()
    assert report["status"]=="AUTHENTICATED_TENANT_REGISTRY_CANDIDATES_ORIGIN_UNVERIFIED"
    assert report["registry_candidate_count"]==1
    assert report["existing_tenant_reader_session_authenticated"] is True
    assert report["existing_reader_registry_source_admitted"] is True
    assert report["registry_read_complete"] is False
    assert report["original_forecast_immutable_registration_verified"] is False
    assert report["forecast_registered_before_outcome_verified"] is False
    assert report["independent_revenue_settlement_verified"] is False
    assert report["customer_forecast_eligible"] is False
    assert report["customer_training_labels_admitted"] is False
    assert report["database_writes"] is False
    assert report["execution_authority"]=="none"
    commands=[a for a,_ in calls]
    assert commands[0]=="SET TRANSACTION READ ONLY"
    assert commands.index(ROLE_SQL)<commands.index(REGISTRY_META_SQL)
    assert commands.index(REGISTRY_META_SQL)<commands.index(REGISTRY_POLICY_SQL)
    assert commands.index(REGISTRY_POLICY_SQL)<commands.index(ROWS_SQL)
    assert all(command.startswith(("SET ","SELECT")) for command in commands)
    serialized=json.dumps(report)
    assert TENANT not in serialized
    assert LOGIN not in serialized
    assert "123" not in serialized
    assert "original_registry_ref_1" not in serialized


@pytest.mark.parametrize("override",[
    {"meta":None},
    {"meta":(False,True,True,False,False)},
    {"meta":(True,False,True,False,False)},
    {"meta":(True,True,False,False,False)},
    {"meta":(True,True,True,True,False)},
    {"meta":(True,True,True,False,True)},
    {"policies":[]},
    {"policies":[EXAMPLE_POLICY,EXAMPLE_POLICY]},
    {"policies":[("public_read","SELECT",["PUBLIC"],"true")]},
    {"policies":[("bad","SELECT",[READER_ROLE],"true")]},
    {"policies":[("widened","SELECT",[READER_ROLE],
                  "dimension_key LIKE 'tenant:%' OR public.empire_current_tenant_id() IS NOT NULL")]},
])
def test_missing_registry_access_or_unsafe_rls_never_selects_rows(override):
    report,calls=run(**override)
    assert report["status"]=="EXISTING_READER_REGISTRY_NOT_ADMITTED"
    assert report["registry_candidate_count"] is None
    assert report["existing_reader_registry_source_admitted"] is False
    assert ROWS_SQL not in [sql for sql,_ in calls]


@pytest.mark.parametrize("rows",[
    [record(1,tenant="00000000-0000-4000-8000-000000000099")],
    [record(1),record(1)],
    [record(1,value=Decimal("-0.01"))],
    [record(1,value=Decimal("4.5"))],
    [record(1,value=True)],
    [record(1,at=NOW+timedelta(days=3))],
    [record(1)[:-1]],
    [(record(1)[0],"",*record(1)[2:])],
])
def test_malformed_or_tampered_row_held_without_export(rows):
    with pytest.raises(RegistrySourceHeld) as err:
        run(rows=rows)
    assert TENANT not in str(err.value)


def test_bounded_result_never_claims_lifetime_census():
    report,calls=run(rows=[record(i) for i in range(1,MAX_ROWS+2)])
    assert report["status"]=="TENANT_REGISTRY_READ_BOUND_HOLD"
    assert report["registry_candidate_count"]==MAX_ROWS
    assert report["registry_read_complete"] is False
    assert report["customer_forecast_eligible"] is False


def test_empty_tenant_registry_proves_only_empty_scoped_window():
    report,_=run(rows=[])
    assert report["status"]=="AUTHENTICATED_TENANT_REGISTRY_EMPTY"
    assert report["registry_candidate_count"]==0
    assert report["original_forecast_immutable_registration_verified"] is False


@pytest.mark.parametrize("override",[
    {"identity":("empiredb","on",LOGIN,READER_ROLE,"not-a-tenant")},
    {"identity":("empiredb","off",LOGIN,READER_ROLE,TENANT)},
    {"login_role":(True,True,False,False,False,False,False)},
    {"reader_role":(False,False,False,False,True,False,False)},
])
def test_untrusted_session_rejected_before_scoped_select(override):
    with pytest.raises(RegistrySourceHeld):
        run(**override)


def test_missing_credential_cannot_fallback_to_superuser():
    with pytest.raises(RegistrySourceHeld):
        read_existing_tenant_registry_receipts(dsn="",now=NOW)
