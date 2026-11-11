"""Bounded read-only official Find a Tender OCDS discovery for retrofit research.

Separate narrow vertical adapter: accepts newer official event tags including
tenderUpdate without altering EmpireOS's pre-existing procurement read model.
All results are research candidates, NOT confirmed open contract opportunities.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from collections.abc import Callable, Mapping
from urllib.parse import urlencode, urlsplit, parse_qs
import re
from hashlib import sha256
from urllib.error import HTTPError

from empire_os.data_exchange_procurement_context import (
    SOURCE, OGL_V3, OCID, NOTICE,
)

SCHEMA = "empire.retrofit_official_tender_titles.v1"
MAX_SAMPLE = 100
KEYWORDS = {
    "heat_pump": re.compile(r"\bheat[\s-]?pumps?\b|\bair[\s-]?source\b", re.I),
    "insulation": re.compile(r"\binsulation\b|\bsolid[\s-]?wall\b|\bcavity[\s-]?wall\b", re.I),
    "solar": re.compile(r"\bsolar\b|\bphotovoltaic\b|\bPV\b", re.I),
    "battery": re.compile(r"\bbatter(?:y|ies)\b|\benergy[\s-]?storage\b", re.I),
    "retrofit": re.compile(r"\bretrofit\b|\bdecarbonis(?:ation|e|ing)\b", re.I),
    "warm_homes": re.compile(r"\bwarm[\s-]?homes\b", re.I),
    "housing": re.compile(r"\bsocial[\s-]?housing\b|\bhousing[\s-]?associations?\b", re.I),
    "resident_support": re.compile(r"\bresident[\s-]?support\b|\benergy[\s-]?advice\b", re.I),
    "glazing": re.compile(r"\bglazing\b|\bwindow[\s-]?replacement\b", re.I),
    "hmo_property": re.compile(
        r"\bHMOs?\b|\bhouses? in multiple occupation\b|"
        r"\bmultiple[ -]occupation housing\b", re.I),
    "property_stock": re.compile(
        r"\b(stock condition|housing stock|property condition) surveys?\b|"
        r"\bEPC assessments?\b|\benergy performance certificates?\b|"
        r"\bPAS[ -]?2035\b", re.I),
    "ventilation": re.compile(
        r"\bventilation (?:upgrade|installation|retrofit|works|replacement)\b", re.I),
    "heat_network": re.compile(r"\bheat networks?\b|\bdistrict heating\b", re.I),
    "energy_efficiency": re.compile(r"\benergy efficiency\b|\blow[ -]carbon heating\b", re.I),
    # A narrow, independently labelled government-software intelligence lane
    # for genuine rostering/scheduling notices. Never infer Empire suitability.
    "workforce_rostering": re.compile(
        r"\be[ -]?rostering\b|\bworkforce rostering\b|"
        r"\bstaff rostering\b|\bclinical rostering\b|"
        r"\bworkforce scheduling (?:systems?|software|services?)\b", re.I),
}
TAG = re.compile(r"^[a-zA-Z]{3,32}$")
KNOWN_TENDER_TAGS = {"tender", "tenderUpdate"}


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("invalid official timestamp")
    try:
        x = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid official timestamp") from exc
    if x.utcoffset() is None:
        raise ValueError("official timestamp missing timezone")
    return x.astimezone(timezone.utc)


def review_official_retrofit_tender_sample(
    *, start_date: date, end_date: date, limit: int,
    observed_at: datetime, fetch_json: Callable[[str], object]
):
    """One non-exhaustive official OCDS sample, no side effects, no DB writes."""
    if not isinstance(observed_at, datetime) or observed_at.utcoffset() is None:
        raise ValueError("observation time must be timezone-aware")
    now = observed_at.astimezone(timezone.utc)
    if (type(start_date) is not date or type(end_date) is not date
            or start_date > end_date or end_date > now.date()
            or end_date - start_date > timedelta(days=2)
            or type(limit) is not int or not 1 <= limit <= MAX_SAMPLE):
        raise ValueError("invalid bounded OCDS window")
    url = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?" + urlencode({
        "updatedFrom": start_date.isoformat() + "T00:00:00Z",
        "updatedTo": (end_date + timedelta(days=1)).isoformat() + "T00:00:00Z",
        "limit": limit,
    })
    package = fetch_json(url)
    if (not isinstance(package, Mapping)
            or package.get("license") != OGL_V3
            or not isinstance(package.get("publisher"), Mapping)
            or package["publisher"].get("name") != "Cabinet Office"):
        raise ValueError("official publisher or licence not verified")
    releases = package.get("releases")
    if not isinstance(releases, list) or len(releases) > limit:
        raise ValueError("bounded release list missing or excessive")
    seen, notices = set(), []
    for record in releases:
        if not isinstance(record, Mapping):
            raise ValueError("invalid official release")
        release_id, ocid = record.get("id"), record.get("ocid")
        event = _timestamp(record.get("date"))
        tags = record.get("tag")
        if (not isinstance(release_id, str) or not NOTICE.fullmatch(release_id)
                or not isinstance(ocid, str) or not OCID.fullmatch(ocid)
                or (release_id, ocid) in seen
                or event > now + timedelta(minutes=5)
                or not isinstance(tags, list) or not tags
                or any(not isinstance(t, str) or not TAG.fullmatch(t) for t in tags)):
            raise ValueError("official release identity, event type or freshness invalid")
        seen.add((release_id, ocid))
        tender = record.get("tender") or {}
        if not isinstance(tender, Mapping):
            raise ValueError("invalid tender body")
        title = tender.get("title") or ""
        if not isinstance(title, str) or len(title) > 512:
            raise ValueError("invalid official tender title")
        relevance = [
            label for label, rx in KEYWORDS.items() if rx.search(title)
        ]
        # Broad social-housing and resident-support titles alone are not
        # evidence of physical retrofit or licensable HMO requirements.
        # "Decarbonisation" alone may describe chemicals, data centres or
        # vehicles. Do not pass such unrelated work as property retrofit.
        if ("retrofit" in relevance and not re.search(r"\bretrofit\b", title, re.I)
                and not re.search(
                    r"\b(?:homes?|housing|properties|property|buildings?|"
                    r"heating|boilers?|insulation|landlords?|council dwellings?)\b",
                    title, re.I,
                )):
            relevance.remove("retrofit")
        relevant = bool(set(relevance) - {"housing", "resident_support"})
        open_stage_candidate = bool(KNOWN_TENDER_TAGS.intersection(tags))
        parties = record.get("parties") or []
        if not isinstance(parties, list):
            raise ValueError("invalid official parties")
        buyers = [
            p.get("name") for p in parties
            if isinstance(p, Mapping) and "buyer" in (p.get("roles") or [])
            and isinstance(p.get("name"), str)
        ]
        period = tender.get("tenderPeriod") or {}
        if not isinstance(period, Mapping):
            raise ValueError("invalid tender period")
        deadline_raw = period.get("endDate")
        deadline = None
        deadline_format_unverified = False
        if deadline_raw is not None:
            try:
                # An optional published deadline can omit its time zone.
                # Preserve the genuine notice, but NEVER infer a deadline.
                deadline = _timestamp(deadline_raw)
            except ValueError:
                deadline_format_unverified = True
        # Relevance is a TITLE HYPOTHESIS only; not a search-engine verdict.
        notices.append({
            "source_id": SOURCE,
            "release_id": release_id,
            "ocid": ocid,
            "official_notice_url": "https://www.find-tender.service.gov.uk/Notice/" + release_id,
            "title": title,
            "official_event_time": event.isoformat(),
            "buyer_name_as_published": buyers[0][:220] if buyers else None,
            "tender_status_as_published": tender.get("status") if isinstance(tender.get("status"), str) else None,
            "deadline_as_published": deadline.isoformat() if deadline else None,
            "deadline_format_unverified": deadline_format_unverified,
            "tags": tags,
            "open_tender_stage_suggested_by_tag": open_stage_candidate,
            "title_relevance_labels": relevance,
            "retrofit_title_relevance_review_needed": relevant,
            "scope_documents_read": False,
            "deadline_verified": False,
            "supplier_bid_eligible": False,
            "buyer_of_empire_services_verified": False,
        })
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "source_id": SOURCE,
        "official_api_url": url,
        "window_from": start_date.isoformat(),
        "window_to": end_date.isoformat(),
        "requested_limit": limit,
        "sample_count": len(notices),
        "non_exhaustive_sample": True,
        "official_source_license": OGL_V3,
        "title_relevance_candidate_count": sum(x["retrofit_title_relevance_review_needed"] for x in notices),
        "notices": notices,
        "confirmed_retrofit_tender_count": 0,
        "bid_submission_enabled": False,
        "outbound_enabled": False,
        "production_writes": False,
        "verified_buyer_count": 0,
        "revenue_gbp": 0,
        "execution_authority": "NONE",
    }

# One existing official-source adapter, now connected to the canonical Radar
# runtime directory. No CRM / tenant / outbound / payment authority.
from pathlib import Path
import json

SOURCE_SNAPSHOT = Path("runtime/opportunity_radar/official_retrofit_tenders_latest.json")
SOURCE_CHECK = Path("runtime/opportunity_radar/official_retrofit_tenders_check_latest.json")
SOURCE_POLL_INTERVAL = timedelta(hours=6)


def _snapshot_json(path: Path) -> dict:
    if path.is_symlink():
        return {}
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return result if isinstance(result, dict) else {}


def _write_private_snapshot(path: Path, value: dict) -> None:
    if path.is_symlink() or path.with_suffix(".tmp").is_symlink():
        raise ValueError("unsafe source snapshot target")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")
    temp.replace(path)



# Bound source budget to the existing six-hour refresh, not every loop tick.
PAGE_LIMIT = 100
MAX_PAGES_PER_DAY = 3
DAYS_PER_SCAN = 2
SCAN_STAGES = ("planning", "tender", "award")
MAX_HISTORY_AGE_DAYS = 30
MAX_RETAINED_RELEVANT = 250
RETAIN_DAYS = 30
CURSOR_RE = re.compile(r"[A-Za-z0-9=]{1,300}\Z")
OFFICIAL_RELEASES = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"


def _page_next(package: Mapping, *, base_query: dict[str, str]) -> str | None:
    links = package.get("links")
    if links is None:
        return None
    if not isinstance(links, Mapping):
        raise ValueError("official pagination links invalid")
    target = links.get("next")
    if target in (None, ""):
        return None
    if not isinstance(target, str):
        raise ValueError("invalid pagination cursor URL")
    parsed = urlsplit(target)
    base = urlsplit(OFFICIAL_RELEASES)
    if (parsed.scheme != "https" or parsed.hostname != base.hostname
            or parsed.path != base.path or parsed.port not in (None, 443)
            or parsed.username or parsed.password or parsed.fragment):
        raise ValueError("untrusted off-origin procurement continuation")
    params = parse_qs(parsed.query, keep_blank_values=True)
    if set(params) != set(base_query) | {"cursor"}:
        raise ValueError("pagination changed source window")
    if any(params.get(k) != [v] for k, v in base_query.items()):
        raise ValueError("pagination modified verified search contract")
    cursor = params["cursor"]
    if len(cursor) != 1 or not CURSOR_RE.fullmatch(cursor[0]):
        raise ValueError("untrusted or oversized cursor")
    return target


def collect_official_retrofit_releases(
    *, clock: datetime, fetch_json: Callable[[str], object],
    backfill_age_days: int | None = None,
) -> dict:
    """Complete bounded per-stage *update-window* walk; fail on truncation.

    No keyword server filters exist: keep full original-source coverage
    accounting, then derive relevant title research observations locally.
    Updated dates are source-update windows, not publication dates.
    """
    all_relevant: dict[tuple[str, str], dict] = {}
    all_observed: dict[tuple[str, str], dict] = {}
    seen_pages: set[str] = set()
    total_releases = 0
    pages = 0
    hashes = []
    base_start = clock.date() - timedelta(days=DAYS_PER_SCAN - 1)
    days = [base_start + timedelta(days=delta) for delta in range(DAYS_PER_SCAN)]
    if backfill_age_days is not None:
        if (type(backfill_age_days) is not int
                or not DAYS_PER_SCAN <= backfill_age_days <= MAX_HISTORY_AGE_DAYS):
            raise ValueError("invalid historical review age")
        day = clock.date() - timedelta(days=backfill_age_days)
        if day not in days:
            days.append(day)
    for day in days:
        window_to = (
            clock.strftime("%Y-%m-%dT%H:%M:%S") if day == clock.date()
            else day.isoformat() + "T23:59:59"
        )
        # The provider currently returns zero for a comma-separated stage
        # filter despite documenting it. Single-stage queries were verified
        # on the original API on 3 November; preserve that exact contract.
        for stage in SCAN_STAGES:
            contract = {
                "updatedFrom": day.isoformat() + "T00:00:00",
                "updatedTo": window_to,
                "stages": stage,
                "limit": str(PAGE_LIMIT),
            }
            url = OFFICIAL_RELEASES + "?" + urlencode(contract)
            for page_no in range(MAX_PAGES_PER_DAY):
                if url in seen_pages:
                    raise ValueError("repeated procurement continuation URL")
                seen_pages.add(url)
                package = fetch_json(url)
                if not isinstance(package, Mapping):
                    raise ValueError("official package not a mapping")
                # Reuse the original parser for every page and stage.
                reviewed = review_official_retrofit_tender_sample(
                    start_date=day, end_date=day, limit=PAGE_LIMIT,
                    observed_at=clock, fetch_json=lambda _: package,
                )
                rows = package.get("releases")
                if not isinstance(rows, list):
                    raise ValueError("official releases missing")
                pages += 1
                total_releases += len(rows)
                hashes.append(sha256(json.dumps(
                    package, sort_keys=True, default=str
                ).encode()).hexdigest())
                for record in reviewed["notices"]:
                    key = (record["ocid"], record["release_id"])
                    if key in all_observed and all_observed[key] != record:
                        raise ValueError("conflicting duplicate official release")
                    all_observed[key] = record
                    if record["retrofit_title_relevance_review_needed"]:
                        all_relevant[key] = record
                continuation = _page_next(package, base_query=contract)
                if continuation is None:
                    # Exactly 100 records without an explicit next-page link
                    # is ambiguous. Never claim complete coverage on a full
                    # bounded response with missing pagination provenance.
                    if len(rows) == PAGE_LIMIT:
                        raise ValueError("official full page missing continuation evidence")
                    break
                if page_no + 1 == MAX_PAGES_PER_DAY:
                    raise ValueError("official source pagination exceeds bounded budget")
                url = continuation
    return {
        "notices": list(all_relevant.values()),
        "all_notices": list(all_observed.values()),
        "official_pages_examined": pages,
        "official_releases_examined": total_releases,
        "source_page_sha256": hashes,
        "window_from": base_start.isoformat(),
        "window_to": clock.date().isoformat(),
        "historical_backfill_day": (
            (clock.date() - timedelta(days=backfill_age_days)).isoformat()
            if backfill_age_days is not None else None
        ),
        "pagination_completed_within_budget": True,
        "official_api_url": OFFICIAL_RELEASES,
    }


def _retain_previous_relevant(previous: Mapping, scan: Mapping, *, clock: datetime) -> dict:
    """Keep published research with true stage chronology across update windows.

    A newer amendment or award with a generic title can update the lifecycle
    of an earlier relevant OCID. Inherited relevance is explicitly labelled
    and cannot certify a contractor, deadline, scope or payment.
    """
    prior_valid = (
        previous.get("schema_version") == SCHEMA
        and previous.get("official_publisher_validated") is True
        and previous.get("mode") == "OBSERVE"
        and previous.get("execution_authority") == "none"
        and previous.get("outbound_enabled") is False
        and previous.get("production_writes") is False
    )
    previous_rows = previous.get("notices") if prior_valid else []
    if not isinstance(previous_rows, list):
        previous_rows = []
    known: dict[tuple[str, str], dict] = {}
    relevance: dict[str, tuple[list[str], str]] = {}
    for row in previous_rows:
        if not isinstance(row, Mapping):
            continue
        ocid, release = row.get("ocid"), row.get("release_id")
        if not isinstance(ocid, str) or not OCID.fullmatch(ocid):
            continue
        if not isinstance(release, str) or not NOTICE.fullmatch(release):
            continue
        try:
            event = _timestamp(row.get("official_event_time"))
        except ValueError:
            continue
        if not timedelta(0) <= clock - event <= timedelta(days=RETAIN_DAYS):
            continue
        if row.get("retrofit_title_relevance_review_needed") is not True:
            continue
        labels = row.get("title_relevance_labels")
        if not isinstance(labels, list) or not all(isinstance(x,str) for x in labels):
            continue
        reference = row.get("relevance_evidence_url") or row.get("official_notice_url")
        if not isinstance(reference, str) or not reference.startswith(
            "https://www.find-tender.service.gov.uk/Notice/"
        ):
            continue
        relevance[ocid] = (labels, reference)
        known[(ocid, release)] = dict(row)
    # Only an actual relevant title or a historically related *same OCID*
    # may qualify an unrelated later award/notice for market review.
    for row in scan["notices"]:
        relevance[row["ocid"]] = (
            row["title_relevance_labels"], row["official_notice_url"]
        )
    by_key = known
    for row in scan["all_notices"]:
        ocid = row["ocid"]
        if ocid not in relevance:
            continue
        item = dict(row)
        if not item["retrofit_title_relevance_review_needed"]:
            item["retrofit_title_relevance_review_needed"] = True
            item["title_relevance_labels"] = list(relevance[ocid][0])
            item["relevance_evidence_url"] = relevance[ocid][1]
            item["relevance_inherited_from_prior_notice"] = True
        else:
            item["relevance_evidence_url"] = item["official_notice_url"]
            item["relevance_inherited_from_prior_notice"] = False
        item["carried_forward_prior_scan"] = False
        item["last_seen_source_scan_at"] = clock.isoformat()
        by_key[(ocid, item["release_id"])] = item
    for key, item in by_key.items():
        if item.get("last_seen_source_scan_at") != clock.isoformat():
            item["carried_forward_prior_scan"] = True
            item["last_seen_source_scan_at"] = (
                item.get("last_seen_source_scan_at") or previous.get("generated_at")
            )
    ordered = sorted(
        by_key.values(), key=lambda x: (
            str(x.get("official_event_time") or ""), str(x.get("release_id") or "")
        ), reverse=True,
    )
    kept = ordered[:MAX_RETAINED_RELEVANT]
    return {
        "notices": kept,
        "retained_relevant_total_before_cap": len(ordered),
        "retained_relevant_truncated": len(ordered) > MAX_RETAINED_RELEVANT,
        "carried_forward_prior_scan_count": sum(
            x.get("carried_forward_prior_scan") is True for x in kept
        ),
    }


def refresh_official_retrofit_tender_source(
    root: Path, *, now: datetime | None = None,
    fetch_json: Callable[[str], object] | None = None,
) -> dict:
    """Original read-only source, now cursor-complete within bounded windows."""
    clock = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    source = root / SOURCE_SNAPSHOT
    check = root / SOURCE_CHECK
    if source.is_symlink() or check.is_symlink():
        return {"status": "SOURCE_PATH_UNSAFE", "source_available": False,
                "execution_authority": "none"}
    prior_check = _snapshot_json(check)
    try:
        checked = _timestamp(prior_check.get("checked_at"))
    except ValueError:
        checked = None
    try:
        blocked_until = _timestamp(prior_check.get("retry_not_before"))
    except ValueError:
        blocked_until = None
    if ((checked and timedelta(0) <= clock - checked < SOURCE_POLL_INTERVAL)
            or (blocked_until is not None and clock < blocked_until)):
        return {
            "status": "SOURCE_POLL_THROTTLED",
            "last_check_status": prior_check.get("status"),
            "source_available": (
                prior_check.get("status") == "OFFICIAL_SOURCE_OBSERVED"
                and bool(_snapshot_json(source))
            ),
            "execution_authority": "none",
        }
    try:
        history_day = date.fromisoformat(prior_check["next_backfill_date"])
    except (ValueError, TypeError, KeyError):
        history_day = clock.date() - timedelta(days=3)
    if not 3 <= (clock.date() - history_day).days <= MAX_HISTORY_AGE_DAYS:
        history_day = clock.date() - timedelta(days=3)
    age = (clock.date() - history_day).days
    reason = None
    retry_after = None
    try:
        if fetch_json is None:
            from empire_os.acquisition_official_tender_intake import _fetch_package
            fetch_json = _fetch_package
        scan = collect_official_retrofit_releases(
            clock=clock, fetch_json=fetch_json, backfill_age_days=age,
        )
        retained = _retain_previous_relevant(
            _snapshot_json(source), scan, clock=clock
        )
        observed = {
            "schema_version": SCHEMA,
            "mode": "OBSERVE",
            "generated_at": clock.isoformat(),
            "source_id": SOURCE,
            "official_source_license": OGL_V3,
            "official_publisher_validated": True,
            "non_exhaustive_sample": True,  # bounded timeframe, not all UK tenders
            "official_api_url": scan["official_api_url"],
            "window_from": scan["window_from"],
            "window_to": scan["window_to"],
            "official_pages_examined": scan["official_pages_examined"],
            "official_releases_examined": scan["official_releases_examined"],
            "source_stage_filters": list(SCAN_STAGES),
            "historical_backfill_day": scan["historical_backfill_day"],
            "source_page_sha256": scan["source_page_sha256"],
            "pagination_completed_within_budget": True,
            "requested_limit": PAGE_LIMIT,
            "sample_count": len(retained["notices"]),
            "title_relevance_candidate_count": len(retained["notices"]),
            **retained,
            "confirmed_retrofit_tender_count": 0,
            "bid_submission_enabled": False,
            "outbound_enabled": False,
            "production_writes": False,
            "verified_buyer_count": 0,
            "revenue_gbp": 0,
            "execution_authority": "none",
        }
        _write_private_snapshot(source, observed)
        state = "OFFICIAL_SOURCE_OBSERVED"
        count = len(retained["notices"])
    except Exception as exc:
        state = "OFFICIAL_SOURCE_UNVERIFIED"
        reason = type(exc).__name__
        count = 0
        if isinstance(exc, HTTPError) and exc.code in (429, 503):
            try:
                seconds = int(exc.headers.get("Retry-After", "0"))
                if 0 < seconds <= 86400:
                    retry_after = seconds
            except (TypeError, ValueError, AttributeError):
                pass
    receipt = {
        "schema_version": "empire.retrofit_official_tender_source_check.v1",
        "mode": "OBSERVE",
        "checked_at": clock.isoformat(),
        "status": state,
        "source_available": state == "OFFICIAL_SOURCE_OBSERVED",
        "title_candidate_count": count,
        "historical_backfill_day": (
            scan.get("historical_backfill_day")
            if state == "OFFICIAL_SOURCE_OBSERVED" else None
        ),
        "next_backfill_date": (
            (history_day - timedelta(days=1)).isoformat()
            if state == "OFFICIAL_SOURCE_OBSERVED"
            else history_day.isoformat()
        ),
        "error_type": reason,
        "retry_after_seconds": retry_after,
        "retry_not_before": (
            (clock + timedelta(seconds=retry_after)).isoformat()
            if retry_after else None
        ),
        "execution_authority": "none",
        "outbound": False, "db_write": False, "payment_execution": False,
    }
    _write_private_snapshot(check, receipt)
    return receipt
