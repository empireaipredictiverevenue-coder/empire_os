"""V15 construction custody: synthetic official-record shapes, no live DB writes."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest

from empire_os.data_exchange_observation_custody import (
    CustodyIntegrityError, GENESIS, SCHEMA, plan_custody_append,
    validate_custody_row, verify_custody_window,
)
from empire_os.data_exchange_custody_transport import (
    EmpireDBConstructionCustody, CustodyTransportError, COLUMN_NAMES,
)
from test_data_exchange_agi_bridge import source, NOW


def first():
    return source(changed=True)[0]


def second():
    return source(changed=True)[1]


def custody_rows():
    start=plan_custody_append(first(),previous=None,assessed_at=NOW)["row"]
    end=plan_custody_append(second(),previous=start,assessed_at=NOW)["row"]
    return start,end


def test_genesis_chain_and_existing_history_digest_match():
    a,b=custody_rows()
    from empire_os.data_exchange_history import build_construction_history
    history=build_construction_history([first(),second()],assessed_at=NOW)
    assert a["sequence"]==0
    assert a["previous_chain_sha256"]==GENESIS
    assert b["sequence"]==1
    assert b["previous_chain_sha256"]==a["chain_sha256"]
    assert b["chain_sha256"]==history["latest_chain_sha256"]
    assert b["snapshot_sha256"]!=a["snapshot_sha256"]
    assert validate_custody_row(b)==b
    check=verify_custody_window([a,b])
    assert check["row_count"]==2
    assert check["head_chain_sha256"]==b["chain_sha256"]
    assert check["window_origin_anchored_to_genesis"] is True
    assert check["external_anchor_verified"] is False
    assert check["customer_delivery_enabled"] is False


def test_exact_repeat_is_no_write_same_history_head():
    a,_=custody_rows()
    result=plan_custody_append(first(),previous=a,assessed_at=NOW)
    assert result["mode"]=="DUPLICATE_EXACT_SNAPSHOT_NO_WRITE"
    assert result["written"] is False
    assert result["chain_sha256"]==a["chain_sha256"]
    assert "row" not in result


def test_same_observation_date_with_conflicting_content_fails_closed():
    a,_=custody_rows()
    modified=deepcopy(first())
    modified["records"][0]["planning_permission_status"]="permissioned"
    with pytest.raises(CustodyIntegrityError,match="non-monotonic"):
        plan_custody_append(modified,previous=a,assessed_at=NOW)


@pytest.mark.parametrize("modification",[
    lambda s:s.update({"contact_email":"contact@example.org"}),
    lambda s:s["records"][0].update({"owner":"PRIVATE PERSON"}),
    lambda s:s.update({"rights_review_eligible":True}),
    lambda s:s.update({"rights_holds":[]}),
    lambda s:s.update({"customer_delivery_enabled":True}),
    lambda s:s.update({"rejected_counts":{"REJECTED":1}}),
    lambda s:s.update({"execution_authority":"EXECUTE"}),
    lambda s:s["records"][0].update({"source_url":"https://other.invalid/entity/1739547"}),
    lambda s:s["records"][0].update({"source_observed_at":"2099-01-01T00:00:00+00:00"}),
])
def test_unapproved_data_or_authority_never_enters_custody(modification):
    snap=first()
    modification(snap)
    with pytest.raises(CustodyIntegrityError):
        plan_custody_append(snap,previous=None,assessed_at=NOW)


@pytest.mark.parametrize("field,value",[
    ("chain_sha256","f"*64),
    ("snapshot_sha256","0"*64),
    ("previous_chain_sha256","1"*64),
    ("source_id","nonofficial"),
    ("dataset_id","contacts"),
    ("sequence",False),
    ("source_observed_at","2026-10-14"),
])
def test_any_mutation_of_stored_provenance_invalidates_row(field,value):
    a,_=custody_rows()
    changed=deepcopy(a);changed[field]=value
    with pytest.raises(CustodyIntegrityError):
        validate_custody_row(changed)


def test_missing_middle_sequence_or_link_is_not_trusted():
    a,b=custody_rows()
    c=deepcopy(b)
    c["sequence"]=3
    with pytest.raises(CustodyIntegrityError):
        verify_custody_window([a,c])
    wrong=deepcopy(b); wrong["previous_chain_sha256"]="a"*64
    with pytest.raises(CustodyIntegrityError):
        verify_custody_window([a,wrong])


def test_only_later_observations_can_extend_chain():
    a,b=custody_rows()
    with pytest.raises(CustodyIntegrityError,match="non-monotonic"):
        plan_custody_append(first(),previous=b,assessed_at=NOW)
    with pytest.raises(CustodyIntegrityError,match="stale"):
        plan_custody_append(first(),previous=None,assessed_at=NOW+timedelta(days=100))


class Cursor:
    def __init__(self, *, head=None, all_rows=None, fail=False):
        self.head=head
        self.all_rows=all_rows
        self.fail=fail
        self.writes=0
        self.queries=[]
        self.last=""
        self.params=None
        self.last_receipt=None
    def __enter__(self):return self
    def __exit__(self,*exc):return False
    def execute(self,sql,params=None):
        self.queries.append((sql,params))
        self.last=sql
        self.params=params
        if self.fail and sql.startswith("INSERT"):
            raise RuntimeError("private transaction credential")
        if sql.startswith("INSERT"):
            self.writes+=1
            self.last_receipt=params[0],params[8]
    def fetchone(self):
        if "ORDER BY sequence DESC LIMIT 1" in self.last:
            return self.head
        if "RETURNING sequence,chain_sha256" in self.last:
            return self.last_receipt
        return None
    def fetchall(self):
        return self.all_rows or []


class Connection:
    def __init__(self,cursor):
        self.c=cursor
    def __enter__(self):return self
    def __exit__(self,*exc):return False
    def cursor(self):return self.c


def db_row(row):
    return tuple(row[k] for k in COLUMN_NAMES)


def test_writer_serializes_and_inserts_once_under_role():
    cur=Cursor()
    transport=EmpireDBConstructionCustody(
        "opaque-test-dsn",connector=lambda *a,**k:Connection(cur))
    receipt=transport.append_once(first(),now=NOW)
    assert receipt["mode"]=="CANONICAL_APPEND_COMMITTED"
    assert receipt["database_writes"] is True
    assert cur.writes==1
    assert any("pg_advisory_xact_lock" in sql for sql,_ in cur.queries)
    assert any("SET LOCAL ROLE empire_data_exchange_custodian" in sql for sql,_ in cur.queries)
    assert not any("UPDATE " in sql or "DELETE " in sql for sql,_ in cur.queries)


def test_writer_exact_repeat_never_inserts_or_changes_chain_head():
    a,_=custody_rows()
    cur=Cursor(head=db_row(a))
    writer=EmpireDBConstructionCustody("test",connector=lambda *a,**k:Connection(cur))
    result=writer.append_once(first(),now=NOW)
    assert result["mode"]=="ALREADY_OBSERVED"
    assert result["database_writes"] is False
    assert result["head_chain_sha256"]==a["chain_sha256"]
    assert cur.writes==0


def test_transport_connection_failure_is_uncertain_not_success_or_retry():
    cur=Cursor(fail=True)
    writer=EmpireDBConstructionCustody("test",connector=lambda *a,**k:Connection(cur))
    with pytest.raises(CustodyTransportError,match="UNCERTAIN"):
        writer.append_once(first(),now=NOW)
    assert cur.writes==0


def test_reader_revalidates_stored_chain_and_uses_read_only_mode():
    a,b=custody_rows()
    cur=Cursor(all_rows=[db_row(b),db_row(a)])
    store=EmpireDBConstructionCustody("test",connector=lambda *a,**k:Connection(cur))
    report=store.read_signal_board(now=NOW)
    assert report["total_validated_changes"]==1
    assert report["canonical_custody"]["last_sequence"]==1
    assert report["canonical_custody"]["external_anchor_verified"] is False
    assert report["customer_delivery_enabled"] is False
    assert any(sql=="SET TRANSACTION READ ONLY" for sql,_ in cur.queries)
    assert cur.writes==0


def test_reader_refuses_single_observation_as_change():
    a,_=custody_rows()
    cur=Cursor(all_rows=[db_row(a)])
    store=EmpireDBConstructionCustody("test",connector=lambda *a,**k:Connection(cur))
    result=store.read_signal_board(now=NOW)
    assert result["feed_status"]=="HOLD_NEED_TWO_CANONICAL_OBSERVATIONS"
    assert result["customer_delivery_enabled"] is False


def test_reader_corrupt_db_row_fails_closed():
    a,b=custody_rows()
    b["snapshot_json"]["records"][0]["email"]="PRIVATE@example.org"
    cur=Cursor(all_rows=[db_row(b),db_row(a)])
    store=EmpireDBConstructionCustody("test",connector=lambda *a,**k:Connection(cur))
    with pytest.raises(CustodyIntegrityError):
        store.read_signal_board(now=NOW)


def test_dedicated_dsn_is_required():
    with pytest.raises(CustodyTransportError,match="dedicated"):
        EmpireDBConstructionCustody("")
