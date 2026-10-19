"""Real PostgreSQL18 catalog probe, fixture-only and mutation-negative tests."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import json

import psycopg
import pytest

from tests.analytics.test_analytics_ledger_pg18_20261019 import db_socket, ADMIN
from empire_os.analytics.catalog_readiness import CATALOG_SQL, inspect_connection, summarize_facts
from scripts import review_analytics_live_catalog_20261019 as operator

MIGRATION055=(Path(__file__).resolve().parents[2] /
              "migrations/empiredb/055_first_party_analytics_erasure_held.sql")

def test_only_pg_catalog_metadata_not_customer_rows():
    raw=CATALOG_SQL.lower()
    for token in ("from public.", "join public.", "insert into ", "update public.",
                  "delete from ", "alter role", "create role", "grant ", "set role"):
        assert token not in raw
    assert "pg_catalog.pg_class" in raw
    assert "pg_catalog.pg_roles" in raw

def test_054_and_then_055_isolated_fixture_catalog(db_socket):
    dsn,_=db_socket
    with psycopg.connect(dsn,autocommit=True) as conn:
        d=inspect_connection(conn,expected_db="empire_analytics_fixture")
        assert d["status"]=="ANALYTICS054_PRESENT_055_NOT_DEPLOYED"
        assert d["fixture_schema_present"] is True
        assert d["fixture_erasure_present"] is False
        assert d["database_writes"] is False
        assert d["analytics054_production_deployed_verified"] is False
        assert d["analytics055_production_deployed_verified"] is False
        assert d["database_catalog_observed"] is True
    env={k:v for k,v in os.environ.items() if not k.startswith("PG")}
    sock=dsn.split("host=")[1].split(" ")[0]
    env.update(PGHOST=sock,PGPORT="56652",PGUSER=ADMIN,PGSSLMODE="disable")
    result=subprocess.run([
        "/usr/lib/postgresql/18/bin/psql","-X","-q","-v","ON_ERROR_STOP=1",
        "-d","empire_analytics_fixture","-f",str(MIGRATION055)
    ],env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr[-1000:]
    with psycopg.connect(dsn,autocommit=True) as conn:
        d=inspect_connection(conn,expected_db="empire_analytics_fixture")
        assert d["status"]=="ANALYTICS054_055_CATALOG_OBJECTS_OBSERVED_RELEASE_HELD"
        assert d["fixture_schema_present"] is True
        assert d["fixture_erasure_present"] is True
        assert d["table_count_catalog"]==4
        assert d["maintenance_role_not_activated_verified"] is True
        assert d["no_public_erasure_execute_verified"] is True
        assert d["analytics054_production_deployed_verified"] is False
        assert d["analytics055_production_deployed_verified"] is False
        # Simulate hypothetical unauthorized grant, verify it is held.
        conn.execute("CREATE ROLE empire_analytics_maintenance_login NOLOGIN NOSUPERUSER NOBYPASSRLS")
        changed=inspect_connection(conn,expected_db="empire_analytics_fixture")
        assert changed["status"]=="HELD_ANALYTICS_UNAPPROVED_RUNTIME_AUTHORITY"
        assert changed["database_catalog_observed"] is False

def test_catalog_state_rejects_partial_object_or_unforced_rls():
    base={
      "database_name_correct":True,"not_recovery_replica":True,
      "migrator_role_safe":True,"table_count":4,
      "session_table":True,"consent_table":True,"event_table":True,
      "audit_table":True,"all_present_tables_forced_rls":True,
      "all_present_table_owners_migrator":True,
      "erasure_function_present":True,
      "erasure_function_security_definer_migrator":True,
      "erasure_function_public_execute":False,
      "maintenance_login_exists":False,
      "maintenance_login_credential_active":False,
      "maintenance_execute_granted":False,
    }
    assert summarize_facts(base)["status"]=="ANALYTICS054_055_CATALOG_OBJECTS_OBSERVED_RELEASE_HELD"
    for key,wrong in (
      ("database_name_correct",False),("not_recovery_replica",False),
      ("migrator_role_safe",False),("all_present_tables_forced_rls",False),
      ("all_present_table_owners_migrator",False),
      ("erasure_function_security_definer_migrator",False),
      ("erasure_function_public_execute",True),
      ("maintenance_execute_granted",True),("maintenance_login_exists",True),
      ("maintenance_login_credential_active",True),("table_count",3),
      ("audit_table",False),
    ):
        changed={**base,key:wrong}
        assert summarize_facts(changed)["status"].startswith("HELD_"),key
    assert summarize_facts({**base,"unexpected_privilege":True})["status"].startswith("HELD_")

def test_cli_denies_non_postgres_account_even_if_connector_given():
    calls=[]
    def fake_connect(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("should not connect")
    d=operator.inspect(connector=fake_connect,peer_uid=1000,postgres_uid=123)
    assert d["status"]=="HELD_EXACT_LOCAL_POSTGRES_PEER_REQUIRED"
    assert calls==[]

def test_cli_fixed_local_socket_and_no_supplied_dsn_or_creds():
    received={}
    class Conn:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def cursor(self):
            raise OSError("expected sanitized test failure")
        def rollback(self):pass
    def connect(**kw):
        received.update(kw)
        return Conn()
    d=operator.inspect(connector=connect,peer_uid=123,postgres_uid=123)
    assert d["status"]=="HELD_ANALYTICS_LOCAL_CATALOG_QUERY_FAILED"
    assert received["host"]=="/var/run/postgresql"
    assert received["dbname"]=="empiredb"
    assert received["user"]=="postgres"
    assert received["autocommit"] is True
    assert "default_transaction_read_only=on" in received["options"]
    assert "password" not in received
    assert "dsn" not in received

def test_cli_rejects_activation_flags_and_outputs_only_redacted_status(monkeypatch,capsys):
    monkeypatch.setattr(operator,"inspect",lambda: {
        "status":"HELD_EXACT_LOCAL_POSTGRES_PEER_REQUIRED",
        "database_catalog_observed":False,
        "mode":"READ_ONLY",
        "database_writes":False,
    })
    assert operator.main(["--read-only"])==2
    d=json.loads(capsys.readouterr().out)
    assert d["database_writes"] is False
    for flags in ([],["--apply"],["--grant"],["--create-role"],
                  ["--read-only","--migrate"],["--read-only","--dump"]):
        with pytest.raises(SystemExit):
            operator.main(flags)
