"""Production V16: root-only READ-ONLY canonical custody and due-time inspector.

Uses the EXISTING /etc/empire/data-exchange-custody.env protected DSN through
the V15 inspector (never prints or changes it). No INSERT, role creation,
systemd mutation, scheduler, service, outbound, customer export or payments.

One-on-demand invocation: --read-only, optionally --recheck-official to make
three bounded GETs to the already reviewed official UK Planning Data endpoint.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from empire_os.data_exchange_custody_transport import EmpireDBConstructionCustody
from empire_os.data_exchange_observation_custody import verify_custody_window
from empire_os.data_exchange_temporal_quality import build_temporal_quality
from scripts.inspect_data_exchange_v15_release import protected_dsn
from scripts.operate_data_exchange_v16_followup import due_check
from scripts.operate_data_exchange_observation_custody import capture

SCHEMA = "empire.data_exchange.live_temporal_inspection.v16"
CANONICAL_ROOT = Path("/srv/empire_os")
# Genesis head is pinned from the independent original founder operator
# receipt. Local git anchoring is NOT an external timestamping attestation.
RELEASED_GENESIS_SHA256 = (
    "c7c3b13bde6684168e07fc9af17c19b8183d8b43c7de5930fa55814210ae4f1c"
)


class InspectionHold(RuntimeError):
    """No authority to assume the production historical state is sound."""


def inspect_live(*, now: datetime, dsn: str, recheck_official: bool = False,
                 fetch_snapshot=capture, store_factory=EmpireDBConstructionCustody) -> dict[str, Any]:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise InspectionHold("UTC_AWARE_TIME_REQUIRED")
    now = now.astimezone(timezone.utc)
    if not isinstance(dsn, str) or not dsn.strip():
        raise InspectionHold("EXISTING_CUSTODY_CONNECTION_REQUIRED")
    # Reader enforces read-only transactions, restricted SET LOCAL ROLE and
    # an explicit 16-row cap. Never query other EmpireDB tables.
    store = store_factory(dsn)
    rows = store.read_window()
    if not rows:
        raise InspectionHold("NO_PERSISTED_CUSTODY_OBSERVATIONS")
    proof = verify_custody_window(rows)
    if proof["first_sequence"] == 0:
        if rows[0]["chain_sha256"] != RELEASED_GENESIS_SHA256:
            raise InspectionHold("PRODUCTION_GENESIS_RECEIPT_MISMATCH")
    if proof["last_sequence"] != rows[-1]["sequence"]:
        raise InspectionHold("CANONICAL_SEQUENCE_READBACK_MISMATCH")
    readiness = due_check(rows, now=now)
    # Network fetch is optional and cannot produce a write. It is NOT a
    # custody observation until a separate, explicitly gated append occurs.
    fresh = fetch_snapshot(now=now) if recheck_official else None
    quality = build_temporal_quality(rows, assessed_at=now, recheck=fresh)
    if (
        quality["canonical_head_sha256"] != readiness["canonical_previous_head_sha256"]
        or quality["canonical_head_sequence"] != readiness["canonical_previous_sequence"]
        or quality["customer_delivery_enabled"] is not False
        or quality["production_writes"] is not False
    ):
        raise InspectionHold("CUSTODY_QUALITY_READBACK_INCONSISTENT")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "CANONICAL_CUSTODY_READONLY_VERIFIED",
        "history_observation_count_in_window": len(rows),
        "canonical_head_sequence": proof["last_sequence"],
        "canonical_head_sha256": proof["head_chain_sha256"],
        "genesis_present_in_window": proof["window_origin_anchored_to_genesis"],
        "production_genesis_receipt_matched": (
            True if proof["window_origin_anchored_to_genesis"] else None
        ),
        "latest_canonical_observed_at": quality["latest_observed_at"],
        "latest_observation_age_seconds": quality["latest_observation_age_seconds"],
        "second_capture_eligible_now": readiness["eligible"],
        "capture_gate_status": readiness["status"],
        "capture_not_before_utc": readiness["next_capture_not_before"],
        "seconds_until_eligible": readiness["seconds_until_eligible"],
        "temporal_quality_status": quality["status"],
        "temporal_quality_holds": list(quality["holds"]),
        "pinned_three_entity_sample_complete": quality["pinned_sample_fully_observed"],
        "source_recheck": quality["same_source_recheck"],
        "source_mismatched_record_count": len(quality["recheck_mismatched_entity_ids"]),
        "source_mismatched_field_record_count": len(quality["recheck_mismatched_fields_by_id"]),
        "v14_board_status": quality["v14_board_status"],
        "v14_observed_field_change_count": quality["observed_source_field_changes"],
        "v14_review_queue_count": quality["board_review_queue_count"],
        "pilot_entity_count": quality["pilot_entity_count"],
        "pilot_entity_scope": quality["pilot_entity_scope"],
        "regional_market_coverage_percent": None,
        "source_authenticity": "NOT_INDEPENDENTLY_VERIFIED",
        "source_rights_cleared": False,
        "buyer_intent_verified": False,
        "external_anchor_verified": False,
        "customer_delivery_enabled": False,
        "outbound_enabled": False,
        "payment_execution": False,
        "database_writes": False,
        "service_started": False,
        "execution_authority": "NONE",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only", action="store_true")
    p.add_argument("--recheck-official", action="store_true")
    args = p.parse_args(argv)
    report: dict[str, Any]
    try:
        if not args.read_only:
            raise InspectionHold("EXPLICIT_READ_ONLY_FLAG_REQUIRED")
        if os.geteuid() != 0:
            raise InspectionHold("AUTHORISED_ROOT_READ_ACCESS_REQUIRED")
        if Path.cwd().resolve() != CANONICAL_ROOT:
            raise InspectionHold("CANONICAL_PRODUCTION_WORKTREE_REQUIRED")
        report = inspect_live(
            now=datetime.now(timezone.utc), dsn=protected_dsn(),
            recheck_official=args.recheck_official,
        )
    except InspectionHold as exc:
        report = {
            "schema_version": SCHEMA, "mode": "OBSERVE",
            "status": "HOLD", "reason_code": str(exc),
            "database_writes": False, "service_started": False,
            "customer_delivery_enabled": False,
            "execution_authority": "NONE",
        }
    except Exception as exc:
        # Do not print exception body: libpq errors could contain the
        # connection identity, host, sensitive private DB details or DSN.
        report = {
            "schema_version": SCHEMA, "mode": "OBSERVE",
            "status": "HOLD",
            "reason_code": "SOURCE_OR_CANONICAL_HISTORY_UNVERIFIED",
            "exception_type": type(exc).__name__,
            "database_writes": False, "service_started": False,
            "customer_delivery_enabled": False,
            "execution_authority": "NONE",
        }
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0 if report["status"] == "CANONICAL_CUSTODY_READONLY_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
