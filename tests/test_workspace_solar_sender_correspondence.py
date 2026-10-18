"""Exact original address vs same-domain peer: bounded reviewer evidence only."""
from __future__ import annotations

from copy import deepcopy

import pytest

from empire_os.workspace_solar_reply_tracking import (
    ANCHORS, review_workspace_solar_threads, newly_observed_workspace_replies,
)
from empire_os.workspace_solar_founder_review import (
    WorkspaceReviewHeld, project_workspace_review,
)
from tests.test_workspace_solar_rfc_parent_review import (
    NOW, PARENT, sample,
)


def inbound_from(rows, address):
    headers=rows[ANCHORS[0][3]]["messages"][1]["payload"]["headers"]
    for header in headers:
        if header["name"] == "From":
            header["value"] = address
            return
    raise AssertionError("fixture incomplete")


@pytest.mark.parametrize("sender,expected,review_step",[
    (
        "info@gbnrg.co.uk",
        "EXACT_ORIGINAL_RECIPIENT",
        "VERIFY_CANONICAL_INTENT_TENANT_SUPPRESSION_AND_CONTENT",
    ),
    (
        "Customer Care <info@gbnrg.co.uk>",
        "EXACT_ORIGINAL_RECIPIENT",
        "VERIFY_CANONICAL_INTENT_TENANT_SUPPRESSION_AND_CONTENT",
    ),
    (
        "sales@gbnrg.co.uk",
        "SAME_DOMAIN_DIFFERENT_ADDRESS",
        "REVIEW_SENDER_THREAD_ROUTING_AND_CONTENT_FIRST",
    ),
])
def test_exact_contact_vs_colleague_kept_separate_with_unchanged_crm_gates(
    sender,expected,review_step
):
    rows = sample([("In-Reply-To",PARENT)])
    inbound_from(rows,sender)
    current=review_workspace_solar_threads(rows,now=NOW)
    candidate=current["threads"][0]["inbound_header_candidates"][0]
    assert candidate["sender_correspondence"] == expected
    view=project_workspace_review(current,now=NOW)
    item=next(row for row in view["items"] if row["inbound_candidate_count"]==1)
    rendered=item["inbound_candidates"][0]
    assert rendered["sender_correspondence"] == expected
    assert rendered["rfc_parent_relation"] == "DIRECT_PARENT_MATCH"
    assert rendered["recipient_routing"] == "EXPECTED_WORKSPACE_TO"
    assert rendered["next_review_step"] == review_step
    assert rendered["crm_handoff_authorized"] is False
    assert rendered["contact_identity_verified"] is False
    assert rendered["commercial_intent_verified"] is False
    assert view["crm_conversation_created"] is False
    assert view["outbound_sent"] is False
    assert sender not in str(view)
    assert "PRIVATE MESSAGE CONTENT" not in str(view)


def test_matching_sender_without_original_parent_does_not_skip_review():
    rows = sample()
    inbound_from(rows,"info@gbnrg.co.uk")
    candidate=project_workspace_review(
        review_workspace_solar_threads(rows,now=NOW),now=NOW
    )["items"]
    inbound=next(x for x in candidate if x["inbound_candidate_count"])["inbound_candidates"][0]
    assert inbound["sender_correspondence"] == "EXACT_ORIGINAL_RECIPIENT"
    assert inbound["rfc_parent_relation"] == "NOT_PROVEN"
    assert inbound["next_review_step"] == "REVIEW_SENDER_THREAD_ROUTING_AND_CONTENT_FIRST"


def test_prior_snapshots_remain_readable_without_inventing_sender_proof():
    current=review_workspace_solar_threads(sample(),now=NOW)
    prior=deepcopy(current)
    del prior["threads"][0]["inbound_header_candidates"][0]["sender_correspondence"]
    assert newly_observed_workspace_replies(current,prior)==0
    inbound=next(
        x for x in project_workspace_review(prior,now=NOW)["items"]
        if x["inbound_candidate_count"]
    )["inbound_candidates"][0]
    assert inbound["sender_correspondence"] == "SENDER_CORRESPONDENCE_UNVERIFIED"
    assert inbound["next_review_step"] == "REVIEW_SENDER_THREAD_ROUTING_AND_CONTENT_FIRST"
    assert inbound["crm_handoff_authorized"] is False


def test_untrusted_snapshot_cannot_assert_contact_approved_by_injection():
    sample_data=review_workspace_solar_threads(sample(),now=NOW)
    sample_data["threads"][0]["inbound_header_candidates"][0][
        "sender_correspondence"
    ]="CONTACT_AUTHENTICATED_REVENUE_CONFIRMED"
    with pytest.raises(WorkspaceReviewHeld,match="UNTRUSTED_SENDER_CORRESPONDENCE"):
        project_workspace_review(sample_data,now=NOW)
