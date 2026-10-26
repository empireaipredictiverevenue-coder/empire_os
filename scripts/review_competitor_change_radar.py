#!/usr/bin/env python3
"""Original EmpireOS competitor change radar: bounded, observe-only research.

Input mode consumes previously fetched, robots-permitted public HTML receipts.
Live mode REUSES original operator atlas and first-party robots/fetch functions.
No automatic marketing, new scheduler, buyer promotion, DB or payment writes.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from empire_os.competitor_change_radar import build_radar, SCHEMA
from empire_os.competitor_call_channel_atlas import DOMAINS
from empire_os.competitor_call_source_watch import permitted_by_robots, fetch_html


def _load(path: Path, limit: int = 5_000_000) -> dict:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
        raise ValueError("invalid/oversize source JSON")
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("source JSON object required")
    return result


def _live_rows(atlas: dict, max_sources: int, cursor: int = 0) -> tuple[list[dict], list[dict], int, list[str]]:
    if atlas.get("schema_version") != "empire.competitor_call_acquisition_atlas.v1" or (
        atlas.get("outreach_enabled") is not False
        or atlas.get("execution_authority") != "none"
    ):
        raise ValueError("untrusted original operator atlas")
    urls = []
    for profile in atlas.get("operator_profiles", []):
        owner = profile.get("operator_id")
        if owner not in DOMAINS:
            raise ValueError("operator not allowlisted")
        for page in profile.get("sources", []):
            url = page.get("url")
            u = urlsplit(url)
            if (u.scheme != "https" or u.hostname not in DOMAINS[owner]
                    or u.username or u.password or u.port is not None or u.fragment):
                raise ValueError("source not permitted by original operator atlas")
            urls.append((owner, url))
    if len(urls) != atlas.get("source_count") or not 1 <= len(urls) <= 30:
        raise ValueError("untrusted source count")
    ordered = sorted(urls)
    if type(cursor) is not int or cursor < 0 or cursor >= len(ordered):
        cursor = 0
    rows, failures, checked = [], [], []
    observed_hosts = set()
    attempts = 0
    while len(checked) < max_sources and attempts < len(ordered):
        owner, url = ordered[(cursor + attempts) % len(ordered)]
        attempts += 1
        host = urlsplit(url).hostname
        if host in observed_hosts:
            continue
        observed_hosts.add(host)
        checked.append(url)
        if not permitted_by_robots(url):
            failures.append({"source_ref": url, "reason": "ROBOTS_DISALLOWED_OR_UNAVAILABLE"})
            continue
        page = fetch_html(url)
        if not page:
            failures.append({"source_ref": url, "reason": "PUBLIC_HTML_UNAVAILABLE"})
            continue
        rows.append({
            "entity_id": owner, "company_name": owner.replace("_", " ").title(),
            "industry": "call_acquisition_operator", "territory": "US",
            "source_ref": url, "observed_at": datetime.now(timezone.utc).isoformat(),
            "html": page, "fetch_authority": "PUBLIC_ROBOTS_PERMITTED",
        })
    return rows, failures, (cursor + attempts) % len(ordered), checked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--observations-file", type=Path)
    group.add_argument("--live-original-atlas", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--max-sources", type=int, default=2)
    parser.add_argument("--output", type=Path, help="Explicit path: candidate snapshot only")
    args = parser.parse_args(argv)
    if not 1 <= args.max_sources <= 2:
        raise ValueError("bounded public source inspection limited to 2 distinct domains")
    previous = _load(args.previous) if args.previous else None
    if previous and (previous.get("schema_version") != SCHEMA
                     or previous.get("execution_authority") != "none"):
        raise ValueError("untrusted previous snapshot")
    if args.live_original_atlas:
        rows, failures, next_cursor, checked = _live_rows(
            _load(args.live_original_atlas), args.max_sources,
            cursor=previous.get("atlas_cursor", 0) if previous else 0,
        )
    else:
        data = _load(args.observations_file)
        rows = data.get("observations")
        if not isinstance(rows, list) or len(rows) > args.max_sources:
            raise ValueError("too many supplied observations")
        failures = []
        next_cursor, checked = None, [row.get("source_ref") for row in rows]
    result = build_radar(rows, previous=previous)
    if next_cursor is not None:
        result["atlas_cursor"] = next_cursor
    result["checked_urls_this_run"] = checked
    result["source_failures_this_run"] = failures
    result["source_fetch_mode"] = "ORIGINAL_ATLAS_READ" if args.live_original_atlas else "SUPPLIED_PUBLIC_RECEIPTS"
    result["no_new_scheduler"] = True
    result["database_writes"] = False
    if args.output:
        dest = args.output.resolve()
        # Intentionally disallow implicit live runtime publication; owner handoff required.
        if str(dest).startswith("/srv/empire_os/runtime/") or str(dest).startswith("/etc/"):
            raise ValueError("direct production runtime publication not authorized")
        if not dest.parent.is_dir() or dest.is_symlink():
            raise ValueError("candidate output directory must exist and be safe")
        import os
        import tempfile
        fd, tmp = tempfile.mkstemp(prefix=".change-radar-", dir=dest.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w") as handle:
                json.dump(result, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(tmp, dest)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    # Avoid printing saved public snippets accidentally to terminal logs.
    print(json.dumps({k: v for k, v in result.items()
        if k not in {"observations", "comparisons", "review_queue"}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
