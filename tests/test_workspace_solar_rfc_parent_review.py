"""Gmail RFC parent checks strengthen future reply evidence, never qualify a buyer."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from empire_os.workspace_solar_founder_review import (
    WorkspaceReviewHeld, project_workspace_review,
)

from empire_os.workspace_solar_reply_tracking import (
    ANCHORS, ACCOUNT, EvidenceHeld, review_workspace_solar_threads,
    newly_observed_workspace_replies,
)

NOW = datetime(2026, 10, 18, 18, 0, tzinfo=timezone.utc)
SENT = datetime(2026, 10, 18, 17, 0, tzinfo=timezone.utc)
INBOUND = datetime(2026, 10, 18, 17, 20, tzinfo=timezone.utc)
PARENT = "<solar-original-sent@empire-ai.co.uk>"
REPLY = "<customer-response@gbnrg.co.uk>"


def message(mid, thread, when, sender, to, labels, extra=()):
    return {
        "id": mid, "threadId": thread,
        "internalDate": str(int(when.timestamp()*1000)),
        "labelIds": labels,
        "payload": {"headers": [
            {"name": "From", "value": sender},
            {"name": "To", "value": to},
            *[{"name": name, "value": value} for name,value in extra],
        ]},
        "snippet": "PRIVATE MESSAGE CONTENT DO NOT STORE",
    }


def sample(extra=(), sent_id=PARENT):
    rows = {}
    for i, (company,domain,recipient,tid,mid) in enumerate(ANCHORS):
        rows[tid] = {"id": tid, "messages": [
            message(mid,tid,SENT,ACCOUNT,recipient,["SENT"],
                    extra=[("Message-ID", sent_id)])
        ]}
        if i == 0:
            rows[tid]["messages"].append(
                message("1a14fa31d0000001",tid,INBOUND,
                        f"Sales <sales@{domain}>",ACCOUNT,["INBOX"],
                        extra=[("Message-ID",REPLY),*extra])
            )
    return rows


@pytest.mark.parametrize(("headers","relation"), [
    ([("In-Reply-To",PARENT)], "DIRECT_PARENT_MATCH"),
    ([("In-Reply-To","<other@domain.test>"),
      ("References",f"<other@domain.test> {PARENT}")],
      "ORIGINAL_MESSAGE_REFERENCED_ONLY"),
    ([("In-Reply-To","<other@domain.test>")], "NOT_PROVEN"),
    ([("In-Reply-To","not-a-valid-rfc-id")], "NOT_PROVEN"),
    ([("References",PARENT)], "ORIGINAL_MESSAGE_REFERENCED_ONLY"),
    ([], "NOT_PROVEN"),
])
def test_bounded_rfc_parent_proof_is_not_contact_or_commercial_authority(headers,relation):
    result=review_workspace_solar_threads(sample(headers),now=NOW)
    assert result["inbound_header_candidate_count"] == 1
    candidate=result["threads"][0]["inbound_header_candidates"][0]
    assert candidate["rfc_parent_relation"] == relation
    assert candidate["status"] == "INBOUND_PROVIDER_HEADER_CANDIDATE_NEEDS_HUMAN_REVIEW"
    assert result["threads"][0]["buyer_intent_verified"] is False
    assert result["founder_crm_ingest_verified"] is False
    assert result["database_writes"] is False
    assert result["outbound_sent"] is False
    # No RFC IDs, personal email address, snippets or subject survive.
    assert PARENT not in str(result) and REPLY not in str(result)
    assert "sales@" not in str(result)
    assert "PRIVATE MESSAGE CONTENT" not in str(result)


def test_sent_rfc_absent_or_malformed_cannot_prove_direct_parent():
    for value in ("invalid", "", "<missing-domain>", "<two@@x>"):
        result=review_workspace_solar_threads(
            sample([("In-Reply-To",PARENT)],sent_id=value),now=NOW
        )
        assert result["threads"][0]["inbound_header_candidates"][0]["rfc_parent_relation"]=="NOT_PROVEN"


def test_duplicate_rfc_headers_fail_closed():
    rows=sample([("Message-ID","<other@x.test>")])
    with pytest.raises(EvidenceHeld,match="DUPLICATED_PROVIDER_IDENTITY_OR_RFC_HEADER"):
        review_workspace_solar_threads(rows,now=NOW)


def test_legacy_snapshot_candidate_id_remains_deduplicated_after_new_rfc_relation():
    current=review_workspace_solar_threads(
        sample([("In-Reply-To",PARENT)]),now=NOW
    )
    previous=review_workspace_solar_threads(sample(),now=NOW)
    # Old snapshot has the same candidate id but no ancestry field.
    del previous["threads"][0]["inbound_header_candidates"][0]["rfc_parent_relation"]
    assert newly_observed_workspace_replies(current,previous)==0


def test_founder_projection_exposes_only_parent_relationship_not_rfc_addresses():
    current=review_workspace_solar_threads(
        sample([("In-Reply-To",PARENT)]),now=NOW
    )
    projected=project_workspace_review(current,now=NOW)
    first=next(x for x in projected["items"] if x["inbound_candidate_count"])
    candidate=first["inbound_candidates"][0]
    assert candidate["rfc_parent_relation"] == "DIRECT_PARENT_MATCH"
    assert candidate["contact_identity_verified"] is False
    assert candidate["commercial_intent_verified"] is False
    assert projected["crm_conversation_created"] is False
    assert PARENT not in str(projected)
    assert REPLY not in str(projected)


def test_founder_projection_does_not_promote_unsupported_rfc_claim():
    current=review_workspace_solar_threads(sample(),now=NOW)
    current["threads"][0]["inbound_header_candidates"][0][
        "rfc_parent_relation"
    ]="AUTHENTICATED_BUYER_FALSE_CLAIM"
    with pytest.raises(WorkspaceReviewHeld, match="UNTRUSTED_RFC_CHAIN_CLASSIFICATION"):
        project_workspace_review(current,now=NOW)


@pytest.mark.parametrize(("to_address","expected"), [
    ("phil@empire-ai.co.uk", "EXPECTED_WORKSPACE_TO"),
    ("Founder <phil@mail.empire-ai.co.uk>", "EXPECTED_WORKSPACE_TO"),
    ("Replies <reply@mail.empire-ai.co.uk>", "EXPECTED_WORKSPACE_TO"),
    ('"Founder, Phil" <phil@mail.empire-ai.co.uk>, Another <test@external.invalid>',
     "EXPECTED_WORKSPACE_TO"),
    ("third-party@unrelated.example", "RECIPIENT_ROUTE_UNVERIFIED"),
    ("", "RECIPIENT_ROUTE_UNVERIFIED"),
    ("not-valid@", "RECIPIENT_ROUTE_UNVERIFIED"),
])
def test_header_recipient_route_is_corroboration_not_commercial_proof(to_address, expected):
    rows = sample([("In-Reply-To", PARENT)])
    incoming = rows[ANCHORS[0][3]]["messages"][1]
    for header in incoming["payload"]["headers"]:
        if header["name"] == "To":
            header["value"] = to_address
    result = review_workspace_solar_threads(rows, now=NOW)
    candidate = result["threads"][0]["inbound_header_candidates"][0]
    assert candidate["recipient_routing"] == expected
    assert candidate["rfc_parent_relation"] == "DIRECT_PARENT_MATCH"
    assert result["inbound_header_candidate_count"] == 1
    assert result["founder_crm_ingest_verified"] is False
    projected = project_workspace_review(result, now=NOW)
    shown = next(r for r in projected["items"] if r["inbound_candidate_count"])
    assert shown["inbound_candidates"][0]["recipient_routing"] == expected
    assert "third-party@" not in str(projected)
    assert projected["crm_conversation_created"] is False


def test_malformed_recipient_routing_state_cannot_be_promoted_in_founder_api():
    current = review_workspace_solar_threads(sample(), now=NOW)
    current["threads"][0]["inbound_header_candidates"][0][
        "recipient_routing"
    ] = "PROVEN_BUYER_AND_TENANT"
    with pytest.raises(WorkspaceReviewHeld, match="UNTRUSTED_RECIPIENT_ROUTING"):
        project_workspace_review(current, now=NOW)
