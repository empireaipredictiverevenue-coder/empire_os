"""Bounded one-login grant, rollback and authenticated source admission."""
import json
from pathlib import Path

import pytest

import scripts.activate_predictive_native_reader_existing_login_20261116 as a


def valid_catalogue(**updates):
    data={key:True for key in a.ADMISSION}
    data.update({
        "existing_membership":False,
        "unexpected_membership":False,
        "existing_registry_role_members":0,
    })
    data.update(updates)
    return data


def success_source():
    return {
      "schema_version":"empire.predictive_revenue.authenticated_source_preflight.v1",
      "mode":"OBSERVE",
      "original_restricted_registry_reader_reused":True,
      "original_restricted_day_census_reader_reused":True,
      "registry_reader_authenticated_session":True,
      "census_reader_authenticated_session":True,
      "reader_tenant_scope_input_valid":True,
      "source_credentials_exposed":False,
      "independently_verified_forecast_actual_pairs":0,
      "model_calibration_ready":False,
      "customer_release_authorized":False,
      "database_writes":False,
      "registry_source_status":"REGISTRY_EMPTY_COVERAGE_UNKNOWN_HOLD",
      "registry_scoped_rows_observed":0,
      "census_source_status":"DAY_CENSUS_INCOMPLETE_HOLD",
      "census_tenant_events_observed":0,
    }


def test_original_role_scope_and_only_grant():
    assert a.LOGIN == "empire_predictive_revenue_evidence_login"
    assert a.ROLE == "empire_predictive_revenue_evidence_reader"
    assert a.REGISTRY_ROLE == "empire_predictive_registry_reader"
    assert "GRANT empire_predictive_registry_reader TO empire_predictive_revenue_evidence_login" in a.GRANT_SQL
    assert "WITH INHERIT FALSE, SET TRUE, ADMIN FALSE" in a.GRANT_SQL
    assert "CREATE ROLE" not in a.GRANT_SQL
    assert "INSERT INTO" not in a.GRANT_SQL
    assert a.GRANT_SQL.startswith("BEGIN;")
    assert a.GRANT_SQL.rstrip().endswith("COMMIT;")
    assert "FORCE" not in a.GRANT_SQL
    assert a.CATALOG.startswith("BEGIN READ ONLY;")
    assert a.CATALOG.rstrip().endswith("ROLLBACK;")


def test_bad_original_role_or_tenant_fails_before_grant():
    for change in (
       {"registry_force_rls":False},
       {"original_active_tenant_only":False},
       {"no_business_registrar_membership":False},
       {"login_safe":False},
       {"existing_registry_role_members":1},
       {"unexpected_membership":True},
    ):
        with pytest.raises(a.ActivationHold):
            a.read_catalog(read_sql=lambda _:json.dumps(valid_catalogue(**change)))


def test_single_grant_and_original_auth_success():
    calls=[]
    state=valid_catalogue()
    def pg(query):
        calls.append(query)
        if query==a.GRANT_SQL:
            state["existing_registry_role_members"]=1
            state["existing_membership"]=True
            return ""
        assert query==a.CATALOG
        return json.dumps(state)
    written=[]
    report=a.apply(read_sql=pg,verify=lambda p:success_source(),
                   save=lambda target,payload:written.append((target,payload)),
                   passfile_provider=lambda:Path("/root/approved-reader.pgpass"))
    assert report["status"]=="NATIVE_FORECAST_READER_TENANT_AUTHENTICATED"
    assert report["original_registry_role_grant_applied"] is True
    assert report["registry_scoped_rows_observed"] == 0
    assert calls==[a.CATALOG,a.GRANT_SQL,a.CATALOG]
    assert written[0][0] == a.OUTPUT
    assert len(written)==1


def test_failed_original_authenticated_read_revokes_only_own_grant():
    state=valid_catalogue()
    calls=[]
    def pg(q):
        calls.append(q)
        if q==a.GRANT_SQL:
            state.update(existing_membership=True,existing_registry_role_members=1)
            return ""
        if q==a.REVOKE_SQL:
            state.update(existing_membership=False,existing_registry_role_members=0)
            return ""
        assert q==a.CATALOG
        return json.dumps(state)
    with pytest.raises(a.ActivationHold):
        a.apply(read_sql=pg,
                verify=lambda path: (_ for _ in ()).throw(
                    a.ActivationHold("AUTHENTICATED_READ_FAILED")),
                save=lambda *args:pytest.fail("never save failure"),
                passfile_provider=lambda:Path("/root/approved-reader.pgpass"))
    assert calls==[a.CATALOG,a.GRANT_SQL,a.CATALOG,a.REVOKE_SQL]
    assert not state["existing_membership"]


def test_preexisting_authorised_grant_is_not_reissued_or_revoked():
    state=valid_catalogue(existing_membership=True,existing_registry_role_members=1)
    calls=[]
    def pg(query):
        calls.append(query)
        assert query==a.CATALOG
        return json.dumps(state)
    result=a.apply(read_sql=pg,verify=lambda path:success_source(),
                   save=lambda *args:None,
                   passfile_provider=lambda:Path("/root/approved-reader.pgpass"))
    assert result["original_registry_role_grant_applied"] is False
    assert calls==[a.CATALOG,a.CATALOG]


def test_readback_no_negative_auth_is_ever_called_success():
    for change in (
        {"registry_reader_authenticated_session":False},
        {"census_reader_authenticated_session":False},
        {"reader_tenant_scope_input_valid":False},
        {"independently_verified_forecast_actual_pairs":1},
    ):
        wrong=success_source(); wrong.update(change)
        # Structural enforcement is in apply(), not just JSON status naming.
        state=valid_catalogue()
        def pg(q):
            if q==a.CATALOG:return json.dumps(state)
            if q==a.GRANT_SQL:
                state.update(existing_registry_role_members=1,existing_membership=True)
                return ""
            if q==a.REVOKE_SQL:
                state.update(existing_registry_role_members=0,existing_membership=False)
                return ""
            pytest.fail("unexpected SQL")
        with pytest.raises(a.ActivationHold):
            a.apply(read_sql=pg,verify=lambda path:wrong,
                    save=lambda *_:pytest.fail("invalid proof saved"),
                    passfile_provider=lambda:Path("/root/approved-reader.pgpass"))
        assert not state["existing_membership"]


def test_nonroot_cannot_execute_grant(monkeypatch, capsys):
    monkeypatch.setattr(a.os,"geteuid",lambda:1000)
    assert a.main(["--apply-founder-approved"])==2
    assert "EXPLICIT_FOUNDER_ROOT_OPERATOR_REQUIRED" in capsys.readouterr().out
