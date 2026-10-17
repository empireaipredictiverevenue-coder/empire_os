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
