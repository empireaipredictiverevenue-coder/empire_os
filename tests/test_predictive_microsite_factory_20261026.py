"""Non-publishing acceptance tests for Predictive Microsite Factory + SlopMonster."""
from copy import deepcopy

import pytest

from empire_os.predictive_microsite_factory import (
    build_candidate, review_copy, review_geography, review_portfolio,
)


def candidate():
    return {
        "site_kind": "local_utility",
        "audience": "Chicago roof replacement researchers",
        "offer": "Review the territory research and ask questions before choosing a contractor.",
        "geography": {"market_id": "US-IL", "kind": "metro", "area": "Chicago, IL",
                      "evidence_refs": ["geo_registry:US-IL"]},
        "keyword_opportunity": {
            "keyword": "chicago roof replacement research",
            "cluster_key": "roofing_chicago",
            "intent_class": "territory", "product_key": "roofing_intel",
            "icp_key": "roofing_researcher", "funnel_stage": "consideration",
            "cta_key": "review-research", "territory_key": "US-IL",
            "evidence_refs": ["research-source:example-a"],
            "observed_demand": .5, "commercial_intent": .7, "product_fit": .6,
            "buyer_fit": .3, "coverage_gap": .4, "competitor_gap": .4,
            "ai_citation_gap": .3, "conversion_evidence": .0,
            "strategic_category_value": .6, "confidence": .3,
        },
        "headline": "Chicago roof replacement: research and coverage",
        "subhead": "Read the source notes behind this research and understand which questions still need answers.",
        "summary": "This page is a research preview. It does not claim contractor availability or approved leads.",
        "local_facts": [
            {"statement": "The EmpireOS geographic registry includes a Chicago market anchor.",
             "source_ref": "empire_os/geo_registry.py:US-IL",
             "checked_at": "2026-10-26T23:00:00Z"},
            {"statement": "The public roofing page describes a ZIP coverage check as planning guidance, not an accepted booking.",
             "source_ref": "apps/empire-public-site/src/app/roofing/page.tsx",
             "checked_at": "2026-10-26T23:00:00Z"},
        ],
    }


def test_factory_generates_noindex_branded_mobile_preview_and_draft_only():
    packet, html = build_candidate(candidate())
    assert packet["mode"] == "OBSERVE"
    assert packet["publishing_enabled"] is False
    assert packet["indexation_enabled"] is False
    assert packet["outbound_enabled"] is False
    assert packet["payments_enabled"] is False
    assert packet["keyword"]["opportunity"]["available"] is True
    assert packet["status"] in ("DRAFT_REVIEW", "HOLD_EVIDENCE")
    assert "SlopMonster" == packet["copy_audit"]["engine"]
    assert 'content="noindex,nofollow,noarchive"' in html
    assert 'name="viewport"' in html
    assert "prefers-reduced-motion" in html
    assert "Empire AI Predictive Revenue" in html
    assert "data:image/svg+xml;base64," in html
    assert len(packet["visual_qa"]["original_brand_logo_sha256"]) == 64
    assert "hero-layout" in html
    assert "<form" not in html.lower()
    assert "Internal draft" in html
    assert packet["visual_qa"]["browser_visual_review_complete"] is False


def test_slopmonster_detects_marketing_cliches_and_flags_copy():
    clean = review_copy("Six nails per shingle, every shingle.")
    bad = review_copy("Our seamless platform unlocks a game-changing journey.")
    assert clean["score"] == 5
    assert bad["score"] < 5
    spec = candidate()
    spec["headline"] = "Our seamless platform unlocks a game-changing journey."
    packet, _ = build_candidate(spec)
    assert packet["status"] == "HOLD_EVIDENCE"
    assert any("SlopMonster" in blocker for blocker in packet["blockers"])


def test_buyer_and_revenue_metrics_missing_remain_unknown_not_invented():
    spec = candidate()
    spec["keyword_opportunity"]["observed_demand"] = None
    packet, _ = build_candidate(spec)
    assert packet["keyword"]["opportunity"]["available"] is False
    assert "keyword scoring evidence incomplete" in packet["blockers"]


def test_area_code_not_treated_as_proven_without_geo_sources():
    spec = candidate()
    spec["geography"] = {"market_id": "US-IL", "kind": "us_zip", "area": "60601"}
    packet, _ = build_candidate(spec)
    assert not packet["market"]["region_verified"]
    assert "ZIP/postcode market membership not source-verified" in packet["blockers"]
    spec["geography"]["market_match_verified"] = True
    spec["geography"]["evidence_refs"] = ["some-source"]
    packet, _ = build_candidate(spec)
    assert packet["market"]["region_verified"]
    assert "ZIP/postcode market membership not source-verified" not in packet["blockers"]


@pytest.mark.parametrize("geography", [
    {"market_id": "US-IL", "kind": "us_zip", "area": "wrong"},
    {"market_id": "GB-LON", "kind": "us_zip", "area": "60601"},
    {"market_id": "US-IL", "kind": "uk_postcode", "area": "SW1A 1AA"},
    {"market_id": "GB-LON", "kind": "uk_postcode", "area": "garbage"},
    {"market_id": "unknown", "kind": "metro"},
    {"market_id": "GB-LON", "kind": "metro", "area": "Manchester"},
])
def test_invalid_territories_fail_closed(geography):
    with pytest.raises(ValueError):
        review_geography(geography)


def test_valid_uk_postcode_shape_still_requires_market_membership():
    item = review_geography({"market_id": "GB-LON", "kind": "uk_postcode", "area": "SW1A 1AA"})
    assert item["region_verified"] is False


def test_facts_need_two_distinct_sources():
    spec = candidate()
    spec["local_facts"][1]["source_ref"] = spec["local_facts"][0]["source_ref"]
    packet, _ = build_candidate(spec)
    assert any("distinct" in blocker for blocker in packet["blockers"])
    spec["local_facts"] = []
    packet, _ = build_candidate(spec)
    assert any("two independently" in blocker for blocker in packet["blockers"])


def test_html_injection_is_escaped():
    spec = candidate()
    spec["headline"] = "<img src=x onerror=alert(1)>"
    spec["local_facts"][0]["statement"] = "<script>alert(9)</script>"
    _, html = build_candidate(spec)
    assert "<script>alert" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;" in html


def test_portfolio_detects_duplicate_location_swaps():
    first = candidate()
    second = deepcopy(first)
    second["geography"] = {"market_id": "US-TX", "kind": "metro", "area": "Dallas, TX"}
    second["keyword_opportunity"]["territory_key"] = "US-TX"
    second["keyword_opportunity"]["keyword"] = "dallas roof replacement research"
    second["headline"] = first["headline"].replace("Chicago", "Dallas")
    second["local_facts"][0]["source_ref"] = "empire_os/geo_registry.py:US-TX"
    reviews = review_portfolio([first, second])
    assert len(reviews) == 2
    assert any("near-duplicate" in blocker for blocker in reviews[1]["blockers"])


def test_factory_does_not_execute_automatic_publish_or_form_work():
    spec = candidate()
    packet, html = build_candidate(spec)
    assert packet["required_approvals"]
    assert 'href="#research-method"' in html
    assert "https://" not in html
    assert "action=" not in html

def test_readonly_site_auditor_detects_html_headings_and_copy_patterns(tmp_path):
    from scripts.review_slopmonster_site_copy_20261026 import inspect_page, run
    path = tmp_path / "index.html"
    original = ('<!doctype html><html><head><meta name="viewport" '
                'content="width=device-width, initial-scale=1"></head>'
                '<body><main><h1>Our seamless platform unlocks everything</h1>'
                '<p>Send source notes for review.</p></main></body></html>')
    path.write_text(original)
    audit = inspect_page(path)
    assert audit["copy_audit"]["review_required"] is True
    assert audit["html_checks"]["h1_count_in_source"] == 1
    assert audit["html_checks"]["viewport_meta_detected"] is True
    assert audit["html_checks"]["javascript_rendered_content_checked"] is False
    report = run([path], max_files=3)
    assert report["flagged_pages"] == 1
    assert report["changed_files"] == 0
    assert path.read_text() == original


def test_site_auditor_caps_scan_and_rejects_unsupported_format(tmp_path):
    from scripts.review_slopmonster_site_copy_20261026 import inspect_page, run
    for n in range(2):
        (tmp_path / f"{n}.html").write_text("<main><h1>Title</h1></main>")
    with pytest.raises(ValueError, match="exceeds"):
        run([tmp_path], max_files=1)
    txt = tmp_path / "other.txt"
    txt.write_text("Text")
    with pytest.raises(ValueError, match="Only HTML"):
        inspect_page(txt)
