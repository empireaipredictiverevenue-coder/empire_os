"""Read-only, fail-closed buyer-admin proof for the existing Lead Smart Direct route.

No receipt producer here. A missing or insufficient buyer-admin review never
promotes launch, records money, changes Ringba, or sends traffic.
"""
from __future__ import annotations

import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "empire.lead_smart.buyer_admin_review.v1"
CAMPAIGN = "CA8278ed3f26e9495b881fe3833174d007"
NUMBER = "+18883579305"


def verified_buyer_admin_proof(
    evidence_root: Path, *, now: datetime | None = None,
    required_owner_uid: int = 0,
) -> tuple[bool, bool]:
    """Return independently reviewed (original ANI, recording governance).

    This is a source-referenced *admin configuration* check, not proof of a
    connected buyer leg or verified Ringba runtime routing. Those stay gated
    separately by the existing routing observer.
    """
    failed = (False, False)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        return failed
    p = evidence_root / "buyer_admin/verified_configuration.json"
    try:
        # Check ownership and consume bytes from the *same* file handle.
        # The parent runtime directory is app-writable; stat-then-open
        # allows a path swap between verification and content retrieval.
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
        fd = os.open(p, flags)
        with os.fdopen(fd, "rb") as stream:
            meta = os.fstat(stream.fileno())
            if (not stat.S_ISREG(meta.st_mode)
                    or not 0 < meta.st_size <= 8192
                    or meta.st_uid != required_owner_uid
                    or meta.st_mode & 0o022):
                return failed
            raw = stream.read(8193)
        if len(raw) > 8192:
            return failed
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            return failed
        when = datetime.fromisoformat(
            str(data["reviewed_at_utc"]).replace("Z", "+00:00")
        )
        if when.tzinfo is None:
            return failed
        age = (now.astimezone(timezone.utc)
               - when.astimezone(timezone.utc)).total_seconds()
        if not 0 <= age <= 604800:
            return failed
        ref = data.get("buyer_admin_source_ref")
        digest = data.get("buyer_admin_source_sha256")
        if not (data.get("schema_version") == SCHEMA
                and data.get("buyer") == "Lead Smart"
                and data.get("campaign_id") == CAMPAIGN
                and data.get("tracking_number") == NUMBER
                and data.get("buyer_admin_source_reviewed") is True
                and data.get("reviewed_by_founder") is True
                and isinstance(ref, str)
                and re.fullmatch(r"gmail:[0-9a-f]{16}", ref)
                and isinstance(digest, str)
                and re.fullmatch(r"[0-9a-f]{64}", digest)
                and data.get("buyer_admin_configuration_confirmed") is True):
            return failed
        ani = (
            data.get("enabled_direct_buyer_destination_confirmed") is True
            and data.get("original_ani_preservation_confirmed") is True
        )
        recording_mode = data.get("recording_mode")
        disabled = (
            recording_mode == "DISABLED"
            and data.get("recording_disable_confirmed_by_buyer_admin") is True
        )
        governed = (
            recording_mode == "ENABLED"
            and data.get("caller_notice_and_consent_verified") is True
            and data.get("responsible_recording_party_verified") is True
            and data.get("recording_access_retention_deletion_verified") is True
            and data.get("applicable_call_law_review_complete") is True
            and isinstance(data.get("independent_legal_review_ref"), str)
            and len(data["independent_legal_review_ref"].strip()) > 8
        )
        return (ani, disabled or governed)
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return failed
