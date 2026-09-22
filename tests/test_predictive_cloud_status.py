from datetime import datetime, timezone
import json

from empire_os.predictive_cloud_status import build_predictive_cloud_status


def write_json(root, relative, payload):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_status_preserves_missing_components_as_unavailable(tmp_path):
    result = build_predictive_cloud_status(
        tmp_path,
        now=datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc),
    )
    assert result["available_component_count"] == 0
    assert "revenue_pulse" in result["unavailable_components"]
    assert result["execution_authority"] == "none"


def test_status_reports_fresh_and_stale_without_inventing_health(tmp_path):
    write_json(
        tmp_path,
        "runtime/revenue_pulse/latest.json",
        {
            "generated_at": "2026-09-22T20:55:00+00:00",
            "pulse_state": "conversation_blocked",
            "highest_priority_blocker": "buyer_conversation",
            "recognized_revenue_truth": {
                "recognized_revenue_cents": 0,
                "realized_gp_cents": 0,
            },
        },
    )
    write_json(
        tmp_path,
        "runtime/market_sweeps/revenue_gps_latest.json",
        {
            "generated_at": "2026-09-22T15:00:00+00:00",
            "market_count": 4,
            "research_queue": [],
        },
    )
    result = build_predictive_cloud_status(
        tmp_path,
        now=datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc),
    )
    assert result["components"]["revenue_pulse"]["freshness"] == "fresh"
    assert result["components"]["market_gps"]["freshness"] == "stale"
    assert (
        result["components"]["revenue_pulse"]["summary"]
        ["recognized_revenue_cents"]
        == 0
    )
    assert result["revenue_recognized_by_status"] is False


def test_status_exposes_opportunity_normalization_progress(tmp_path):
    write_json(
        tmp_path,
        "runtime/opportunity_factory/normalized_signals_latest.json",
        {
            "generated_at": "2026-09-22T20:58:00+00:00",
            "candidate_count": 24,
            "candidates_with_any_normalized_score": 4,
            "total_normalized_scores": 13,
            "search_result_counts_used_as_scores": False,
        },
    )
    result = build_predictive_cloud_status(
        tmp_path,
        now=datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc),
    )
    summary = result["components"]["opportunity_normalizer"]["summary"]
    assert summary["candidate_count"] == 24
    assert summary["candidates_with_any_normalized_score"] == 4
    assert summary["total_normalized_scores"] == 13
    assert summary["search_result_counts_used_as_scores"] is False
