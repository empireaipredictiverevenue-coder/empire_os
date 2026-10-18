"""JEV NewsJack → existing Marketing Agency / Media OS draft + tracking contract.

The Marketing Director owns campaign stages and real attribution; this is a
pure handoff proposal. No duplicate campaign executor, anonymous tracking,
outbound, automatic indexation, or artificial lead/revenue evidence.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, Mapping
from urllib.parse import urlencode, urlsplit

from empire_os import marketing_agency, media_content_pipeline
from empire_os.jev_newsjack_traffic import _timestamp
from empire_os.jev_newsjack_traffic_briefs import APPROVED_PAGE_ROUTES, COMMERCIAL_CONTACT

CHANNELS = {
    "linkedin": ("linkedin", "organic_social"),
    "youtube": ("youtube", "organic_video"),
    "newsletter": ("owned_newsletter", "email"),
}
RESEARCH_ANGLES = {
    "solar": {
        "audience": "UK solar installers and renewable-energy service teams",
        "seo_title": "UK solar installer opportunities: policy signals and buyer evidence",
        "focus": "Which local solar installation facts and buyer signals matter?",
    },
    "roofing": {
        "audience": "US commercial roofing contractors and buyer-development teams",
        "seo_title": "US roofing market changes: separate buyer signals from headlines",
        "focus": "Which properties, permits or storm-related changes are verifiable?",
    },
    "ai": {
        "audience": "Business leaders reviewing AI and predictive-revenue opportunities",
        "seo_title": "AI business opportunity: verified evidence before revenue forecasts",
        "focus": "What measurable problem and decision would make a paid assessment useful?",
    },
}


def _tracked_url(page: str, *, cid: str, channel: str, asset_id: str) -> str:
    source, medium = CHANNELS[channel]
    return page + "?" + urlencode({
        "utm_source": source,
        "utm_medium": medium,
        "utm_campaign": cid,
        "utm_content": asset_id,
    })


def prepare_marketing_director_handoff(
    review: Mapping[str, Any], *, generated_at: str
) -> dict[str, Any]:
    """Produce claim-free drafts for existing first-party owners to review.

    Intended to be called directly on a freshly produced *trusted* inspector
    review; importing this alone cannot prove source or page authenticity.
    """
    if (not isinstance(review, Mapping) or
            review.get("schema_version") != "empire.organic.jev_editorial_traffic_review.v1"
            or review.get("mode") != "OBSERVE"
            or review.get("execution_authority") != "none"
            or review.get("live_publication") is not False):
        raise ValueError("trusted read-only editorial review required")
    now = _timestamp(generated_at)
    if now is None:
        raise ValueError("timezone-aware generated_at required")
    rows = review.get("review_queue")
    pages = review.get("observed_owned_pages")
    if (not isinstance(rows, list) or not 0 <= len(rows) <= 50
            or not isinstance(pages, Mapping)):
        raise ValueError("bounded review and page receipts required")
    if not pages:
        return {
            "schema_version": "empire.organic.marketing_director_handoff.v1",
            "mode": "OBSERVE", "campaign_previews": [],
            "campaign_preview_count": 0, "external_publish_authorized": False,
            "execution_authority": "none",
        }

    jobs = []
    for item in rows:
        if not isinstance(item, Mapping):
            raise ValueError("invalid editorial review item")
        sector, market = item.get("sector"), item.get("market")
        page = APPROVED_PAGE_ROUTES.get((sector, market))
        if (item.get("status") != "EDITORIAL_RESEARCH_PREVIEW"
                or page is None or item.get("page_url") != page
                or item.get("cta_existing_commercial_page") != COMMERCIAL_CONTACT):
            continue
        if (pages.get(page, {}).get("live_verified") is not True
                or pages.get(COMMERCIAL_CONTACT, {}).get("live_verified") is not True):
            continue
        sha = item.get("page_content_sha256")
        if (not isinstance(sha, str) or len(sha) != 64
                or pages[page].get("content_sha256") != sha):
            continue
        identity = item.get("signal_id")
        refs = item.get("source_evidence_refs")
        if (not isinstance(identity, str) or not 1 <= len(identity) <= 128
                or not isinstance(refs, list) or not 1 <= len(refs) <= 12
                or not all(isinstance(ref, str) and ref for ref in refs)
                or not isinstance(item.get("source_url"), str)
                or urlsplit(item["source_url"]).scheme != "https"):
            continue
        # A stable ID is a measurement JOIN KEY, not a new campaign activation.
        campaign_id = "campaign_" + sha256(
            f"empire:jev-news:{sector}:{market}:{identity}".encode()
        ).hexdigest()[:24]
        angle = RESEARCH_ANGLES[sector]
        call = "Review the evidence and tell Empire AI which market question matters to your team."
        body = (
            f"{angle['focus']} Before treating news as buyer demand, "
            "separate dated primary-source evidence, open questions and known limitations. "
            "The source gives us a question to investigate, not a sales forecast."
        )
        asset = media_content_pipeline.campaign_draft_content(
            content_id=campaign_id + ":research",
            topic=angle["seo_title"], audience=angle["audience"],
            body=body, cta=call, evidence_refs=refs,
            opportunity_key="news:" + identity,
            product_refs=(), generated_at=now.isoformat(),
        )
        # Do not give an unverified story the Media OS verified-claim schema.
        classification = item.get("jev_classification")
        strong_model = (
            isinstance(classification, Mapping)
            and classification.get("label") == "content_brief"
            and type(classification.get("confidence")) in (int, float)
            and classification["confidence"] >= 0.75
        )
        target_assets = []
        for channel, (source, medium) in CHANNELS.items():
            asset_id = campaign_id + ":" + channel
            target_assets.append({
                "asset_id": asset_id, "channel": channel,
                "campaign_id": campaign_id,
                "destination_url": page,
                "preview_url": _tracked_url(
                    page, cid=campaign_id,
                    channel=channel, asset_id=asset_id,
                ),
                "research_question": angle["focus"],
                "source_url": item["source_url"],
                "copy_requires_editorial_review": True,
                "public_publish_authorized": False,
                "actual_channel_clicks": None,
                "execution_authority": "none",
            })
        jobs.append({
            "campaign_id": campaign_id,
            "campaign_owner": "existing_marketing_agency.marketing_director",
            "next_stage": "INTERNAL_SOURCE_AND_CLAIM_REVIEW",
            "status": "UNSUBMITTED_INTERNAL_DRAFT",
            "sector": sector, "market": market,
            "original_source_url": item["source_url"],
            "original_source_refs": list(refs),
            "owned_page_url": page, "owned_page_sha256": sha,
            "commercial_page_url": COMMERCIAL_CONTACT,
            "source_story_title_unverified": item.get("source_title_unverified"),
            "seo_metadata_proposal": {
                "title": angle["seo_title"],
                "description": (
                    f"Evidence-led questions for {angle['audience'].lower()}. "
                    "Review primary sources, limits and installer opportunities."
                )[:160],
                "destination_change_requested": False,
            },
            "content_draft": asset,
            "channel_previews": target_assets,
            "attribution_plan": {
                "owner": "search_intelligence.attribution",
                "campaign_id": campaign_id,
                "required_chain": list(marketing_agency.ATTRIBUTION_CHAIN),
                "event_contract_owner": "marketing_agency",
                "event_names_for_owner_review": [
                    "landing_view", "cta_click", "enquiry_submitted",
                    "prospect_linked", "conversation_linked",
                ],
                "capture_installed_or_verified": False,
                "visitor_sessions": None,
                "enquiries": None,
                "recognized_revenue": None,
                "reporting_window": None,
            },
            "jev_suggested_content_brief_above_threshold": strong_model,
            "evidence_gaps": list(item.get("research_gaps") or []),
            "publication_ready": False,
            "marketing_agency_ingested": False,
            "website_modified": False,
            "messages_sent": False,
            "paid_traffic_enabled": False,
            "execution_authority": "none",
        })
    return {
        "schema_version": "empire.organic.marketing_director_handoff.v1",
        "mode": "OBSERVE", "campaign_preview_count": len(jobs),
        "campaign_previews": jobs,
        "existing_campaign_owner": "marketing_agency",
        "source_review_count": len(rows),
        "claim_verification_complete": False,
        "external_publish_authorized": False,
        "auto_indexation_authorized": False,
        "attribution_capture_verified": False,
        "execution_authority": "none",
    }
