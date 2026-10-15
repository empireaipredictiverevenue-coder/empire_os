#!/usr/bin/env python3
"""One-shot read-only first-party SEO -> PPC commercial evidence probe.

Consumes a previously reviewed GSC baseline. Fetches only fixed Empire-owned
pages (no redirects, API credentials, new scheduler, billing or website writes).
Prints bounded JSON; does not copy HTML or consumer data into a report.
"""
from __future__ import annotations

import argparse
from datetime import date
from html.parser import HTMLParser
import json
from pathlib import Path
from typing import Any, Callable

import requests

from empire_os.search_intelligence.organic_ppc_commercial_review import (
    PAGE_PATHS, review_owned_organic_ppc,
)

BASELINE_ROOT = Path("/var/tmp")
ORIGIN = "https://empire-ai.co.uk"
WWW = "https://www.empire-ai.co.uk/"


class Metadata(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_count = 0
        self.h1_count = 0
        self.description = False
        self.canonicals: list[str] = []
        self.robots: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        data = dict(attrs)
        if tag == "title":
            self.title_count += 1
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "meta" and str(data.get("name", "")).casefold() == "description":
            self.description = bool(str(data.get("content", "")).strip())
        elif tag == "meta" and str(data.get("name", "")).casefold() == "robots":
            self.robots.append(str(data.get("content", "")))
        elif tag == "link" and "canonical" in str(data.get("rel", "")).casefold().split():
            self.canonicals.append(str(data.get("href", "")))


def _load_local_baseline(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("existing_non_symlink_gsc_evidence_required")
    real = path.resolve()
    if not real.is_relative_to(BASELINE_ROOT.resolve()) or real.stat().st_size > 160_000:
        raise ValueError("untrusted_local_gsc_source")
    try:
        data = json.loads(real.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        raise ValueError("untrusted_local_gsc_source") from None
    if not isinstance(data, dict):
        raise ValueError("untrusted_local_gsc_source")
    return data


def probe_owned_pages(
    *, getter: Callable[..., Any] = requests.get,
) -> tuple[list[dict[str, Any]], int | None, str | None]:
    pages = []
    for path in PAGE_PATHS:
        url = ORIGIN + path
        try:
            response = getter(url, timeout=7, allow_redirects=False, headers={
                "User-Agent": "EmpireOS-Owned-OrganicPPC-Review/1.0"
            })
            status = response.status_code
            if type(status) is not int or not 100 <= status <= 599:
                raise ValueError("unexpected_site_http_response")
            if status == 200 and len(response.content) <= 250_000:
                parsed = Metadata()
                parsed.feed(response.text)
                canonical = parsed.canonicals[0] if len(parsed.canonicals) == 1 else None
                robots = " ".join(parsed.robots)
                xrobots = response.headers.get("X-Robots-Tag", "")
                if xrobots:
                    robots += " " + str(xrobots)[:100]
                pages.append({
                    "path": path, "http": status,
                    "title_present": parsed.title_count == 1,
                    "h1_count": parsed.h1_count,
                    "canonical": canonical,
                    "robots": robots[:160],
                    "description_present": parsed.description,
                })
                continue
            pages.append({
                "path": path, "http": status,
                "title_present": False, "h1_count": 0,
                "canonical": None, "robots": "",
                "description_present": False,
            })
        except (requests.RequestException, ValueError, UnicodeError):
            pages.append({
                "path": path, "http": None,
                "title_present": False, "h1_count": None,
                "canonical": None, "robots": "",
                "description_present": False,
            })
    try:
        r = getter(WWW, timeout=7, allow_redirects=False, headers={
            "User-Agent": "EmpireOS-Owned-OrganicPPC-Review/1.0"
        })
        www_status = r.status_code if type(r.status_code) is int else None
        location = r.headers.get("Location") if www_status in (301, 308) else None
    except requests.RequestException:
        www_status, location = None, None
    # Do not echo untrusted redirect hosts or anything from body.
    if location not in (ORIGIN, ORIGIN + "/"):
        location = None
    return pages, www_status, location


def run(*, baseline_path: Path,
        getter: Callable[..., Any] = requests.get,
        today: date | None = None) -> dict[str, Any]:
    baseline = _load_local_baseline(baseline_path)
    actual_today = today or date.today()
    try:
        end = date.fromisoformat(baseline["window"]["end"])
    except (KeyError, ValueError, TypeError):
        raise ValueError("invalid_reviewed_gsc_window") from None
    if not 0 <= (actual_today - end).days <= 7:
        raise ValueError("gsc_evidence_stale_or_future")
    pages, status, location = probe_owned_pages(getter=getter)
    return review_owned_organic_ppc(
        baseline, pages=pages,
        www_home_http=status,
        www_home_redirect_location=location,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe Empire-owned organic and PPC readiness")
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(baseline_path=args.baseline)
    except Exception as exc:
        # Do not include customer data, HTTP response bodies, credentials or
        # URLs from failures in operator output.
        print(json.dumps({
            "status": "EVIDENCE_HOLD", "reason_code": type(exc).__name__,
            "paid_media_spend_authorized": False,
            "live_referral_redirects_enabled": False,
            "production_publish_authorized": False,
            "execution_authority": "none",
        },sort_keys=True))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
