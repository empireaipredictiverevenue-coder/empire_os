"""Aggregate independently read-back YouTube-declared buyer sources.

Existing EmpireDB reader supplies canonical prospect evidence. This module
does NOT read the database or establish causality; it verifies the shape and
produces PII-free, owner-only cohort summaries for the Founder Console.

No one can use this module to turn clicks or browser beacons into enquiries.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Iterable, Mapping

from empire_os.media_youtube_enquiry_source import (
    review_canonical_youtube_enquiry_link,
)
from empire_os.media_youtube_channel_binding import EMPIRE_AI_YOUTUBE_CHANNEL_ID

SCHEMA = "empire.media.youtube_canonical_enquiry_cohort.v1"
# No unbounded replay of historical viewer/revenue estimates in Founder UI.
MAX_SNAPSHOT_AGE_SECONDS = 26 * 60 * 60
SNAPSHOT = Path("runtime/media_os/youtube_enquiry_cohort_latest.json")
_HEX = re.compile(r"^yt-[0-9a-f]{18}$")
_SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")


def _check_nonnegative_integer(value: Any) -> bool:
    return type(value) is int and value >= 0


def compile_youtube_enquiry_cohort(
    *,
    canonical_prospect_readbacks: Iterable[Mapping[str, Any]],
    canonical_reader_batch_evidence_ref: str,
) -> dict[str, Any]:
    """Materialize only caller-supplied *canonical reader* evidence.

    Batch ref is a required provenance claim by the upstream reader.
    It is not a signature/cryptographic proof and cannot independently prove
    a production fetch, contact, visitor identity or a YouTube-caused sale.
    """
    if (
        not isinstance(canonical_reader_batch_evidence_ref, str)
        or not canonical_reader_batch_evidence_ref.startswith("empiredb:readback:")
        or len(canonical_reader_batch_evidence_ref) > 240
    ):
        raise ValueError("youtube_enquiry_batch_canonical_reader_evidence_required")
    counts: Counter[tuple[str, str, str]] = Counter()
    distinct: dict[str, str] = {}
    records = list(canonical_prospect_readbacks)
    if len(records) > 5000:
        raise ValueError("youtube_enquiry_batch_limit_exceeded")
    for row in records:
        if not isinstance(row, Mapping) or set(row) != {"prospect", "readback_ref"}:
            raise ValueError("youtube_enquiry_readback_row_contract_invalid")
        prospect = row["prospect"]
        readback_ref = row["readback_ref"]
        if not isinstance(prospect, Mapping):
            raise ValueError("youtube_enquiry_prospect_readback_invalid")
        source = prospect.get("evidence", {}).get("youtube_buyer_declared_source") if isinstance(prospect.get("evidence"), Mapping) else None
        if not isinstance(source, Mapping):
            raise ValueError("youtube_enquiry_readback_source_missing")
        if (
            source.get("channel_id") != EMPIRE_AI_YOUTUBE_CHANNEL_ID
            or source.get("source_classification") != "BUYER_SUBMITTED_REGISTERED_UTM_NOT_INDEPENDENTLY_VERIFIED"
            or not isinstance(source.get("tracking_key"), str)
            or not _HEX.fullmatch(source["tracking_key"])
            or not isinstance(source.get("video_ref"), str)
            or not _SAFE_NAME.fullmatch(source["video_ref"])
            or not isinstance(source.get("campaign"), str)
            or not _SAFE_NAME.fullmatch(source["campaign"])
            or not isinstance(source.get("placement"), str)
            or source.get("youtube_click_proven") is not False
            or source.get("unique_visitor_proven") is not False
            or source.get("causal_attribution_proven") is not False
            or source.get("recognized_revenue") is not False
            or source.get("execution_authority") != "none"
        ):
            raise ValueError("youtube_enquiry_causal_or_source_claim_invalid")
        link = review_canonical_youtube_enquiry_link(
            prospect_readback=prospect,
            issued_source=source,
            canonical_empiredb_readback_evidence_ref=readback_ref,
        )
        assert link["media_attribution"]["attributed_revenue_state"] == "UNKNOWN"
        prospect_id = prospect.get("id")
        tracking_key = source["tracking_key"]
        if prospect_id in distinct:
            if distinct[prospect_id] != tracking_key:
                raise ValueError("youtube_enquiry_conflicting_prospect_source")
            # Canonical prospect returned twice: never count twice.
            continue
        distinct[prospect_id] = tracking_key
        counts[(tracking_key, source["video_ref"], source["campaign"])] += 1
    breakdown = [
        {
            "tracking_key": key,
            "video_ref": video,
            "campaign": campaign,
            "buyer_declared_canonical_enquiries": value,
            "qualified_leads": None,
            "causal_youtube_conversions": None,
            "revenue_recognized_gbp": None,
        }
        for (key, video, campaign), value in sorted(counts.items())
    ]
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "channel_id": EMPIRE_AI_YOUTUBE_CHANNEL_ID,
        "status": "UPSTREAM_READER_ATTESTED_NOT_INDEPENDENTLY_FETCHED_HERE",
        "canonical_reader_batch_evidence_ref": canonical_reader_batch_evidence_ref,
        "buyer_declared_canonical_enquiries": len(distinct),
        "qualified_leads": None,
        "causal_youtube_conversions": None,
        "youtube_clicks_verified": None,
        "unique_visitors_verified": None,
        "recognized_revenue_gbp": None,
        "breakdown": breakdown,
        "prospect_personal_data_included": False,
        "video_causality_proven": False,
        "paid_customer_proven": False,
        "live_empiredb_read_performed": False,
        "execution_authority": "none",
    }


def _missing(status: str = "CANONICAL_CRM_COHORT_NOT_CONNECTED") -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "channel_id": EMPIRE_AI_YOUTUBE_CHANNEL_ID,
        "status": status,
        "canonical_reader_batch_evidence_ref": None,
        "buyer_declared_canonical_enquiries": None,
        "qualified_leads": None,
        "causal_youtube_conversions": None,
        "youtube_clicks_verified": None,
        "unique_visitors_verified": None,
        "recognized_revenue_gbp": None,
        "breakdown": [],
        "prospect_personal_data_included": False,
        "video_causality_proven": False,
        "paid_customer_proven": False,
        "live_empiredb_read_performed": False,
        "execution_authority": "none",
    }


def load_youtube_enquiry_cohort_snapshot(
    root: Path, *, now: datetime | None = None,
) -> dict[str, Any]:
    """Read-only private aggregate. Stale samples become UNKNOWN, never 0."""
    clock = now if now is not None else datetime.now(timezone.utc)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("youtube_enquiry_cohort_timezone_aware_clock_required")
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("youtube_enquiry_cohort_repository_root_invalid")
    path = root / SNAPSHOT
    if path.is_symlink() or not path.exists():
        return _missing()
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return _missing()
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or (info.st_mode & 0o077)
            or info.st_size <= 0
            or info.st_size > 512000
        ):
            raise ValueError("youtube_enquiry_cohort_snapshot_permissions_invalid")
        age_seconds = clock.timestamp() - info.st_mtime
        if age_seconds > MAX_SNAPSHOT_AGE_SECONDS or age_seconds < -300:
            return _missing("CANONICAL_CRM_COHORT_STALE_OR_FUTURE")
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            descriptor = -1
            packet = json.load(handle)
    except (ValueError, UnicodeError):
        raise ValueError("youtube_enquiry_cohort_snapshot_corrupt") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return validate_youtube_enquiry_snapshot_packet(packet)


def validate_youtube_enquiry_snapshot_packet(packet: Any) -> dict[str, Any]:
    """Validate all aggregate-only, no-causality fields independently of disk."""
    if not isinstance(packet, Mapping) or set(packet) != set(_missing()):
        raise ValueError("youtube_enquiry_cohort_schema_keys_invalid")
    if (
        packet["schema_version"] != SCHEMA
        or packet["mode"] != "OBSERVE"
        or packet["channel_id"] != EMPIRE_AI_YOUTUBE_CHANNEL_ID
        or packet["status"] != "UPSTREAM_READER_ATTESTED_NOT_INDEPENDENTLY_FETCHED_HERE"
        or not isinstance(packet["canonical_reader_batch_evidence_ref"], str)
        or not packet["canonical_reader_batch_evidence_ref"].startswith("empiredb:readback:")
        or packet["prospect_personal_data_included"] is not False
        or packet["video_causality_proven"] is not False
        or packet["paid_customer_proven"] is not False
        or packet["live_empiredb_read_performed"] is not False
        or packet["execution_authority"] != "none"
        or any(packet[key] is not None for key in (
            "qualified_leads", "causal_youtube_conversions", "youtube_clicks_verified",
            "unique_visitors_verified", "recognized_revenue_gbp"
        ))
        or not _check_nonnegative_integer(packet["buyer_declared_canonical_enquiries"])
        or not isinstance(packet["breakdown"], list)
        or len(packet["breakdown"]) > 5000
    ):
        raise ValueError("youtube_enquiry_cohort_snapshot_truth_invalid")
    expected = packet["buyer_declared_canonical_enquiries"]
    found = 0
    distinct_keys=set()
    for row in packet["breakdown"]:
        if not isinstance(row, Mapping) or set(row) != {
            "tracking_key", "video_ref", "campaign", "buyer_declared_canonical_enquiries",
            "qualified_leads", "causal_youtube_conversions", "revenue_recognized_gbp",
        }:
            raise ValueError("youtube_enquiry_cohort_row_invalid")
        if (
            not isinstance(row["tracking_key"], str) or not _HEX.fullmatch(row["tracking_key"])
            or not isinstance(row["video_ref"], str) or not _SAFE_NAME.fullmatch(row["video_ref"])
            or not isinstance(row["campaign"], str) or not _SAFE_NAME.fullmatch(row["campaign"])
            or not _check_nonnegative_integer(row["buyer_declared_canonical_enquiries"])
            or any(row[x] is not None for x in (
                "qualified_leads","causal_youtube_conversions","revenue_recognized_gbp"
            ))
        ):
            raise ValueError("youtube_enquiry_cohort_row_truth_invalid")
        signature=(row["tracking_key"],row["video_ref"],row["campaign"])
        if signature in distinct_keys:
            raise ValueError("youtube_enquiry_cohort_duplicate_rows")
        distinct_keys.add(signature)
        found += row["buyer_declared_canonical_enquiries"]
    if found != expected:
        raise ValueError("youtube_enquiry_cohort_count_mismatch")
    return dict(packet)
