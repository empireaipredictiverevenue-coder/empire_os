"""First-party commercial entry-page bridge: claim != verified attribution."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest

from empire_os.first_party_sales_interest import (
    CommercialInterestError, REVIEWED_ENTRY_PATHS, record_founder_led_interest,
)

NOW = datetime(2026,10,17,19,55,tzinfo=timezone.utc)


def payload(**overrides):
    data = dict(
        product_code="consultancy_opportunity_assessment",
        business_name="Test Example Ltd",
        email="buyer@example.test",
        domain="example.test",
        industry="Professional Services",
        geography="UK",
        desired_outcome="Review prospect conversion in the coming quarter.",
        contact_consent=True,
        idempotency_key="test-source-claim-20261017",
        now=NOW,
    )
    return {**data,**overrides}


def test_each_reviewed_page_only_creates_unverified_attribution_candidate(tmp_path):
    for page in sorted(REVIEWED_ENTRY_PATHS):
        calls=[]
        def mocked_rpc(method, route, *, payload):
            calls.append((method, route, payload))
            return {"decision":"created","prospect":{"id":"test-prospect"}}
        result=record_founder_led_interest(
            root=tmp_path,request=mocked_rpc,**payload(claimed_entry_page=page))
        assert result["decision"]=="commercial_enquiry_recorded"
        assert result["actual_revenue"] is False
        assert result["payment_action"] is False
        assert len(calls)==1
        verb,route,submitted=calls[0]
        assert (verb,route)==("POST","/rest/v1/rpc/ingest_prospect_atomic")
        assert submitted["p_prospect"]["contact_source"]=="first_party_commercial_sales_enquiry"
        review=submitted["p_evidence"]["claimed_entry_page_review"]
        assert review=={
            "path":page,
            "source":"UNVERIFIED_BROWSER_SUBMITTED",
            "organic_search_attributed":False,
            "search_click_proven":False,
            "qualified_buyer_proven":False,
            "marketing_consent_granted":False,
            "recognized_revenue_proven":False,
        }
        consent=submitted["p_evidence"]["contact_consent_evidence"]
        assert consent["source_url"]=="https://empire-ai.co.uk/commercial"
        assert consent["newsletter_or_ongoing_marketing_consent"] is False
        assert submitted["p_evidence"]["outreach_authority"]=="none"


@pytest.mark.parametrize("invalid",[
    "", " ", "/unknown","/roofing", "/commercial?utm_source=google",
    "/commercial#commercial-enquiry", "/commercial/",
    "//evil.com", "https://empire-ai.co.uk/industries/solar",
    "https://evil.example/commercial","/industries/solar?email=secret@example.test",
    "javascript:alert(1)", "/commercial\r\nPWN", "solar",
    [],{},100,False,
])
def test_invalid_or_external_claim_fails_before_database(tmp_path,invalid):
    def forbidden(*args,**kwargs):
        pytest.fail("untrusted source ever reached canonical DB")
    with pytest.raises(CommercialInterestError,match="invalid_claimed_entry_page"):
        record_founder_led_interest(
            root=tmp_path,request=forbidden,**payload(claimed_entry_page=invalid))


def test_existing_request_without_claim_still_works(tmp_path):
    seen=[]
    def stub(method,route,*,payload):
        seen.append(payload)
        return {"decision":"created","prospect":{"id":"existing-prospect"}}
    recorded=record_founder_led_interest(root=tmp_path,request=stub,**payload())
    assert recorded["decision"]=="commercial_enquiry_recorded"
    assert "claimed_entry_page_review" not in seen[0]["p_evidence"]
    assert recorded["actual_revenue"] is False


def test_consent_validation_remains_precedent(tmp_path):
    with pytest.raises(CommercialInterestError,match="specific_contact_consent_required"):
        record_founder_led_interest(
            root=tmp_path,
            request=lambda *_a,**_k:pytest.fail("no consent means no DB call"),
            **payload(contact_consent=False,claimed_entry_page="/industries/solar")
        )


def test_api_passes_browser_claim_to_existing_recorder_with_no_extra_side_effects(monkeypatch):
    import empire_os.self_serve_checkout_api as api
    invoked=[]
    def recorder(**kwargs):
        invoked.append(kwargs)
        return {
            "decision":"commercial_enquiry_recorded",
            "actual_revenue":False,
            "checkout_authorized":False,
            "execution_authority":"none",
        }
    monkeypatch.setattr(api,"record_founder_led_interest",recorder)
    client=TestClient(api.app)
    body={k:v for k,v in payload().items() if k != "now"}
    body["claimed_entry_page"]="/predictive-revenue"
    response=client.post("/v1/commercial/interests",json=body)
    assert response.status_code==200
    assert response.json()["actual_revenue"] is False
    assert len(invoked)==1 and invoked[0]["claimed_entry_page"]=="/predictive-revenue"


def test_api_is_backwards_compatible_and_holds_malformed_input(monkeypatch):
    import empire_os.self_serve_checkout_api as api
    captured=[]
    monkeypatch.setattr(
        api,"record_founder_led_interest",
        lambda **kwargs: (
            captured.append(kwargs) or
            {"decision":"commercial_enquiry_recorded","actual_revenue":False}
        ),
    )
    client=TestClient(api.app)
    body={k:v for k,v in payload().items() if k != "now"}
    original=client.post("/v1/commercial/interests",json=body)
    assert original.status_code==200
    assert captured[0]["claimed_entry_page"] is None
    body["claimed_entry_page"]="X"*100
    rejected=client.post("/v1/commercial/interests",json=body)
    assert rejected.status_code==422
    assert len(captured)==1
