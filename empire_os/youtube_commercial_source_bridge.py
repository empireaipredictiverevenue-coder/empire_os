"""First-party YouTube-to-commercial enquiry source review (NOT live plumbing).

Reuse canonical campaign-link issuance, protected registry and CRM readback
validation. This module performs no HTTP POST, writes, cookie tracking, source
registry issuance, publication, customer identification, or economic claims.
The existing /commercial website and intake owners must integrate it.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit

from empire_os.media_youtube_campaign_tracking import make_owned_youtube_campaign_link
from empire_os.media_youtube_enquiry_source import (
    verify_enquiry_source,
    review_canonical_youtube_enquiry_link,
)

SCHEMA = "empire.media.youtube_commercial_source_review.v1"
_QUERY = frozenset({"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_id"})


def review_commercial_video_source(
    *, landing_url: str, registry_root: Path, now: datetime
) -> dict[str, Any]:
    """Accept an EXACT issued YouTube-owned commercial link, not arbitrary UTMs.

    This requires an already-issued private registry and will fail closed when
    there isn't one. Client query params are never permission or causal proof.
    """
    if not isinstance(landing_url, str) or len(landing_url) > 2048:
        raise ValueError("bounded commercial source URL required")
    if not isinstance(registry_root, Path) or not registry_root.is_absolute():
        raise ValueError("trusted private issuance registry root required")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware trusted server clock required")
    parts = urlsplit(landing_url)
    if (
        parts.scheme != "https"
        or parts.netloc != "empire-ai.co.uk"
        or parts.path != "/commercial"
        or parts.fragment
        or parts.username
        or parts.password
    ):
        raise ValueError("only exact first-party commercial destinations allowed")
    try:
        params = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise ValueError("invalid commercial source parameters") from exc
    if set(params) != _QUERY or any(len(values) != 1 or not values[0] for values in params.values()):
        raise ValueError("unexpected or duplicate YouTube source parameters")
    if params["utm_source"] != ["youtube"]:
        raise ValueError("not an issued YouTube traffic source")
    issued = verify_enquiry_source(params["utm_id"][0], root=registry_root, now=now)
    if issued is None:
        raise ValueError("no approved source issuance")
    if issued["placement"] not in {"long_description", "pinned_comment", "short_profile"}:
        raise ValueError("placement not supported for commercial source handoff")
    original = make_owned_youtube_campaign_link(
        campaign=issued["campaign"],
        video_ref=issued["video_ref"],
        placement=issued["placement"],
        destination_path="/commercial",
    )
    if original["url"] != landing_url:
        raise ValueError("issued source does not match exact signed campaign URL contract")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "REGISTERED_SOURCE_LINK_REVIEWED_NOT_CONVERTED",
        "tracking_key": original["tracking_key"],
        "campaign": issued["campaign"],
        "video_ref": issued["video_ref"],
        "placement": issued["placement"],
        "source_ref": issued["release_evidence_ref"],
        "issued_source": issued,
        "buyer_reported_source_class": issued["source_classification"],
        "source_url": original["url"],
        "contact_submission_recorded": False,
        "commercial_form_source_wired": False,
        "canonical_buyer_readback_observed": False,
        "qualified_buyer_proven": False,
        "independent_referral_causality_proven": False,
        "realised_revenue": False,
        "source_registry_mutated": False,
        "automatic_publication_or_outreach_authorized": False,
        "execution_authority": "none",
    }


def review_commercial_video_source_submission(
    *,
    source_campaign_key: Any,
    source_landing_url: Any,
    registry_root: Path,
    now: datetime,
) -> dict[str, Any] | None:
    """Review optional browser fields before any authorised CRM intake write.

    A missing source means an ordinary untagged buyer enquiry; do not reject
    legitimate contact or infer a source. Partial/forged source is rejected.
    Trusted server chooses registry_root and now; client controls neither.
    """
    if source_campaign_key is None and source_landing_url is None:
        return None
    if (
        not isinstance(source_campaign_key, str)
        or not isinstance(source_landing_url, str)
        or not source_campaign_key
        or not source_landing_url
    ):
        raise ValueError("partial or invalid optional commercial YouTube source")
    reviewed = review_commercial_video_source(
        landing_url=source_landing_url, registry_root=registry_root, now=now
    )
    if reviewed["tracking_key"] != source_campaign_key:
        raise ValueError("form campaign key does not match trusted registry")
    return {
        "schema_version": "empire.media.youtube_commercial_source_submission.v1",
        "status": "OPTIONAL_REGISTERED_SOURCE_CANDIDATE_NOT_PROOF_OF_CLICK",
        "source_campaign_key": source_campaign_key,
        "source_evidence": reviewed["issued_source"],
        "consumer_identifiers_collected": False,
        "contact_consent_inferred": False,
        "client_source_verified_causal": False,
        "buyer_qualification_inferred": False,
        "realised_revenue": False,
        "crm_write_performed": False,
        "execution_authority": "none",
    }


def review_commercial_video_buyer_readback(
    *, source_review: Mapping[str, Any],
    canonical_prospect_readback: Mapping[str, Any],
    canonical_empiredb_readback_evidence_ref: str,
) -> dict[str, Any]:
    """Pass a trusted, separately obtained canonical CRM snapshot to its OWNER.

    Caller must obtain the actual protected tenant readback independently; no
    browser user or ChatGPT tool should be allowed to forge these parameters.
    """
    if (
        not isinstance(source_review, Mapping)
        or source_review.get("schema_version") != SCHEMA
        or source_review.get("status") != "REGISTERED_SOURCE_LINK_REVIEWED_NOT_CONVERTED"
        or source_review.get("execution_authority") != "none"
        or source_review.get("contact_submission_recorded") is not False
        or source_review.get("independent_referral_causality_proven") is not False
        or source_review.get("realised_revenue") is not False
    ):
        raise ValueError("untrusted commercial source review")
    result = review_canonical_youtube_enquiry_link(
        prospect_readback=canonical_prospect_readback,
        issued_source=source_review.get("issued_source"),
        canonical_empiredb_readback_evidence_ref=canonical_empiredb_readback_evidence_ref,
    )
    return {
        "schema_version": "empire.media.youtube_commercial_source_readback.v1",
        "mode": "OBSERVE",
        "status": "SOURCE_ASSOCIATED_NOT_CAUSAL",
        "canonical_review": result,
        "qualified_buyer_proven_by_utm": False,
        "realised_revenue_proven_by_utm": False,
        "public_publish_or_outreach_authorized": False,
        "execution_authority": "none",
    }
