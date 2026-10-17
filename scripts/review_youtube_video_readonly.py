"""First-party YouTube link research entry point for the existing Empire Media OS.

No vidIQ account, GPT transcript guessing, video download, captions scraping,
publishing, API-key printing, paid API calls, or writes to EmpireDB.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.runtime_env import load_runtime_env
from empire_os.youtube_intelligence import (
    youtube_inspiration_review,
    review_youtube_commercial_opportunities,
)
from empire_os.youtube_read_adapter import (
    YouTubeDataReadAdapter,
    read_public_youtube_oembed,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Empire Media OS YouTube research (read-only)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Public YouTube video link or ID")
    group.add_argument("--query", help="Search YouTube by topic using official Data API")
    group.add_argument("--opportunities-file", help="Review an existing Media OS normalized-observations JSON packet offline")
    parser.add_argument("--description-file", help="Optional supplied video description with published chapter labels")
    parser.add_argument("--allow-one-search-call", action="store_true", help="Explicitly spend one YouTube search quota call")
    parser.add_argument("--max-results", type=int, default=10)
    args = parser.parse_args(argv)

    if args.opportunities_file:
        file = Path(args.opportunities_file).resolve()
        if not file.is_file() or file.stat().st_size > 3_000_000:
            raise ValueError("opportunity packet must be local and <=3MB")
        packet = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(packet, dict) or not isinstance(packet.get("observations"), list):
            raise ValueError("normalized observations packet required")
        result = review_youtube_commercial_opportunities(
            packet["observations"],
            commercial_capacity=packet.get("commercial_capacity"),
            limit=args.max_results,
        )
    elif args.url:
        public = read_public_youtube_oembed(args.url)
        description = ""
        if args.description_file:
            path = Path(args.description_file).resolve()
            if not path.is_file() or path.stat().st_size > 100_000:
                raise ValueError("description input must be a local file <=100KB")
            description = path.read_text(encoding="utf-8")
        review = youtube_inspiration_review(
            video_id=public["video_id"],
            title=public["title"],
            creator=public["author_name"],
            published_description=description,
        )
        result = {
            "schema_version": "empire.media.youtube_research_cli.v1",
            "public_metadata": public,
            "inspiration_review": review,
            "capabilities": {"public_oembed": True, "creator_chapters": bool(description),
                             "transcript": False, "video_visual_review": False,
                             "upload_or_publish": False},
        }
    else:
        if not args.allow_one_search_call:
            raise ValueError("topic search requires --allow-one-search-call")
        env = load_runtime_env("/etc/empire_os.env")
        key = (env.get("EMPIRE_YOUTUBE_API_KEY") or env.get("YOUTUBE_API_KEY") or "").strip()
        if not key:
            result = {
                "schema_version": "empire.media.youtube_research_cli.v1",
                "mode": "OBSERVE",
                "status": "UNAVAILABLE_API_KEY",
                "next_action": "Configure a read-only YouTube Data API key in existing EmpireOS runtime environment.",
                "search_call_performed": False,
                "paid_vidiq_required": False,
            }
        else:
            rows = YouTubeDataReadAdapter(api_key=key).search_videos(
                args.query,
                max_results=args.max_results,
                search_call_allowance=1,
            )
            result = {
                "schema_version": "empire.media.youtube_research_cli.v1",
                "mode": "OBSERVE",
                "status": "SEARCH_RETURNED",
                "results": rows,
                "search_call_performed": True,
                "source": "YOUTUBE_DATA_API",
                "visual_content_verified": False,
                "paid_vidiq_required": False,
            }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
