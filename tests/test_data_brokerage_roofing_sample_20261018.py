"""Original roofing sample must not turn archived domain edges into live SEO claims."""
from __future__ import annotations

from pathlib import Path
import json

import pytest

from empire_os.data_brokerage_roofing_sample import (
    GRAPH_CANDIDATES, SCHEMA, build_roofing_competitor_sample,
    render_roofing_sample_markdown,
)
from empire_os.free_dataset_intelligence import SOURCE_REPORT


def test_real_reviewed_free_archive_produces_reproducible_founder_sample():
    report = build_roofing_competitor_sample()
    assert report["schema_version"] == SCHEMA
    assert report["approved_list_price_usd"] == 199
    assert report["original_service_code"] == "competitor_search_gap"
    assert report["source"]["historical_total_relationships"] == 1974
    assert report["source"]["historical_distinct_source_domains"] == 1870
    assert report["source"]["independently_verified_current_link_count"] == 0
    c = report["comparison"]
    assert c["nations_source_domain_count"] == 168
    assert c["tecta_source_domain_count"] == 212
    assert c["shared_source_domain_count"] == 25
    assert c["nations_only_count"] == 143
    assert c["tecta_only_count"] == 187
    assert c["union_source_domain_count"] == 355
    assert set(p["source_domain"] for p in
               c["historical_domain_samples_not_current_links"]) == {
        "iibec.org", "rooferscoffeeshop.com", "gaf.com", "roofingalliance.net"
    }
    assert report["customer_delivery_authorized"] is False
    assert report["prospect_or_buyer_verified"] is False
    assert report["recognized_revenue_verified"] is False
    assert report["raw_dataset_resale_authorized"] is False
    assert report["paid_api_calls"] == 0
    assert report["empiredb_writes"] is False
    text = render_roofing_sample_markdown(report)
    assert "$199" in text
    assert "143" in text and "187" in text and "25" in text
    assert "current SERP" not in text or "none" in text
    assert "zero verified backlinks" not in text or "none" in text
    assert "No outbound has been sent" in text
    assert report == build_roofing_competitor_sample()


def test_candidate_and_review_files_are_never_modified():
    before = (
        SOURCE_REPORT.read_bytes(),
        GRAPH_CANDIDATES.read_bytes(),
    )
    build_roofing_competitor_sample()
    assert SOURCE_REPORT.read_bytes() == before[0]
    assert GRAPH_CANDIDATES.read_bytes() == before[1]


def test_missing_or_mismatching_review_is_held(tmp_path):
    with pytest.raises(ValueError, match="review_evidence_failed"):
        build_roofing_competitor_sample(
            review_path=tmp_path/"missing.json")
    review = json.loads(SOURCE_REPORT.read_text())
    review["historical_domain_relationships"] = 1975
    p=tmp_path/"bad_review.json"
    p.write_text(json.dumps(review))
    with pytest.raises(ValueError,match="review_evidence_failed"):
        build_roofing_competitor_sample(review_path=p)


def test_historical_graph_never_claims_live_backlinks_or_source_pages(tmp_path):
    review=GRAPH_CANDIDATES
    original=json.loads(review.read_text())
    for prop,value in (
        ("verified_live_backlink",True),
        ("source_page_url","https://example.org/roofing"),
    ):
        change=json.loads(review.read_text())
        change["historical_domain_candidates"][0][prop]=value
        p=tmp_path/(prop+".json")
        p.write_text(json.dumps(change))
        with pytest.raises(ValueError,match="candidate_untrusted"):
            build_roofing_competitor_sample(candidates_path=p)
    assert len(original["historical_domain_candidates"])==1974


def test_nonmatching_target_count_or_cross_target_cohort_held(tmp_path):
    doc=json.loads(GRAPH_CANDIDATES.read_text())
    doc["historical_domain_candidates"][0]["target_domain"]="nationsroof.com"
    p=tmp_path/"tampered_target.json"
    p.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        build_roofing_competitor_sample(candidates_path=p)


def test_malformed_domain_rejected_but_existing_punycode_domain_accepted(tmp_path):
    original=json.loads(GRAPH_CANDIDATES.read_text())
    assert any(row["source_domain"].endswith(".xn--p1ai")
               for row in original["historical_domain_candidates"])
    doc=json.loads(GRAPH_CANDIDATES.read_text())
    doc["historical_domain_candidates"][0]["source_domain"]="not a domain\nsecret"
    p=tmp_path/"bad_domain.json"
    p.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match="candidate_untrusted"):
        build_roofing_competitor_sample(candidates_path=p)


def test_render_rejects_spoofed_release_to_customer():
    source=build_roofing_competitor_sample()
    for key,value in (
        ("customer_delivery_authorized",True),
        ("report_kind","DELIVERED"),
        ("approved_list_price_usd",1999),
    ):
        modified={**source,key:value}
        with pytest.raises(ValueError,match="untrusted_report_preflight"):
            render_roofing_sample_markdown(modified)
    modified=json.loads(json.dumps(source))
    modified["source"]["independently_verified_current_link_count"]=1
    with pytest.raises(ValueError,match="untrusted_report_preflight"):
        render_roofing_sample_markdown(modified)


def test_no_customer_contact_or_raw_graph_candidate_dump_in_sample():
    report=build_roofing_competitor_sample()
    output=render_roofing_sample_markdown(report)
    assert "verified customer" not in output.lower()
    assert "guaranteed rankings" not in output.lower()
    assert "contact@" not in output
    assert len(report["comparison"]["historical_domain_samples_not_current_links"]) <= 4
    assert "private phone" not in json.dumps(report).lower()
