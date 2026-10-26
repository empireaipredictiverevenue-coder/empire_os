"""Operator web-source research requires a baseline before change claims."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from empire_os.competitor_call_channel_atlas import SOURCE, build_atlas
from empire_os.competitor_call_source_watch import (
    inspect_sources, text_digest, _source_url,
)
from empire_os.competitor_intelligence_feed import build_feed_runtime

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 27, tzinfo=timezone.utc)
TEXT_A = "<html><body><main><h1>Publisher programme</h1>" + ("We accept direct organic search publisher calls for verified homeowner needs. " * 5) + "</main><script>random()</script></body></html>"
TEXT_B = "<html><body><main><h1>Publisher programme</h1>" + ("Now includes a different public acquisition channel and approval policy. " * 6) + "</main></body></html>"


def atlas():
    return build_atlas(json.loads((ROOT / SOURCE).read_text()), now=NOW)


def test_first_bounded_scan_creates_baselines_only():
    read = []
    a = atlas()
    state = inspect_sources(a, fetch=lambda u: (read.append(u), TEXT_A)[-1],
                            permitted=lambda url: True, now=NOW)
    assert len(read) == 2
    assert len({u.split("/")[2] for u in read}) == 2
    assert state["checked_this_cycle"] == 2
    assert len(state["first_baselines_this_cycle"]) == 2
    assert state["confirmed_text_changes_this_cycle"] == []
    assert state["existing_baseline_count"] == 2
    assert state["outreach_enabled"] is False


def test_changed_content_is_review_signal_only_not_traffic_proof():
    first = inspect_sources(atlas(), fetch=lambda url: TEXT_A,
                            permitted=lambda url: True, now=NOW)
    prior = {**first, "cursor": 0}
    changed = inspect_sources(atlas(), prior, fetch=lambda url: TEXT_B,
                              permitted=lambda url: True, now=NOW)
    assert len(changed["confirmed_text_changes_this_cycle"]) == 2
    assert all(x["review_required"] is True
               and x["buyer_intent_inferred"] is False
               for x in changed["confirmed_text_changes_this_cycle"])
    assert changed["competitor_traffic_or_conversion_measured"] is False
    assert changed["outreach_enabled"] is False


def test_robots_disallowed_preserves_existing_digest():
    baseline = inspect_sources(atlas(), fetch=lambda u: TEXT_A,
                               permitted=lambda u: True, now=NOW)
    prior = {**baseline, "cursor": 0}
    rerun = inspect_sources(atlas(), prior, fetch=lambda u: TEXT_B,
                            permitted=lambda u: False, now=NOW)
    assert rerun["confirmed_text_changes_this_cycle"] == []
    assert len(rerun["source_unavailable_this_cycle"]) == 2
    assert rerun["fingerprints"] == baseline["fingerprints"]


def test_visible_text_digest_ignores_script_only_changes():
    a = TEXT_A
    b = a.replace("random()", "different-random-script()")
    assert text_digest(a) == text_digest(b)
    assert text_digest("<html><body>too short</body></html>") is None


@pytest.mark.parametrize("bad", [
    "https://localhost/robots.txt",
    "http://www.elocal.com/affiliate-contact/",
    "https://127.0.0.1/private",
    "https://example.invalid/affiliate/",
])
def test_cannot_probe_non_allowlisted_or_non_https_url(bad):
    assert not _source_url(bad, "elocal")


def test_untrusted_operator_url_fails_before_network_access():
    a = atlas()
    a = copy.deepcopy(a)
    a["operator_profiles"][0]["sources"][0]["url"] = "https://localhost/"
    with pytest.raises(ValueError):
        inspect_sources(a, fetch=lambda _: pytest.fail("called fetch"),
                        permitted=lambda _: pytest.fail("called robots"),
                        now=NOW)


def test_strict_two_page_limit():
    with pytest.raises(ValueError):
        inspect_sources(atlas(), limit=9, now=NOW)


def test_existing_founder_feed_uses_read_only_geo_and_watch_summaries(tmp_path):
    runtime = tmp_path / "runtime/competitive_intelligence"
    runtime.mkdir(parents=True)
    (runtime / "competitor_intelligence_feed_latest.json").write_text(
        '{"canonical_company_count": 14, "metro": "denver, co"}')
    (runtime / "call_acquisition_atlas_latest.json").write_text(
        json.dumps(atlas()))
    geo = {
        "schema_version": "empire.competitor_call_geo_research.v1",
        "mode": "OBSERVE", "outbound_authorized": False,
        "execution_authority": "none",
        "fresh_for_research": True, "states": [{"state": "TX"}],
    }
    (runtime / "call_geo_research_latest.json").write_text(json.dumps(geo))
    watch = inspect_sources(atlas(), fetch=lambda _: TEXT_A,
                            permitted=lambda _: True, now=NOW)
    (runtime / "call_source_watch_latest.json").write_text(json.dumps(watch))
    original = build_feed_runtime(tmp_path)
    overlay = original["call_acquisition_intelligence"]
    assert original["canonical_company_count"] == 14
    assert original["metro"] == "denver, co"
    assert overlay["geo_research"]["available"] is True
    assert overlay["geo_research"]["states"][0]["state"] == "TX"
    assert overlay["source_change_watch"]["available"] is True
    assert "fingerprints" not in overlay["source_change_watch"]
