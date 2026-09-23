from urllib.parse import parse_qs, urlparse

import pytest

from empire_os.youtube_read_adapter import (
    YouTubeAnalyticsReadAdapter,
    YouTubeDataReadAdapter,
    youtube_read_adapter_contract,
)


def test_public_video_adapter_is_read_only_and_preserves_evidence():
    calls = []

    def transport(url, headers, timeout):
        calls.append((url, dict(headers), timeout))
        return {
            "items": [
                {
                    "id": "video-1",
                    "snippet": {
                        "channelId": "channel-1",
                        "title": "Observed video",
                    },
                    "statistics": {
                        "viewCount": "1234",
                    },
                    "contentDetails": {
                        "duration": "PT4M20S",
                    },
                }
            ]
        }

    adapter = YouTubeDataReadAdapter(
        api_key="test-key",
        transport=transport,
    )
    rows = adapter.videos(["video-1"])

    assert len(rows) == 1
    assert rows[0]["id"] == "video-1"
    assert rows[0]["read_only"] is True
    assert rows[0]["evidence_refs"] == [
        "youtube:data_api:video:video-1"
    ]

    url, headers, _ = calls[0]
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.path.endswith("/youtube/v3/videos")
    assert query["part"] == ["snippet,contentDetails,statistics"]
    assert query["id"] == ["video-1"]
    assert query["key"] == ["test-key"]
    assert headers["Accept"] == "application/json"


def test_owned_analytics_adapter_uses_authorized_read_query():
    calls = []

    def transport(url, headers, timeout):
        calls.append((url, dict(headers), timeout))
        return {
            "columnHeaders": [
                {"name": "video"},
                {"name": "engagedViews"},
                {"name": "views"},
                {"name": "estimatedMinutesWatched"},
                {"name": "averageViewDuration"},
                {"name": "averageViewPercentage"},
                {"name": "subscribersGained"},
                {"name": "subscribersLost"},
            ],
            "rows": [
                [
                    "video-1",
                    900,
                    1000,
                    6000,
                    360,
                    60.0,
                    42,
                    2,
                ]
            ],
        }

    adapter = YouTubeAnalyticsReadAdapter(
        access_token="secret-token",
        transport=transport,
    )
    rows = adapter.top_videos(
        start_date="2026-09-01",
        end_date="2026-09-23",
    )

    assert rows[0]["video_id"] == "video-1"
    assert rows[0]["engaged_views"] == 900
    assert rows[0]["watch_time_minutes"] == 6000
    assert rows[0]["subscribers_gained"] == 42
    assert rows[0]["read_only"] is True

    url, headers, _ = calls[0]
    query = parse_qs(urlparse(url).query)

    assert query["ids"] == ["channel==MINE"]
    assert query["dimensions"] == ["video"]
    assert query["sort"] == ["-views"]
    assert query["maxResults"] == ["200"]
    assert headers["Authorization"] == "Bearer secret-token"
    assert "secret-token" not in url


def test_traffic_source_adapter_maps_distribution_surfaces():
    def transport(url, headers, timeout):
        return {
            "columnHeaders": [
                {"name": "video"},
                {"name": "insightTrafficSourceType"},
                {"name": "engagedViews"},
                {"name": "views"},
                {"name": "estimatedMinutesWatched"},
            ],
            "rows": [
                ["v1", "YT_SEARCH", 100, 120, 400],
                ["v1", "RELATED_VIDEO", 80, 100, 350],
                ["v1", "SHORTS", 50, 70, 120],
                ["v1", "SUBSCRIBER", 40, 60, 180],
            ],
        }

    adapter = YouTubeAnalyticsReadAdapter(
        access_token="token",
        transport=transport,
    )
    rows = adapter.traffic_sources(
        start_date="2026-09-01",
        end_date="2026-09-23",
        video_id="v1",
    )

    by_raw = {
        row["traffic_source_type_raw"]: row
        for row in rows
    }
    assert by_raw["YT_SEARCH"]["surface"] == "SEARCH"
    assert by_raw["RELATED_VIDEO"]["surface"] == "SUGGESTED"
    assert by_raw["SHORTS"]["surface"] == "SHORTS_FEED"
    assert by_raw["SUBSCRIBER"]["surface"] == "BROWSE"
    assert all(row["read_only"] is True for row in rows)


def test_analytics_adapter_rejects_invalid_date_range_before_network():
    called = False

    def transport(url, headers, timeout):
        nonlocal called
        called = True
        return {}

    adapter = YouTubeAnalyticsReadAdapter(
        access_token="token",
        transport=transport,
    )

    with pytest.raises(ValueError, match="start_date"):
        adapter.top_videos(
            start_date="2026-09-24",
            end_date="2026-09-23",
        )

    assert called is False


def test_youtube_read_contract_contains_no_mutation_capability():
    contract = youtube_read_adapter_contract()

    assert contract["write_methods_present"] is False
    assert contract["upload_supported"] is False
    assert contract["metadata_mutation_supported"] is False
    assert contract["rating_mutation_supported"] is False
    assert contract["comment_mutation_supported"] is False
    assert contract["execution_authority"] == "none"
