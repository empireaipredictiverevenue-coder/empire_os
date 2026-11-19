"""OBSERVE-only construction data-exchange preview.

Consumes externally obtained, evidence-bearing records. Does not crawl, insert
prospects, contact buyers, publish exports, bind licences or collect payments.
A source catalogue entry is NOT a downstream data-distribution licence.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit
import re

from empire_os.source_intelligence import source_contract

SCHEMA_VERSION = "empire.data_exchange.construction_preview.v1"
SOURCE_ID = "gb_planning_data"
DATASET_ID = "brownfield-land"
REGION = "north_west_england"
MAX_RECORDS = 1000
MAX_AGE_DAYS = 90
_ID_RE = re.compile(r"^[0-9]{1,12}$")
_STATUSES = {"permissioned", "non-permissioned", "not-permissioned", "pending-decision"}
_ALLOWED_HOSTS = {"planning.data.gov.uk", "www.planning.data.gov.uk"}
_REQUIRED_RIGHTS = (
    "source_id", "dataset_id", "licence_id", "attribution",
    "reviewed_by", "reviewed_at", "review_status",
)


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None or result.utcoffset() is None:
        return None
    return result.astimezone(timezone.utc)


def _official_entity_url(value: Any, record_id: str) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS
        or parsed.username or parsed.password or port not in (None, 443)
        or parsed.query or parsed.fragment
    ):
        return False
    # Require explicit official entity evidence; a homepage is not evidence.
    return parsed.path == f"/entity/{record_id}"


def _rights_assessment(review: Any, *, now: datetime) -> tuple[bool, list[str]]:
    if not isinstance(review, Mapping):
        return False, ["RIGHTS_REVIEW_MISSING"]
    if any(not review.get(key) for key in _REQUIRED_RIGHTS):
        return False, ["RIGHTS_REVIEW_INCOMPLETE"]
    if review.get("source_id") != SOURCE_ID or review.get("dataset_id") != DATASET_ID:
        return False, ["RIGHTS_REVIEW_SCOPE_MISMATCH"]
    if review.get("review_status") != "approved":
        return False, ["RIGHTS_REVIEW_NOT_APPROVED"]
    if review.get("licence_id") != "OGL-3.0":
        return False, ["LICENCE_UNVERIFIED"]
    if (
        review.get("derived_product_use_cleared") is not True
        or review.get("third_party_rights_cleared") is not True
        or review.get("personal_data_excluded") is not True
    ):
        return False, ["RIGHTS_RESTRICTION_UNRESOLVED"]
    reviewed = _utc(review.get("reviewed_at"))
    if reviewed is None or reviewed > now:
        return False, ["RIGHTS_REVIEW_DATE_INVALID"]
    if (now - reviewed).days > 90:
        return False, ["RIGHTS_REVIEW_STALE"]
    return True, []


def build_construction_preview(
    records: Sequence[Mapping[str, Any]] | Any,
    *,
    rights_review: Mapping[str, Any] | None = None,
    observed_at: datetime,
) -> dict[str, Any]:
    """Build a non-exportable read-only pilot assessment.

    Eligibility is only an internal review result. It never grants sale,
    customer delivery, training, or outbound authority.
    """
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    now = observed_at.astimezone(timezone.utc)
    contract = source_contract(SOURCE_ID)
    if (
        contract.production_status != "verified"
        or "derived_products" not in contract.allowed_uses
    ):
        raise ValueError("source catalogue not enabled for derived analytics")
    rights_ok, rights_holds = _rights_assessment(rights_review, now=now)
    if not isinstance(records, (list, tuple)) or len(records) > MAX_RECORDS:
        raise ValueError("expected bounded list of source records")

    by_id: dict[str, dict[str, Any]] = {}
    conflicting_ids: set[str] = set()
    held: dict[str, int] = {}

    def hold(reason: str) -> None:
        held[reason] = held.get(reason, 0) + 1

    for row in records:
        if not isinstance(row, Mapping):
            hold("INVALID_RECORD")
            continue
        record_id = row.get("record_id")
        if not isinstance(record_id, str) or not _ID_RE.fullmatch(record_id):
            hold("INVALID_RECORD_ID")
            continue
        if (
            row.get("source_id") != SOURCE_ID
            or row.get("dataset_id") != DATASET_ID
            or row.get("region") != REGION
            or row.get("record_type") != "brownfield_land"
        ):
            hold("OUT_OF_PILOT_SCOPE")
            continue
        if not _official_entity_url(row.get("source_url"), record_id):
            hold("SOURCE_EVIDENCE_MISSING")
            continue
        recorded = _utc(row.get("source_observed_at"))
        if recorded is None or recorded > now:
            hold("OBSERVATION_INVALID")
            continue
        if (now - recorded).days > MAX_AGE_DAYS:
            hold("OBSERVATION_STALE")
            continue
        # Never accept free-text descriptions, addresses, contact fields,
        # or buyer-intent predictions into this public-data preview.
        if set(row) - {
            "record_id", "source_id", "dataset_id", "region", "record_type",
            "source_url", "source_observed_at", "planning_permission_status",
            "site_area_hectares", "source_entry_date",
        }:
            hold("UNREVIEWED_FIELDS")
            continue
        planning_status = row.get("planning_permission_status")
        if planning_status is not None and (
            not isinstance(planning_status, str) or planning_status not in _STATUSES
        ):
            hold("UNRECOGNISED_PLANNING_STATUS")
            continue
        area = row.get("site_area_hectares")
        if area is not None:
            try:
                if isinstance(area, bool):
                    raise InvalidOperation
                amount = Decimal(str(area))
                if not amount.is_finite() or not 0 <= amount <= 100000:
                    raise InvalidOperation
                area = format(amount, "f")
            except (InvalidOperation, TypeError, ValueError):
                hold("INVALID_SITE_AREA")
                continue
        source_entry_date = row.get("source_entry_date")
        if source_entry_date is not None:
            try:
                if (
                    not isinstance(source_entry_date, str)
                    or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", source_entry_date)
                    or date.fromisoformat(source_entry_date) > now.date()
                ):
                    raise ValueError
            except ValueError:
                hold("INVALID_SOURCE_ENTRY_DATE")
                continue
        clean = {
            "record_id": record_id,
            "source_id": SOURCE_ID,
            "dataset_id": DATASET_ID,
            "region": REGION,
            "record_type": "brownfield_land",
            "source_url": row["source_url"],
            "source_observed_at": recorded.isoformat(),
            "signal_class": "development_context_not_buyer_intent",
            "planning_permission_status": planning_status,
            "site_area_hectares": area,
            "source_entry_date": source_entry_date,
        }
        if record_id in conflicting_ids:
            hold("CONFLICTING_RECORD_ID")
            continue
        previous = by_id.get(record_id)
        if previous is not None and previous != clean:
            by_id.pop(record_id)
            conflicting_ids.add(record_id)
            hold("CONFLICTING_RECORD_ID")
            continue
        by_id[record_id] = clean

    rows = [by_id[key] for key in sorted(by_id)]
    status = (
        "RIGHTS_REVIEW_PASSED_INTERNAL_ONLY"
        if rights_ok and rows and not held
        else "HOLD"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "OBSERVE",
        "product": "empire_construction_signals",
        "pilot_region": REGION,
        "data_source": SOURCE_ID,
        "source_dataset": DATASET_ID,
        "dataset_record_count": len(rows),
        "records": rows,
        "rejected_counts": dict(sorted(held.items())),
        "rights_review_eligible": rights_ok,
        "rights_holds": rights_holds,
        "assessment_status": status,
        "source_claim_verification": "NOT_INDEPENDENTLY_VERIFIED",
        "signal_semantics": "development_context_not_buyer_intent",
        "customer_delivery_enabled": False,
        "data_resale_authorized": False,
        "outbound_enabled": False,
        "payment_execution": False,
        "production_writes": False,
        "actual_revenue": False,
        "execution_authority": "NONE",
    }


# Organisation identities checked against official Planning Data entity pages
# on 2026-10-14. This is an intentionally narrow pilot, not a comprehensive
# North West authority coverage claim.
_NW_AUTHORITY_IDS = {207: "Manchester City Council", 202: "Liverpool City Council"}
MAX_LIVE_PROBE_ENTITIES = 5


def normalise_official_brownfield_entities(
    entity_ids: Sequence[int],
    *,
    fetch_json: Any,
    observed_at: datetime,
) -> list[dict[str, Any]]:
    """Fetch a bounded set of official public records via injected read-only GET.

    The network transport is explicit and must only GET the provided official
    endpoint. Response fields other than public entity/dataset/source identity
    are excluded from the preview, including addresses, notes and contacts.
    """
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    if (
        not isinstance(entity_ids, (tuple, list))
        or not 1 <= len(entity_ids) <= MAX_LIVE_PROBE_ENTITIES
        or any(type(value) is not int or value <= 0 for value in entity_ids)
        or len(set(entity_ids)) != len(entity_ids)
    ):
        raise ValueError("expected 1 to 5 distinct positive official entity IDs")

    rows: list[dict[str, Any]] = []
    for entity_id in entity_ids:
        url = f"https://www.planning.data.gov.uk/entity/{entity_id}.json"
        data = fetch_json(url)
        if not isinstance(data, Mapping):
            raise ValueError("official source response malformed")
        if (
            data.get("entity") != entity_id
            or data.get("dataset") != DATASET_ID
            or data.get("quality") != "authoritative"
            or data.get("organisation-entity") not in _NW_AUTHORITY_IDS
            or data.get("end-date") not in (None, "")
        ):
            raise ValueError("official entity identity, coverage, validity or quality mismatch")
        rows.append({
            "record_id": str(entity_id),
            "source_id": SOURCE_ID,
            "dataset_id": DATASET_ID,
            "region": REGION,
            "record_type": "brownfield_land",
            "source_url": f"https://www.planning.data.gov.uk/entity/{entity_id}",
            "source_observed_at": observed_at.astimezone(timezone.utc).isoformat(),
            "planning_permission_status": data.get("planning-permission-status") or None,
            "site_area_hectares": data.get("hectares") or None,
            "source_entry_date": data.get("entry-date") or None,
        })
    return rows
