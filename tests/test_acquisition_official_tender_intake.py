from copy import deepcopy
from datetime import datetime,timezone
from urllib.parse import urlparse,parse_qs
import pytest

from empire_os.data_exchange_procurement_context import OGL_V3
from empire_os.acquisition_official_tender_intake import (
    review_official_releases, combine_official_reviews, retrieve_bounded_notices
)
NOW=datetime(2026,10,23,11,0,tzinfo=timezone.utc)
CATA={"generated_at":NOW.isoformat(),"products":[
    {"product_code":"technical_search_audit","active":True,"binding_terms_ready":True,
    "catalog_state":"VERIFIED","version_state":"VERIFIED"},
    {"product_code":"search_growth_command","active":True,"binding_terms_ready":True,
    "catalog_state":"VERIFIED","version_state":"VERIFIED"}
]}


def example_notice(*,title="Technical SEO Audit",status="active",deadline="2026-11-30T12:00:00Z"):
    return {"id":"c058f7a4-2509-4e26-a9cd-4cbe83360000-999001",
            "ocid":"ocds-b5fd17-3211-4821-a00a-123456789abc",
            "date":"2026-10-22T10:00:00Z","tag":["tender"],
            "parties":[{"name":"Example Council","roles":["buyer"]}],
            "tender":{"title":title,"description":"We invite quotations from external suppliers.",
                      "status":status,"tenderPeriod":{"endDate":deadline},
                      "documents":[{"documentType":"tenderNotice",
                          "url":"https://www.contractsfinder.service.gov.uk/Notice/c058f7a4-2509-4e26-a9cd-4cbe83360000"}]}}


def pack(*releases):
    return {"publisher":{"name":"Cabinet Office"},"license":OGL_V3,
            "releases":list(releases)}


def test_original_government_rfp_yields_only_product_hypothesis():
    r=review_official_releases(source="contracts_finder",
        package=pack(example_notice()),catalog=CATA,now=NOW)
    assert r["explicit_current_service_requests"]==1
    item=r["records"][0]
    assert item["buyer_organisation"]=="Example Council"
    assert item["candidate_product_code"]=="technical_search_audit"
    assert item["external_purchasing_requirement_evidence"] is True
    assert item["buyer_interest_in_empire_ai_verified"] is False
    assert item["contact_permission_cleared"] is False
    assert r["outbound_authorized"] is False


def test_paid_media_and_generic_digital_marketing_are_held():
    a=example_notice(title="Media Planning and Buying Services")
    b=example_notice(title="Tourism Campaign - Digital Marketing")
    a["tender"]["description"]="Paid media campaign booking and optimization"
    for notice,expected in ((a,"NO_PAID_TRAFFIC_POLICY_HOLD"),(b,"DIGITAL_MARKETING_PAID_SCOPE_NOT_EXCLUDED_HOLD")):
        r=review_official_releases(source="contracts_finder",package=pack(notice),catalog=CATA,now=NOW)
        assert r["records"][0]["review_status"]==expected
        assert r["records"][0]["candidate_product_code"] is None


def test_closed_and_invalid_publisher_rejected():
    past=example_notice(deadline="2026-10-20T11:00:00Z")
    result=review_official_releases(source="contracts_finder",package=pack(past),catalog=CATA,now=NOW)
    assert not result["records"]
    with pytest.raises(ValueError):
        review_official_releases(source="contracts_finder",
            package={"publisher":{"name":"Unknown"},"license":OGL_V3,"releases":[]},
            catalog=CATA,now=NOW)


def test_amendment_deduplicates_latest_original_notice_by_ocid():
    earlier=example_notice()
    later=deepcopy(earlier)
    later["date"]="2026-10-23T10:00:00Z"
    later["tag"]=["tenderAmendment"]
    r1=review_official_releases(source="contracts_finder",package=pack(earlier),catalog=CATA,now=NOW)
    r2=review_official_releases(source="contracts_finder",package=pack(later),catalog=CATA,now=NOW)
    combined=combine_official_reviews([r1,r2])
    assert combined["open_service_requirements_identified"]==1
    assert combined["canonical_qualified"]==0
    assert combined["records"][0]["notice_release_at"].startswith("2026-10-23")
    assert combined["jev_observations_submitted"]==1
    assert not combined["outbound_authorized"]


def test_bounded_official_pagination_and_no_unsafe_redirects():
    calls=[]
    def source(url):
        calls.append(url)
        if len(calls)==1:
            return {"links":{"next":"https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search?cursor=abc"},"releases":[]}
        return {"releases":[]}
    out=retrieve_bounded_notices(source="contracts_finder",
        from_iso="2026-10-01T00:00:00+00:00",to_iso="2026-10-23T10:00:00+00:00",fetch=source)
    assert len(out)==2
    assert len(calls)==2
    assert parse_qs(urlparse(calls[0]).query)["stages"]==["tender"]


def test_offsite_pagination_denied():
    def fetch(url):
        return {"links":{"next":"https://unknown.com/Published/Notices/OCDS/Search?cursor=x"},"releases":[]}
    with pytest.raises(ValueError):
        retrieve_bounded_notices(source="contracts_finder",
            from_iso="2026-10-01T00:00:00+00:00",to_iso="2026-10-23T10:00:00+00:00",fetch=fetch)


def test_manual_read_only_owner_review_without_writes(tmp_path):
    import json
    from pathlib import Path
    from empire_os.acquisition_official_tender_intake import run_manual_official_intake
    catalog=tmp_path/"runtime/commercial_catalog/latest.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_text(json.dumps(CATA))
    request_urls=[]
    def fetch(url):
        request_urls.append(url)
        return pack(example_notice())
    result=run_manual_official_intake(repo=tmp_path,now=NOW,fetch=fetch,save=True)
    assert result["releases_inspected"]==2
    # Contracts Finder notice is valid; it deliberately cannot masquerade as
    # a differently identified Find a Tender notice.
    assert result["open_service_requirements_identified"]==1
    assert result["external_bid_submitted"] is False
    assert result["crm_writes"] is False
    assert result["canonical_qualified"]==0
    report=tmp_path/"runtime/acquisition_research/official_procurement_requirements_latest.json"
    assert report.exists()
    assert report.stat().st_mode & 0o777 == 0o600
    assert len(request_urls)==2



def test_official_land_guide_advert_estimate_and_sme_flag_not_bid_authority():
    from copy import deepcopy
    notice=example_notice(
        title="CA18567 - RFQ 2026/43 - Development of a Dublin Belfast Economic Corridor Investment Land Guide",
        deadline="2026-10-30T12:00:00Z",
    )
    notice["tender"]["value"]={"amount":25000,"currency":"GBP"}
    notice["tender"]["suitability"]={"sme":True}
    notice["tender"]["contractPeriod"]={
        "startDate":"2026-11-30T00:00:00Z",
        "endDate":"2027-03-31T23:59:59+01:00",
    }
    result=review_official_releases(source="contracts_finder",
        package=pack(notice),catalog=CATA,now=NOW)
    original=result["records"][0]
    assert original["published_estimated_value_gbp"]=="25000.00"
    assert original["published_value_source"]=="OFFICIAL_OCDS_TENDER_VALUE_NOT_BINDING"
    assert original["published_sme_suitable"] is True
    assert original["published_contract_start_at"]=="2026-11-30T00:00:00+00:00"
    assert original["published_contract_end_at"]=="2027-03-31T22:59:59+00:00"
    assert original["candidate_product_code"] is None
    assert original["bid_eligibility_verified"] is False
    assert result["outbound_authorized"] is False


@pytest.mark.parametrize("amount,currency",[
    (True,"GBP"), ("NaN","GBP"), ("Infinity","GBP"),
    ("-12","GBP"), ("12.345","GBP"), (25000,"USD"),
    (None,"GBP"), ("bad","GBP"),
])
def test_bad_or_non_gbp_original_tender_values_never_count_as_estimates(amount,currency):
    notice=example_notice(title="GDPR Data Audit")
    notice["tender"]["value"]={"amount":amount,"currency":currency}
    result=review_official_releases(source="contracts_finder",
        package=pack(notice),catalog=CATA,now=NOW)
    assert result["records"][0]["published_estimated_value_gbp"] is None
    assert result["records"][0]["bid_eligibility_verified"] is False
    assert result["outbound_authorized"] is False
