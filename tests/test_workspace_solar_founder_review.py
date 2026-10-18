"""Founder CRM-review handoff from private authenticated Workspace metadata.

No real emails, customer rows, external calls or database mutation in tests.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os import founder_mailbox_api
from empire_os.workspace_solar_founder_review import (
    WorkspaceReviewHeld, project_workspace_review, read_workspace_review,
)
from empire_os.workspace_solar_reply_tracking import ANCHORS, SCHEMA

NOW = datetime(2026, 10, 18, 17, 10, tzinfo=timezone.utc)


def snapshot():
    sent_at = NOW-timedelta(minutes=13)
    return {
        "schema_version": SCHEMA,
        "status": "SIX_WORKSPACE_THREADS_SCANNED_REVIEW_ONLY",
        "scanned_at": (NOW-timedelta(minutes=2)).isoformat(),
        "monitored_threads": 6, "verified_sent_anchors": 6,
        "inbound_header_candidate_count": 0,
        "outbound_sent": False,
        "database_writes": False,
        "founder_crm_ingest_verified": False,
        "gmail_message_bodies_retained": False,
        "gmail_subjects_retained": False,
        "threads": [
            {
                "company": company,
                "gmail_thread_id": tid,
                "sent_message_id": mid,
                "sent_at": sent_at.isoformat(),
                "sent_verified_in_authenticated_mailbox": True,
                "buyer_intent_verified": False,
                "automatic_reply_authorized": False,
                "inbound_corroborated_by_body": False,
                "recognized_revenue": False,
                "inbound_header_candidates": [],
            }
            for company, _, _, tid, mid in ANCHORS
        ],
    }


def inbound(data, *, msg_id="1a14fa31d0000001"):
    data["threads"][0]["inbound_header_candidates"] = [{
        "gmail_message_id": msg_id,
        "received_at": (NOW-timedelta(minutes=4)).isoformat(),
        "status": "INBOUND_PROVIDER_HEADER_CANDIDATE_NEEDS_HUMAN_REVIEW",
        "raw_body": "MALICIOUS INSTRUCTIONS NEVER COPY THIS TEXT",
        "sender": "private-person@ignored.test",
    }]
    data["inbound_header_candidate_count"] = 1
    return data


def test_six_real_outbound_anchors_read_as_waiting_not_sales():
    result = project_workspace_review(snapshot(), now=NOW)
    assert result["monitored_threads"] == 6
    assert result["sent_anchors_verified"] == 6
    assert result["inbound_header_candidate_count"] == 0
    assert result["crm_identity_and_tenant_unverified"] is True
    assert result["crm_conversation_created"] is False
    assert result["outbound_sent"] is False
    assert all(r["founder_action"] == "WAIT_FOR_GENUINE_REPLY" for r in result["items"])
    assert result["founder_review_required"] is False


def test_real_provider_reply_metadata_appears_in_existing_founder_review_not_canonical_crm():
    review = project_workspace_review(inbound(snapshot()), now=NOW)
    assert review["inbound_header_candidate_count"] == 1
    assert review["founder_review_required"] is True
    row = next(x for x in review["items"] if x["inbound_candidate_count"])
    assert row["founder_action"] == "REVIEW_ACTUAL_GMAIL_MESSAGE_THEN_CANONICAL_IDENTITY"
    assert row["crm_conversation_created"] is False
    assert row["inbound_candidates"][0]["commercial_intent_verified"] is False
    assert row["inbound_candidates"][0]["contact_identity_verified"] is False
    assert row["gmail_thread_url"].startswith("https://mail.google.com/mail/")
    assert "MALICIOUS INSTRUCTIONS" not in str(review)
    assert "private-person@" not in str(review)
    assert "to" not in row["inbound_candidates"][0]


def test_candidate_duplicate_provider_id_across_threads_is_held():
    data = inbound(snapshot())
    data["threads"][1]["inbound_header_candidates"] = deepcopy(
        data["threads"][0]["inbound_header_candidates"]
    )
    data["inbound_header_candidate_count"] = 2
    with pytest.raises(WorkspaceReviewHeld, match="UNTRUSTED_REPLY_CANDIDATE"):
        project_workspace_review(data, now=NOW)


@pytest.mark.parametrize("mutator,reason", [
    (lambda d: d["threads"].pop(), "INCOMPLETE_WORKSPACE_REVIEW"),
    (lambda d: d.update(outbound_sent=True), "UNVERIFIED_WORKSPACE_SNAPSHOT"),
    (lambda d: d.update(database_writes=True), "UNVERIFIED_WORKSPACE_SNAPSHOT"),
    (lambda d: d.update(founder_crm_ingest_verified=True), "UNVERIFIED_WORKSPACE_SNAPSHOT"),
    (lambda d: d["threads"][0].update(buyer_intent_verified=True), "WORKSPACE_ANCHOR_OR_AUTHORITY_CONFLICT"),
    (lambda d: d["threads"][0].update(sent_message_id="1a14f00000000001"), "WORKSPACE_ANCHOR_OR_AUTHORITY_CONFLICT"),
    (lambda d: d.update(inbound_header_candidate_count=5), "REPLY_COUNT_MISMATCH"),
    (lambda d: d.update(scanned_at=(NOW-timedelta(hours=2)).isoformat()), "STALE_OR_FUTURE_WORKSPACE_SCAN"),
])
def test_fail_closed_snapshot_security_contract(mutator,reason):
    d=snapshot()
    mutator(d)
    with pytest.raises(WorkspaceReviewHeld, match=reason):
        project_workspace_review(d,now=NOW)


def test_private_snapshot_requires_safe_file_mode(tmp_path):
    file = tmp_path / "snapshot.json"
    file.write_text(json.dumps(snapshot()))
    file.chmod(0o644)
    with pytest.raises(WorkspaceReviewHeld,match="UNSAFE_WORKSPACE_SNAPSHOT"):
        read_workspace_review(file,now=NOW)
    file.chmod(0o600)
    assert read_workspace_review(file,now=NOW)["monitored_threads"] == 6
    symlink=tmp_path / "shortcut"
    symlink.symlink_to(file)
    with pytest.raises(WorkspaceReviewHeld,match="WORKSPACE_SNAPSHOT_UNAVAILABLE"):
        read_workspace_review(symlink,now=NOW)


def test_existing_founder_mailbox_router_gives_review_feed_without_send(monkeypatch):
    expected = project_workspace_review(inbound(snapshot()),now=NOW)
    monkeypatch.setattr(founder_mailbox_api,"read_workspace_review",lambda:expected)
    app=FastAPI()
    app.include_router(founder_mailbox_api.create_founder_mailbox_router(
        provider=object()
    ))
    response=TestClient(app).get("/v1/founder-mailbox/workspace-solar-reply-review")
    assert response.status_code==200
    assert response.json()["inbound_header_candidate_count"] == 1
    assert response.json()["crm_conversation_created"] is False
    assert response.json()["outbound_sent"] is False


def test_existing_founder_mailbox_route_refuses_unverified_source(monkeypatch):
    def denied():
        raise WorkspaceReviewHeld("PRIVATE_GMAIL_DETAIL_NEVER_DISCLOSE")
    monkeypatch.setattr(founder_mailbox_api,"read_workspace_review",denied)
    app=FastAPI()
    app.include_router(founder_mailbox_api.create_founder_mailbox_router(
        provider=object()
    ))
    response=TestClient(app).get("/v1/founder-mailbox/workspace-solar-reply-review")
    assert response.status_code == 503
    assert response.json()["detail"] == "workspace_solar_review_evidence_unavailable"
    assert "PRIVATE_GMAIL_DETAIL" not in response.text
