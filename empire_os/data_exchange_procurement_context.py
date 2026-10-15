"""Bounded, read-only UK procurement context, NOT a site-project join.

Uses official Find a Tender public OCDS release packages. Releases are
independent regional/national procurement context; neither location nor
proximity provides a verified relation to a brownfield entity.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import re
from typing import Any, Callable, Mapping
from urllib.parse import urlencode, urlsplit

SOURCE = "gb_find_a_tender_ocds"
OGL_V3 = "http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
SCHEMA = "empire.data_exchange.procurement_context.v1"
OCID = re.compile(r"^ocds-h6vhtk-[a-zA-Z0-9-]{1,64}$")
NOTICE = re.compile(r"^[0-9]{6}-20[0-9]{2}$")
TAGS = frozenset({"planning", "tender", "award", "contract", "implementation"})
MAX_RELEASES = 5


def _date(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("procurement release time invalid")
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("procurement release time invalid") from exc
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("procurement time requires timezone")
    return t.astimezone(timezone.utc)


def inspect_procurement_releases(
    *,
    start_date: date,
    end_date: date,
    limit: int,
    fetch_json: Callable[[str], Any],
    observed_at: datetime,
) -> dict[str, Any]:
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at needs timezone")
    now = observed_at.astimezone(timezone.utc)
    if (
        type(start_date) is not date or type(end_date) is not date
        or start_date > end_date
        or end_date > now.date()
        or end_date - start_date > timedelta(days=2)
    ):
        raise ValueError("procurement window must be recent and bounded")
    if type(limit) is not int or not 1 <= limit <= MAX_RELEASES:
        raise ValueError("procurement limit out of bounds")
    start = start_date.isoformat() + "T00:00:00Z"
    finish = (end_date + timedelta(days=1)).isoformat() + "T00:00:00Z"
    url = (
        "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?"
        + urlencode({"updatedFrom": start, "updatedTo": finish, "limit": limit})
    )
    package = fetch_json(url)
    if not isinstance(package, Mapping):
        raise ValueError("procurement source response invalid")
    if package.get("license") != OGL_V3 or (
        not isinstance(package.get("publisher"), Mapping)
        or package["publisher"].get("name") != "Cabinet Office"
    ):
        raise ValueError("procurement licence or publisher not verified")
    releases = package.get("releases")
    if not isinstance(releases, list) or not 1 <= len(releases) <= limit:
        raise ValueError("procurement releases empty or unbounded")
    rows: list[dict[str, Any]] = []
    unique = set()
    for release in releases:
        if not isinstance(release, Mapping):
            raise ValueError("procurement release malformed")
        release_id = release.get("id")
        ocid = release.get("ocid")
        tags = release.get("tag")
        event_time = _date(release.get("date"))
        if (
            not isinstance(release_id, str)
            or not NOTICE.fullmatch(release_id)
            or not isinstance(ocid, str)
            or not OCID.fullmatch(ocid)
            or not isinstance(tags, list)
            or not tags
            or any(not isinstance(x, str) or x not in TAGS for x in tags)
            or (release_id, ocid) in unique
            or event_time > now
        ):
            raise ValueError("procurement release identity, tags or time invalid")
        unique.add((release_id, ocid))
        rows.append({
            "source_id": SOURCE,
            "release_id": release_id,
            "ocid": ocid,
            "source_url": "https://www.find-tender.service.gov.uk/Notice/" + release_id,
            "release_date": event_time.isoformat(),
            "stages": sorted(set(tags)),
            "relation_to_brownfield_site": "NONE_VERIFIED",
            "buyer_intent_from_site": "UNKNOWN",
        })
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "source_id": SOURCE,
        "source_dataset": "find-a-tender-ocds-releases",
        "window_from": start_date.isoformat(),
        "window_to": end_date.isoformat(),
        "requested_limit": limit,
        "sample_count": len(rows),
        "notices": rows,
        "source_rights_status": "DATASET_LICENSE_STATED_FIELD_REVIEW_PENDING",
        "cross_source_entity_link": "NOT_VERIFIED",
        "relationship_to_construction_records": "NOT_ESTABLISHED",
        "source_claim_verification": "OFFICIAL_API_NOT_INDEPENDENTLY_REVIEWED",
        "buyer_intent_verified": False,
        "customer_delivery_enabled": False,
        "data_resale_authorized": False,
        "outbound_enabled": False,
        "payment_execution": False,
        "production_writes": False,
        "actual_revenue": False,
        "execution_authority": "NONE",
    }
