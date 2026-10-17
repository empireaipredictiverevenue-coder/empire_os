from empire_os.media_trend_fusion import (
    MediaTrendSignal,
    fuse_media_trend,
)
from empire_os.youtube_intelligence import (
    VIEW_COUNT_SEMANTICS_CHANGE_DATE,
    build_channel_baseline,
    build_outlier_candidates,
    normalize_youtube_video_observation,
    parse_iso8601_duration_seconds,
)


def test_youtube_duration_parser_preserves_unknowns():
    assert parse_iso8601_duration_seconds("PT15M33S") == 933
    assert parse_iso8601_duration_seconds("PT1H2M3S") == 3723
    assert parse_iso8601_duration_seconds(None) is None
    assert parse_iso8601_duration_seconds("not-a-duration") is None


def test_channel_baseline_requires_enough_observed_videos():
    weak = build_channel_baseline([100, 120], metric="views")
    assert weak.value is None
    assert weak.baseline_state == "INSUFFICIENT_EVIDENCE"

    ready = build_channel_baseline(
        [90, 100, 110, 1000],
        metric="views",
    )
    assert ready.value == 105.0
    assert ready.baseline_state == "OBSERVED_MEDIAN"


def test_public_youtube_observation_is_evidence_only():
    baseline = build_channel_baseline(
        [100, 100, 100, 100],
        metric="views",
    )
    row = normalize_youtube_video_observation(
        {
            "id": "video-1",
            "snippet": {
                "channelId": "channel-1",
                "title": "A breakout video",
                "description": "Public description",
                "publishedAt": "2026-09-20T12:00:00Z",
            },
            "contentDetails": {"duration": "PT8M10S"},
            "statistics": {
                "viewCount": "350",
                "likeCount": "25",
                "commentCount": "9",
            },
        },
        evidence_refs=("youtube:data-api:video-1",),
        channel_baseline=baseline,
    )

    assert row["duration_seconds"] == 490
    assert row["outlier_ratio"] == 3.5
    assert row["outlier_state"] == "OUTLIER_CANDIDATE"
    assert row["outlier_classification"] == "HEURISTIC"
    assert row["view_count_semantics"]["change_date"] == (
        VIEW_COUNT_SEMANTICS_CHANGE_DATE
    )
    assert row["buyer_intent_inferred"] is False
    assert row["commercial_intent_inferred"] is False
    assert row["revenue_inferred"] is False
    assert row["actual_revenue"] is False
    assert row["execution_authority"] == "none"


def test_owned_channel_prefers_engaged_views_when_baseline_matches():
    baseline = build_channel_baseline(
        [80, 100, 120],
        metric="engaged_views",
    )
    row = normalize_youtube_video_observation(
        {
            "id": "owned-1",
            "statistics": {"viewCount": "500"},
            "analytics": {
                "engaged_views": 250,
                "impressions": 5000,
                "impressions_ctr": 0.05,
                "watch_time_minutes": 800,
                "subscribers_gained": 12,
            },
        },
        evidence_refs=("youtube:analytics:owned-1",),
        owned_channel=True,
        channel_baseline=baseline,
    )

    assert row["primary_performance_metric"] == "engaged_views"
    assert row["primary_performance_value"] == 250
    assert row["outlier_ratio"] == 2.5
    assert row["owned_analytics"]["subscribers_gained"] == 12


def test_outlier_candidates_do_not_authorize_copying_or_action():
    rows = [
        {"video_id": "a", "outlier_ratio": 1.2},
        {"video_id": "b", "outlier_ratio": 4.5},
    ]
    result = build_outlier_candidates(rows)

    assert result["candidate_count"] == 1
    assert result["candidates"][0]["video_id"] == "b"
    assert result["classification"] == "HEURISTIC_CANDIDATE_ONLY"
    assert result["copy_competitor_creative_authorized"] is False
    assert result["public_action_performed"] is False
    assert result["execution_authority"] == "none"


def test_trend_fusion_requires_multiple_observed_sources_for_acceleration():
    result = fuse_media_trend(
        "AI lead generation",
        (
            MediaTrendSignal(
                topic="AI lead generation",
                source_family="youtube",
                velocity=0.7,
                evidence_refs=("youtube:1",),
            ),
            MediaTrendSignal(
                topic="AI lead generation",
                source_family="search",
                velocity=0.5,
                evidence_refs=("search:1",),
            ),
            MediaTrendSignal(
                topic="AI lead generation",
                source_family="community",
                velocity=0.4,
                evidence_refs=("community:1",),
            ),
        ),
    )

    assert result["trend_state"] == "MULTISOURCE_ACCELERATION"
    assert result["source_family_count"] == 3
    assert result["classification"] == "DESCRIPTIVE_HEURISTIC"
    assert result["high_confidence_claim_created"] is False
    assert result["buyer_intent_inferred"] is False
    assert result["revenue_inferred"] is False
    assert result["media_publish_authorized"] is False
    assert result["execution_authority"] == "none"


def test_published_chapter_parser_marks_ideas_as_unverified():
    from empire_os.youtube_intelligence import (
        extract_creator_chapters, youtube_inspiration_review,
    )
    description = (
        "00:00 Intro\n"
        "04:15 Give AI Clearer Instructions\n"
        "39:53 Add Animation Around Your Talking Video\n"
        "56:28 Put Your Face and Voice in Videos\n"
        "1:00:29 Build a Workflow From a YouTube Video\n"
    )
    rows = extract_creator_chapters(description)
    assert len(rows) == 5
    assert rows[2]["at_seconds"] == 2393
    assert rows[3]["at_seconds"] == 3388
    assert rows[-1]["at_seconds"] == 3629
    assert rows[3]["observed_video_content"] is False
    result = youtube_inspiration_review(
        video_id="j6JlWhDw-2w", creator="Paul Ponna Official",
        title="Make LONG AI Videos FREE & UNLIMITED",
        published_description=description,
    )
    assert "avatar_presenter" in result["workflow_topics"]
    assert "source_analysis" in result["workflow_topics"]
    assert result["transcript_obtained"] is False
    assert result["ideas_are_unverified_candidates"] is True
    assert result["production_auto_publish"] is False


def test_chapters_skip_bad_timestamps():
    from empire_os.youtube_intelligence import extract_creator_chapters
    rows = extract_creator_chapters(
        "00:00 Intro\n00:00 Duplicate\n00:87 Broken\n"
        "07:09 Teach With Your Own Examples\n04:15 Earlier Chapter\n"
    )
    assert len(rows) == 2
    assert rows[-1]["at"] == "07:09"


def test_commercial_opportunities_rank_real_baselines_but_not_fake_revenue():
    from datetime import datetime, timedelta, timezone
    from empire_os.youtube_intelligence import review_youtube_commercial_opportunities

    now = datetime.now(timezone.utc)
    published = (now - timedelta(days=2)).isoformat()
    baseline = build_channel_baseline([100, 110, 90, 100], metric="views")

    def observation(video, title, views):
        return normalize_youtube_video_observation({
            "id": video,
            "snippet": {"title": title, "channelId": "source-channel", "publishedAt": published},
            "statistics": {"viewCount": str(views)},
        }, evidence_refs=("youtube:data_api:" + video,), channel_baseline=baseline)

    rows = [
        observation("a", "UK Roofing Lead Generation Explained", 450),
        observation("b", "AI consultancy business automation UK", 270),
        observation("c", "Local news unrelated video", 99999),
        observation("d", "US Solar Installation Business Guide", 90),
    ]
    result = review_youtube_commercial_opportunities(
        rows,
        commercial_capacity={
            "roofing": {"status": "NO_VERIFIED_CAPACITY"},
            "ai_consultancy": {"status": "TERMS_PENDING"},
        },
        now=now,
    )
    assert result["candidate_count"] == 2
    assert [row["video_id"] for row in result["candidates"]] == ["a", "b"]
    top = result["candidates"][0]
    assert top["vertical"] == "roofing"
    assert top["outlier_ratio_descriptive"] == 4.5
    assert top["priority"] == "HIGH_SIGNAL_REVIEW"
    assert top["market_cues_not_territory_proof"] == ["UK"]
    assert top["suggested_next_step"] == "RESEARCH_EDUCATIONAL_CONTENT_NO_PAYABLE_LEAD_CLAIMS"
    assert top["revenue_proven"] is False
    assert top["public_publish_authorized"] is False
    assert result["commercial_activation_authorized"] is False
    assert result["performance_benchmark_against_vidiq_proven"] is False


def test_commercial_review_requires_fresh_comparable_evidence():
    from datetime import datetime, timedelta, timezone
    from empire_os.youtube_intelligence import review_youtube_commercial_opportunities

    now = datetime.now(timezone.utc)
    row = normalize_youtube_video_observation({
        "id": "a", "snippet": {
            "title": "UK Roofing Market Explained",
            "publishedAt": (now - timedelta(days=3)).isoformat(),
        },
        "statistics": {"viewCount": "20000"},
    }, evidence_refs=("youtube:video:a",))
    # No valid channel baseline must not become a winning competitor just
    # because the raw view count is large.
    packet = review_youtube_commercial_opportunities([row], now=now)
    assert packet["candidate_count"] == 0
    assert packet["excluded_reason_counts"]["NO_COMPARABLE_CHANNEL_BASELINE"] == 1
    row["channel_baseline"] = build_channel_baseline([100, 100, 100]).as_dict()
    row["outlier_ratio"] = 99999  # Malicious/stale pre-computed claim.
    row["observed_at"] = (now - timedelta(days=15)).isoformat()
    packet = review_youtube_commercial_opportunities([row, row], now=now)
    assert packet["candidate_count"] == 0
    assert packet["excluded_reason_counts"]["STALE_OR_UNKNOWN_OBSERVATION"] == 1
    assert packet["excluded_reason_counts"]["duplicate_video_id"] == 1


def test_commercial_review_notices_market_uncertainty_and_source_status():
    from datetime import datetime, timedelta, timezone
    from empire_os.youtube_intelligence import review_youtube_commercial_opportunities

    now = datetime.now(timezone.utc)
    row = normalize_youtube_video_observation({
        "id": "z",
        "snippet": {"title": "AI consulting market challenges",
                    "publishedAt": (now-timedelta(days=4)).isoformat()},
        "statistics": {"viewCount": "500"},
    }, evidence_refs=("youtube:data_api:z",),
       channel_baseline=build_channel_baseline([100, 100, 100]))
    packet = review_youtube_commercial_opportunities(
        [row], now=now,
        commercial_capacity={
            "ai_consultancy": {"status": "VERIFIED_CAPACITY", "evidence_refs": ["upstream:claimed"]},
        },
    )
    assert packet["candidate_count"] == 1
    selected = packet["candidates"][0]
    assert selected["priority"] == "RESEARCH_REVIEW"
    assert selected["market_cues_not_territory_proof"] == []
    assert selected["buyer_capacity_independently_verified_here"] is False
    assert selected["suggested_next_step"] == "REVIEW_EVIDENCE_AND_EDITORIAL_ANGLE"
    assert packet["automatic_publication_authorized"] is False


def test_commercial_review_empty_and_rejects_wrong_contract():
    from empire_os.youtube_intelligence import review_youtube_commercial_opportunities
    import pytest

    packet = review_youtube_commercial_opportunities([])
    assert packet["candidate_count"] == 0
    assert packet["revenue_recognized"] is False
    with pytest.raises(ValueError, match="normalized video"):
        review_youtube_commercial_opportunities([{"title": "roofing"}])
    with pytest.raises(ValueError, match="limit"):
        review_youtube_commercial_opportunities([], limit=0)


def test_commercial_cli_runs_offline_with_existing_youtube_intelligence(tmp_path, capsys):
    from datetime import datetime, timedelta, timezone
    import json
    from scripts.review_youtube_video_readonly import main

    now = datetime.now(timezone.utc)
    row = normalize_youtube_video_observation({
        "id": "offline-example",
        "snippet": {
            "title": "Solar customer questions in UK",
            "publishedAt": (now - timedelta(days=1)).isoformat(),
        },
        "statistics": {"viewCount": "340"},
    }, evidence_refs=["fixture:youtube:api"],
       channel_baseline=build_channel_baseline([100, 110, 90]))
    payload = tmp_path / "existing_media_packet.json"
    payload.write_text(json.dumps({"observations": [row],
                                   "commercial_capacity": {
                                       "solar": {"status": "NO_VERIFIED_CAPACITY"}
                                   }}))
    assert main(["--opportunities-file", str(payload)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["candidate_count"] == 1
    assert output["candidates"][0]["vertical"] == "solar"
    assert output["candidates"][0]["revenue_proven"] is False
    assert output["automatic_publication_authorized"] is False


def test_age_cohort_benchmark_uses_other_videos_in_same_channel_and_duration():
    from datetime import datetime, timedelta, timezone
    from empire_os.youtube_intelligence import (
        benchmark_youtube_channel_videos, review_youtube_commercial_opportunities,
    )

    now = datetime.now(timezone.utc)
    published = (now - timedelta(days=12)).isoformat()
    def api_row(video_id, views, channel="UCc", duration="PT6M", title="UK Roofing Homeowner Guidance"):
        return {
            "id": video_id, "source_adapter": "youtube_data_api", "read_only": True,
            "evidence_refs": ["youtube:data_api:video:" + video_id],
            "snippet": {"channelId": channel, "title": title, "publishedAt": published},
            "statistics": {"viewCount": str(views)},
            "contentDetails": {"duration": duration},
        }
    rows = [api_row("high", 1000), api_row("peer-a", 100),
            api_row("peer-b", 110), api_row("peer-c", 90),
            api_row("unrelated-channel", 100000, channel="UCdifferent"),
            api_row("short-format", 200000, duration="PT30S")]
    packet = benchmark_youtube_channel_videos(rows, now=now)
    assert packet["eligible_count"] == 6
    assert packet["compared_count"] == 4
    assert packet["outlier_candidate_count"] == 1
    assert packet["outlier_candidates"][0]["video_id"] == "high"
    assert packet["outlier_candidates"][0]["outlier_ratio"] == 10.0
    assert packet["outlier_candidates"][0]["cohort_comparison"]["peer_count_excluding_target"] == 3
    assert packet["outlier_candidates"][0]["cohort_comparison"]["full_age_normalisation_proven"] is False
    assert packet["omitted_reason_counts"]["INSUFFICIENT_MATCHED_PEERS"] == 2
    assert packet["vidiq_comparison_proven"] is False
    commercial = review_youtube_commercial_opportunities(
        packet["observations"], now=now,
    )
    assert commercial["candidate_count"] == 1
    assert commercial["candidates"][0]["vertical"] == "roofing"
    assert commercial["candidates"][0]["revenue_proven"] is False


def test_age_cohort_excludes_unverified_sources_and_old_or_incomplete_videos():
    from datetime import datetime, timedelta, timezone
    from empire_os.youtube_intelligence import benchmark_youtube_channel_videos
    import pytest

    now = datetime.now(timezone.utc)
    def api_row(video_id, days, *, source="youtube_data_api", duration="PT6M", views="100"):
        return {
            "id": video_id, "source_adapter": source, "read_only": True,
            "evidence_refs": ["youtube:data_api:video:" + video_id],
            "snippet": {"channelId": "c", "title": "Dental Marketing",
                        "publishedAt": (now - timedelta(days=days)).isoformat()},
            "statistics": ({"viewCount": views} if views is not None else {}),
            "contentDetails": {"duration": duration},
        }
    with pytest.raises(ValueError, match="official read-only"):
        benchmark_youtube_channel_videos([api_row("bad", 10, source="scraped")], now=now)
    with pytest.raises(ValueError, match="official video evidence"):
        row = api_row("badref", 10)
        row["evidence_refs"] = []
        benchmark_youtube_channel_videos([row], now=now)
    packet = benchmark_youtube_channel_videos(
        [api_row("outdated", 600), api_row("recent", 10),
         api_row("noduration", 10, duration=""), api_row("noviews", 10, views=None)],
        now=now,
    )
    assert packet["eligible_count"] == 1
    assert packet["compared_count"] == 0
    assert packet["omitted_reason_counts"]["OUTSIDE_AGE_BANDS"] == 1
    assert packet["omitted_reason_counts"]["NO_PUBLIC_VIEWS_OR_DURATION"] == 2


def test_age_cohort_cli_accepts_offline_official_packet(tmp_path, capsys):
    from datetime import datetime, timedelta, timezone
    import json
    from scripts.review_youtube_video_readonly import main

    now = datetime.now(timezone.utc)
    packet = {"observations": [
        {
            "id": f"test-{i}", "source_adapter": "youtube_data_api",
            "read_only": True, "evidence_refs": [f"youtube:data_api:video:test-{i}"],
            "snippet": {"channelId": "ch1", "title": "UK Solar Installation Guide",
                        "publishedAt": (now - timedelta(days=5)).isoformat()},
            "statistics": {"viewCount": str(900 if i == 0 else 100)},
            "contentDetails": {"duration": "PT6M"},
        }
        for i in range(4)
    ]}
    path = tmp_path / "official.json"
    path.write_text(json.dumps(packet))
    assert main(["--benchmark-file", str(path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["outlier_candidate_count"] == 1
    assert output["commercial_opportunity_review"]["candidate_count"] == 1
    assert output["commercial_opportunity_review"]["candidates"][0]["vertical"] == "solar"
    assert output["public_publish_authorized"] is False


def test_channel_benchmark_without_key_does_not_issue_network_requests(capsys):
    import json
    from scripts.review_youtube_video_readonly import main
    assert main(["--benchmark-channel", "UCany"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "UNAVAILABLE_API_KEY"
    assert result["data_api_calls_performed"] is False
