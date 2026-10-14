"""Dedicated read-only EmpireDB paid-order evidence reader tests."""
from __future__ import annotations
from copy import deepcopy
from uuid import uuid4
import pytest

from empire_os.paid_search_fulfilment_reader import (
    PaidOrderReadOnlyReader, PaidOrderReadbackHold,
    SETUP,IDENTITY_SQL,ORDER_SQL,PAYMENT_SQL,EVIDENCE_SQL,
)
from empire_os.paid_search_fulfilment_review import review_paid_search_order

OID=str(uuid4()); BID=str(uuid4()); RID=str(uuid4())
EID=str(uuid4()); PAYER="0x"+"1"*40


def facts():
    return {
        "order":[{
            "id":OID,"buyer_id":BID,"state":"accepted","price_cents":19900,
            "commercial_payload":{
                "product_code":"competitor_search_gap",
                "buyer_terms_accepted":True,
                "settlement_mode":"direct",
                "commercial_terms_sha256":"a"*64,
                "payer_wallet":PAYER,
            },
            "delivery_payload":{"target_domain":"example.com"},
        }],
        "payment":[{
            "id":RID,"buyer_id":BID,"fulfilment_order_id":OID,
            "settlement_mode":"direct","status":"approved",
            "amount_usdt":"199",
        }],
        "evidence":[{
            "id":EID,"request_id":RID,
            "fulfilment_order_id":OID,
            "chain_id":56,"confirmations":12,
        }],
    }


class Cursor:
    def __init__(self,records=None,*,identity=("empiredb","empire_revenue_recognizer",False),fail_at=None):
        self.calls=[]
        self.records=facts() if records is None else records
        self.identity=identity
        self.query=None
        self.fail_at=fail_at

    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,sql,params=None):
        self.calls.append((sql,params))
        if self.fail_at and self.fail_at in sql:
            raise RuntimeError("database diagnostic never leaks")
        self.query=sql
    def fetchone(self):
        assert self.query==IDENTITY_SQL
        return self.identity
    def fetchall(self):
        if self.query==ORDER_SQL: bucket="order"
        elif self.query==PAYMENT_SQL: bucket="payment"
        elif self.query==EVIDENCE_SQL: bucket="evidence"
        else:raise AssertionError("unexpected unbounded SQL")
        return [(deepcopy(x),) for x in self.records[bucket]]


class Connection:
    def __init__(self,cursor):self.cur=cursor;self.rollbacks=0
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def cursor(self):return self.cur
    def rollback(self):self.rollbacks+=1


def reader(*,records=None,identity=("empiredb","empire_revenue_recognizer",False),fail_at=None):
    cursor=Cursor(records,identity=identity,fail_at=fail_at)
    connection=Connection(cursor)
    r=PaidOrderReadOnlyReader(
        "postgresql://dedicated-role-not-public",
        connect_factory=lambda dsn:connection,
    )
    return r,cursor,connection


def test_single_order_exact_three_queries_and_explicit_readonly_role():
    r,cur,con=reader()
    item=r(OID)
    assert tuple(item)==("order","payment","evidence")
    assert item["order"]["id"]==OID
    assert item["evidence"]["id"]==EID
    assert con.rollbacks==1
    assert [q for q,p in cur.calls]==[
        *SETUP,IDENTITY_SQL,ORDER_SQL,PAYMENT_SQL,EVIDENCE_SQL,
    ]
    assert [p for q,p in cur.calls[-3:]]==[(OID,),(OID,),(RID,)]
    assert all("LIMIT 2" in q for q in (ORDER_SQL,PAYMENT_SQL,EVIDENCE_SQL))
    assert not any(any(v in q.lower() for v in (
        "update public","insert into","delete from",
        "drop table","create table"
    )) for q,p in cur.calls)


def test_missing_order_is_hold_without_payment_or_evidence():
    records=facts(); records["order"]=[]
    r,cur,con=reader(records=records)
    with pytest.raises(PaidOrderReadbackHold,match="order unavailable"):
        r(OID)
    assert PAYMENT_SQL not in [q for q,p in cur.calls]


def test_existing_reader_to_review_bridge_holds_on_missing_report_provenance():
    r,cur,con=reader()
    result=r.review_order(OID)
    # Even with canonical mocked payment/evidence and an order, no report
    # is authorised, nor is any delivery record changed.
    assert result["decision"] in (
        "HOLD_CANONICAL_PAYMENT_EVIDENCE",
        "HOLD_OBSERVED_REPORT_EVIDENCE",
    )
    assert result["delivery_authorized"] is False
    assert result["revenue_recognized"] is False
    assert con.rollbacks==1


def test_missing_payment_yields_reviewable_hold_not_approval():
    records=facts(); records["payment"]=[]
    r,cur,con=reader(records=records)
    bundle=r(OID)
    assert bundle["payment"] is None and bundle["evidence"] is None
    assert EVIDENCE_SQL not in [q for q,p in cur.calls]
    output=review_paid_search_order(**bundle)
    assert output["decision"]=="HOLD_CANONICAL_PAYMENT_EVIDENCE"


def test_missing_evidence_yields_payment_hold():
    records=facts(); records["evidence"]=[]
    r,cur,con=reader(records=records)
    output=review_paid_search_order(**r(OID))
    assert output["decision"]=="HOLD_CANONICAL_PAYMENT_EVIDENCE"


@pytest.mark.parametrize("bucket",["order","payment","evidence"])
def test_ambiguous_row_count_never_picks_arbitrary_approval(bucket):
    records=facts()
    records[bucket]=[records[bucket][0],deepcopy(records[bucket][0])]
    r,cur,_=reader(records=records)
    with pytest.raises(PaidOrderReadbackHold,match="ambiguous"):
        r(OID)


@pytest.mark.parametrize("identity",[
    ("empiredb","postgres",False),
    ("other","empire_revenue_recognizer",False),
    ("empiredb","empire_revenue_recognizer",True),
])
def test_wrong_database_role_or_replica_holds(identity):
    r,cur,_=reader(identity=identity)
    with pytest.raises(PaidOrderReadbackHold,match="canonical database role"):
        r(OID)
    assert ORDER_SQL not in [q for q,p in cur.calls]


@pytest.mark.parametrize("bad",[
    "","not-a-uuid","00000000-0000-0000-0000-000000000000' OR true --",
    None,True,str(uuid4()).upper(),
])
def test_untrusted_identity_fails_before_network(bad):
    r,cur,_=reader()
    with pytest.raises(PaidOrderReadbackHold):
        r(bad)
    assert cur.calls==[]


def test_missing_dedicated_dsn_denied_before_network():
    with pytest.raises(PaidOrderReadbackHold,match="dedicated recognizer"):
        PaidOrderReadOnlyReader("",connect_factory=lambda *a:None)


def test_database_exception_fails_closed_with_redacted_diagnostic():
    r,cur,_=reader(fail_at="FROM public.bsc_payment_requests")
    with pytest.raises(PaidOrderReadbackHold) as e:
        r(OID)
    assert "database diagnostic never leaks" not in str(e.value)
    assert "canonical readback unavailable" in str(e.value)


def test_no_email_or_buyer_details_in_sql_projection():
    sql="\n".join((ORDER_SQL,PAYMENT_SQL,EVIDENCE_SQL)).lower()
    assert "email" not in sql and "buyer_name" not in sql
    assert "direct_bsc_buyer_capabilities" not in sql
    assert "outbound_intents" not in sql
    assert "wallet" in sql  # exact payment terms match needs payer binding
    assert "target_domain" in sql


def test_public_module_does_not_connect_at_import_or_send():
    import inspect
    from empire_os import paid_search_fulfilment_reader as mod
    text=inspect.getsource(mod)
    assert "smtp" not in text.lower() and "send_mail(" not in text.lower()
    assert "response.json" not in text
    assert "connection.rollback()" in text
