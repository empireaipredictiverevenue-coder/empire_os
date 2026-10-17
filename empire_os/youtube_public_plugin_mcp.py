"""Private-preview public-data MCP facade for the existing Empire Media OS.

Not the internal ops MCP. No database, tenant, CRM, shell, publisher,
payment, login or YouTube API-key access. NOT publicly deployed.
"""
from __future__ import annotations

import argparse
from typing import Any

from mcp.server.mcpserver import MCPServer

from empire_os.youtube_read_adapter import read_public_youtube_oembed

server = MCPServer(
    name="empire_youtube_intelligence_public",
    title="Empire AI YouTube Intelligence (Private Preview)",
    description="Public YouTube link facts only; no invented audience metrics.",
    version="0.1.0",
    instructions=(
        "Use only public video metadata. Do not imply that video scenes or "
        "transcripts were reviewed. This preview cannot rank competitor "
        "channels or validate business revenue."
    ),
)


def public_video_review(video_url: str) -> dict[str, Any]:
    """Review a public YouTube link. No account access or paid service."""
    result = read_public_youtube_oembed(video_url)
    return {
        "status": "PUBLIC_METADATA_REVIEW",
        "public_video": result,
        "limitations": [
            "Video not watched and no transcript obtained",
            "No private channel analytics, search-volume, view-count or revenue claims",
            "No automatic video generation or publishing",
        ],
        "publisher": "Empire AI",
        "execution_authority": "read_only",
    }


@server.tool(name="empire_youtube_public_video_review", structured_output=True)
def review_video(video_url: str) -> dict[str, Any]:
    """Get authoritative public title and creator for a YouTube video URL.

    Read-only. Returns unknown where captions, retention, competitor rankings,
    sales metrics or direct video analysis are not available.
    """
    return public_video_review(video_url)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--private-loopback-only",
        action="store_true",
        help="Explicit local development opt-in; not public deployment authority",
    )
    parser.add_argument("--port", type=int, default=8877)
    args = parser.parse_args(argv)
    if not args.private_loopback_only:
        parser.error("Preview MCP server is disabled without private-loopback opt-in")
    if not 1024 <= args.port <= 65535:
        parser.error("Invalid preview port")
    server.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=args.port,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
