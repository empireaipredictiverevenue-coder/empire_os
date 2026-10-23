from datetime import datetime, timezone
import pytest
from empire_os.acquisition_yc_commercial_evidence import (
    review_six, _parse_role_links, _extract_detail, _evidence_hints, _fetch_yc_detail
)

NOW = datetime(2026, 10, 23, 9, tzinfo=timezone.utc)
URL = "https://www.ycombinator.com/companies/example/jobs"
TITLE = "Founding Sales"
DETAIL_URL = URL + "/AbC123-founding-sales"


def listing():
    return f'<html><a href="/companies/example/jobs/AbC123-founding-sales">{TITLE}</a></html>'.encode()


def detail():
    return (f'<html><head><title>{TITLE} at Example | Y Combinator</title></head>'
            '<body><h1>About the role</h1>We have far more enterprise inbound than we can handle. '
            'Build a repeatable sales process. Role is full-time employment.</body></html>').encode()


def fixture():
    r={"company":"Example","prospect_ref":"ref1", "niche":"B2B",
       "yc_original_listing_url":URL,
       "relevant_job_titles":[TITLE],"qualified_for_copy":False,
       "outbound_authorized":False,"independent_buying_trigger_verified":False,
       "candidate_product_code":"search_growth_command"}
    return {"schema_version":"empire.acquisition_yc_first_party_sweep.v1",
       "mode":"OBSERVE","outbound_authorized":False,"crm_writes":False,
       "records":[r]+[{
       "company":f"Other{i}", "prospect_ref":f"other{i}",
       "relevant_job_titles":[] } for i in range(19)]}


def catalog():
    return {"generated_at":NOW.isoformat(), "products":[{
        "product_code":"search_growth_command","active":True,"binding_terms_ready":True,
        "catalog_state":"VERIFIED","version_state":"VERIFIED"}]}


def test_parse_link_and_description():
    assert _parse_role_links(listing(), company_slug="example", relevant_titles=[TITLE]) == [(TITLE,DETAIL_URL)]
    text, digest = _extract_detail(detail(), company="Example", title=TITLE)
    assert len(digest)==64
    assert len(_evidence_hints(text)) == 2


def test_hiring_clues_never_promote_to_purchase():
    result = review_six(source=fixture(), catalog=catalog(), now=NOW,
                        listing_fetch=lambda _:listing(), detail_fetch=lambda _:detail())
    assert result["companies_reviewed"]==1
    assert result["companies_with_commercial_clues"]==1
    assert result["confirmed_procurement_signals"]==0
    assert result["authorized_decision_makers"]==0
    assert result["copy_review_eligible"]==0
    assert result["contact_review_ready"]==0
    assert result["canonical_research_hold_count"]==1
    assert result["canonical_qualification_contract"]=="empire.acquisition_pool_qualification.v1"
    assert result["records"][0]["canonical_qualification_status"]=="RESEARCH_ONLY"
    assert "dated_commercial_trigger_verified" in result["records"][0]["canonical_missing_evidence"]
    assert result["records"][0]["potential_product_code"] is None
    assert result["records"][0]["product_match_reason"] == "NO_DEFENSIBLE_PRODUCT_MATCH_YET"
    assert result["records"][0]["job_details"][0]["original_source_url"]==DETAIL_URL
    assert not result["outbound_authorized"]


def test_unready_product_not_mapped():
    result=review_six(source=fixture(),catalog={"generated_at":NOW.isoformat(),"products":[]},
                      now=NOW, listing_fetch=lambda _:listing(),detail_fetch=lambda _:detail())
    assert result["records"][0]["potential_product_code"] is None


def test_non_yc_link_not_accepted():
    with pytest.raises(ValueError):
        _fetch_yc_detail("https://evil.example.com/companies/example/jobs/x01234")


def test_company_mismatch_not_accepted():
    with pytest.raises(ValueError):
        _extract_detail(detail(), company="Other", title=TITLE)


def test_unverified_source_doesnt_get_promoted():
    source=fixture()
    source["records"][0]["outbound_authorized"]=True
    with pytest.raises(ValueError):
        review_six(source=source,catalog=catalog(),now=NOW,
                   listing_fetch=lambda _:listing(),detail_fetch=lambda _:detail())


def test_vertical_gtm_can_suggest_only_catalog_verified_related_product():
    c = catalog()
    c["products"] = [{"product_code":"competitor_search_gap",
                      "active":True,"binding_terms_ready":True,
                      "catalog_state":"VERIFIED","version_state":"VERIFIED"}]
    vertical_detail = (f'<html><head><title>{TITLE} at Example | Y Combinator</title></head>'
                       '<body>About the role We are developing vertical GTM playbooks '
                       'with deep competitive intelligence for enterprises.</body></html>').encode()
    r=review_six(source=fixture(),catalog=c,now=NOW,
                 listing_fetch=lambda _:listing(),detail_fetch=lambda _:vertical_detail)
    assert r["records"][0]["potential_product_code"]=="competitor_search_gap"
    assert not r["records"][0]["product_fit_verified"]
    assert not r["records"][0]["copy_review_eligible"]


def test_search_snippet_and_hiring_cannot_create_copy_authority():
    r = review_six(source=fixture(), catalog=catalog(), now=NOW,
                   listing_fetch=lambda _:listing(),detail_fetch=lambda _:detail())
    item=r["records"][0]
    assert item["company_identity_source"]=="https://www.ycombinator.com/companies/example"
    assert item["canonical_qualification_status"]=="RESEARCH_ONLY"
    assert not item["copy_review_eligible"]
    assert not item["contact_review_ready"]
    assert "copy.trigger" in item["canonical_missing_evidence"]
