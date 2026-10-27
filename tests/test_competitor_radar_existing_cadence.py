"""The original scheduled opportunity-brief job owns the radar cadence."""
from __future__ import annotations

from pathlib import Path

from scripts.refresh_opportunity_brief_chain import (
    refresh_bounded_competitor_watch,
)


def test_without_original_atlas_no_fetch_or_ghost_market(tmp_path):
    result = refresh_bounded_competitor_watch(
        tmp_path, watch_fn=lambda _: (_ for _ in ()).throw(AssertionError("network"))
    )
    assert result["status"] == "ORIGINAL_OPERATOR_ATLAS_UNAVAILABLE"
    assert result["checked"] == 0


def test_active_original_atlas_calls_one_existing_watcher(tmp_path):
    atlas = tmp_path / "runtime" / "competitive_intelligence" / "call_acquisition_atlas_latest.json"
    atlas.parent.mkdir(parents=True)
    atlas.write_text("{}")
    invoked = []
    def watched(root: Path):
        invoked.append(root)
        return {"checked_this_cycle": 2,
                "source_unavailable_this_cycle": [{"reason": "ROBOTS_UNAVAILABLE_OR_DISALLOWED"}],
                "commercial_radar": {
                    "status": "OBSERVE_REVIEW_ONLY",
                    "pending_review_count": 1,
                    "new_review_candidate_count": 0,
                }}
    output = refresh_bounded_competitor_watch(tmp_path, watch_fn=watched)
    assert invoked == [tmp_path]
    assert output["status"] == "BOUNDED_ORIGINAL_WATCHER_REFRESHED"
    assert output["checked"] == 2
    assert output["radar_pending_review_count"] == 1
    assert output["radar_new_review_candidate_count"] == 0
    assert output["source_unavailable_count"] == 1
    assert output["outreach_enabled"] is False


def test_failed_watcher_does_not_break_opportunity_briefs(tmp_path):
    atlas = tmp_path / "runtime" / "competitive_intelligence" / "call_acquisition_atlas_latest.json"
    atlas.parent.mkdir(parents=True)
    atlas.write_text("{}")
    def broken(_: Path):
        raise ValueError("invalid source")
    result = refresh_bounded_competitor_watch(tmp_path, watch_fn=broken)
    assert result["status"] == "RESEARCH_REFRESH_FAILED"
    assert result["error_type"] == "ValueError"
    assert result["execution_authority"] == "none"
