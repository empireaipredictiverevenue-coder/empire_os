#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path

from empire_os.runtime_env import load_runtime_env
from empire_os.youtube_read_adapter import (
    YouTubeAnalyticsReadAdapter,
    YouTubeDataReadAdapter,
)


INPUT_DIR = Path("runtime/media_os/input")


def _write(root: Path, relative: Path, payload) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument(
        "--channel-id",
        action="append",
        default=[],
        help=(
            "Public YouTube channel ID to ingest. May be supplied more "
            "than once. If omitted, EMPIRE_YOUTUBE_CHANNEL_ID is used."
        ),
    )
    parser.add_argument("--max-videos", type=int, default=100)
    parser.add_argument("--analytics-start-date")
    parser.add_argument("--analytics-end-date")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    env = load_runtime_env("/etc/empire_os.env")

    api_key = (
        env.get("EMPIRE_YOUTUBE_API_KEY")
        or env.get("YOUTUBE_API_KEY")
        or ""
    ).strip()
    access_token = (
        env.get("EMPIRE_YOUTUBE_ACCESS_TOKEN")
        or env.get("YOUTUBE_ACCESS_TOKEN")
        or ""
    ).strip()
    default_channel = str(
        env.get("EMPIRE_YOUTUBE_CHANNEL_ID") or ""
    ).strip()

    channels = list(dict.fromkeys(
        [
            *[
                str(value).strip()
                for value in args.channel_id
                if str(value).strip()
            ],
            *([default_channel] if default_channel else []),
        ]
    ))

    start = str(args.analytics_start_date or "").strip()
    end = str(args.analytics_end_date or "").strip()
    if bool(start) != bool(end):
        raise ValueError(
            "analytics-start-date and analytics-end-date "
            "must be supplied together"
        )
    if start and end:
        date.fromisoformat(start)
        date.fromisoformat(end)
        if start > end:
            raise ValueError(
                "analytics-start-date cannot be after analytics-end-date"
            )

    public_rows = []
    owned_video_rows = []
    owned_distribution_rows = []
    calls_performed = {
        "public_data_api": False,
        "owned_analytics_api": False,
    }

    data_adapter = None
    if api_key:
        data_adapter = YouTubeDataReadAdapter(api_key=api_key)

    if channels and data_adapter is not None:
        for channel_id in channels:
            rows = data_adapter.channel_videos(
                channel_id,
                max_videos=max(1, int(args.max_videos)),
            )
            for row in rows:
                row["requested_channel_id"] = channel_id
            public_rows.extend(rows)
        calls_performed["public_data_api"] = True

    analytics_adapter = None
    if access_token:
        analytics_adapter = YouTubeAnalyticsReadAdapter(
            access_token=access_token
        )

    if analytics_adapter is not None and start and end:
        owned_video_rows = analytics_adapter.top_videos(
            start_date=start,
            end_date=end,
        )
        owned_distribution_rows = analytics_adapter.traffic_sources(
            start_date=start,
            end_date=end,
        )
        calls_performed["owned_analytics_api"] = True

        # If Data API read access is also configured, enrich owned top-video
        # IDs with public snippet/contentDetails/statistics without needing to
        # guess the external channel ID.
        if data_adapter is not None:
            owned_ids = [
                str(row.get("video_id") or "").strip()
                for row in owned_video_rows
                if str(row.get("video_id") or "").strip()
            ]
            public_rows.extend(data_adapter.videos(owned_ids))
            if owned_ids:
                calls_performed["public_data_api"] = True

    # Deduplicate public video objects by video ID. Keep first observed row.
    unique_public: dict[str, dict] = {}
    anonymous_public = []
    for row in public_rows:
        video_id = str(row.get("id") or "").strip()
        if video_id:
            unique_public.setdefault(video_id, row)
        else:
            anonymous_public.append(row)
    public_rows = [*unique_public.values(), *anonymous_public]

    written = []
    if calls_performed["public_data_api"]:
        written.append(str(_write(
            repo_root,
            INPUT_DIR / "youtube_public_observations.json",
            {
                "schema_version": (
                    "empire.media.youtube_public_input.v1"
                ),
                "observations": public_rows,
                "read_only_source": True,
                "external_action": "read",
            },
        )))

    if calls_performed["owned_analytics_api"]:
        written.append(str(_write(
            repo_root,
            INPUT_DIR / "youtube_owned_video_metrics.json",
            {
                "schema_version": (
                    "empire.media.youtube_owned_video_metrics_input.v1"
                ),
                "records": owned_video_rows,
                "date_range": {
                    "start": start,
                    "end": end,
                },
                "read_only_source": True,
                "external_action": "read",
            },
        )))
        written.append(str(_write(
            repo_root,
            INPUT_DIR / "youtube_owned_analytics.json",
            {
                "schema_version": (
                    "empire.media.youtube_owned_distribution_input.v1"
                ),
                "observations": owned_distribution_rows,
                "date_range": {
                    "start": start,
                    "end": end,
                },
                "read_only_source": True,
                "external_action": "read",
            },
        )))

    print(json.dumps({
        "ok": True,
        "configured": {
            "data_api": bool(api_key),
            "analytics_api": bool(access_token),
            "public_channel_count": len(channels),
            "analytics_window_supplied": bool(start and end),
        },
        "calls_performed": calls_performed,
        "public_video_observation_count": len(public_rows),
        "owned_video_metric_count": len(owned_video_rows),
        "owned_distribution_observation_count": len(
            owned_distribution_rows
        ),
        "written_paths": written,
        "secrets_persisted": False,
        "public_publish_authorized": False,
        "comment_publish_authorized": False,
        "metadata_mutation_authorized": False,
        "external_write_performed": False,
        "database_write_performed": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
