#!/usr/bin/env python3
"""Read-only PII-free health of original buyer Gmail metadata + Buyer Scout.

No Gmail or EmpireDB credentials, provider calls, contact details, outbound,
source signing, lead qualification, product/financial execution or file writes.
A warm thread message / classifier event is NOT an authenticated buyer enquiry.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

from empire_os.commercial_buyer_source_health import inspect_original_buyer_health
from scripts.import_connected_gmail_buyer_metadata import (
    _private, SOURCE, INDEX, SCHEMA,
)
from empire_os.buyer_mail_semantics import EVENT_CODES


SCHEMA_VERSION = "empire.prime.original_buyer_source_availability_review.v1"


def inspect(root: Path, *, now: datetime) -> dict[str, Any]:
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("trusted_UTC_review_time_required")
    current = now.astimezone(timezone.utc)
    health = inspect_original_buyer_health(root, now=current)
    out = {
        "schema_version": SCHEMA_VERSION,
        "mode": "OBSERVE",
        "status": "NO_AUTHENTICATED_SINGLE_BUYER_RECEIPT",
        "original_buyer_capacity_owner_status": health["status"],
        "original_buyer_capacity_report_is_not_buyer_authentication": True,
        "original_message_index_available": False,
        "original_message_index_fresh": False,
        "owner_thread_count_not_verified_buyers": None,
        "owner_message_count_not_verified_replies": None,
        "semantic_event_code_count_not_verified_intent": None,
        "snapshot_age_minutes_floor": None,
        "original_provider_credential_or_email_body_access": False,
        "canonical_provider_contact_tenant_binding_verified": False,
        "single_original_buyer_intent_receipt_authenticated": False,
        "owner_signing_key_and_source_rights_proven": False,
        "atomic_durable_replay_guard_active": False,
        "source_admission_authorized": False,
        "buyer_outbound_authorized": False,
        "financial_execution": False,
        "database_writes": False,
        "execution_authority": "none",
        "blockers": [
            "ORIGINAL_PROVIDER_AND_CANONICAL_CONTACT_BINDING_NOT_CONNECTED",
            "ORIGINAL_SECURITY_SIGNED_SOURCE_CUSTODY_NOT_CONNECTED",
            "EMPIREDB_DURABLE_REPLAY_LEDGER_NOT_DEPLOYED",
        ],
    }
    try:
        src = _private(root / SOURCE, 2_500_000)
        index = _private(root / INDEX, 900_000)
        if (src.get("schema_version") != "empire.buyer_mail_relationship_summary.v1"
            or src.get("origin") != "connected_gmail_connector_read_only"
            or index.get("schema_version") != SCHEMA
            or index.get("source") not in (
                "connected_gmail_connector_read_only", "empire_gmail_api_readonly",
            )):
            raise ValueError("not_existing_original_buyer_metadata_owner")
        at = datetime.fromisoformat(index["collected_at"].replace("Z", "+00:00"))
        if at.utcoffset() is None:
            raise ValueError("UTC owner snapshot required")
        age = current - at.astimezone(timezone.utc)
        if age < -timedelta(minutes=5):
            raise ValueError("future_original_snapshot")
        threads = index.get("threads")
        if not isinstance(threads, list) or not 1 <= len(threads) <= 24:
            raise ValueError("bounded_original_buyer_threads_required")
        observed = set()
        count = events = 0
        for thread in threads:
            if not isinstance(thread, dict) or thread.get("truncated") is not False:
                raise ValueError("incomplete_original_thread")
            tid = thread.get("thread_id")
            if not isinstance(tid, str) or not tid or tid in observed:
                raise ValueError("duplicate_original_thread")
            observed.add(tid)
            messages = thread.get("messages")
            if (not isinstance(messages, list) or not 1 <= len(messages) <= 80
                or thread.get("message_count") != len(messages)):
                raise ValueError("incomplete_original_thread")
            count += len(messages)
            mids = set()
            for m in messages:
                if not isinstance(m, dict):
                    raise ValueError("malformed_message")
                mid = m.get("id")
                if not isinstance(mid, str) or not mid or mid in mids:
                    raise ValueError("duplicate_original_message")
                mids.add(mid)
                codes = m.get("recognized_codes", [])
                if (not isinstance(codes, list) or len(codes) > 30
                    or any(type(code) is not str or code not in EVENT_CODES
                           for code in codes)):
                    raise ValueError("untrusted_original_message_semantic_codes")
                events += len(codes)
        out.update(
            status="FRESH_ORIGINAL_OWNER_METADATA_ONLY_NO_VERIFIED_BUYER"
                if age <= timedelta(hours=3)
                else "STALE_ORIGINAL_OWNER_METADATA_NO_VERIFIED_BUYER",
            original_message_index_available=True,
            original_message_index_fresh=age <= timedelta(hours=3),
            owner_thread_count_not_verified_buyers=len(threads),
            owner_message_count_not_verified_replies=count,
            semantic_event_code_count_not_verified_intent=events,
            snapshot_age_minutes_floor=max(0, int(age.total_seconds() // 60)),
        )
    except (OSError, TypeError, KeyError, ValueError, AttributeError,
            json.JSONDecodeError):
        out["status"] = "PRIVATE_ORIGINAL_BUYER_METADATA_UNAVAILABLE_OR_UNVERIFIED"
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/srv/empire_os")
    options = parser.parse_args()
    print(json.dumps(inspect(Path(options.root), now=datetime.now(timezone.utc)),
                     sort_keys=True))


if __name__ == "__main__":
    main()
