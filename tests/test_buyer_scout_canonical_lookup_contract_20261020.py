"""Canonical exact-domain requests must remain unexecuted, scoped and PII-free."""
from copy import deepcopy

import pytest

from empire_os.buyer_scout_canonical_dedupe_request_v1 import (
    prepare_canonical_lookup_requests,
)


def sample():
    domain = "roofstampa.com"
    return {
        "schema_version": "empire.buyer_scout.source_verification_queue.v1",
        "mode": "OBSERVE",
        "execution_authority": "NONE",
        "owner": "existing_buyer_scout",
        "canonical_crm_records_created": 0,
        "verified_revenue_buyers": 0,
        "outbound_messages_sent": 0,
        "tasks_dispatched_to_live_buyer_scout": 0,
        "search_api_results_persisted": False,
        "ready_first_party_verification_count": 1,
        "held_site_count": 1,
        "historical_official_context_count": 1,
        "ready_first_party_verification_tasks": [{
            "public_company_domain": domain,
            "stable_review_task_id": "a" * 24,
            "source_content_sha256": "b" * 64,
            "market": "tampa, fl",
            "sector": "roofing",
            "state": "OWNER_REVIEW_NOT_DELIVERED",
            "contact_allowed": False,
            "can_create_customer": False,
            "commercial_claims_verified": False,
            "requires_canonical_empiredb_duplicate_and_suppression_check": True,
        }],
        "held_site_tasks": [{}],
        "historical_official_company_context": [{}],
    }


def test_exact_domain_request_is_not_clearance():
    result = prepare_canonical_lookup_requests(sample())
    assert result["lookup_request_count"] == 1
    assert result["canonical_database_read_performed"] is False
    assert result["canonical_lookup_results_verified"] == 0
    assert result["canonical_no_match_claims"] == 0
    assert result["crm_writes"] == 0
    assert result["outbound_sent"] == 0
    assert not result["outreach_authorized"]
    row = result["lookup_requests"][0]
    assert row["match_state"] == "UNKNOWN_NOT_CHECKED"
    assert row["selector"] == "EXACT_NORMALIZED_PUBLIC_COMPANY_DOMAIN"
    assert row["public_company_domain"] == "roofstampa.com"
    assert row["return_email_addresses"] is False
    assert row["return_phone_numbers"] is False
    assert row["can_send_message"] is False


def test_stable_ids_and_duplicate_fails_closed():
    source = sample()
    result = prepare_canonical_lookup_requests(source)
    assert result == prepare_canonical_lookup_requests(source)
    source["ready_first_party_verification_tasks"].append(
        deepcopy(source["ready_first_party_verification_tasks"][0])
    )
    source["ready_first_party_verification_count"] = 2
    with pytest.raises(ValueError, match="INVALID_OR_DUPLICATE"):
        prepare_canonical_lookup_requests(source)


@pytest.mark.parametrize("tamper", [
    lambda x: x.update({"verified_revenue_buyers": 1}),
    lambda x: x.update({"outbound_messages_sent": 1}),
    lambda x: x.update({"canonical_crm_records_created": 1}),
    lambda x: x["ready_first_party_verification_tasks"][0].update({"contact_allowed": True}),
    lambda x: x["ready_first_party_verification_tasks"][0].update({"can_create_customer": True}),
    lambda x: x["ready_first_party_verification_tasks"][0].update({"source_content_sha256": "invalid"}),
    lambda x: x["ready_first_party_verification_tasks"][0].update({"market": "london"}),
    lambda x: x["ready_first_party_verification_tasks"][0].update({"state": "BUYER_APPROVED"}),
])
def test_invalid_or_forged_authority_rejected(tamper):
    value = sample()
    tamper(value)
    with pytest.raises(ValueError):
        prepare_canonical_lookup_requests(value)
