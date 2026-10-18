"""DBA-gated historical six sent receipts only; no live SQL in tests."""
from datetime import datetime
from pathlib import Path
from copy import deepcopy

import pytest

from empire_os.workspace_solar_historical_manifest import build_historical_manifest
from scripts import import_workspace_historical_sent_receipts_20261018 as importer
from tests.test_workspace_solar_founder_review import NOW,snapshot


def manifest(monkeypatch):
    data=build_historical_manifest(snapshot(),now=NOW)
    monkeypatch.setattr(importer,"read_source_build_manifest",lambda: data)
    return data


class Cursor:
    def __init__(self,owner):
        self.owner=owner
        self.result=[]
        self.calls=[]
    def __enter__(self): return self
    def __exit__(self,*args):return False
    def execute(self,query,params=None):
        self.calls.append((query,params))
        if query.startswith("SELECT current_database"):
            self.result=[("empiredb","postgres",True)]
        elif query.startswith("SELECT c.relrowsecurity"):
            self.result=[(True,True)]
        elif query.startswith("SELECT count(*) FROM pg_catalog.pg_trigger"):
            self.result=[(1,)]
        elif query==importer.SELECT_SQL:
            self.result=sorted(self.owner.saved.values(),key=lambda r:r[0])
        elif query==importer.INSERT_SQL:
            mid,tid,recipient,sent,scanned,digest,kind=params
            if mid in self.owner.saved or tid in {r[1] for r in self.owner.saved.values()}:
                raise ValueError("duplicate")
            self.owner.saved[mid]=(
                mid,tid,recipient,
                datetime.fromisoformat(sent),datetime.fromisoformat(scanned),
                digest,kind,importer.EXPECTED_LINKAGE,False,False,False
            )
            self.result=[]
        else:
            self.result=[]
    def fetchone(self):
        return self.result[0]
    def fetchall(self):
        return list(self.result)


class Connection:
    def __init__(self):
        self.saved={}
        self.cursor_obj=Cursor(self)
        self.commit_count=0
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def cursor(self):return self.cursor_obj
    def commit(self):self.commit_count+=1


def test_six_receipts_insert_exactly_once_then_idempotent_replay(monkeypatch):
    data=manifest(monkeypatch)
    conn=Connection()
    factory=lambda *a,**kw:conn
    first=importer.import_exact_six_receipts(data,connect_factory=factory)
    assert first["verified_receipts"]==6
    assert first["new_receipts"]==6
    assert first["historical_approvals_backfilled"]==0
    assert first["canonical_outbound_intents_created"]==0
    assert first["emails_sent"] is False
    assert first["crm_handoff_authorized"] is False
    assert len(conn.saved)==6
    assert conn.commit_count==1
    assert sum(sql==importer.INSERT_SQL for sql,_ in conn.cursor_obj.calls)==6
    second=importer.import_exact_six_receipts(data,connect_factory=factory)
    assert second["new_receipts"]==0
    assert second["replayed_identical_receipts"]==6
    assert sum(sql==importer.INSERT_SQL for sql,_ in conn.cursor_obj.calls)==6
    assert conn.commit_count==2


@pytest.mark.parametrize("field,value",[
    ("recipient_sha256","0"*64),
    ("sent_at","2026-10-01T10:00:00+00:00"),
    ("source_kind","INVENTED_EXTERNAL_SEND"),
    ("historical_approval_attested",True),
    ("crm_contact_bound",True),
])
def test_privileged_import_rejects_tampered_field_even_with_original_digest(
    monkeypatch,field,value
):
    data=deepcopy(manifest(monkeypatch))
    data["items"][0][field]=value
    conn=Connection()
    with pytest.raises(importer.HistoricalImportHeld,match="LIVE_WORKSPACE_SOURCE_DRIFT"):
        importer.import_exact_six_receipts(
            data,connect_factory=lambda *a,**kw:conn
        )
    assert conn.commit_count==0


def test_conflicting_previous_receipt_is_rejected_no_new_inserts(monkeypatch):
    data=manifest(monkeypatch)
    conn=Connection()
    one=data["items"][0]
    scan=data["source_scanned_at"]
    row=list(importer._expected(one,scan))
    row[5]="0"*64
    conn.saved[one["original_provider_message_id"]]=(
        *row[:3],datetime.fromisoformat(row[3]),datetime.fromisoformat(row[4]),*row[5:]
    )
    with pytest.raises(importer.HistoricalImportHeld,match="EXISTING_HISTORICAL_EVIDENCE_CONFLICT"):
        importer.import_exact_six_receipts(data,connect_factory=lambda *a,**kw:conn)
    assert conn.commit_count==0
    assert sum(q==importer.INSERT_SQL for q,_ in conn.cursor_obj.calls)==0


@pytest.mark.parametrize("unexpected",[
    lambda current: current.update(evidence_count=5),
    lambda current: current.update(database_writes=True),
    lambda current: current["items"].pop(),
])
def test_incomplete_or_write_claiming_manifest_is_never_imported(monkeypatch,unexpected):
    data=manifest(monkeypatch)
    bad=deepcopy(data)
    unexpected(bad)
    conn=Connection()
    with pytest.raises(importer.HistoricalImportHeld):
        importer.import_exact_six_receipts(bad,connect_factory=lambda *a,**kw:conn)
    assert conn.commit_count==0


def test_staged_ddl_is_append_only_scope_not_outbound_lifecycle():
    path=Path("/srv/empire_os/migrations/empiredb/052_workspace_historical_send_receipts_observe_only.sql")
    sql=path.read_text()
    assert "STAGED ONLY" in sql
    assert "workspace_historical_sent_receipts" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "workspace_historical_receipts_append_only" in sql
    assert "BEFORE UPDATE OR DELETE" in sql
    assert "GRANT SELECT ON TABLE public.workspace_historical_sent_receipts" in sql
    assert "CHECK (historical_approval_attested IS FALSE)" in sql
    assert "CHECK (crm_contact_bound IS FALSE)" in sql
    assert "UNBOUND_EXTERNAL_SENT_OBSERVED" in sql
    assert "COMMIT;" in sql
    assert "CREATE ROLE" not in sql.upper()
    assert "INSERT INTO public.outbound_intents" not in sql
    assert "ALTER TABLE public.outbound_intents" not in sql


def test_dba_import_script_never_auto_activates_schema():
    text=Path(importer.__file__).read_text()
    assert "ROOT_OPERATOR" not in text
    assert "ROOT_PRIVATE_CUSTODY_OPERATOR_REQUIRED" in text
    assert "os.setgroups([])" in text
    assert "os.setgid(account.pw_gid)" in text
    assert "os.setuid(account.pw_uid)" in text
    assert "_connect_as_postgres_after_private_custody_validation" in text
    assert "--apply-founder-approved-historical-receipts-only" in text
    assert "psycopg.connect" in text
    assert "DROP TABLE" not in text
    assert "CREATE TABLE" not in text
    assert "UPDATE public.outbound_intents" not in text
