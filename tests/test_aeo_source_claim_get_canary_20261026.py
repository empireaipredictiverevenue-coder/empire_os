"""Existing enquiry GET-only canary: detect exactly three AEO source links."""
from urllib.parse import quote
from scripts import probe_first_party_sales_http_readonly as canary

SOURCES=canary.AEO_APPROVED_ROUTES
SCRIPT="/_next/static/chunks/app/commercial/page-f7925fbc225b79ad.js"


def stub(*, changed_link=None, broken_script=False, broken_canonical=None,
         removed_from_js=None, external_script=False):
    visited=[]
    def fetch(path, maximum):
        visited.append((path,maximum))
        if path in SOURCES:
            expected="/commercial?entry="+quote(path,safe="")+"#commercial-enquiry"
            if path==changed_link:
                expected="/commercial"
            canonical="https://empire-ai.co.uk"+path.rstrip("/")
            if path==broken_canonical:
                canonical="https://example.invalid/unrelated"
            html=(f'<html><head><link rel="canonical" href="{canonical}"></head>'
                  f'<main><a href="{expected}">Discuss a scoped market assessment</a></main></html>')
            return 200,"text/html",html.encode()
        if path=="/commercial":
            bad='<script src="https://third.example/collect.js"></script>' if external_script else ''
            body='<html><head>'+bad+f'<script src="{SCRIPT}"></script></head></html>'
            return 200,"text/html",body.encode()
        if path==SCRIPT:
            if broken_script:
                return 404,"text/html",b"missing"
            routes=[s for s in SOURCES if s!=removed_from_js]
            contents=(" ".join(routes)+" /v1/checkout/commercial/interests").encode()
            return 200,"application/javascript",contents
        raise AssertionError("unapproved_get:"+path)
    return fetch,visited


def test_exact_published_three_and_browser_source_client_no_database():
    source, visited=stub()
    result=canary.inspect_aeo_claim_handoff(source)
    assert result["status"]=="THREE_AEO_TO_COMMERCIAL_SOURCE_LINKS_GET_VERIFIED"
    assert result["live_aeo_links_verified"]==3
    assert result["commercial_compiled_claim_support_verified"] is True
    assert [x[0] for x in visited]==[*SOURCES,"/commercial",SCRIPT]
    assert result["submitted_enquiries_verified"] is False
    assert result["real_browser_visits_verified"] is False
    assert result["canonical_sales_acquisitions_checked"] is False
    assert result["database_writes"] is False
    assert result["outbound_sent"] is False


def test_changed_aeo_link_fails_before_any_form_or_database():
    src,visited=stub(changed_link=SOURCES[1])
    out=canary.inspect_aeo_claim_handoff(src)
    assert out["status"]=="HELD"
    assert out["reason_code"]=="AEO_APPROVED_SOURCE_LINK_DRIFT"
    assert "/commercial" not in [x[0] for x in visited]


def test_broken_canonical_is_detected_even_when_link_exists():
    src,_=stub(broken_canonical=SOURCES[0])
    out=canary.inspect_aeo_claim_handoff(src)
    assert out["reason_code"]=="AEO_APPROVED_CANONICAL_DRIFT"


def test_missing_commercial_compiled_allowlist_blocks_claim_of_health():
    src,_=stub(removed_from_js=SOURCES[2])
    out=canary.inspect_aeo_claim_handoff(src)
    assert out["status"]=="HELD"
    assert out["reason_code"]=="ORIGINAL_COMMERCIAL_AEO_SOURCE_ALLOWLIST_DRIFT"
    assert out["commercial_compiled_claim_support_verified"] is False


def test_missing_compiled_script_is_held_and_no_lead_test_is_sent():
    src,_=stub(broken_script=True)
    out=canary.inspect_aeo_claim_handoff(src)
    assert out["status"]=="HELD"
    assert out["reason_code"]=="ORIGINAL_COMMERCIAL_COMPILED_JS_UNAVAILABLE"


def test_external_script_url_is_never_followed():
    src,visited=stub(external_script=True)
    out=canary.inspect_aeo_claim_handoff(src)
    assert out["status"]=="THREE_AEO_TO_COMMERCIAL_SOURCE_LINKS_GET_VERIFIED"
    assert not any(x[0].startswith("http") for x in visited)


def test_daily_lifecycle_uses_existing_canary_with_bounded_nonblocking_result(monkeypatch):
    from scripts import review_original_seo_action_lifecycle_20261026 as daily
    from scripts import review_live_organic_buyer_journey_20261024 as journey
    from empire_os import gtm_ops_first_sale_source as ops
    from tests.test_original_seo_action_lifecycle_20261026 import sources,NOW
    from pathlib import Path
    week,index,buyer,release=sources()
    def documents(path):
        if path.name.startswith("google-index-"):return index
        if path.name.startswith("weekly_seo_growth_actions_"):return week
        return release
    monkeypatch.setattr(daily,"_trusted_json",documents)
    monkeypatch.setattr(daily,"_latest_weekly",
                        lambda:Path("weekly_seo_growth_actions_2026-10-26.json"))
    monkeypatch.setattr(journey,"review",lambda:buyer)
    monkeypatch.setattr(ops,"observe_owner_ops_first_sale",
                        lambda root,now:{"source_count_verified":False})
    from scripts import probe_first_party_sales_http_readonly as actual
    tested_function=canary.inspect_aeo_claim_handoff
    def no_network_canary():
        return tested_function(stub()[0])
    monkeypatch.setattr(actual,"inspect_aeo_claim_handoff",no_network_canary)
    safe=lambda url:{"status":"TESTED_READ_ONLY_NO_MUTATION","http_status":200,
                     "self_canonical":True,"html_content_type":True,
                     "indexable":True}
    report=daily.build_run(observed=NOW,get=safe)
    assert report["aeo_source_handoff_canary"]["status"]=="THREE_AEO_TO_COMMERCIAL_SOURCE_LINKS_GET_VERIFIED"
    assert report["canonical_sitewide_sales_evidence"]["sitewide_sales_acquisitions"] is None
    assert report["database_writes"] is False
    assert report["outbound_sent"] is False
