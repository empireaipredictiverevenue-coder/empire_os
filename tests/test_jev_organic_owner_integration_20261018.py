"""Website owner merge: claimed entry and news campaign token stay independent.

All canonical EmpireDB I/O is injected, no live buyer or session data.
"""
from datetime import datetime, timezone

import pytest

from empire_os.first_party_sales_interest import CommercialInterestError, record_founder_led_interest

CID = "campaign_" + "a" * 24
TOKEN = {
    "campaign_id": CID,
    "asset_id": CID + ":linkedin",
    "source": "linkedin",
    "medium": "organic_social",
    "landing_path": "/industries/solar",
}
PARAMS = {
    "product_code": "consultancy_opportunity_assessment",
    "business_name": "Testing Example Ltd",
    "email": "research@example.test",
    "domain": "example.test",
    "industry": "Solar installation",
    "geography": "United Kingdom",
    "desired_outcome": "Assess a real service territory against source evidence.",
    "idempotency_key": "merge-rehearsal-test-001",
    "contact_consent": True,
}


def test_claimed_first_party_entry_and_organic_token_both_preserved(tmp_path):
    messages = []
    def canonical_rpc(method, path, *, payload):
        assert method == "POST"
        assert path == "/rest/v1/rpc/ingest_prospect_atomic"
        messages.append(payload)
        return {"decision": "created", "prospect": {"id": "test-id-only"}}

    result = record_founder_led_interest(
        **PARAMS,
        claimed_entry_page="/industries/solar",
        organic_touch=TOKEN,
        request=canonical_rpc,
        now=datetime(2026, 10, 18, 12, tzinfo=timezone.utc),
        root=tmp_path,
    )
    assert result["decision"] == "commercial_enquiry_recorded"
    assert len(messages) == 1
    proof = messages[0]["p_evidence"]
    assert proof["claimed_entry_page_review"]["path"] == "/industries/solar"
    assert proof["claimed_entry_page_review"]["organic_search_attributed"] is False
    assert proof["organic_campaign_touch"]["campaign_id"] == CID
    assert proof["organic_campaign_touch"]["session_verified"] is False
    assert proof["organic_campaign_touch"]["attributable_enquiry_confirmed"] is False
    assert proof["contact_consent_evidence"]["newsletter_or_ongoing_marketing_consent"] is False
    assert "youtube_buyer_declared_source" not in proof
    assert messages[0]["p_prospect"]["buy_signal_score"] == 0


@pytest.mark.parametrize("kwargs", [
    {"claimed_entry_page": "/admin"},
    {"organic_touch": {**TOKEN, "source": "unknown-source"}},
    {"contact_consent": False},
])
def test_untrusted_or_unconsented_combination_never_hits_db(tmp_path, kwargs):
    def no_write(*args, **kw):
        pytest.fail("unexpected_canonical_db_write")
    with pytest.raises(CommercialInterestError):
        record_founder_led_interest(
            **{**PARAMS, **kwargs},
            request=no_write,
            now=datetime(2026, 10, 18, 12, tzinfo=timezone.utc),
            root=tmp_path,
        )


def test_organic_utm_and_registry_youtube_claim_cannot_both_enter_canonical_db(tmp_path):
    def no_write(*args, **kwargs):
        pytest.fail("conflicting_campaigns_recorded_in_empiredb")
    with pytest.raises(CommercialInterestError, match="conflicting_campaign_source_claims"):
        record_founder_led_interest(
            **PARAMS,
            claimed_entry_page="/industries/solar",
            organic_touch=TOKEN,
            source_campaign_key="yt-" + "b" * 18,
            source_landing_url="https://empire-ai.co.uk/commercial",
            request=no_write,
            now=datetime(2026, 10, 18, 12, tzinfo=timezone.utc),
            root=tmp_path,
        )


def test_unregistered_youtube_claim_is_separate_from_valid_organic_token(tmp_path):
    def no_write(*args, **kwargs):
        pytest.fail("unregistered_youtube_campaign_recorded_in_empiredb")
    with pytest.raises(CommercialInterestError, match="commercial_youtube_source_unverified"):
        record_founder_led_interest(
            **PARAMS,
            source_campaign_key="yt-" + "b" * 18,
            source_landing_url="https://empire-ai.co.uk/commercial",
            request=no_write,
            now=datetime(2026, 10, 18, 12, tzinfo=timezone.utc),
            root=tmp_path,
        )
