"""Bounded, crash-replay-safe UK tender cursor miner (feature-only).

Only the existing public Find a Tender OCDS GET. One page per explicit
invocation. High watermark advances ONLY after the final page; no lost pages
on interruption or overlap. Local checkpoint may be explicitly staged in the
isolated feature worktree, NEVER in /srv/empire_os or EmpireDB.

This is public procurement evidence, not a qualified sale or buyer contract.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import parse_qs, urlencode, urlsplit
import fcntl
import json
import os
import re
import tempfile
import urllib.error
import urllib.request

from empire_os.uk_public_tender_observer import (
    BASE, MAX_BYTES, PAGE_LIMIT, _RejectRedirects,
    normalize_uk_tender_releases,
)

SCHEMA = "empire.uk_tender_incremental_checkpoint.v2"
REPORT_SCHEMA = "empire.uk_tender_incremental_page_review.v1"
STAGE_PATH = "runtime/source_intelligence/uk_tender_incremental_v2.json"
LEGACY_STAGE_PATH = "runtime/source_intelligence/uk_tender_incremental_v1.json"
MAX_PAGES_PER_WINDOW = 100
SOURCE_PARTITION_HOURS = 4
INITIAL_BACKFILL_DAYS = 7
MAX_RECENT = 1200
MAX_PENDING_RESEARCH = 100
MAX_CHECKPOINT_BYTES = 350_000
CURSOR_PATTERN = re.compile(r"[A-Za-z0-9=]{1,300}\Z")
DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


class TenderIncrementalHold(RuntimeError):
    """Source or state is inconsistent; DO NOT advance high watermark."""


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("timezone-aware observation required")
    return value.astimezone(timezone.utc)


def empty_checkpoint() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "last_complete_window_end": None,
        "recent": {},
        "inflight": None,
        "pending_sector_research": {},
    }


def _date(value: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value
    ):
        raise TenderIncrementalHold("invalid source update-window timestamp")
    try:
        return datetime.strptime(value, TIME_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise TenderIncrementalHold("invalid calendar source update window") from exc


def _serialized(state: Mapping[str, Any]) -> bytes:
    try:
        encoded = (json.dumps(state, sort_keys=True, separators=(",", ":"),
                              allow_nan=False) + "\n").encode()
    except (TypeError, ValueError) as exc:
        raise TenderIncrementalHold("source checkpoint cannot be serialized") from exc
    if not 0 < len(encoded) <= MAX_CHECKPOINT_BYTES:
        raise TenderIncrementalHold("source checkpoint exceeds bounded storage")
    return encoded


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and DIGEST_PATTERN.fullmatch(value) is not None


def _validate_pending_research(key: Any, row: Any) -> None:
    from empire_os.uk_public_tender_observer import CPV_CLASSES
    if (not _is_digest(key) or not isinstance(row, Mapping)
            or set(row) != {"source_ref", "release_digest", "process_digest",
                           "verticals", "source_window_complete"}
            or not all(_is_digest(row.get(field))
                       for field in ("release_digest", "process_digest"))
            or type(row.get("source_window_complete")) is not bool
            or not isinstance(row.get("verticals"), list)
            or not 1 <= len(row["verticals"]) <= 4
            or len(set(row["verticals"])) != len(row["verticals"])
            or any(value not in set(CPV_CLASSES.values())
                   for value in row["verticals"])
            or not isinstance(row.get("source_ref"), str)
            or not re.fullmatch(
                r"https://www\.find-tender\.service\.gov\.uk/api/1\.0/"
                r"ocdsRecordPackages/ocds-[a-z0-9]{6}-[A-Za-z0-9-]{1,80}",
                row["source_ref"],
            )):
        raise TenderIncrementalHold("untrusted procurement research outbox")


def _state(original: Any, now: datetime) -> dict[str, Any]:
    """Validate untrusted persisted progress rather than trusting its flags."""
    if not isinstance(original, Mapping):
        raise TenderIncrementalHold("source checkpoint must be mapping")
    if set(original) != {
        "schema_version", "mode", "execution_authority",
        "last_complete_window_end", "recent", "inflight",
        "pending_sector_research"
    }:
        raise TenderIncrementalHold("source checkpoint contract drift")
    if (original["schema_version"] != SCHEMA
            or original["mode"] != "OBSERVE"
            or original["execution_authority"] != "none"):
        raise TenderIncrementalHold("source checkpoint authority drift")
    recent = original["recent"]
    if not isinstance(recent, Mapping) or len(recent) > MAX_RECENT:
        raise TenderIncrementalHold("unbounded completed source receipts")
    def check_rows(receipts):
        if not isinstance(receipts, Mapping) or len(receipts) > MAX_RECENT:
            raise TenderIncrementalHold("invalid source receipt inventory")
        for release, value in receipts.items():
            if (not _is_digest(release) or not isinstance(value, Mapping)
                    or set(value) != {"semantic_digest", "ocid_digest"}
                    or not _is_digest(value["semantic_digest"])
                    or not _is_digest(value["ocid_digest"])):
                raise TenderIncrementalHold("invalid source receipt identity")
    check_rows(recent)
    pending = original["pending_sector_research"]
    if not isinstance(pending, Mapping) or len(pending) > MAX_PENDING_RESEARCH:
        raise TenderIncrementalHold("unbounded research outbox")
    for key, row in pending.items():
        _validate_pending_research(key, row)
    last = original["last_complete_window_end"]
    if last is not None and _date(last) > now:
        raise TenderIncrementalHold("future source high watermark")
    flight = original["inflight"]
    if flight is not None:
        if not isinstance(flight, Mapping) or set(flight) != {
            "updated_from", "updated_to", "next_cursor",
            "page_count", "seen"
        }:
            raise TenderIncrementalHold("incomplete source flight schema")
        start, end = _date(flight["updated_from"]), _date(flight["updated_to"])
        if not start < end <= now:
            raise TenderIncrementalHold("source flight window outside observation clock")
        if last is not None and start > _date(last):
            raise TenderIncrementalHold("source overlap must not skip watermark")
        cursor = flight["next_cursor"]
        if cursor is not None and (
            not isinstance(cursor, str) or not CURSOR_PATTERN.fullmatch(cursor)
        ):
            raise TenderIncrementalHold("invalid persisted cursor token")
        if (type(flight["page_count"]) is not int
                or not 0 <= flight["page_count"] <= MAX_PAGES_PER_WINDOW):
            raise TenderIncrementalHold("invalid bounded source page counter")
        if (flight["page_count"] == 0) != (cursor is None):
            raise TenderIncrementalHold("source page count and cursor disagree")
        check_rows(flight["seen"])
    validated = json.loads(_serialized(original))
    return validated


def _source_url(begin: str, end: str, cursor: str | None) -> str:
    query = {
        "limit": str(PAGE_LIMIT),
        "stages": "tender",
        "updatedFrom": begin,
        "updatedTo": end,
    }
    if cursor is not None:
        if not CURSOR_PATTERN.fullmatch(cursor):
            raise TenderIncrementalHold("provider cursor contains invalid characters")
        query["cursor"] = cursor
    return BASE + "?" + urlencode(query)


def _next_cursor(document: Mapping[str, Any], begin: str, end: str) -> str | None:
    links = document.get("links")
    if links is None:
        return None
    if not isinstance(links, Mapping):
        raise TenderIncrementalHold("malformed official pagination links")
    next_url = links.get("next")
    if next_url is None:
        return None
    if not isinstance(next_url, str) or len(next_url) > 900:
        raise TenderIncrementalHold("unbounded provider pagination link")
    parts, base = urlsplit(next_url), urlsplit(BASE)
    if (parts.scheme != "https" or parts.netloc != base.netloc
            or parts.path != base.path or parts.fragment or parts.username
            or parts.password):
        raise TenderIncrementalHold("provider next link crosses official host")
    try:
        params = parse_qs(parts.query, strict_parsing=True, keep_blank_values=True)
    except ValueError as exc:
        raise TenderIncrementalHold("malformed provider pagination query") from exc
    if set(params) != {"limit", "stages", "updatedFrom", "updatedTo", "cursor"}:
        raise TenderIncrementalHold("unexpected provider cursor query parameters")
    for key, expected in (
        ("limit", str(PAGE_LIMIT)), ("stages", "tender"),
        ("updatedFrom", begin), ("updatedTo", end),
    ):
        if params.get(key) != [expected]:
            raise TenderIncrementalHold("provider changed frozen update window")
    token = params["cursor"]
    if len(token) != 1 or not CURSOR_PATTERN.fullmatch(token[0]):
        raise TenderIncrementalHold("provider returned invalid cursor")
    return token[0]


def _get_page(begin: str, end: str, cursor: str | None) -> bytes:
    req = urllib.request.Request(_source_url(begin, end, cursor),
        headers={"Accept": "application/json",
                 "User-Agent": "EmpireAI-SourceIntelligence/1.0 (empire-ai.co.uk)"},
        method="GET")
    try:
        with urllib.request.build_opener(_RejectRedirects).open(req, timeout=8) as response:
            if response.status != 200 or "json" not in str(
                    response.headers.get("Content-Type", "")).lower():
                raise TenderIncrementalHold("invalid source content type/status")
            payload = response.read(MAX_BYTES + 1)
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        raise TenderIncrementalHold("official incremental page unavailable") from exc
    if not 0 < len(payload) <= MAX_BYTES:
        raise TenderIncrementalHold("oversized incremental page")
    return payload


def advance_one_public_page(
    previous: Mapping[str, Any],
    *, as_of: datetime,
    fetch_page: Callable[[str, str, str | None], bytes] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """One page; returns proposed state + review. No file or DB writes."""
    now = _utc(as_of)
    state = _state(previous, now)
    if state["inflight"] is None:
        # Backfill begins seven days ago but each individually complete source
        # partition spans at most four hours. A full seven-day cursor run can
        # exceed provider page budgets and would otherwise never complete.
        latest_safe_end = now - timedelta(minutes=5)
        previous_end = state["last_complete_window_end"]
        if previous_end is None:
            start_dt = latest_safe_end - timedelta(days=INITIAL_BACKFILL_DAYS)
            end_dt = min(latest_safe_end, start_dt + timedelta(hours=SOURCE_PARTITION_HOURS))
        else:
            last_end = _date(previous_end)
            start_dt = last_end - timedelta(minutes=5)
            end_dt = min(latest_safe_end, last_end + timedelta(hours=SOURCE_PARTITION_HOURS))
        if start_dt >= end_dt:
            raise TenderIncrementalHold("no completed new source window available")
        state["inflight"] = {
            "updated_from": start_dt.strftime(TIME_FORMAT),
            "updated_to": end_dt.strftime(TIME_FORMAT),
            "next_cursor": None,
            "page_count": 0,
            "seen": {},
        }
    flight = state["inflight"]
    if flight["page_count"] >= MAX_PAGES_PER_WINDOW:
        raise TenderIncrementalHold("provider page budget reached; manual coverage review")
    begin, end, cursor = (
        flight["updated_from"], flight["updated_to"], flight["next_cursor"]
    )
    raw = (fetch_page or _get_page)(begin, end, cursor)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise TenderIncrementalHold("invalid or over-budget provider bytes")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise TenderIncrementalHold("invalid official source JSON") from exc
    if not isinstance(document, Mapping):
        raise TenderIncrementalHold("official source package must be object")
    # Already-verified official Cabinet Office publisher + OGL and bounded
    # records; the normalizer never emits bidder/party contact details.
    page = normalize_uk_tender_releases(document, as_of=now)
    next_cursor = _next_cursor(document, begin, end)
    if page["sample_at_limit"] and next_cursor is None:
        raise TenderIncrementalHold("full source page lacks trusted completion pagination")
    if next_cursor is not None and not page["source_observations"]:
        raise TenderIncrementalHold("empty source page unexpectedly reports next cursor")
    if next_cursor is not None and next_cursor == cursor:
        raise TenderIncrementalHold("provider cursor made no progress")
    changes: list[dict[str, Any]] = []
    kinds: Counter[str] = Counter()
    previously_known_processes = {
        value["ocid_digest"] for value in state["recent"].values()
    } | {value["ocid_digest"] for value in flight["seen"].values()}
    for row in page["source_observations"]:
        release, process, semantic = (
            row["release_digest"], row["ocid_digest"],
            row["source_semantic_digest"],
        )
        if any(not _is_digest(token) for token in (release, process, semantic)):
            raise TenderIncrementalHold("untrusted normalized release receipt")
        identity = {"semantic_digest": semantic, "ocid_digest": process}
        within = flight["seen"].get(release)
        previous_seen = state["recent"].get(release)
        if within is not None and within != identity:
            raise TenderIncrementalHold("same release changed inside a frozen window")
        if within is not None or previous_seen == identity:
            kind = "REPEATED_IDENTICAL_RELEASE"
        elif previous_seen is not None:
            kind = "CHANGED_EXISTING_RELEASE"
        elif process in previously_known_processes:
            kind = "NEW_RELEASE_EXISTING_PROCESS"
        else:
            kind = "NEW_PUBLIC_PROCUREMENT_PROCESS"
        if within is None:
            flight["seen"][release] = identity
        previously_known_processes.add(process)
        kinds[kind] += 1
        if kind != "REPEATED_IDENTICAL_RELEASE":
            changes.append({
                "change_class": kind,
                "release_digest": release,
                "ocid_digest": process,
                "source_record_ref": row["source_record_ref"],
                "verticals_from_official_cpv": row["matched_verticals_from_cpv"],
                "status_as_published": row["source_reported_tender_status"],
                "future_submission_deadline_evidenced": row[
                    "future_submissions_deadline_evidenced"
                ],
                "award_or_revenue_verified": False,
            })
    flight["page_count"] += 1
    if len(flight["seen"]) > MAX_RECENT:
        raise TenderIncrementalHold("source window exceeded safe checkpoint bound")
    flight["next_cursor"] = next_cursor
    finished = next_cursor is None
    if finished:
        updated = dict(state["recent"])
        updated.update(flight["seen"])
        if len(updated) > MAX_RECENT:
            raise TenderIncrementalHold("history bound prevents promoting complete window")
        state["recent"] = updated
        state["last_complete_window_end"] = end
        state["inflight"] = None
    # Durable research outbox committed in the SAME atomic checkpoint as the
    # cursor; replay after crash can never lose a queued sector evidence task.
    for candidate in build_internal_tender_research(review={
        "schema_version": REPORT_SCHEMA,
        "mode": "OBSERVE", "execution_authority": "none",
        "recognized_revenue": False, "outbound_sent": False,
        "window_high_watermark_promoted": finished,
        "non_identical_source_evidence": changes,
    })["candidates"]:
        key = sha256((
            candidate["source_record_digest"] + "|" +
            flight["seen"][candidate["source_record_digest"]]["semantic_digest"]
        ).encode()).hexdigest()
        row = {
            "source_ref": candidate["source_ref"],
            "release_digest": candidate["source_record_digest"],
            "process_digest": candidate["source_process_digest"],
            "verticals": candidate["sector_codes_matched"],
            "source_window_complete": finished,
        }
        if key not in state["pending_sector_research"] and (
            len(state["pending_sector_research"]) >= MAX_PENDING_RESEARCH
        ):
            raise TenderIncrementalHold("research outbox full: do not advance cursor")
        state["pending_sector_research"][key] = row
    _state(state, now)
    report = {
        "schema_version": REPORT_SCHEMA,
        "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "status": "COMPLETE_WINDOW_REVIEW" if finished else "INCOMPLETE_WINDOW_CURSOR_STAGED",
        "frozen_updated_from": begin,
        "frozen_updated_to": end,
        "pages_in_window_so_far": flight["page_count"],
        "source_page_records": page["record_count_in_bounded_page"],
        "pending_sector_research_count": len(state["pending_sector_research"]),
        "source_change_counts_on_this_page": dict(sorted(kinds.items())),
        "non_identical_source_evidence": changes,
        "next_cursor_exists": not finished,
        "window_high_watermark_promoted": finished,
        "progress_is_private_feature_staging_only": True,
        "recognized_revenue": False,
        "buyer_terms_verified": False,
        "contact_extracted": False,
        "outbound_sent": False,
        "source_update_window_is_global_complete": False,
        "bounded_partition_complete": finished,
        "execution_authority": "none",
    }
    report["sector_research"] = build_internal_tender_research(review=report)
    return state, report


def _private_path(worktree_root: Path, *, test_only: bool = False) -> Path:
    root = worktree_root.resolve()
    owned = Path(__file__).resolve().parents[1]
    if root != owned and not test_only:
        raise PermissionError("isolated feature worktree only; no production checkpoint writes")
    if root == Path("/srv/empire_os"):
        raise PermissionError("production source registry must not be touched")
    return root / STAGE_PATH


def _persist_checkpoint(target: Path, state: Mapping[str, Any]) -> None:
    encoded = _serialized(state)
    fd, temp = tempfile.mkstemp(
        dir=target.parent, prefix=".uk_tender_checkpoint.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "wb") as staging:
            os.fchmod(staging.fileno(), 0o600)
            staging.write(encoded)
            staging.flush()
            os.fsync(staging.fileno())
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def advance_private_checkpoint(
    worktree_root: Path,
    *, as_of: datetime,
    apply: bool = False,
    fetch_page: Callable[[str, str, str | None], bytes] | None = None,
    test_only: bool = False,
) -> dict[str, Any]:
    """Explicit side-effect option; preview must not create any state files.

    A private lock covers read+fetch+stage, so parallel invocations cannot
    both advance a source cursor. Crash before atomic replace simply replays.
    """
    target = _private_path(worktree_root, test_only=test_only)
    if not apply:
        if target.exists():
            if target.is_symlink() or target.stat().st_size > MAX_CHECKPOINT_BYTES:
                raise TenderIncrementalHold("unsafe private source checkpoint")
            old = json.loads(target.read_text())
        else:
            old = empty_checkpoint()
        new, result = advance_one_public_page(old, as_of=as_of, fetch_page=fetch_page)
        return dict(result, status="PREVIEW_" + result["status"],
                    window_would_complete_if_applied=result["window_high_watermark_promoted"],
                    window_high_watermark_promoted=False,
                    checkpoint_written=False)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if target.is_symlink() or target.parent.is_symlink():
        raise TenderIncrementalHold("unsafe private source checkpoint path")
    lock = target.with_suffix(".lock")
    if lock.is_symlink():
        raise TenderIncrementalHold("unsafe checkpoint lock")
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "a+b") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            if target.exists():
                if target.is_symlink() or not target.is_file() or (
                    target.stat().st_size > MAX_CHECKPOINT_BYTES
                ):
                    raise TenderIncrementalHold("untrusted checkpoint file")
                old = json.loads(target.read_text())
            else:
                old = empty_checkpoint()
            new, result = advance_one_public_page(
                old, as_of=as_of, fetch_page=fetch_page
            )
            _persist_checkpoint(target, new)
            return dict(result, checkpoint_written=True)
    finally:
        # fd is owned by the context manager after successful fdopen.
        pass


def build_internal_tender_research(*, review: Mapping[str, Any]) -> dict[str, Any]:
    """Source-linked sector matches for HUMAN internal verification only.

    Original published procurement is evidence of organisational purchasing
    requirements; it is not an Empire customer, won bid, payout or permission
    to send anything. Only narrow official CPV codes enter these packets.
    """
    from empire_os.uk_public_tender_observer import CPV_CLASSES

    if (not isinstance(review, Mapping)
            or review.get("schema_version") != REPORT_SCHEMA
            or review.get("mode") != "OBSERVE"
            or review.get("execution_authority") != "none"
            or review.get("recognized_revenue") is not False
            or review.get("outbound_sent") is not False):
        raise TenderIncrementalHold("invalid source review for internal research")
    changes = review.get("non_identical_source_evidence")
    if not isinstance(changes, list) or len(changes) > PAGE_LIMIT:
        raise TenderIncrementalHold("over-budget tender research evidence")
    allowed_verticals = set(CPV_CLASSES.values())
    candidate_rows = []
    seen: set[str] = set()
    for row in changes:
        if not isinstance(row, Mapping):
            raise TenderIncrementalHold("tender research evidence invalid")
        release = row.get("release_digest")
        ocid = row.get("ocid_digest")
        reference = row.get("source_record_ref")
        verticals = row.get("verticals_from_official_cpv")
        kind = row.get("change_class")
        if (not _is_digest(release) or not _is_digest(ocid)
                or release in seen
                or not isinstance(verticals, list)
                or len(verticals) > 4
                or any(not isinstance(v, str) or v not in allowed_verticals
                       for v in verticals)
                or (not isinstance(reference, str)
                    or not re.fullmatch(
                        r"https://www\.find-tender\.service\.gov\.uk/api/1\.0/"
                        r"ocdsRecordPackages/ocds-[a-z0-9]{6}-[A-Za-z0-9-]{1,80}",
                        reference,
                    ))
                or kind not in (
                    "NEW_PUBLIC_PROCUREMENT_PROCESS",
                    "NEW_RELEASE_EXISTING_PROCESS",
                    "CHANGED_EXISTING_RELEASE",
                )):
            raise TenderIncrementalHold("invalid procurement source identity/sector")
        seen.add(release)
        if (not verticals or row.get("status_as_published") != "active"
                or row.get("future_submission_deadline_evidenced") is not True
                or row.get("award_or_revenue_verified") is not False):
            continue
        candidate_rows.append({
            "review_key": "tender_source_" + release[:24],
            "source_ref": reference,
            "source_record_digest": release,
            "source_process_digest": ocid,
            "sector_codes_matched": sorted(set(verticals)),
            "research_instruction": "VERIFY_ORIGINAL_PUBLIC_PROCUREMENT_REQUIREMENTS",
            "source_event_kind": "PUBLISHED_PROCUREMENT_NOTICE",
            "source_window_complete": review.get("window_high_watermark_promoted") is True,
            "independent_current_notice_and_eligibility_check_required": True,
            "opportunity_factory_admission_authorized": False,
            "buyer_terms_or_conversion_probability_proven": False,
            "recognized_revenue_or_award": False,
            "outbound_or_bid_authorized": False,
        })
    return {
        "schema_version": "empire.uk_tender_internal_sector_research.v1",
        "status": (
            "SECTOR_RESEARCH_CANDIDATES" if candidate_rows
            else "NO_MATCHED_ACTIVE_CPV_IN_THIS_PAGE"
        ),
        "candidate_count_in_bounded_page": len(candidate_rows),
        "candidates": candidate_rows,
        "same_procurement_may_have_multiple_releases": True,
        "not_complete_market_coverage": review.get("window_high_watermark_promoted") is not True,
        "new_crm_records_created": False,
        "money_or_bids_placed": False,
        "worker_dispatched": False,
        "execution_authority": "none",
    }


def review_incremental_checkpoint(
    repo_root: Path, *, as_of: datetime,
) -> dict[str, Any]:
    """Safe read-only bounded summary; never emit cursors or release hashes."""
    root = Path(repo_root).resolve()
    now = _utc(as_of)
    target = root / STAGE_PATH
    baseline = {
        "schema_version": "empire.uk_tender_incremental.health.v1",
        "status": "NOT_ACTIVATED",
        "last_complete_window_end": None,
        "inflight_page_count": None,
        "inflight_source_records": None,
        "completed_source_receipt_count": None,
        "pending_sector_research_count": None,
        "complete_source_coverage_claimed": False,
        "caught_up_to_latest_safe_window": False,
        "backfill_remaining_hours": None,
        "next_cursor_or_identifiers_exposed": False,
        "provider_worker_running": False,
        "source_polling_scheduled": False,
        "commercial_execution_authorized": False,
        "execution_authority": "none",
    }
    if not target.exists():
        return baseline
    try:
        if (target.is_symlink() or target.parent.is_symlink()
                or (root / "runtime").is_symlink()
                or not target.is_file()
                or not 0 < target.stat().st_size <= MAX_CHECKPOINT_BYTES):
            raise TenderIncrementalHold("unsafe private checkpoint path")
        state = _state(json.loads(target.read_text(encoding="utf-8")), now)
    except (ValueError, TypeError, OSError, UnicodeError,
            TenderIncrementalHold):
        return dict(baseline, status="UNTRUSTED_PRIVATE_CHECKPOINT")
    inflight = state["inflight"]
    last = _date(state["last_complete_window_end"]) if state["last_complete_window_end"] else None
    lag = max(0.0, ((now - timedelta(minutes=5)) - last).total_seconds() / 3600) if last else None
    caught_up = last is not None and lag is not None and lag <= 0.002
    return dict(
        baseline,
        status=("PARTIAL_BACKFILL" if inflight
                else "CAUGHT_UP_TO_OBSERVATION_LAG" if caught_up
                else "BACKFILL_BEHIND_CURRENT_WINDOW"),
        caught_up_to_latest_safe_window=caught_up,
        backfill_remaining_hours=round(lag, 2) if lag is not None else None,
        last_complete_window_end=state["last_complete_window_end"],
        inflight_page_count=inflight["page_count"] if inflight else 0,
        inflight_source_records=len(inflight["seen"]) if inflight else 0,
        completed_source_receipt_count=len(state["recent"]),
        pending_sector_research_count=len(state["pending_sector_research"]),
        complete_source_coverage_claimed=False,
    )


def deliver_one_pending_sector_review(
    worktree_root: Path,
    *,
    as_of: datetime,
    apply: bool = False,
    department_repo_root: Path | None = None,
    test_only: bool = False,
) -> dict[str, Any]:
    """Idempotent internal ASTRA handoff, with acknowledgement AFTER queue write.

    One verified source reference per invocation; default is read-only.
    Queueing source research does NOT establish a prospect, buyer or order.
    """
    from empire_os.department_work_queue import DepartmentWorkQueue

    now = _utc(as_of)
    target = _private_path(worktree_root, test_only=test_only)
    dept_root = Path(department_repo_root or worktree_root).resolve()
    if apply and dept_root != Path("/srv/empire_os") and not (
        test_only and dept_root == Path(worktree_root).resolve()
    ):
        raise PermissionError("existing canonical ASTRA department queue required")
    if not target.exists() or target.is_symlink() or target.parent.is_symlink():
        return {
            "status": "NO_TRUSTED_PRIVATE_RESEARCH_CHECKPOINT",
            "queued": False, "pending": None,
            "outbound_sent": False, "commercial_execution_authorized": False,
        }
    lock = target.with_suffix(".lock")
    if lock.is_symlink():
        raise TenderIncrementalHold("unsafe private lock")
    if not apply:
        old = _state(json.loads(target.read_text()), now)
        return {
            "status": "REVIEW_ONLY",
            "queued": False,
            "pending": len(old["pending_sector_research"]),
            "outbound_sent": False,
            "commercial_execution_authorized": False,
        }
    # Lock serialises source-cursor writer and research acknowledgement.
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        if not target.is_file() or target.stat().st_size > MAX_CHECKPOINT_BYTES:
            raise TenderIncrementalHold("unsafe private research checkpoint")
        state = _state(json.loads(target.read_text()), now)
        pending = state["pending_sector_research"]
        if not pending:
            return {
                "status": "NO_PENDING_RESEARCH",
                "queued": False, "pending": 0,
                "outbound_sent": False, "commercial_execution_authorized": False,
            }
        key = sorted(pending)[0]
        packet = pending[key]
        step = {
            "step_id": "tender_rev_" + key[:32],
            "goal_key": "verify_real_official_sector_procurement_source",
            "department_keys": ["business_development"],
            "target_component": "existing_source_intelligence_and_opportunity_factory",
            "action": "review_official_public_procurement_notice_for_sector_relevance_and_eligibility",
            "authority": "observe",
            "evidence_refs": [packet["source_ref"]],
            "rationale": "Public OCDS tender observation requires individual official notice verification",
            "success_condition": (
                "Confirm original active notice, sector and bid eligibility in an internal "
                "review; do not assume buyer acceptance, contact, paid work or revenue"
            ),
            "intelligence_request": {
                "official_tender_source_review": {
                    "source_record_digest": packet["release_digest"],
                    "source_process_digest": packet["process_digest"],
                    "source_change_receipt": key,
                    "official_source_ref": packet["source_ref"],
                    "matched_sectors": packet["verticals"],
                    "source_window_complete": packet["source_window_complete"],
                    "source_provenance_independently_recheck_required": True,
                    "notice_is_not_a_won_contract": True,
                    "no_contact_or_price_inferred": True,
                    "crm_admission_authorized": False,
                    "outbound_or_bid_authorized": False,
                },
                "budget": {"requested_model_tokens": 0, "requested_external_cost_cents": 0},
            },
        }
        # The existing queue's deterministic ID protects the handoff if the
        # process crashes after enqueue, before the checkpoint acknowledgement.
        item, created = DepartmentWorkQueue(dept_root).enqueue_step(
            plan_id="uk_tender_sector_source_review_v2", step=step, priority=92
        )
        del pending[key]
        _persist_checkpoint(target, state)
        return {
            "schema_version": "empire.uk_tender_sector_source_handoff.v1",
            "status": "QUEUED" if created else "ALREADY_QUEUED",
            "queued": created,
            "work_id": item.id,
            "pending": len(pending),
            "existing_queue_reused": True,
            "external_spend_cents": 0,
            "outbound_sent": False,
            "commercial_execution_authorized": False,
            "execution_authority": "none",
        }
