"""Private Founder read-only status of six historical sends, no CRM writes."""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os import founder_mailbox_api
from empire_os import workspace_solar_historical_status as status
from empire_os.workspace_solar_historical_manifest import build_historical_manifest
from tests.test_workspace_solar_founder_review import snapshot,NOW
from scripts.import_workspace_historical_sent_receipts_20261018 import _expected


def manifest():
    return build_historical_manifest(snapshot(),now=NOW)


def rows(m):
    records=[]
    for item in m["items"]:
        r=list(_expected(item,m["source_scanned_at"]))
        r[3]=datetime.fromisoformat(r[3])
        r[4]=datetime.fromisoformat(r[4])
        records.append(tuple(r))
    return sorted(records,key=lambda r:r[0])


def test_schema_not_activated_is_truthful_not_six_db_receipts():
    report=status._status_from_rows(manifest(),table_exists=False,rows=None)
    assert report["status"]=="PRIVATE_CUSTODY_ONLY_DATABASE_SCHEMA_HELD"
    assert report["private_custody_receipts_verified"]==6
    assert report["database_historical_receipts_verified"]==0
    assert report["database_historical_receipt_table_active"] is False
    assert report["canonical_outbound_intents_created"]==0
    assert report["crm_handoff_authorized"] is False
    assert report["database_writes"] is False
    assert all(x["empiredb_historical_evidence_admitted"] is False for x in report["items"])


def test_six_valid_rows_are_historical_observations_never_intents():
    m=manifest()
    report=status._status_from_rows(m,table_exists=True,rows=rows(m))
    assert report["status"]=="SIX_HISTORICAL_RECEIPTS_VERIFIED_IN_EMPIREDB"
    assert report["database_historical_receipts_verified"]==6
    assert all(r["empiredb_historical_evidence_admitted"] for r in report["items"])
    assert all(r["historical_approval_verified"] is False for r in report["items"])
    assert all(r["crm_contact_bound"] is False for r in report["items"])
    assert all(r["commercial_revenue_verified"] is False for r in report["items"])
    assert "@" not in str(report)


def test_partial_database_admission_must_not_claim_completion():
    m=manifest()
    report=status._status_from_rows(m,table_exists=True,rows=rows(m)[:2])
    assert report["status"]=="HISTORICAL_DATABASE_IMPORT_PARTIAL_NEEDS_REVIEW"
    assert report["database_historical_receipts_verified"]==2


@pytest.mark.parametrize("mutator",[
    lambda out: out.pop(),
    lambda out: out.append(out[-1]),
    lambda out: out.__setitem__(0,(*out[0][:5],"0"*64,*out[0][6:])),
    lambda out: out.__setitem__(0,(*out[0][:8],True,*out[0][9:])),
    lambda out: out.__setitem__(0,("ffffffffffffffff",*out[0][1:])),
])
def test_partial_or_corrupt_record_never_claims_success(mutator):
    m=manifest()
    out=rows(m)
    mutator(out)
    if len(out) == 5:
        assert status._status_from_rows(m,table_exists=True,rows=out)["status"] == "HISTORICAL_DATABASE_IMPORT_PARTIAL_NEEDS_REVIEW"
    else:
        with pytest.raises(status.HistoricalReadStatusUnavailable):
            status._status_from_rows(m,table_exists=True,rows=out)


class Cursor:
    def __init__(self,exists,provider_rows):
        self.exists=exists
        self.provider_rows=provider_rows
        self.queries=[]
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,sql,params=None):self.queries.append((sql,params))
    def fetchone(self):return (self.exists,)
    def fetchall(self):return self.provider_rows

class Connection:
    def __init__(self,cursor):self.c=cursor
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def cursor(self):return self.c


@pytest.mark.parametrize("exists", [False,True])
def test_least_privilege_sql_and_no_data_mutation(monkeypatch,exists):
    m=manifest()
    monkeypatch.setattr(status,"load_private_custody",lambda:m)
    cursor=Cursor(exists,rows(m) if exists else [])
    report=status.review_six_historical_receipt_admission(
        dsn="fake-readonly-test",connect_factory=lambda *a,**kw:Connection(cursor)
    )
    assert report["database_historical_receipts_verified"] == (6 if exists else 0)
    assert cursor.queries[0][0]=="SET TRANSACTION READ ONLY"
    assert cursor.queries[1][0]=="SET LOCAL ROLE empire_closer_observer"
    assert cursor.queries[3]==(status.CATALOG_QUERY,(status.TABLE,))
    if exists:
        assert cursor.queries[4][1] == ([r["original_provider_message_id"] for r in m["items"]],)
    else:
        assert len(cursor.queries)==5
    assert cursor.queries[-1][0]=="ROLLBACK"
    assert "fake-readonly-test" not in str(report)


def test_new_private_endpoint_status_and_sanitized_503(monkeypatch):
    m=manifest()
    monkeypatch.setattr(
        founder_mailbox_api,"review_six_historical_receipt_admission",
        lambda:status._status_from_rows(m,table_exists=False,rows=None)
    )
    app=FastAPI()
    app.include_router(founder_mailbox_api.create_founder_mailbox_router(provider=object()))
    path="/v1/founder-mailbox/workspace-solar-historical-evidence-status"
    response=TestClient(app).get(path)
    assert response.status_code==200
    assert response.json()["database_historical_receipts_verified"]==0
    assert not any("@" in str(x) for x in response.json()["items"])
    def held():
        raise status.HistoricalReadStatusUnavailable("PRIVATE_RAW_DATABASE_ERROR")
    monkeypatch.setattr(founder_mailbox_api,"review_six_historical_receipt_admission",held)
    denied=TestClient(app).get(path)
    assert denied.status_code==503
    assert denied.json()["detail"]=="workspace_solar_historical_evidence_status_unavailable"
    assert "PRIVATE_RAW_DATABASE_ERROR" not in denied.text
