#!/usr/bin/env python3
"""Compare a candidate flagship static build against independently live bytes.

This is a release gate, not an uploader. Source imports are necessary but
insufficient: the candidate must not silently overwrite approved live pages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

APPROVED_HOME_SHA = "0e63856577b9894ebc62d3715f95cb96e788c4caf9c0e45c382e14bb5cbecf1c"
PROTECTED = (
    "index.html",
    "roofing.html",
    "industries/roofing.html",
    "industries/solar.html",
    "buy.html",
    "commercial.html",
    "predictive-revenue.html",
    "trust.html",
)
HOMEPAGE_TOKENS = (b"Intelligence Infrastructure", b"ENTER THE SYSTEM",
                   b"/brand/empire-orbital-a-reference-mark.webp")
SOURCE_IMPORT = 'import CinematicExperience from "@/components/CinematicExperience";'
SCHEMA = "empire.flagship.cinematic_source_build_review.v1"


def _digest(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def review(candidate: Path, live: Path, source: Path) -> dict:
    entry = source / "src/app/page.tsx"
    source_ok = entry.is_file() and SOURCE_IMPORT in entry.read_text(encoding="utf-8")
    live_home = live / "out/index.html"
    built_home = candidate / "out/index.html"
    old_brand_source_blocked = not source_ok
    protected = []
    for path in PROTECTED:
        current, build = live / "out" / path, candidate / "out" / path
        a = _digest(current) if current.is_file() else None
        b = _digest(build) if build.is_file() else None
        protected.append({
            "path": path,
            "live_sha256": a,
            "candidate_sha256": b,
            "byte_identical": a is not None and a == b,
        })
    tokens_ok = (built_home.is_file() and all(
        t in built_home.read_bytes() for t in HOMEPAGE_TOKENS))
    live_approved = live_home.is_file() and _digest(live_home) == APPROVED_HOME_SHA
    drift = [r["path"] for r in protected if not r["byte_identical"]]
    # Deliberately require independent exact page evidence. A passing
    # Next.js build never authorizes a new whole-site release.
    approved_for_full_static_release = (
        source_ok and tokens_ok and live_approved and not drift)
    return {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY",
        "source_imports_cinematic": source_ok,
        "source_still_uses_old_theme": old_brand_source_blocked,
        "candidate_contains_cinematic_art": tokens_ok,
        "live_approved_cinematic_homepage_verified": live_approved,
        "protected_pages_checked": len(protected),
        "protected_page_differences": drift,
        "comparison": protected,
        "full_site_release_authorized": approved_for_full_static_release,
        "next_action": "RECONCILE_EXACT_APPROVED_SECTOR_AND_CHECKOUT_PAGES"
            if drift else "VERIFY_INDEPENDENT_RELEASE_APPROVAL",
        "production_files_modified": False,
        "caller_data_read": False,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--candidate", type=Path,
                   default=Path("/home/ubuntu/empire_worktrees/flagship_current_cinematic_source_guard_20261020/apps/empire-public-site"))
    p.add_argument("--live", type=Path,
                   default=Path("/srv/empire_os/apps/empire-public-site"))
    p.add_argument("--source", type=Path)
    a = p.parse_args()
    status = review(a.candidate, a.live, a.source or a.candidate)
    print(json.dumps(status, sort_keys=True))
    return 0 if status["full_site_release_authorized"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
