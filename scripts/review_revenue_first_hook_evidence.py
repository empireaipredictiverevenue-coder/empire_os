#!/usr/bin/env python3
"""Run one read-only SEO/website/CRM/revenue hook replay against existing sources.

The only network actions are bounded GETs to the already-running loopback
Search Intelligence read API and, when requested, four public website routes.
This operator performs no workflow dispatch, publication, subscribed audience
enrolment, database write, model inference, email or payment.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from empire_os.revenue_first_hook_evidence import review_revenue_first_sources


CANONICAL = Path("/srv/empire_os")
SOURCES = {
    "conversion_snapshot": Path("runtime/conversion/latest.json"),
    "reply_collector": Path("runtime/conversations_replies_control/collector_health_latest.json"),
    "revenue_pulse": Path("runtime/revenue_pulse/latest.json"),
}
SEARCH_URL = "http://127.0.0.1:8771/v1/search/summary"
FOUNDER_MAILBOX_SUMMARY_URL = "http://127.0.0.1:8766/v1/founder-mailbox/summary?limit=10"
SEARCH_DAILY_URL = "http://127.0.0.1:8771/v1/search/search-console/daily"
PUBLIC_BASE = "https://empire-ai.co.uk"
PUBLIC_PATHS = (
    "/", "/about", "/commercial", "/insights/revenue-opportunity-assessment",
)
MAX_JSON = 524_288


def _read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON:
        raise ValueError("missing_or_oversize_source:" + path.name)
    data = json.loads(path.read_text("utf8"))
    if not isinstance(data, dict):
        raise ValueError("source_must_be_dict:" + path.name)
    return data


def _search_summary(now: datetime) -> dict[str, Any]:
    req = Request(
        SEARCH_URL,
        method="GET",
        headers={"Accept": "application/json", "User-Agent": "EmpireOS-HookEvidenceRead/1.0"},
    )
    with urlopen(req, timeout=5) as response:
        if response.status != 200:
            raise ValueError("search_read_api_unavailable")
        payload = response.read(MAX_JSON + 1)
        if len(payload) > MAX_JSON:
            raise ValueError("search_read_api_response_too_large")
        source = json.loads(payload)
        if not isinstance(source, dict):
            raise ValueError("invalid_search_summary")
        # The source has no native created_at field: accurately mark the
        # instant a bounded, successful read was performed.
        return {**source, "observed_at": now.isoformat()}


def _search_console_daily(now: datetime) -> dict[str, Any]:
    # Date-scoped summary only; no query text, search terms, personal identifiers,
    # backlink outreach or unsupported claims of rank/Google indexation.
    start = (now - timedelta(days=7)).date().isoformat()
    end = (now - timedelta(days=1)).date().isoformat()
    req = Request(
        f"{SEARCH_DAILY_URL}?start_date={start}&end_date={end}&limit=14",
        method="GET",
        headers={"Accept": "application/json", "User-Agent": "EmpireOS-HookEvidenceRead/1.0"},
    )
    with urlopen(req, timeout=6) as response:
        if response.status != 200:
            raise ValueError("search_console_daily_unavailable")
        raw = response.read(MAX_JSON + 1)
        if len(raw) > MAX_JSON:
            raise ValueError("search_console_daily_response_too_large")
        daily = json.loads(raw)
        if not isinstance(daily, dict):
            raise ValueError("invalid_daily_aggregate")
        return {**daily, "observed_at": now.isoformat()}


def _founder_mailbox_summary(now: datetime) -> dict[str, Any]:
    # The Founder API exposes recorded EmpireDB replies, NOT general Gmail.
    # Read a bounded summary only: no email identities, bodies or thread rows.
    request = Request(
        FOUNDER_MAILBOX_SUMMARY_URL,
        method="GET",
        headers={"Accept": "application/json", "User-Agent": "EmpireOS-HookEvidenceRead/1.0"},
    )
    with urlopen(request, timeout=5) as response:
        if response.status != 200:
            raise ValueError("founder_mailbox_read_api_unavailable")
        raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("founder_mailbox_read_api_response_too_large")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("founder_mailbox_summary_invalid")
        return {**data, "observed_at": now.isoformat()}


def _website_route_status() -> dict[str, Any]:
    observations: dict[str, int | str] = {}
    for path in PUBLIC_PATHS:
        req = Request(
            PUBLIC_BASE + path,
            method="GET",
            headers={"User-Agent": "EmpireOS-HookEvidenceRead/1.0"},
        )
        try:
            with urlopen(req, timeout=6) as response:
                # Bounded page read only, no form submit, no file mutation.
                response.read(8192)
                observations[path] = int(response.status)
        except Exception:
            observations[path] = "UNAVAILABLE"
    return {"pages": observations}


def run(*, root: Path, include_public_website: bool, now: datetime | None = None) -> dict[str, Any]:
    clock = now or datetime.now(timezone.utc)
    loaded = {}
    for name, relative in SOURCES.items():
        target = root / relative
        try:
            loaded[name] = _read_json(target)
        except (ValueError, OSError, UnicodeError, json.JSONDecodeError):
            loaded[name] = None
    try:
        search = _search_summary(clock)
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError, TimeoutError):
        search = None
    try:
        daily = _search_console_daily(clock)
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError, TimeoutError):
        daily = None
    try:
        mailbox = _founder_mailbox_summary(clock)
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError, TimeoutError):
        mailbox = None
    website = _website_route_status() if include_public_website else None
    return review_revenue_first_sources(
        search_summary=search,
        search_console_daily=daily,
        founder_mailbox_summary=mailbox,
        conversion_snapshot=loaded["conversion_snapshot"],
        reply_collector=loaded["reply_collector"],
        revenue_pulse=loaded["revenue_pulse"],
        website_checks=website,
        now=clock,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-public-website", action="store_true",
        help="GET four known, first-party live pages; no conversions or submissions",
    )
    args = parser.parse_args()
    result = run(root=CANONICAL, include_public_website=args.include_public_website)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
