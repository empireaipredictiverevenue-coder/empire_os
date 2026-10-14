"""Strict first-party YouTube campaign referral candidate for existing EmpireDB enquiries.

A source supplied on a buyer form is a BUYER-REPORTED UTM, not verified
referral causality, a unique visitor, a qualified lead or a realized sale.
The campaign's reference must be issued in a protected founder-controlled
registry, or an explicit test-only injected registry. No service or DB write.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping

from empire_os.media_youtube_campaign_tracking import make_owned_youtube_campaign_link
from empire_os.media_youtube_channel_binding import EMPIRE_AI_YOUTUBE_CHANNEL_ID

REGISTRY = Path("runtime/media_os/youtube_approved_source_registry.v1.json")
REGISTRY_SCHEMA = "empire.media.youtube_approved_source_registry.v1"
_REF = re.compile(r"^yt-[0-9a-f]{18}$")


def validate_issued_registry(registry: Mapping[str, Any], *, now: datetime) -> dict[str, dict[str, Any]]:
    if (not isinstance(registry, Mapping)
            or registry.get("schema_version") != REGISTRY_SCHEMA
            or registry.get("status") != "FOUNDER_APPROVED_FOR_SOURCE_MEASUREMENT"
            or registry.get("execution_authority") != "none"):
        raise ValueError("youtube_enquiry_approved_source_registry_missing")
    try:
        expires = datetime.fromisoformat(registry["valid_until"].replace("Z", "+00:00"))
    except (TypeError, ValueError, KeyError, AttributeError):
        raise ValueError("youtube_enquiry_approved_registry_expiry_invalid") from None
    if expires.tzinfo is None or expires.utcoffset() is None or now >= expires:
        raise ValueError("youtube_enquiry_source_registry_expired")
    rows = registry.get("links")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError("youtube_enquiry_source_registry_rows_invalid")
    verified = {}
    for row in rows:
        if (not isinstance(row, Mapping)
                or row.get("channel_id") != EMPIRE_AI_YOUTUBE_CHANNEL_ID
                or not isinstance(row.get("release_evidence_ref"), str)
                or not row["release_evidence_ref"].startswith("media:release:")
                or len(row["release_evidence_ref"]) > 160):
            raise ValueError("youtube_enquiry_source_registry_evidence_invalid")
        try:
            rebuilt = make_owned_youtube_campaign_link(
                campaign=row.get("campaign"), video_ref=row.get("video_ref"),
                placement=row.get("placement"), destination_path=row.get("destination_path")
            )
        except ValueError:
            raise ValueError("youtube_enquiry_source_registry_link_invalid") from None
        if row.get("tracking_key") != rebuilt["tracking_key"] or row.get("url") != rebuilt["url"]:
            raise ValueError("youtube_enquiry_source_registry_link_mismatch")
        if rebuilt["tracking_key"] in verified:
            raise ValueError("youtube_enquiry_source_duplicate_link")
        verified[rebuilt["tracking_key"]] = {
            "tracking_key": rebuilt["tracking_key"],
            "channel_id": rebuilt["channel_id"],
            "campaign": rebuilt["campaign"],
            "video_ref": rebuilt["video_ref"],
            "placement": rebuilt["placement"],
            "release_evidence_ref": row["release_evidence_ref"],
        }
    return verified


def load_issued_registry(root: Path, *, now: datetime) -> dict[str, dict[str, Any]]:
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("youtube_enquiry_registry_root_invalid")
    path = root / REGISTRY
    if path.is_symlink():
        raise ValueError("youtube_enquiry_approved_source_registry_missing")
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except (OSError, ValueError):
        raise ValueError("youtube_enquiry_approved_source_registry_missing") from None
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or (info.st_mode & 0o077)
                or info.st_size > 65000 or info.st_size <= 0):
            raise ValueError("youtube_enquiry_registry_private_file_required")
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            descriptor = -1
            document = json.load(handle)
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("youtube_enquiry_registry_json_invalid") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return validate_issued_registry(document, now=now)


def verify_enquiry_source(
    source_campaign_key: Any,
    *,
    root: str | Path,
    now: datetime,
) -> dict[str, Any] | None:
    """Verify issuance from protected file; user-supplied UTM is not causality."""
    if source_campaign_key == "":
        return None
    if not isinstance(source_campaign_key, str) or not _REF.fullmatch(source_campaign_key):
        raise ValueError("youtube_enquiry_source_campaign_key_invalid")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("youtube_enquiry_clock_required")
    registry = load_issued_registry(Path(root), now=now)
    issued = registry.get(source_campaign_key)
    if (not isinstance(issued, Mapping)
            or issued.get("tracking_key") != source_campaign_key
            or issued.get("channel_id") != EMPIRE_AI_YOUTUBE_CHANNEL_ID
            or not isinstance(issued.get("video_ref"), str)
            or not isinstance(issued.get("release_evidence_ref"), str)):
        raise ValueError("youtube_enquiry_campaign_not_registered")
    return {
        "schema_version": "empire.media.youtube_buyer_declared_utm_source.v1",
        "tracking_key": source_campaign_key,
        "channel_id": EMPIRE_AI_YOUTUBE_CHANNEL_ID,
        "video_ref": issued["video_ref"],
        "campaign": issued["campaign"],
        "placement": issued["placement"],
        "release_evidence_ref": issued["release_evidence_ref"],
        "source_classification": "BUYER_SUBMITTED_REGISTERED_UTM_NOT_INDEPENDENTLY_VERIFIED",
        "youtube_click_proven": False,
        "unique_visitor_proven": False,
        "causal_attribution_proven": False,
        "qualified_buyer_proven_by_utm": False,
        "recognized_revenue": False,
        "execution_authority": "none",
    }


def review_canonical_youtube_enquiry_link(
    *,
    prospect_readback: Mapping[str, Any],
    issued_source: Mapping[str, Any],
    canonical_empiredb_readback_evidence_ref: str,
) -> dict[str, Any]:
    """Prepare non-causal lead-source link from independent canonical readback.

    Caller must have separately fetched a real prospect/evidence row from
    the canonical EmpireDB reader; this pure function cannot attest to that
    fetch or perform any database write.
    """
    from empire_os.media_attribution import MediaAttributionLink, build_media_attribution_packet

    if (not isinstance(prospect_readback, Mapping)
            or not isinstance(issued_source, Mapping)
            or issued_source.get("schema_version") != "empire.media.youtube_buyer_declared_utm_source.v1"
            or issued_source.get("causal_attribution_proven") is not False
            or issued_source.get("recognized_revenue") is not False):
        raise ValueError("youtube_enquiry_canonical_source_evidence_required")
    if (not isinstance(canonical_empiredb_readback_evidence_ref, str)
            or not canonical_empiredb_readback_evidence_ref.startswith("empiredb:readback:")
            or len(canonical_empiredb_readback_evidence_ref) > 240):
        raise ValueError("youtube_enquiry_independent_readback_ref_required")
    prospect_id = prospect_readback.get("id")
    evidence = prospect_readback.get("evidence")
    if (not isinstance(prospect_id,str) or not prospect_id.strip()
            or not isinstance(evidence,Mapping)
            or evidence.get("youtube_buyer_declared_source") != issued_source
            or not isinstance(evidence.get("contact_consent_evidence"),Mapping)
            or evidence["contact_consent_evidence"].get("consent_to_contact") is not True):
        raise ValueError("youtube_enquiry_canonical_prospect_source_mismatch")
    row = MediaAttributionLink(
        link_id=issued_source["tracking_key"],
        source_type="VIDEO",
        source_id=issued_source["video_ref"],
        target_type="LEAD",
        target_id=prospect_id,
        evidence_refs=(
            canonical_empiredb_readback_evidence_ref,
            issued_source["release_evidence_ref"],
        ),
        attribution_method="buyer_reported_campaign_source_not_causal",
    )
    packet=build_media_attribution_packet(links=[row])
    return {
        "schema_version":"empire.media.youtube_canonical_lead_source_review.v1",
        "campaign_key":issued_source["tracking_key"],
        "media_attribution":packet,
        "buyer_reported_utm_registered":True,
        "real_youtube_click_ever_proved_by_this_review":False,
        "causal_attribution_proved":False,
        "recognized_revenue_proved":False,
        "canonical_reader_result_not_fetched_by_pure_module":True,
        "automatic_outbound":False,
        "execution_authority":"none",
    }
