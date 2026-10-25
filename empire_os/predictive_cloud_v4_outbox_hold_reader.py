"""Predictive Cloud V4.3: held EmpireDB outbox read/replay review.

Pure, fail-closed review of owner-scoped *fictional* fixture rows.
No DB driver, connection, credentials, Redis command, sender, or execution.
The source/tenant authority MUST be obtained separately from EmpireDB owners.
"""
from __future__ import annotations

import json
import re
import sys
from collections.abc import Mapping
from uuid import UUID

CONTRACT = "empire.predictive_cloud.v4.held_reader.v1"
MAX_ROWS = 32
DIGEST = re.compile(r"^[a-f0-9]{64}$")
SECTORS = frozenset({
    "roofing", "hvac", "solar", "dental", "legal", "b2b_saas",
    "ecommerce", "logistics", "heat_pumps", "storm",
})
COLUMNS = frozenset({
    "event_digest", "tenant_id", "sector", "entity_digest",
    "source_evidence_digest", "revision", "event_kind",
    "delivery_state", "execution_authority", "latest_revision",
    "withdrawn", "source_review_state", "watermark_source_digest",
})


class V4ProjectionHold(ValueError):
    """Fail closed on untrusted or inexact owner-scope review rows."""


def _digest(value: object, name: str) -> str:
    if type(value) is not str or DIGEST.fullmatch(value) is None:
        raise V4ProjectionHold(f"invalid_{name}")
    return value


def _uuid(value: object) -> str:
    if type(value) is not str:
        raise V4ProjectionHold("tenant_uuid_required")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        raise V4ProjectionHold("tenant_uuid_invalid") from None
    if parsed.int == 0 or str(parsed) != value:
        raise V4ProjectionHold("tenant_uuid_not_canonical")
    return value


def review_held_outbox(
    rows: object, *, requested_tenant_id: str, max_rows: int = MAX_ROWS,
) -> dict[str, object]:
    """Review a bounded canonical-held snapshot; intentionally never release.

    The caller must independently prove its database and tenant access; this
    function does NOT authenticate an identity, approve a source, or deliver.
    """
    tenant = _uuid(requested_tenant_id)
    if type(max_rows) is not int or not 1 <= max_rows <= MAX_ROWS:
        raise V4ProjectionHold("reader_limit_invalid")
    if type(rows) is not list or len(rows) > max_rows:
        raise V4ProjectionHold("reader_rows_unbounded")
    seen_events: set[str] = set()
    seen_revision_keys: set[tuple[str, str, int]] = set()
    reviews: list[dict[str, object]] = []

    for item in rows:
        if type(item) is not dict or set(item) != COLUMNS:
            raise V4ProjectionHold("row_schema_inexact")
        if _uuid(item["tenant_id"]) != tenant:
            raise V4ProjectionHold("cross_tenant_row_refused")
        sector = item["sector"]
        if type(sector) is not str or sector not in SECTORS:
            raise V4ProjectionHold("sector_unrecognised")
        entity = _digest(item["entity_digest"], "entity_digest")
        event = _digest(item["event_digest"], "event_digest")
        _digest(item["source_evidence_digest"], "source_evidence_digest")
        wm_source = _digest(item["watermark_source_digest"], "watermark_source_digest")
        revision, latest = item["revision"], item["latest_revision"]
        if (type(revision) is not int or type(latest) is not int
            or not 1 <= revision <= 1_000_000_000
            or not 1 <= latest <= 1_000_000_000
            or revision > latest):
            raise V4ProjectionHold("revision_regression_or_invalid")
        if (type(item["withdrawn"]) is not bool
            or item["source_review_state"] != "UNVERIFIED"
            or item["delivery_state"] != "HELD"
            or item["execution_authority"] != "none"
            or item["event_kind"] not in ("OBSERVED", "WITHDRAWN")):
            raise V4ProjectionHold("unexpected_release_or_source_authority")
        if event in seen_events:
            raise V4ProjectionHold("duplicate_event_digest_in_snapshot")
        unique_rev = (sector, entity, revision)
        if unique_rev in seen_revision_keys:
            raise V4ProjectionHold("duplicate_entity_revision_in_snapshot")
        seen_events.add(event)
        seen_revision_keys.add(unique_rev)
        if revision == latest and item["source_evidence_digest"] != wm_source:
            raise V4ProjectionHold("latest_source_digest_mismatch")
        if item["event_kind"] == "WITHDRAWN" and (
            revision != latest or item["withdrawn"] is not True
        ):
            raise V4ProjectionHold("withdrawal_tombstone_inconsistent")
        if item["withdrawn"]:
            reason = "WITHDRAWN_SOURCE_HELD"
        elif revision < latest:
            reason = "SUPERSEDED_REVISION_HELD"
        else:
            reason = "UNVERIFIED_TENANT_AND_SOURCE_HELD"
        reviews.append({
            "event_digest": event,
            "sector": sector,
            "entity_digest": entity,
            "revision": revision,
            "current_revision": latest,
            "reason": reason,
            "redis_publish_authorized": False,
            "execution_authority": "none",
        })
    return {
        "schema_version": CONTRACT,
        "status": "ALL_EVENTS_HELD" if reviews else "NO_HELD_EVENTS",
        "tenant_id": tenant,
        "reviewed_count": len(reviews),
        "source_authority_verified": False,
        "crm_tenant_membership_verified": False,
        "redis_cloud_connected": False,
        "redis_publish_authorized": False,
        "production_empiredb_writes": False,
        "execution_authority": "none",
        "reviews": reviews,
    }


def main() -> None:
    """Fixture-only JSON stdin, never a live DB client or background worker."""
    raw = sys.stdin.read(32768)
    if len(raw) >= 32768:
        raise SystemExit("V4_HELD_READER_TOO_LARGE")
    payload = json.loads(raw)
    if type(payload) is not dict or set(payload) != {"rows", "requested_tenant_id"}:
        raise SystemExit("V4_HELD_READER_FIXTURE_ENVELOPE_REQUIRED")
    try:
        result = review_held_outbox(
            payload["rows"], requested_tenant_id=payload["requested_tenant_id"]
        )
    except V4ProjectionHold as exc:
        raise SystemExit(f"V4_HELD_READER_REJECTED:{exc}") from None
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
