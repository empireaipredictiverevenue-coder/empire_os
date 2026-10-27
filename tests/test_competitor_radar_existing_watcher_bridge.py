"""Radar integration must reuse original watcher HTML and cannot add requests."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from empire_os.competitor_call_channel_atlas import SOURCE, build_atlas
from empire_os.competitor_call_source_watch import refresh as original_refresh
from empire_os.competitor_intelligence_feed import build_feed_runtime

ROOT = Path(__file__).resolve().parents[1]
HTML_A = "<html><body><h1>Buyer partner programme</h1>" + (
    "<p>Get automated routing with API access and a dashboard.</p>" * 5
) + "</body></html>"
HTML_B = HTML_A.replace(
    "Get automated routing with API access and a dashboard.",
    "Get automated routing with API access and a new feature dashboard priced at £49 per month.",
)


def _root(tmp_path):
    p = tmp_path / "runtime" / "competitive_intelligence"
    p.mkdir(parents=True)
    atlas = build_atlas(json.loads((ROOT / SOURCE).read_text()),
                        now=datetime(2026, 10, 27, tzinfo=timezone.utc))
    (p / "call_acquisition_atlas_latest.json").write_text(json.dumps(atlas))
    (p / "competitor_intelligence_feed_latest.json").write_text(
        json.dumps({"schema_version": "empire.competitor_intelligence_feed.v1",
                    "mode": "OBSERVE", "canonical_company_count": 14,
                    "buyer_intent_inferred": False, "outreach_enabled": False}))
    return p


def test_one_original_fetch_creates_original_digest_and_radar(tmp_path):
    p = _root(tmp_path)
    calls = []
    def fetch(url):
        calls.append(url)
        return HTML_A
    first = original_refresh(tmp_path, permitted=lambda _: True, fetch=fetch)
    assert len(calls) == 2
    assert first["existing_baseline_count"] == 2
    assert first["commercial_radar"]["observed_this_run"] == 2
    assert first["commercial_radar"]["review_candidate_count"] == 0
    radar = json.loads((p / "competitor_change_radar_latest.json").read_text())
    assert radar["source_fetch_mode"] == "REUSED_ORIGINAL_SOURCE_WATCH"
    assert radar["new_baselines_this_run"] == 2
    assert len(radar["observations"]) == 2
    assert "html" not in json.dumps(radar)
    feed = build_feed_runtime(tmp_path)
    assert feed["commercial_change_radar"]["available"] is True
    assert feed["canonical_company_count"] == 14
    assert feed["outreach_enabled"] is False


def test_reobserved_price_change_requires_review_not_outreach(tmp_path):
    p = _root(tmp_path)
    original_refresh(tmp_path, permitted=lambda _: True, fetch=lambda _: HTML_A)
    watched = p / "call_source_watch_latest.json"
    old = json.loads(watched.read_text())
    old["cursor"] = 0
    watched.write_text(json.dumps(old))
    second = original_refresh(tmp_path, permitted=lambda _: True, fetch=lambda _: HTML_B)
    radar = json.loads((p / "competitor_change_radar_latest.json").read_text())
    assert second["commercial_radar"]["review_candidate_count"] == 2
    assert radar["review_candidate_count"] == 2
    assert all(row["research_priority"] == "PRICING_OR_OFFER_REVIEW"
               for row in radar["review_queue"])
    assert radar["qualified_leads"] == 0
    assert radar["outreach_enabled"] is False


def test_original_source_failure_does_not_erase_radar_baselines(tmp_path):
    p = _root(tmp_path)
    original_refresh(tmp_path, permitted=lambda _: True, fetch=lambda _: HTML_A)
    second = original_refresh(tmp_path, permitted=lambda _: False,
                              fetch=lambda _: (_ for _ in ()).throw(AssertionError("fetch")))
    radar = json.loads((p / "competitor_change_radar_latest.json").read_text())
    assert second["commercial_radar"]["observed_this_run"] == 0
    assert len(radar["source_failures_this_run"]) == 2
    assert len(radar["observations"]) == 2
    assert radar["review_candidate_count"] == 0


def test_bad_radar_does_not_block_original_source_monitor(tmp_path):
    p = _root(tmp_path)
    dst = p / "competitor_change_radar_latest.json"
    dst.write_text('{"schema_version":"empire.competitor_change_radar.v1","mode":"OBSERVE","execution_authority":"send"}')
    result = original_refresh(tmp_path, permitted=lambda _: True, fetch=lambda _: HTML_A)
    assert result["commercial_radar"]["status"] == "NOT_PUBLISHED"
    assert json.loads((p / "call_source_watch_latest.json").read_text())["existing_baseline_count"] == 2
    assert json.loads(dst.read_text())["execution_authority"] == "send"
