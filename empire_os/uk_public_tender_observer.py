"""Bounded UK Find a Tender public OCDS stream for existing revenue research.

Explicit opt-in one public GET. Classifies by published CPV only, no text
scraping, names, contacts, pricing or inference of revenue/buyer acceptance.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
import urllib.request
import urllib.error
from typing import Any, Callable, Mapping

SCHEMA = "empire.uk_public_tender_observation.v1"
BASE = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
DOCUMENTATION = "https://www.find-tender.service.gov.uk/apidocumentation/1.0/GET-ocdsReleasePackages"
MAX_BYTES = 1_000_000
PAGE_LIMIT = 5

# Narrow high precision CPV classes grounded in UK official procurement
# notices. Do not map broad 45* building classes to roofing sales.
CPV_CLASSES = {
    "09331000": "solar", "09332000": "solar",
    "45261215": "solar", "45261210": "roofing",
    "45331000": "hvac", "45331200": "hvac",
    "42511110": "hvac", "85130000": "dental",
}

class PublicTenderSourceUnavailable(RuntimeError):
    pass

class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise PublicTenderSourceUnavailable("tender data host redirected")


def _stamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 60:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc) if dt.utcoffset() is not None else None


def _utc(value: datetime | None) -> datetime:
    now = value or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("timezone-aware tender observation required")
    return now.astimezone(timezone.utc)


def _url(now: datetime) -> str:
    # Freeze a bounded lookback, not a historical bulk scrape.
    begin = (now - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00")
    return f"{BASE}?limit={PAGE_LIMIT}&stages=tender&updatedFrom={begin}"


def _public_get(now: datetime) -> bytes:
    req = urllib.request.Request(
        _url(now), method="GET",
        headers={"Accept": "application/json",
                 "User-Agent": "EmpireAI-SourceIntelligence/1.0 (empire-ai.co.uk)"},
    )
    try:
        with urllib.request.build_opener(_RejectRedirects).open(
            req, timeout=8,
        ) as res:
            if res.status != 200 or "json" not in str(
                res.headers.get("Content-Type", "")).lower():
                raise PublicTenderSourceUnavailable("tender source HTTP/content-type invalid")
            raw = res.read(MAX_BYTES + 1)
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        raise PublicTenderSourceUnavailable("official tender source unavailable") from exc
    if not 0 < len(raw) <= MAX_BYTES:
        raise PublicTenderSourceUnavailable("tender source exceeds bounded page")
    return raw


def normalize_uk_tender_releases(
    document: Mapping[str, Any], *, as_of: datetime,
) -> dict[str, Any]:
    now = _utc(as_of)
    if not isinstance(document, Mapping):
        raise ValueError("OCDS package object required")
    publisher = document.get("publisher")
    if not isinstance(publisher, Mapping) or publisher.get("name") != "Cabinet Office":
        raise ValueError("official tender publisher identity absent")
    if "nationalarchives.gov.uk/doc/open-government-licence" not in str(
        document.get("license") or "").lower():
        raise ValueError("official OCDS OGL metadata missing")
    releases = document.get("releases")
    if not isinstance(releases, list) or len(releases) > PAGE_LIMIT:
        raise ValueError("unbounded or missing OCDS releases")
    seen: set[str] = set()
    counts: Counter[str] = Counter()
    states: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for release in releases:
        if not isinstance(release, Mapping):
            raise ValueError("invalid OCDS release")
        ocid = release.get("ocid")
        release_id = release.get("id")
        if (not isinstance(ocid, str)
                or not re.fullmatch(r"ocds-[a-z0-9]{6}-[a-zA-Z0-9-]{1,80}", ocid)
                or not isinstance(release_id, str)
                or not 0 < len(release_id) <= 180
                or release_id in seen):
            raise ValueError("invalid/duplicate public procurement release")
        seen.add(release_id)
        tags = release.get("tag")
        if not isinstance(tags, list) or "tender" not in tags:
            raise ValueError("non-tender OCDS release included")
        tender = release.get("tender")
        if not isinstance(tender, Mapping):
            raise ValueError("OCDS tender record required")
        classification = tender.get("classification")
        if not isinstance(classification, Mapping):
            classification = {}
        codes = []
        if isinstance(classification.get("id"), str):
            codes.append(classification["id"])
        for item in tender.get("items") or []:
            if not isinstance(item, Mapping):
                raise ValueError("invalid tender item")
            cpv = item.get("classification")
            if isinstance(cpv, Mapping) and isinstance(cpv.get("id"), str):
                codes.append(cpv["id"])
        if len(codes) > 100:
            raise ValueError("excessive tender classifications")
        verticals = sorted({CPV_CLASSES[code] for code in codes
                            if code in CPV_CLASSES})
        stage = tender.get("status")
        if stage not in ("active", "complete", "cancelled", "withdrawn", "unsuccessful"):
            stage = "UNKNOWN"
        deadline = _stamp((tender.get("tenderPeriod") or {}).get("endDate")) if isinstance(
            tender.get("tenderPeriod"), Mapping) else None
        deadline_current = bool(
            stage == "active" and deadline is not None and deadline > now
        )
        # Stable semantic revision, independent of our observation clock.
        # A status/deadline/CPV change to the same release can now be mined.
        semantic = sha256(json.dumps({
            "status": stage,
            "cpv_codes": sorted(set(codes)),
            "deadline_as_published": (
                tender.get("tenderPeriod") or {}
            ).get("endDate") if isinstance(tender.get("tenderPeriod"), Mapping) else None,
            "published_release_date": release.get("date"),
            # Full published tender payload is hashed (never output) so a
            # requirements amendment is detected even when CPV/deadline stay.
            "tender_payload_sha256": sha256(json.dumps(
                tender, sort_keys=True, separators=(",", ":"),
                allow_nan=False,
            ).encode()).hexdigest(),
        }, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        for vertical in verticals:
            counts[vertical] += 1
        states[stage] += 1
        rows.append({
            "source_semantic_digest": semantic,
            "ocid_digest": sha256(ocid.encode()).hexdigest(),
            "release_digest": sha256(release_id.encode()).hexdigest(),
            "source_record_ref": f"https://www.find-tender.service.gov.uk/api/1.0/ocdsRecordPackages/{ocid}",
            "matched_verticals_from_cpv": verticals,
            "source_reported_tender_status": stage,
            "future_submissions_deadline_evidenced": deadline_current,
            "source_category_truth": "PUBLIC_PROCUREMENT_NOTICE",
            "notice_is_contract_award": False,
            "buyer_acceptance_or_payment_verified": False,
        })
    rows.sort(key=lambda row: row["release_digest"])
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "publisher": "Cabinet Office",
        "documented_source": BASE,
        "source_documentation": DOCUMENTATION,
        "attribution_required": "© Crown copyright and database right (OGL v3)",
        "record_count_in_bounded_page": len(rows),
        "sample_at_limit": len(rows) == PAGE_LIMIT,
        "global_open_tender_count_known": False,
        "vertical_matches_in_page": dict(sorted(counts.items())),
        "tender_status_counts_in_page": dict(sorted(states.items())),
        "source_observations": rows,
        "status": "PUBLIC_TENDER_SAMPLE_OBSERVED" if rows else "EMPTY_BOUNDED_SOURCE_WINDOW",
        "commercial_opportunity_kind": "PUBLISHED_PROCUREMENT_SIGNAL_ONLY",
        "outreach_or_bid_authorized": False,
        "customer_or_supplier_contacts_returned": False,
        "actual_contract_or_revenue_proven": False,
        "existing_opportunity_or_crm_created": False,
        "worker_dispatched": False, "payment_authorized": False,
        "execution_authority": "none",
    }


def observe_uk_public_tenders(
    *, as_of: datetime | None = None, fetcher: Callable[[], bytes] | None = None,
) -> dict[str, Any]:
    now = _utc(as_of)
    raw = (fetcher or (lambda: _public_get(now)))()
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise PublicTenderSourceUnavailable("tender response size invalid")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise PublicTenderSourceUnavailable("tender source JSON unavailable") from exc
    return normalize_uk_tender_releases(payload, as_of=now)
