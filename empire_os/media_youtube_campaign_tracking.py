"""First-party, privacy-minimised YouTube campaign URL attribution contract.

Generates owned-site HTTPS URLs with non-personal UTM parameters. No pixel,
cookies, visitor IDs, redirects, event ingestion, or revenue write. The existing
Media Attribution + Revenue Pulse owners retain conversion truth.
"""
from __future__ import annotations

from hashlib import sha256
import re
from typing import Any, Mapping
from urllib.parse import urlencode, urlsplit, parse_qs

from empire_os.media_youtube_channel_binding import EMPIRE_AI_YOUTUBE_CHANNEL_ID
from empire_os.media_attribution import MediaAttributionLink, build_media_attribution_packet

BASE = "https://empire-ai.co.uk"
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
_PATHS = frozenset({"/", "/commercial"})
_PLACEMENTS = frozenset({"long_description", "channel_profile", "short_profile", "pinned_comment", "end_screen"})
_MEDIUM = {
    "long_description": "organic_video",
    "pinned_comment": "organic_video",
    "end_screen": "organic_video",
    "short_profile": "organic_short",
    "channel_profile": "organic_channel",
}


def make_owned_youtube_campaign_link(
    *, campaign: str, video_ref: str,
    placement: str, destination_path: str = "/",
) -> dict[str, Any]:
    if (
        not isinstance(campaign, str) or not _SLUG.fullmatch(campaign)
        or not isinstance(video_ref, str) or not _SLUG.fullmatch(video_ref)
    ):
        raise ValueError("youtube_campaign_and_video_ref_safe_slug_required")
    if placement not in _PLACEMENTS:
        raise ValueError("youtube_campaign_placement_unknown")
    if destination_path not in _PATHS:
        raise ValueError("youtube_campaign_destination_not_allowlisted")
    tracking_key = "yt-" + sha256(
        f"{EMPIRE_AI_YOUTUBE_CHANNEL_ID}|{campaign}|{video_ref}|{placement}".encode()
    ).hexdigest()[:18]
    params = {
        "utm_source": "youtube",
        "utm_medium": _MEDIUM[placement],
        "utm_campaign": campaign,
        "utm_content": f"{video_ref}-{placement.replace('_','-')}",
        "utm_id": tracking_key,
    }
    url = BASE + destination_path + "?" + urlencode(params)
    return {
        "schema_version": "empire.media.youtube_owned_campaign_link.v1",
        "mode": "OBSERVE",
        "channel_id": EMPIRE_AI_YOUTUBE_CHANNEL_ID,
        "campaign": campaign,
        "video_ref": video_ref,
        "placement": placement,
        "destination_path": destination_path,
        "tracking_key": tracking_key,
        "url": url,
        "analytics_kind": "FIRST_PARTY_NONPERSONAL_UTM",
        "clicks_observed": None,
        "visits_observed": None,
        "enquiries_verified": None,
        "recognized_revenue_cents": None,
        "shorts_description_link_clickable": False,
        "owner_site_deployment_verified": False,
        "site_event_ingestion_active": False,
        "cookies_written": False,
        "pixel_installed": False,
        "automatic_public_publish": False,
        "execution_authority": "none",
    }


def review_website_campaign_referral(
    *, landing_url: str,
    approved_links: Mapping[str, Mapping[str, Any]],
    source_event_evidence_ref: str,
    canonical_session_ref: str | None,
) -> dict[str, Any]:
    """Normalize independent first-party site visit evidence, never invent a click.

    Caller must supply a real, independently captured first-party event reference.
    No IP, email, cookie, fingerprint, geolocation, or inferred conversion.
    """
    if not isinstance(source_event_evidence_ref, str) or not source_event_evidence_ref.startswith("site:event:"):
        raise ValueError("verified_first_party_site_event_ref_required")
    parsed = urlsplit(landing_url)
    if parsed.scheme != "https" or parsed.netloc != "empire-ai.co.uk" or parsed.path not in _PATHS or parsed.fragment:
        raise ValueError("youtube_referral_only_from_owned_site")
    query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    if set(query) != {"utm_source","utm_medium","utm_campaign","utm_content","utm_id"}:
        raise ValueError("youtube_campaign_query_contract_invalid")
    if any(len(v) != 1 for v in query.values()):
        raise ValueError("youtube_campaign_duplicate_parameters")
    key = query["utm_id"][0]
    allowed = approved_links.get(key)
    if not isinstance(allowed, Mapping) or allowed.get("url") != landing_url:
        raise ValueError("youtube_campaign_not_in_approved_registry")
    if canonical_session_ref is not None:
        if not isinstance(canonical_session_ref, str) or not canonical_session_ref.startswith("site:session:"):
            raise ValueError("canonical_session_evidence_required")
        attribution = build_media_attribution_packet(links=[
            MediaAttributionLink(
                link_id=key,source_type="VIDEO",
                source_id=allowed["video_ref"],target_type="SESSION",
                target_id=canonical_session_ref,
                evidence_refs=(source_event_evidence_ref,),
                attribution_method="observed_owned_landing_url",
            )
        ])
    else:
        attribution = build_media_attribution_packet(links=[])
    return {
        "schema_version": "empire.media.youtube_first_party_referral_review.v1",
        "tracking_key": key,
        "channel_id": EMPIRE_AI_YOUTUBE_CHANNEL_ID,
        "site_event_evidence_ref": source_event_evidence_ref,
        "canonical_session_ref": canonical_session_ref,
        "attribution": attribution,
        "cookies_or_pixels_set": False,
        "event_saved": False,
        "click_or_visit_count_claimed": False,
        "sale_or_revenue_attributed": False,
        "execution_authority": "none",
    }
