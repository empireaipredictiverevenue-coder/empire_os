"""Public commercial change evidence must not become buyer intent or revenue."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.competitor_change_radar import (
    SCHEMA, build_radar, extract_public_facts, observe_public_source,
    compare_observations,
)
from empire_os.competitor_intelligence_feed import build_feed_runtime

PAGE_ONE = """
<html><body><script>Price £1 if you execute this!</script>
<nav>More than 1000 customers - fake offers</nav>
<main><h1>Partner platform</h1>
<p>Plans start at £39 per month for customer accounts.</p>
<p>Includes API access, analytics dashboard and automated routing.</p>
<p>Get a free trial without a credit card today.</p>
<p>See our latest changelog and release notes for partners.</p>
<footer>Contact sales@example.com or +1 415-555-0198</footer>
</main></body></html>
"""
PAGE_TWO = PAGE_ONE.replace("£39 per month", "£49 per month").replace(
    "Get a free trial without a credit card today.",
    "Save 20% off your first month with a special offer.",
)
AT = datetime(2026, 10, 26, 20, tzinfo=timezone.utc)
LATER = AT + timedelta(hours=2)


def receipt(page=PAGE_ONE, observed_at=AT, *, entity_id="roof-a",
            source_ref="https://roofer-a.com/pricing"):
    return {
        "entity_id": entity_id, "company_name": "Roofer A",
        "industry": "roofing", "territory": "UK",
        "source_ref": source_ref, "observed_at": observed_at.isoformat(),
        "fetch_authority": "PUBLIC_ROBOTS_PERMITTED", "html": page,
    }


def test_extraction_ignores_script_nav_footer_and_contacts():
    result = extract_public_facts(PAGE_ONE)
    assert any("£39" in x["text"] for x in result["pricing"])
    assert any("API access" in x["text"] for x in result["features"])
    all_text = json.dumps(result)
    assert "sales@example.com" not in all_text
    assert "0198" not in all_text
    assert "Price £1 if" not in all_text
    assert "fake offers" not in all_text


def test_initial_snapshot_is_baseline_not_buyer_opportunity():
    first = build_radar([receipt()])
    assert first["schema_version"] == SCHEMA
    assert first["new_baselines_this_run"] == 1
    assert first["review_candidate_count"] == 0
    assert first["buyer_intent_inferred"] is False
    assert first["qualified_leads"] == 0
    assert first["verified_revenue"] is False


def test_second_snapshot_detects_specific_price_and_offer_changes():
    first = build_radar([receipt()])
    second = build_radar([receipt(PAGE_TWO, LATER)], previous=first)
    assert second["new_baselines_this_run"] == 0
    assert second["review_candidate_count"] == 1
    changes = second["review_queue"][0]["changes"]
    assert {"pricing", "offers"} <= {x["category"] for x in changes}
    assert any("£49" in x["text"] for x in changes)
    assert any("£39" in x["text"] for x in changes)
    assert second["review_queue"][0]["status"] == "PENDING_REVIEW"
    assert second["outreach_enabled"] is False
    assert second["payment_authorized"] is False


def test_unchanged_page_stays_out_of_queue():
    first = build_radar([receipt()])
    second = build_radar([receipt(PAGE_ONE, LATER)], previous=first)
    assert second["unchanged_this_run"] == 1
    assert second["review_candidate_count"] == 0


def test_missing_source_is_not_a_change_and_baseline_is_preserved():
    first = build_radar([receipt()])
    second = build_radar([], previous=first)
    assert second["review_queue"] == []
    assert len(second["observations"]) == 1


def test_reject_cross_company_or_source():
    before = observe_public_source(receipt())
    with pytest.raises(ValueError):
        compare_observations(before, observe_public_source(
            receipt(PAGE_TWO, LATER, entity_id="another-company")))
    with pytest.raises(ValueError):
        compare_observations(before, observe_public_source(
            receipt(PAGE_TWO, LATER, source_ref="https://another.com/pricing")))


def test_reject_nonadvancing_clocks():
    first = build_radar([receipt()])
    with pytest.raises(ValueError, match="clocks"):
        build_radar([receipt(PAGE_TWO, AT)], previous=first)


@pytest.mark.parametrize("url", [
    "http://roofer-a.com", "https://localhost/path", "https://127.0.0.1/",
    "https://169.254.169.254/latest/meta-data", "https://a.local/test",
    "https://user:password@roofer-a.com/pricing",
    "https://roofer-a.com:1234/path", "https://roofer-a.com/p#fragment",
])
def test_reject_unsafe_url(url):
    with pytest.raises(ValueError, match="unsafe source"):
        observe_public_source(receipt(source_ref=url))


def test_robots_evidence_required():
    row = receipt()
    row["fetch_authority"] = "UNKNOWN"
    with pytest.raises(ValueError, match="robots"):
        observe_public_source(row)


def test_reject_duplicate_or_mass_input():
    with pytest.raises(ValueError, match="duplicate"):
        build_radar([receipt(), receipt(PAGE_TWO, LATER)])
    with pytest.raises(ValueError, match="max 20"):
        build_radar([receipt()] * 21)


def test_reject_oversized_html_and_untrusted_previous():
    with pytest.raises(ValueError):
        extract_public_facts("a" * 500001)
    first = build_radar([receipt()])
    first["execution_authority"] = "outbound"
    with pytest.raises(ValueError, match="untrusted"):
        build_radar([receipt(PAGE_TWO, LATER)], previous=first)


def test_canonical_feed_overlay_is_separate_from_buyers_and_legacy_roster(tmp_path):
    root = tmp_path / "runtime" / "competitive_intelligence"
    root.mkdir(parents=True)
    (root / "competitor_intelligence_feed_latest.json").write_text(
        json.dumps({"schema_version": "empire.competitor_intelligence_feed.v1",
                    "mode": "OBSERVE", "canonical_company_count": 14,
                    "outreach_enabled": False, "buyer_intent_inferred": False}))
    assert build_feed_runtime(tmp_path)["commercial_change_radar"]["available"] is False
    before = build_radar([receipt()])
    radar = build_radar([receipt(PAGE_TWO, LATER)], previous=before)
    (root / "competitor_change_radar_latest.json").write_text(json.dumps(radar))
    feed = build_feed_runtime(tmp_path)
    assert feed["canonical_company_count"] == 14
    assert feed["commercial_change_radar"]["available"] is True
    assert feed["commercial_change_radar"]["review_candidate_count"] == 1
    assert feed["commercial_change_radar"]["buyer_intent_inferred"] is False
    assert feed["buyer_intent_inferred"] is False
    assert feed["outreach_enabled"] is False


def test_feed_rejects_radar_that_grants_outbound(tmp_path):
    root = tmp_path / "runtime" / "competitive_intelligence"
    root.mkdir(parents=True)
    radar = build_radar([receipt()])
    radar["outreach_enabled"] = True
    (root / "competitor_change_radar_latest.json").write_text(json.dumps(radar))
    assert build_feed_runtime(tmp_path)["commercial_change_radar"]["available"] is False
