"""No real customer/database access. Exactly six, aggregate-only canonical probes."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os import founder_mailbox_api
from empire_os.workspace_solar_canonical_intent_review import (
    CanonicalIntentReviewUnavailable, _parse_counts,
    review_six_workspace_canonical_intents, SQL,
)
from empire_os.workspace_solar_reply_tracking import ANCHORS


def rows(default=(0,0,0,0)):
    return [(a[3], *default) for a in ANCHORS]


def test_zero_visible_is_not_attested_absence_or_crm():
    report=_parse_counts(rows())
    assert report["threads_checked"]==6
    assert report["source_visibility_complete"] is False
    assert report["zero_count_means_no_row_visible_not_global_absence"] is True
    assert all(r["status"] == "NO_CANONICAL_GMAIL_THREAD_INTENT_VISIBLE_TO_READER" for r in report["items"])
    assert all(r["crm_handoff_authorized"] is False for r in report["items"])
    assert report["crm_mutation"] is False
    assert report["outbound_sent"] is False
    assert report["founder_crm_delivery_verified"] is False
    assert "@" not in str(report)
    assert all(x["next_founder_review_action"] == "REVIEW_HISTORICAL_SENT_EVIDENCE_FOR_CANONICAL_ADMISSION" for x in report["items"])
    assert all(x["historical_send_reconciliation_automatically_authorized"] is False for x in report["items"])


@pytest.mark.parametrize("counts,code,action",[
    ((1,0,0,0),"GMAIL_THREAD_PRESENT_ORIGINAL_RECIPIENT_NOT_BOUND","REVIEW_EXACT_ORIGINAL_RECIPIENT_MISMATCH"),
    ((2,2,2,2),"AMBIGUOUS_CANONICAL_SENT_INTENT","RESOLVE_CANONICAL_INTENT_AMBIGUITY"),
    ((1,1,0,1),"CANONICAL_APPROVAL_EVIDENCE_NOT_COMPLETE","VERIFY_ACTUAL_FOUNDER_APPROVAL_PROVENANCE"),
    ((1,1,1,0),"ORIGINAL_PROVIDER_SENT_MESSAGE_ID_NOT_BOUND","RECONCILE_ORIGINAL_PROVIDER_MESSAGE_PROVENANCE"),
    ((1,1,1,1),"STRUCTURAL_CANDIDATE_ONLY_REQUIRES_TENANT_AND_PROVIDER_REVIEW","VERIFY_TENANT_CONTACT_SUPPRESSION_AND_BUYER_REPLY"),
])
def test_six_exact_source_states_never_promote(counts,code,action):
    report=_parse_counts(rows(counts))
    assert all(r["status"] == code and r["next_founder_review_action"] == action for r in report["items"])
    assert not any(r["tenant_identity_verified"] or r["crm_handoff_authorized"] or r["historical_send_reconciliation_automatically_authorized"] for r in report["items"])


@pytest.mark.parametrize("broken",[
    lambda rr: rr[:-1],
    lambda rr: rr + rr[:1],
    lambda rr: rr[:-1]+[("0000000000000000",0,0,0,0)],
    lambda rr: rr[:-1]+[(rr[0][0],0,0,0,0)],
    lambda rr: rr[:-1]+[(rr[-1][0],1,2,0,0)],
    lambda rr: rr[:-1]+[(rr[-1][0],1,1,2,0)],
    lambda rr: rr[:-1]+[(rr[-1][0],1,1,1,2)],
    lambda rr: rr[:-1]+[(rr[-1][0],True,0,0,0)],
])
def test_incomplete_or_contradictory_aggregate_is_held(broken):
    with pytest.raises(CanonicalIntentReviewUnavailable):
        _parse_counts(broken(rows()))


class Cursor:
    def __init__(self,output):self.output=output;self.calls=[]
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,query,params=None):self.calls.append((query,params))
    def fetchall(self):return self.output


class Connection:
    def __init__(self,out):self.cursor_obj=Cursor(out)
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def cursor(self):return self.cursor_obj


def test_existing_credentials_reader_enforces_readonly_and_exact_allowlist():
    conn=Connection(rows((1,1,1,1)))
    connect_calls=[]
    def connect(dsn,**kw):
        connect_calls.append((dsn,kw))
        return conn
    report=review_six_workspace_canonical_intents(
        dsn="fake-test-credential", connect_factory=connect,
    )
    assert report["threads_checked"]==6
    commands=conn.cursor_obj.calls
    assert commands[0][0] == "SET TRANSACTION READ ONLY"
    assert commands[1][0] == "SET LOCAL ROLE empire_closer_observer"
    assert "statement_timeout" in commands[2][0]
    assert commands[3][0] == SQL
    assert commands[3][1] == (
        [a[3] for a in ANCHORS],
        [a[2] for a in ANCHORS],
        [a[4] for a in ANCHORS],
    )
    assert commands[-1][0] == "ROLLBACK"
    assert connect_calls[0][1] == {"connect_timeout":5}
    assert "fake-test-credential" not in str(report)
    assert "@" not in str(report)


def test_missing_credential_fails_closed():
    with pytest.raises(CanonicalIntentReviewUnavailable,match="DEDICATED_READER_UNAVAILABLE"):
        review_six_workspace_canonical_intents(dsn="")


def test_exact_private_founder_endpoint_read_success_and_no_customer_fields(monkeypatch):
    report=_parse_counts(rows((1,1,1,0)))
    monkeypatch.setattr(founder_mailbox_api,
                        "review_six_workspace_canonical_intents",lambda:report)
    app=FastAPI()
    app.include_router(founder_mailbox_api.create_founder_mailbox_router(provider=object()))
    resp=TestClient(app).get("/v1/founder-mailbox/workspace-solar-canonical-intent-review")
    assert resp.status_code==200
    assert resp.json()["threads_checked"] == 6
    assert all(anchor[2] not in resp.text for anchor in ANCHORS)
    assert all(anchor[3] not in resp.text for anchor in ANCHORS)
    assert '"canonical_contact_verified":false' in resp.text
    assert '"crm_mutation":false' in resp.text


def test_private_endpoint_returns_sanitised_unavailable_without_db_errors(monkeypatch):
    def unreadable():
        raise CanonicalIntentReviewUnavailable("RAW_PRIVATE_DATABASE_SECRET")
    monkeypatch.setattr(founder_mailbox_api,"review_six_workspace_canonical_intents",unreadable)
    app=FastAPI()
    app.include_router(founder_mailbox_api.create_founder_mailbox_router(provider=object()))
    resp=TestClient(app).get("/v1/founder-mailbox/workspace-solar-canonical-intent-review")
    assert resp.status_code==503
    assert resp.json()["detail"]=="workspace_solar_canonical_intent_review_unavailable"
    assert "RAW_PRIVATE_DATABASE_SECRET" not in resp.text
