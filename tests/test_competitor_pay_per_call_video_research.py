"""Direct YouTube watchlist and operator excerpts, no inferred income or ads."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from empire_os.competitor_pay_per_call_video_research import SOURCE, build_research
from empire_os.competitor_intelligence_feed import build_feed_runtime

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 27, 13, 30, tzinfo=timezone.utc)

def original():
    return json.loads((ROOT / SOURCE).read_text())

def test_verified_operator_youtube_watchlist_and_first_party_transcript():
    result = build_research(original(), now=NOW)
    assert result["video_count"] == 7
    assert result["full_published_transcript_count"] == 1
    assert result["case_source_count"] == 3
    assert len(result["owner_research_actions"]) == 5
    assert result["video_watchlist"][0]["speaker"].startswith("Matthew")
    assert all(x["youtube_url"].startswith("https://www.youtube.com/watch?v=")
               for x in result["video_watchlist"])
    assert all(x["claims_audited_independently"] is False
               for x in result["video_watchlist"])
    assert all(x["full_youtube_video_verified_watched"] is False
               for x in result["video_watchlist"])
    assert result["full_video_playback_claimed"] is False
    assert result["live_competitor_traffic_share_established"] is False
    assert result["outbound_authorized"] is False
    assert result["paid_traffic_authorized"] is False

@pytest.mark.parametrize("edit", [
    lambda x: x["videos"][0].update(youtube_url="https://localhost/watch?v=aaaaaaaaaaa"),
    lambda x: x["videos"][0].update(youtube_url="http://www.youtube.com/watch?v=im5dlsEk9aQ"),
    lambda x: x["videos"][0].update(owner_url="https://wrong.example/claims"),
    lambda x: x["videos"][0].update(evidence_type="VIDEO_FULLY_WATCHED"),
    lambda x: x["videos"][0].update(priority=7),
    lambda x: x["videos"].pop(),
    lambda x: x["controls"].update(paid_traffic_enabled=True),
    lambda x: x["observed_results"].update(empire_payable_calls=99),
    lambda x: x.update(reviewed_at_utc="2028-01-01T00:00:00+00:00"),
])
def test_video_claims_and_authority_fail_closed(edit):
    src = copy.deepcopy(original())
    edit(src)
    with pytest.raises((ValueError, TypeError)):
        build_research(src, now=NOW)

def test_original_founder_competitor_reader_is_unchanged_and_video_attached(tmp_path):
    from empire_os.competitor_call_channel_atlas import SOURCE as ATLAS, build_atlas
    dest = tmp_path / "runtime/competitive_intelligence"
    dest.mkdir(parents=True)
    atlas = build_atlas(json.loads((ROOT / ATLAS).read_text()), now=NOW)
    (dest / "call_acquisition_atlas_latest.json").write_text(json.dumps(atlas))
    (dest / "competitor_intelligence_feed_latest.json").write_text(
        '{"canonical_company_count":14,"metro":"denver, co"}')
    report = build_research(original(), now=NOW)
    (dest / "pay_per_call_youtube_research_latest.json").write_text(json.dumps(report))
    feed = build_feed_runtime(tmp_path)
    assert feed["canonical_company_count"] == 14
    videos = feed["call_acquisition_intelligence"]["operator_video_research"]
    assert videos["available"] is True
    assert videos["video_count"] == 7
    assert videos["paid_traffic_authorized"] is False
    assert len(videos["owner_research_actions"]) == 5
    report["paid_traffic_authorized"] = True
    (dest / "pay_per_call_youtube_research_latest.json").write_text(json.dumps(report))
    assert build_feed_runtime(tmp_path)["call_acquisition_intelligence"][
        "operator_video_research"]["available"] is False
