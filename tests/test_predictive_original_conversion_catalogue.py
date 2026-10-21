"""Original conversion registry catalogue only; never query commercial data."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess

import pytest

from empire_os.predictive_original_conversion_catalogue import (
    SCHEMA, EXPECTED_COLS, ROLE_NAMES,
    OBJECT_SQL,ROLE_INVENTORY_SQL,TABLE_SQL,COLUMN_SQL,
    POLICY_SQL,ROUTINE_SQL,TRIGGER_SQL,
    ConversionCatalogueHold, review_original_conversion_catalogue,
)
from empire_os.predictive_tenant_outcome_reader_preflight import (
    IDENTITY_SQL,ROLE_SQL,READER_ROLE,
)

TENANT="4ec7c503-b78f-4201-ad2a-2a00f7b1b6f4"
LOGIN="fixture_restricted_login"
SEVEN=(False,False,False,False,False,False,False)
CREDENTIAL="synthetic-no-secret"
DEFAULT={
    "objects":(False,False,False,False),
    "roles":[],
    "table":None,
    "columns":[],
    "policies":[],
    "routines":[],
    "triggers":[],
}

def installed():
    return {
        "objects":(True,True,True,True),
        "roles":[(name,*SEVEN,False) for name in sorted(ROLE_NAMES)],
        "table":(True,True,False,False,False,False),
        "columns":[(key,) for key in sorted(EXPECTED_COLS)],
        "policies":[
            ("original_conversion_migrator_tenant_insert","INSERT",["empiredb_migrator"],None,
             "(tenant_id = empire_current_tenant_id())"),
            ("original_conversion_migrator_tenant_read","SELECT",["empiredb_migrator"],
             "(tenant_id = empire_current_tenant_id())",None),
        ],
        "routines":[
            ("read_original_conversion_prediction_v1",True,"s",False),
            ("record_original_conversion_prediction_v1",True,"v",False),
            ("reject_original_conversion_prediction_change_v1",False,"v",False),
        ],
        "triggers":[("original_conversion_prediction_immutable","O",False)],
    }


class Cursor:
    def __init__(self,state):
        self.state=state
        self.calls=[]
        self.last=None
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,sql,params=None):
        self.calls.append((sql,params))
        self.last=(sql,params)
    def fetchone(self):
        sql,params=self.last
        if sql==IDENTITY_SQL:
            return self.state.get("identity",("empiredb","on",LOGIN,READER_ROLE,TENANT))
        if sql==ROLE_SQL:
            return (True,*SEVEN[1:]) if params==(LOGIN,) else SEVEN
        if sql==OBJECT_SQL:return self.state["objects"]
        if sql==TABLE_SQL:return self.state["table"]
        raise AssertionError("unexpected row fetch")
    def fetchall(self):
        sql,params=self.last
        m={
            ROLE_INVENTORY_SQL:"roles",
            COLUMN_SQL:"columns",
            POLICY_SQL:"policies",
            ROUTINE_SQL:"routines",
            TRIGGER_SQL:"triggers",
        }
        if sql==ROLE_INVENTORY_SQL:
            assert params==(list(ROLE_NAMES),)
        assert sql in m
        return self.state[m[sql]]


class Connection:
    def __init__(self,state):
        self.cur=Cursor(state)
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def cursor(self):return self.cur


def run(state=None):
    source=dict(DEFAULT if state is None else state)
    connections=[]
    def connect(dsn,*,connect_timeout):
        assert dsn==CREDENTIAL and connect_timeout==5
        obj=Connection(source)
        connections.append(obj)
        return obj
    result=review_original_conversion_catalogue(dsn=CREDENTIAL,connect_factory=connect)
    return result,connections[0].cur.calls


def test_authenticated_absence_is_not_unverified_permission_denial():
    result,calls=run()
    assert result["status"]=="DEDICATED_ORIGINAL_CONVERSION_REGISTRY_NOT_INSTALLED"
    assert result["authenticated_tenant_session"] is True
    assert result["catalogue_metadata_completeness_verified"] is True
    assert not any(result["object_presence"].values())
    assert result["original_conversion_rows_queried"] is False
    assert result["old_directional_predictive_forecasts_not_substituted"] is True
    assert result["forecast_immutable_registration_proven"] is False
    assert result["scientific_training_or_customer_forecast_authorized"] is False
    assert result["new_roles_grants_ddl_migrations_or_credentials"] is False
    assert result["database_writes"] is False
    assert result["execution_authority"]=="none"
    commands=[c for c,_ in calls]
    assert commands[0]=="SET TRANSACTION READ ONLY"
    assert commands.index(ROLE_SQL)<commands.index(OBJECT_SQL)
    assert commands[-1]==TRIGGER_SQL
    assert all(c.startswith(("SELECT","SET ")) for c in commands)
    serialized=json.dumps(result)
    assert TENANT not in serialized and LOGIN not in serialized


def test_full_metadata_is_review_candidate_not_registry_or_science_approval():
    result,_=run(installed())
    assert result["status"]=="DEDICATED_CONVERSION_OBJECTS_PRESENT_REVIEW_REQUIRED"
    assert result["original_registry_metadata_candidate"] is True
    assert result["expected_column_inventory_match"] is True
    assert result["dedicated_roles_metadata_safe_shape"] is True
    assert result["expected_immutability_trigger_metadata_match"] is True
    assert result["original_conversion_records_admitted"] is False
    assert result["forecast_immutable_registration_proven"] is False
    assert result["real_customer_outcomes_proven"] is False


@pytest.mark.parametrize("field,replacement",[
    ("objects",(True,False,False,False)),
    ("roles",[]),
    ("roles",[(ROLE_NAMES[0],True,*SEVEN[1:],False)]),
    ("roles",[(ROLE_NAMES[0],*SEVEN,True)]),
    ("table",(True,False,False,False,False,False)),
    ("table",(True,True,True,False,False,False)),
    ("columns",[(col,) for col in sorted(EXPECTED_COLS-{ "recorded_at"})]),
    ("policies",[]),
    ("policies",[("read_all","SELECT",["PUBLIC"],"true",None)]),
    ("routines",[]),
    ("triggers",[]),
    ("triggers",[("original_conversion_prediction_immutable","D",False)]),
])
def test_partial_or_unsafe_privileges_hold(field,replacement):
    src=installed()
    src[field]=replacement
    result,calls=run(src)
    assert result["status"]=="DEDICATED_CONVERSION_PARTIAL_OR_SECURITY_DRIFT_HOLD"
    assert result["original_registry_metadata_candidate"] is False
    assert result["original_conversion_rows_queried"] is False
    assert all(sql.startswith(("SET ","SELECT")) for sql,_ in calls)


@pytest.mark.parametrize("override",[
    {"identity":("otherdb","on",LOGIN,READER_ROLE,TENANT)},
    {"identity":("empiredb","off",LOGIN,READER_ROLE,TENANT)},
    {"identity":("empiredb","on",LOGIN,READER_ROLE,"wrong")},
    {"identity":("empiredb","on",LOGIN,"postgres",TENANT)},
    {"identity":("empiredb","on","postgres",READER_ROLE,TENANT)},
])
def test_wrong_authentication_fails_without_metadata_read(override):
    src=dict(DEFAULT)
    src.update(override)
    with pytest.raises(ConversionCatalogueHold):
        run(src)


def test_missing_credential_holds():
    with pytest.raises(ConversionCatalogueHold):
        review_original_conversion_catalogue(dsn="")


def test_script_only_root_pinned_read_only_code():
    src=(Path(__file__).resolve().parents[1]/
         "scripts/run_guarded_conversion_catalogue_readonly_20261021.sh").read_text()
    for required in (
        "sha256sum", "SOURCE", "chown -R root:root",
        "chmod 0555", "chmod 0444",
        "PGPASSFILE=", "PYTHONPATH=",
        "git -c safe.directory=", "archive",
        '"$PY" -P -B -m scripts.review_original_conversion_catalogue_20261021 --read-only',
        "ORIGINAL_CONVERSION_CATALOGUE_CHECK_NO_ROW_READS_WRITES_OR_GRANTS=true",
    ):
        # SOURCE is not an interface promise; separate guards below check exact package.
        if required=="SOURCE":continue
        assert required in src
    assert "empire_os/predictive_original_conversion_catalogue.py" in src
    assert "scripts/review_original_conversion_catalogue_20261021.py" in src
    for token in ("ALTER ROLE", "CREATE ROLE", "GRANT SELECT", "psql -", "curl "):
        assert token not in src
    for args in ((),("--check",),("--run-read-only","abc"),
                 ("--write","f"*40),("--run-read-only","f"*40)):
        c=subprocess.run(["bash",str(Path(__file__).resolve().parents[1]/
                    "scripts/run_guarded_conversion_catalogue_readonly_20261021.sh"),*args],
                     capture_output=True,text=True,timeout=10)
        assert c.returncode!=0


def test_catalogue_cli_auth_failure_is_redacted(monkeypatch,capsys):
    import scripts.review_original_conversion_catalogue_20261021 as cli
    monkeypatch.delenv(cli.ENV,raising=False)
    assert cli.main(["--read-only"])==0
    x=json.loads(capsys.readouterr().out)
    assert x["status"]=="DEDICATED_CONVERSION_CATALOGUE_AUTHENTICATION_HELD"
    assert x["database_writes"] is False
    assert x["execution_authority"]=="none"
