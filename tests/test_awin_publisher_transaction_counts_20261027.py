"""Awin publisher transaction counts: original-account, no PII or fake revenue."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
import json
import stat

from empire_os.awin_publisher_transaction_counts import review
from empire_os.awin_publisher_api import PUBLISHER_ID

NOW=datetime(2026,10,27,14,50,tzinfo=timezone.utc)

def member(tmp_path, statuses=None, *, offset=timedelta(0)):
    states=statuses or {"122556":"PENDING","73922":"PENDING"}
    path=tmp_path/"membership.json"
    document={
        "schema_version":"empire.awin.publisher_programme_membership.v1",
        "status":"AWIN_API_MEMBERSHIP_REVIEW_VERIFIED",
        "publisher_id":PUBLISHER_ID,
        "api_live_verified":True,
        "observed_at":(NOW+offset).isoformat(),
        "affiliate_publication_authorized":False,
        "commission_earned_verified":False,"commission_paid_verified":False,
        "outbound_sent":False,"database_writes":False,
        "programmes":[
            {"advertiser_id":id,"membership_status":state,
             "membership_verified_by_authenticated_awin_api":True,
             "publisher_authorised_to_use_tracking_link":False}
            for id,state in states.items()
        ]
    }
    path.write_text(json.dumps(document));path.chmod(0o600)
    return path

def token(tmp_path):
    p=tmp_path/"secret"
    p.write_text("eyJhbGciOiJIUzI1NiJ9.test.value.token.mocked")
    p.chmod(0o600)
    return p

def source(rows, calls):
    def fetch(url,secret):
        calls.append(url)
        u=urlsplit(url)
        assert u.scheme=="https" and u.netloc=="api.awin.com"
        assert u.path=="/publishers/3136281/transactions/"
        q=parse_qs(u.query)
        assert q["dateType"]==["transaction"] and q["timezone"]==["UTC"]
        assert q["showBasketProducts"]==["false"]
        assert set(q)=={"advertiserId","dateType","timezone","showBasketProducts","startDate","endDate"}
        assert secret.startswith("eyJ")
        return rows[q["advertiserId"][0]]
    return fetch

def txn(advertiser_id, ident=3, state="pending"):
    return {"advertiserId":int(advertiser_id),"id":ident,
            "commissionStatus":state,
            "orderRef":"NEVER_STORE",
            "clickRef":"PRIVATE_CUSTOMER",
            "publisherCommission":{"amount":500}}


def test_pending_does_not_request_api_or_write_snapshot(tmp_path):
    calls=[]
    r=review(now=NOW,membership_path=member(tmp_path),
        token_path=tmp_path/"missing",output=tmp_path/"out",
        transport=lambda *x:calls.append(x),write=True)
    assert r["status"]=="AWIN_TRANSACTIONS_WAITING_FOR_JOINED_PROGRAMME"
    assert not calls and r["api_requests_made"]==0
    assert not (tmp_path/"out").exists()
    assert not r["revenue_verified"]


def test_joined_one_programme_aggregates_status_without_pii(tmp_path):
    calls=[]
    joined=member(tmp_path,{"122556":"JOINED","73922":"PENDING"})
    r=review(now=NOW,membership_path=joined,token_path=token(tmp_path),
       output=tmp_path/"out",write=True,
       transport=source({"122556":[txn("122556",15,"approved"),txn("122556",16,"pending")]},calls))
    assert r["status"]=="AWIN_JOINED_PROGRAMME_TRANSACTION_COUNTS_OBSERVED"
    assert len(calls)==1 and r["joined_programmes_checked"]==["122556"]
    assert r["programme_results"][0]["record_count"]==2
    assert r["programme_results"][0]["status_counts"]=={
        "pending":1,"approved":1,"declined":0,"deleted":0}
    assert r["revenue_verified"] is False and r["payout_verified"] is False
    raw=(tmp_path/"out").read_text()
    assert "NEVER_STORE" not in raw and "PRIVATE_CUSTOMER" not in raw
    assert "500" not in raw and "publisherCommission" not in raw
    assert stat.S_IMODE((tmp_path/"out").stat().st_mode)==0o600


def test_two_joined_programmes_zero_is_verified_count_not_commission(tmp_path):
    r=review(now=NOW,membership_path=member(tmp_path,{"122556":"JOINED","73922":"JOINED"}),
         token_path=token(tmp_path),write=False,output=tmp_path/"out",
         transport=source({"122556":[],"73922":[]},[]))
    assert [x["record_count"] for x in r["programme_results"]]==[0,0]
    assert r["api_requests_made"]==2
    assert r["snapshot_written"] is False and not r["revenue_verified"]
    assert not (tmp_path/"out").exists()


def test_duplicate_transaction_id_fails_entire_review(tmp_path):
    old=member(tmp_path,{"122556":"JOINED","73922":"PENDING"})
    data={"122556":[txn("122556",15),txn("122556",15)]}
    r=review(now=NOW,membership_path=old,token_path=token(tmp_path),
             output=tmp_path/"out",write=True,transport=source(data,[]))
    assert r["status"].startswith("HELD_")
    assert not (tmp_path/"out").exists()


def test_mismatched_advertiser_fails_closed(tmp_path):
    old=member(tmp_path,{"122556":"JOINED","73922":"PENDING"})
    r=review(now=NOW,membership_path=old,token_path=token(tmp_path),
         output=tmp_path/"out",write=True,
         transport=source({"122556":[txn("73922")]},[]))
    assert r["status"].startswith("HELD_")
    assert not (tmp_path/"out").exists()


def test_unknown_financial_status_fails_closed(tmp_path):
    old=member(tmp_path,{"122556":"JOINED","73922":"PENDING"})
    r=review(now=NOW,membership_path=old,token_path=token(tmp_path),
         output=tmp_path/"out",write=True,
         transport=source({"122556":[txn("122556",12,"paid")]},[]))
    assert r["status"].startswith("HELD_")
    assert not (tmp_path/"out").exists()


def test_stale_authenticated_membership_blocks_requests(tmp_path):
    calls=[]
    path=member(tmp_path,{"122556":"JOINED","73922":"PENDING"},
                offset=timedelta(hours=-2))
    r=review(now=NOW,membership_path=path,token_path=token(tmp_path),
             output=tmp_path/"out",write=True,
             transport=lambda *a:calls.append(1))
    assert r["status"].startswith("HELD_")
    assert not calls


def test_insecure_membership_blocks_requests(tmp_path):
    path=member(tmp_path,{"122556":"JOINED","73922":"PENDING"})
    path.chmod(0o644)
    r=review(now=NOW,membership_path=path,token_path=token(tmp_path),
         output=tmp_path/"out",transport=lambda *a:[],write=True)
    assert r["status"].startswith("HELD_") and r["api_requests_made"]==0


def test_no_partial_snapshot_on_second_programme_failure(tmp_path):
    calls=[]
    def supplier(url,secret):
        calls.append(url)
        if len(calls)==2:
            raise RuntimeError("OTHER_PROVIDER_BAD_RESPONSE")
        return []
    p=member(tmp_path,{"122556":"JOINED","73922":"JOINED"})
    r=review(now=NOW,membership_path=p,token_path=token(tmp_path),
         output=tmp_path/"out",write=True,transport=supplier)
    assert r["status"].startswith("HELD_")
    assert not (tmp_path/"out").exists()


def test_insecure_existing_snapshot_preserved(tmp_path):
    out=tmp_path/"out"
    out.write_text("original");out.chmod(0o644)
    p=member(tmp_path,{"122556":"JOINED","73922":"PENDING"})
    r=review(now=NOW,membership_path=p,token_path=token(tmp_path),
         output=out,write=True,transport=source({"122556":[]},[]))
    assert r["status"].startswith("HELD_")
    assert out.read_text()=="original"


def test_zero_result_snapshot_repeat_is_idempotent_for_same_clock(tmp_path):
    p=member(tmp_path,{"122556":"JOINED","73922":"PENDING"})
    t=token(tmp_path)
    out=tmp_path/"out"
    args=dict(now=NOW,membership_path=p,token_path=t,output=out,write=True,
              transport=source({"122556":[]},[]))
    a=review(**args)
    previous=out.read_bytes()
    b=review(**args)
    assert a["status"]==b["status"]=="AWIN_JOINED_PROGRAMME_TRANSACTION_COUNTS_OBSERVED"
    assert out.read_bytes()==previous
