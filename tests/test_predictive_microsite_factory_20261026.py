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

def test_official_chicago_pilot_has_useful_checklist_and_genuine_sources():
    import json
    from pathlib import Path
    spec = json.loads(
        (Path(__file__).parent / "fixtures" /
         "chicago_roofing_60601_official_research_pilot_20261027.json").read_text()
    )["candidates"][0]
    packet, html = build_candidate(spec)
    assert packet["locally_useful_research_steps"] == 5
    assert packet["linked_official_source_count"] == 5
    assert html.count("Read official source") == 5
    assert 'href="https://chicago.gov/' in html
    assert 'href="https://idfpr.illinois.gov/checklicense.html"' in html
    assert 'id="utility-title"' in html
    assert "source_claims_independently_confirmed_by_site_owner" in packet
    assert packet["source_claims_independently_confirmed_by_site_owner"] is False
    assert packet["status"] == "HOLD_EVIDENCE"
    assert packet["copy_audit"]["score"] == 5
    assert packet["publishing_enabled"] is False
    assert "<form" not in html.lower()


@pytest.mark.parametrize("url", [
    "http://chicago.gov/permits", "https://fakechicago.gov/permit",
    "https://chicago.gov.example.org/permits",
    "javascript:alert(1)",
    "https://chicago.gov/permits?tracking=123",
    "https://user:password@chicago.gov/permits",
])
def test_pilot_official_links_require_exact_approved_https_government_host(url):
    spec = candidate()
    spec["local_facts"][0]["official_url"] = url
    with pytest.raises(ValueError):
        build_candidate(spec)


def test_official_links_and_steps_escape_script_and_dangerous_markup():
    spec = candidate()
    spec["local_facts"][0]["official_url"] = "https://chicago.gov/permits"
    spec["research_steps"] = [
        "Compare written bids before hiring anyone.",
        "Review permit status for the property, not just the ZIP.",
        "Check <script>alert(1)</script> with the original government record.",
    ]
    packet, html = build_candidate(spec)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert packet["publishing_enabled"] is False


def test_duplicate_checklist_cannot_create_fake_distinct_utility():
    spec = candidate()
    spec["research_steps"] = [
        "Check the official building permit record.",
        "Check the official building permit record.",
        "Ask for a written price comparison.",
    ]
    with pytest.raises(ValueError, match="duplicate steps"):
        build_candidate(spec)

def test_citywide_chicago_candidate_keeps_real_jurisdiction_and_keyword_unknown():
    import json
    from pathlib import Path
    p = Path(__file__).parent / "fixtures" / "chicago_city_roofing_official_research_pilot_20261027.json"
    spec = json.loads(p.read_text())["candidates"][0]
    item, html = build_candidate(spec)
    assert item["market"]["kind"] == "metro"
    assert item["market"]["region_verified"] is True
    assert item["copy_audit"]["score"] == 5
    assert item["linked_official_source_count"] == 5
    assert item["locally_useful_research_steps"] == 5
    assert "keyword scoring evidence incomplete" in item["blockers"]
    assert item["status"] == "HOLD_EVIDENCE"
    assert 'content="noindex,nofollow,noarchive"' in html
    assert item["visual_qa"]["brand_public_distribution_approved_by_owner"] is False


def test_private_original_logo_requires_exact_existing_owner_custodied_bytes(tmp_path, monkeypatch):
    from empire_os.predictive_microsite_factory import _original_brand_image
    monkeypatch.setenv("EMPIRE_MICROSITE_PRIVATE_APPROVED_LOGO", str(tmp_path / "missing.png"))
    with pytest.raises(ValueError, match="regular existing"):
        _original_brand_image()
    fake = tmp_path / "other.png"
    fake.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 128)
    monkeypatch.setenv("EMPIRE_MICROSITE_PRIVATE_APPROVED_LOGO", str(fake))
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        _original_brand_image()


def test_default_public_logo_does_not_impersonate_owner_signoff(monkeypatch):
    from empire_os.predictive_microsite_factory import _original_brand_image
    monkeypatch.delenv("EMPIRE_MICROSITE_PRIVATE_APPROVED_LOGO", raising=False)
    src, digest = _original_brand_image()
    assert src.startswith("data:image/svg+xml;base64,")
    assert len(digest) == 64


def test_citywide_roofing_facts_match_source_scope_without_inventing_demand():
    import json
    from pathlib import Path
    spec = json.loads(
        (Path(__file__).parent / "fixtures" /
         "chicago_city_roofing_official_research_pilot_20261027.json").read_text()
    )["candidates"][0]
    source_statements = " ".join(row["statement"] for row in spec["local_facts"])
    assert "25% of roof area" in source_statements
    assert "one existing covering layer" in source_statements
    assert "36 months" in source_statements
    assert "Illinois Roofing Contractor license" in source_statements
    assert "ZIP Code Tabulation Areas" in source_statements
    assert spec["keyword_opportunity"]["observed_demand"] is None
    assert spec["geography"]["kind"] == "metro"
    assert "buyer_signal" not in spec
    packet, html = build_candidate(spec)
    assert packet["copy_audit"]["score"] == 5
    assert packet["status"] == "HOLD_EVIDENCE"
    assert packet["publishing_enabled"] is False
    assert "25% of roof area" in html
    assert "36 months" in html
    assert "<form" not in html.casefold()
