"""Limited EmpireDB owner SELECT chain: source shape is never actual revenue."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import pytest

from empire_os.data_cloud_contract import DataBackend
from empire_os.exchange_native_seat_owner_reader_v1 import (
    COLUMNS,
    review_native_exchange_seat_by_order,
)
from tests.test_exchange_seat_payment_receipt_review_v1_20261020 import (
    BUYER, ORDER, REQ, NOW, records,
)

TENANT="11111111-1111-4111-8111-111111111111"


class SyntheticOwnerReader:
    backend=DataBackend.EMPIREDB
    configured=True
    def __init__(self,*,rows=None,fail=False):
        originals=records()
        self.rows=rows or {
            "buyers":[dict(id=BUYER,org_id=TENANT,commercial_activation_state="activated",contact_email="private@example.invalid")],
            "fulfilment_orders":[deepcopy(originals["order"])],
            "bsc_payment_requests":[deepcopy(originals["request"])],
            "bsc_payment_evidence":[deepcopy(originals["evidence"])],
        }
        self.calls=[]
        self.fail=fail

    def select(self,table,columns="*",filters=None,order=None,limit=1000,offset=0):
        if self.fail:
            raise RuntimeError("Database secret password=SHOULD_NOT_PRINT")
        self.calls.append((table,columns,filters,limit,offset))
        assert table in COLUMNS
        assert columns==COLUMNS[table]
        assert all(w not in columns for w in ("email","phone","notes","contact_name"))
        assert len(filters)==1
        assert limit==2 and offset==0 and order is None
        return [r for r in self.rows[table]
                if all(r.get(k)==v for k,v in filters.items())]


def run(reader=None,**kwargs):
    return review_native_exchange_seat_by_order(
        reader,
        order_id=ORDER,buyer_id=BUYER,expected_tenant_id=TENANT,
        private_finance_quote=records()["finance_quote"],
        read_intent_approved=True,now=NOW,
        **kwargs,
    )


def test_exact_bounded_four_reads_and_no_wallets_emitted():
    db=SyntheticOwnerReader()
    x=run(db)
    assert x["state"]=="OWNER_READ_RECEIPT_SHAPE_REVIEW_ONLY"
    assert x["source_tables_queried_count"]==4
    assert [s[0] for s in db.calls]==[
        "buyers","fulfilment_orders","bsc_payment_requests","bsc_payment_evidence"]
    assert db.calls[0][2]=={"id":BUYER}
    assert db.calls[1][2]=={"id":ORDER}
    assert db.calls[2][2]=={"fulfilment_order_id":ORDER}
    assert db.calls[3][2]=={"request_id":REQ}
    assert x["root_owner_identity_and_rls_proven"] is False
    assert x["recognized_mrr_cents"]==0
    assert x["seat_subscription_authorized"] is False
    assert x["database_writes"] is False
    assert x["receipt_join_review"]["actual_paid_subscription_count_verified"]==0
    out=json.dumps(x)
    assert "private@example.invalid" not in out
    assert "0x"+"f"*64 not in out
    assert "0x"+"c"*40 not in out
    assert BUYER not in out and ORDER not in out and REQ not in out


def test_default_never_reads_anything():
    db=SyntheticOwnerReader()
    x=review_native_exchange_seat_by_order(
        db,order_id=ORDER,buyer_id=BUYER,expected_tenant_id=TENANT,
        private_finance_quote=records()["finance_quote"],
    )
    assert x["state"]=="HOLD"
    assert db.calls==[]


def test_no_config_no_quote_and_invalid_id_never_read():
    assert run(None)["reason"]=="no_authorised_owner_reader"
    db=SyntheticOwnerReader()
    x=review_native_exchange_seat_by_order(
        db,order_id="invalid",buyer_id=BUYER,
        expected_tenant_id=TENANT,
        private_finance_quote=records()["finance_quote"],
        read_intent_approved=True,
    )
    assert x["state"]=="HOLD" and not db.calls
    y=review_native_exchange_seat_by_order(
        db,order_id=ORDER,buyer_id=BUYER,
        expected_tenant_id=TENANT,
        private_finance_quote=None,read_intent_approved=True,
    )
    assert y["state"]=="HOLD" and not db.calls


def test_other_backend_cannot_fallback_to_noncanonical():
    db=SyntheticOwnerReader()
    db.backend=DataBackend.SUPABASE_LEGACY
    x=run(db)
    assert x["state"]=="HOLD" and db.calls==[]
    db.backend=DataBackend.EMPIREDB
    db.configured=False
    assert run(db)["state"]=="HOLD" and db.calls==[]


@pytest.mark.parametrize("failure",[
    "tenant_mismatch","buyer_not_activated","order_for_other_buyer",
    "request_for_other_buyer","duplicate_request","duplicate_evidence",
    "missing_evidence","wrong_source_order","bad_payment_join",
])
def test_identity_ambiguous_and_invalid_rows_fail_closed(failure):
    db=SyntheticOwnerReader()
    rows=db.rows
    if failure=="tenant_mismatch":
        rows["buyers"][0]["org_id"]="22222222-1111-4111-8111-111111111111"
    elif failure=="buyer_not_activated":
        rows["buyers"][0]["commercial_activation_state"]="discovered"
    elif failure=="order_for_other_buyer":
        rows["fulfilment_orders"][0]["buyer_id"]=TENANT
    elif failure=="request_for_other_buyer":
        rows["bsc_payment_requests"][0]["buyer_id"]=TENANT
    elif failure=="duplicate_request":
        rows["bsc_payment_requests"].append(deepcopy(rows["bsc_payment_requests"][0]))
    elif failure=="duplicate_evidence":
        rows["bsc_payment_evidence"].append(deepcopy(rows["bsc_payment_evidence"][0]))
    elif failure=="missing_evidence":
        rows["bsc_payment_evidence"]=[]
    elif failure=="wrong_source_order":
        rows["fulfilment_orders"][0]["id"]=TENANT
    else:
        rows["bsc_payment_evidence"][0]["confirmations"]=5
    x=run(db)
    assert x["state"]=="HOLD",failure
    assert not x["seat_subscription_authorized"] and x["recognized_mrr_cents"]==0
    assert not x["database_writes"]


def test_provider_failure_must_not_disclose_secrets():
    db=SyntheticOwnerReader(fail=True)
    x=run(db)
    assert x["state"]=="HOLD"
    assert "SHOULD_NOT_PRINT" not in json.dumps(x)


def test_commercial_enquiry_not_payable_membership():
    db=SyntheticOwnerReader()
    db.rows["fulfilment_orders"][0]["commercial_payload"]["purchase_purpose"]="one_off_intelligence"
    x=run(db)
    assert x["state"]=="HOLD"
    assert "not_a_valid_monthly_membership_order" in x["receipt_join_review"]["blockers"]
