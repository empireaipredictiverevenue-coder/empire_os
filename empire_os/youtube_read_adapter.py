"""Read-only YouTube source adapters for Empire Media OS.

Uses official YouTube Data API / YouTube Analytics API read endpoints only.
Publishing, metadata mutation, rating and upload methods are intentionally
absent from this adapter.
"""
from __future__ import annotations

from datetime import date
import json
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen


JsonTransport = Callable[[str, Mapping[str, str], float], Mapping[str, Any]]

DATA_API = "https://www.googleapis.com/youtube/v3"
ANALYTICS_API = "https://youtubeanalytics.googleapis.com/v2/reports"

TRAFFIC_SURFACE_MAP = {
    "YT_SEARCH": "SEARCH",
    "RELATED_VIDEO": "SUGGESTED",
    "YT_RELATED": "SUGGESTED",
    "SHORTS": "SHORTS_FEED",
    "YT_CHANNEL": "CHANNEL_PAGE",
    "NOTIFICATION": "NOTIFICATIONS",
    "PLAYLIST": "PLAYLIST",
    "EXT_URL": "EXTERNAL",
    "NO_LINK_OTHER": "DIRECT_OR_UNKNOWN",
    "UNKNOWN_MOBILE_OR_DIRECT": "DIRECT_OR_UNKNOWN",
    "SUBSCRIBER": "BROWSE",
    "YT_OTHER_PAGE": "BROWSE",
}


def _default_transport(
    url: str,
    headers: Mapping[str, str],
    timeout: float,
) -> Mapping[str, Any]:
    request = Request(url, headers=dict(headers), method="GET")
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("YouTube API response must be an object")
    return payload


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index:index + size]


def _table_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    headers = payload.get("columnHeaders")
    rows = payload.get("rows")
    if not isinstance(headers, list) or not isinstance(rows, list):
        return []

    names = [
        str(row.get("name") or "").strip()
        for row in headers
        if isinstance(row, Mapping)
    ]
    if not names:
        return []

    output = []
    for values in rows:
        if not isinstance(values, list):
            continue
        output.append({
            name: values[index] if index < len(values) else None
            for index, name in enumerate(names)
        })
    return output


class YouTubeDataReadAdapter:
    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float = 20.0,
        transport: JsonTransport = _default_transport,
    ) -> None:
        key = str(api_key or "").strip()
        if not key:
            raise ValueError("YouTube Data API key is required")
        self._api_key = key
        self._timeout = max(1.0, float(timeout_seconds))
        self._transport = transport

    def channel_video_ids(
        self,
        channel_id: str,
        *,
        max_videos: int = 100,
    ) -> list[str]:
        channel = str(channel_id or "").strip()
        if not channel:
            raise ValueError("channel_id is required")
        limit = max(1, int(max_videos))

        channel_query = urlencode({
            "part": "contentDetails",
            "id": channel,
            "key": self._api_key,
        })
        payload = self._transport(
            f"{DATA_API}/channels?{channel_query}",
            {"Accept": "application/json"},
            self._timeout,
        )
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            return []

        first = items[0] if isinstance(items[0], Mapping) else {}
        uploads = (
            (first.get("contentDetails") or {})
            .get("relatedPlaylists", {})
            .get("uploads")
        )
        playlist_id = str(uploads or "").strip()
        if not playlist_id:
            return []

        output: list[str] = []
        page_token: str | None = None

        while len(output) < limit:
            remaining = limit - len(output)
            params: dict[str, Any] = {
                "part": "contentDetails",
                "playlistId": playlist_id,
                "maxResults": min(50, remaining),
                "key": self._api_key,
            }
            if page_token:
                params["pageToken"] = page_token

            playlist_payload = self._transport(
                f"{DATA_API}/playlistItems?{urlencode(params)}",
                {"Accept": "application/json"},
                self._timeout,
            )
            rows = playlist_payload.get("items")
            if not isinstance(rows, list):
                break

            for row in rows:
                if not isinstance(row, Mapping):
                    continue
                video_id = str(
                    (row.get("contentDetails") or {}).get("videoId")
                    or ""
                ).strip()
                if video_id and video_id not in output:
                    output.append(video_id)
                    if len(output) >= limit:
                        break

            next_token = str(
                playlist_payload.get("nextPageToken") or ""
            ).strip()
            if not next_token or not rows:
                break
            page_token = next_token

        return output

    def channel_videos(
        self,
        channel_id: str,
        *,
        max_videos: int = 100,
    ) -> list[dict[str, Any]]:
        video_ids = self.channel_video_ids(
            channel_id,
            max_videos=max_videos,
        )
        return self.videos(video_ids)

    def videos(
        self,
        video_ids: Iterable[str],
    ) -> list[dict[str, Any]]:
        ids = list(dict.fromkeys(
            str(value).strip()
            for value in video_ids
            if str(value).strip()
        ))
        if not ids:
            return []

        output: list[dict[str, Any]] = []
        for batch in _chunks(ids, 50):
            query = urlencode({
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(batch),
                "key": self._api_key,
            })
            payload = self._transport(
                f"{DATA_API}/videos?{query}",
                {"Accept": "application/json"},
                self._timeout,
            )
            items = payload.get("items")
            if not isinstance(items, list):
                continue
            for row in items:
                if not isinstance(row, Mapping):
                    continue
                item = dict(row)
                video_id = str(item.get("id") or "").strip()
                item["evidence_refs"] = [
                    f"youtube:data_api:video:{video_id}"
                ] if video_id else []
                item["source_adapter"] = "youtube_data_api"
                item["read_only"] = True
                output.append(item)
        return output


class YouTubeAnalyticsReadAdapter:
    def __init__(
        self,
        *,
        access_token: str,
        timeout_seconds: float = 30.0,
        transport: JsonTransport = _default_transport,
    ) -> None:
        token = str(access_token or "").strip()
        if not token:
            raise ValueError("YouTube Analytics access token is required")
        self._token = token
        self._timeout = max(1.0, float(timeout_seconds))
        self._transport = transport

    def _query(
        self,
        *,
        start_date: str,
        end_date: str,
        metrics: str,
        dimensions: str | None = None,
        filters: str | None = None,
        sort: str | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        # Validate dates before sending a request.
        date.fromisoformat(start_date)
        date.fromisoformat(end_date)
        if start_date > end_date:
            raise ValueError("start_date cannot be after end_date")

        params: dict[str, Any] = {
            "ids": "channel==MINE",
            "startDate": start_date,
            "endDate": end_date,
            "metrics": metrics,
        }
        if dimensions:
            params["dimensions"] = dimensions
        if filters:
            params["filters"] = filters
        if sort:
            params["sort"] = sort
        if max_results is not None:
            params["maxResults"] = max(1, int(max_results))

        payload = self._transport(
            f"{ANALYTICS_API}?{urlencode(params)}",
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}",
            },
            self._timeout,
        )
        return _table_rows(payload)

    def top_videos(
        self,
        *,
        start_date: str,
        end_date: str,
        max_results: int = 200,
    ) -> list[dict[str, Any]]:
        rows = self._query(
            start_date=start_date,
            end_date=end_date,
            dimensions="video",
            metrics=(
                "engagedViews,views,estimatedMinutesWatched,"
                "averageViewDuration,averageViewPercentage,"
                "subscribersGained,subscribersLost"
            ),
            sort="-views",
            max_results=min(200, max(1, int(max_results))),
        )
        output = []
        for row in rows:
            video_id = str(row.get("video") or "").strip()
            output.append({
                "video_id": video_id or None,
                "engaged_views": row.get("engagedViews"),
                "views": row.get("views"),
                "watch_time_minutes": row.get("estimatedMinutesWatched"),
                "average_view_duration_seconds": row.get(
                    "averageViewDuration"
                ),
                "average_view_percentage": row.get(
                    "averageViewPercentage"
                ),
                "subscribers_gained": row.get("subscribersGained"),
                "subscribers_lost": row.get("subscribersLost"),
                "evidence_refs": [
                    (
                        "youtube:analytics:top_video:"
                        f"{video_id}:{start_date}:{end_date}"
                    )
                ] if video_id else [],
                "source_adapter": "youtube_analytics_api",
                "read_only": True,
            })
        return output

    def traffic_sources(
        self,
        *,
        start_date: str,
        end_date: str,
        video_id: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = (
            f"video=={str(video_id).strip()}"
            if str(video_id or "").strip()
            else None
        )
        rows = self._query(
            start_date=start_date,
            end_date=end_date,
            dimensions="video,insightTrafficSourceType",
            metrics="engagedViews,views,estimatedMinutesWatched",
            filters=filters,
            sort="-views",
        )

        output = []
        for row in rows:
            raw_type = str(
                row.get("insightTrafficSourceType") or ""
            ).strip()
            vid = str(row.get("video") or "").strip()
            surface = TRAFFIC_SURFACE_MAP.get(
                raw_type,
                "DIRECT_OR_UNKNOWN",
            )
            output.append({
                "video_id": vid or None,
                "surface": surface,
                "traffic_source_type_raw": raw_type or None,
                "views": row.get("views"),
                "engaged_views": row.get("engagedViews"),
                "watch_time_minutes": row.get(
                    "estimatedMinutesWatched"
                ),
                "evidence_refs": [
                    (
                        "youtube:analytics:traffic_source:"
                        f"{vid}:{raw_type}:{start_date}:{end_date}"
                    )
                ] if vid and raw_type else [],
                "source_adapter": "youtube_analytics_api",
                "surface_mapping_classification": (
                    "NORMALIZED_FROM_OFFICIAL_TRAFFIC_SOURCE"
                ),
                "read_only": True,
            })
        return output


def youtube_read_adapter_contract() -> dict[str, Any]:
    return {
        "schema_version": "empire.media.youtube_read_adapter.v1",
        "data_api_actions": [
            "channels.list",
            "playlistItems.list",
            "videos.list",
        ],
        "analytics_actions": [
            "owned_channel_top_video_report",
            "owned_channel_traffic_source_report",
        ],
        "write_methods_present": False,
        "upload_supported": False,
        "metadata_mutation_supported": False,
        "rating_mutation_supported": False,
        "comment_mutation_supported": False,
        "oauth_scope_requirement": "youtube.readonly",
        "execution_authority": "none",
    }
