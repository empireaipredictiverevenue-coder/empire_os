"""Verified public identity for the founder-supplied existing Empire-AI channel.

Public HTML identity != OAuth ownership or permission to upload. No I/O.
"""
from __future__ import annotations

import re
from typing import Any

EMPIRE_AI_YOUTUBE_HANDLE = "@Empire-AI-Predictive-Revenue"
EMPIRE_AI_YOUTUBE_CHANNEL_ID = "UCTG4cE-alHNHtrwh9e6qePA"
EMPIRE_AI_YOUTUBE_HANDLE_URL = "https://www.youtube.com/" + EMPIRE_AI_YOUTUBE_HANDLE
EMPIRE_AI_YOUTUBE_CANONICAL_URL = (
    "https://www.youtube.com/channel/" + EMPIRE_AI_YOUTUBE_CHANNEL_ID
)

_CANONICAL = re.compile(
    r'<link\s+rel="canonical"\s+href="(https://www\.youtube\.com/channel/UC[A-Za-z0-9_-]{22})"',
    re.I,
)
_EXTERNAL_ID = re.compile(r'"externalId"\s*:\s*"(UC[A-Za-z0-9_-]{22})"')
_VANITY = re.compile(r'"vanityChannelUrl"\s*:\s*"([^"]+)"')


def verify_empire_ai_public_channel_html(html: str) -> dict[str, Any]:
    """Match all three independent fields in the public channel-page HTML.

    The page must be fetched from YouTube over HTTPS by a trusted caller; this
    pure parser does not itself authenticate any fetch or OAuth transport.
    """
    if not isinstance(html, str) or not 0 < len(html) <= 16_000_000:
        raise ValueError("public_youtube_html_missing_or_oversized")
    canonical = set(_CANONICAL.findall(html))
    external_ids = set(_EXTERNAL_ID.findall(html))
    vanity_urls = set(_VANITY.findall(html))
    valid_vanity = {
        EMPIRE_AI_YOUTUBE_HANDLE_URL,
        "http://www.youtube.com/" + EMPIRE_AI_YOUTUBE_HANDLE,
    }
    if (
        canonical != {EMPIRE_AI_YOUTUBE_CANONICAL_URL}
        or external_ids != {EMPIRE_AI_YOUTUBE_CHANNEL_ID}
        or not vanity_urls
        or not vanity_urls.issubset(valid_vanity)
    ):
        raise ValueError("empire_ai_public_channel_identity_mismatch")
    return {
        "schema_version": "empire.media.youtube_public_channel_binding.v1",
        "internal_channel_ref": "empire-ai",
        "display_name": "Empire-AI",
        "public_handle": EMPIRE_AI_YOUTUBE_HANDLE,
        "public_handle_url": EMPIRE_AI_YOUTUBE_HANDLE_URL,
        "canonical_channel_url": EMPIRE_AI_YOUTUBE_CANONICAL_URL,
        "external_youtube_channel_id": EMPIRE_AI_YOUTUBE_CHANNEL_ID,
        "public_identity_matches": True,
        "founder_reported_as_owned": True,
        "oauth_ownership_authenticated": False,
        "api_upload_permission_verified": False,
        "publisher_execution_authority": "none",
    }


def empire_ai_public_channel_binding() -> dict[str, Any]:
    """Stable public record for offline Media OS; not an OAuth attestation."""
    return {
        "schema_version": "empire.media.youtube_public_channel_binding.v1",
        "internal_channel_ref": "empire-ai",
        "display_name": "Empire-AI",
        "public_handle": EMPIRE_AI_YOUTUBE_HANDLE,
        "public_handle_url": EMPIRE_AI_YOUTUBE_HANDLE_URL,
        "canonical_channel_url": EMPIRE_AI_YOUTUBE_CANONICAL_URL,
        "external_youtube_channel_id": EMPIRE_AI_YOUTUBE_CHANNEL_ID,
        "public_identity_matches": True,
        "founder_reported_as_owned": True,
        "oauth_ownership_authenticated": False,
        "api_upload_permission_verified": False,
        "publisher_execution_authority": "none",
    }
