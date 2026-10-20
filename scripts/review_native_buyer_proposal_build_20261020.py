#!/usr/bin/env python3
"""Read-only source and static-export evidence for the buyer proposal handoff.

This DOES NOT authorize a new checkout release or rebaseline the legacy
13 October approved manifest. ASTRA's cinematic homepage is separately owned.
"""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys

SCHEMA = "empire.website.native_buyer_proposal_stage.v1"
SOURCES = (
    "src/app/buy/page.tsx",
    "src/app/commercial/page.tsx",
    "src/lib/buyer-proposal-handoff.ts",
)
PAGES = ("buy.html", "commercial.html")
MAX_BYTES = 2_000_000


class _Refs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets: set[str] = set()
        self.external_scripts = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        uri = a.get("src") if tag == "script" else a.get("href") if tag == "link" else None
        if not isinstance(uri, str):
            return
        if tag == "script" and not uri.startswith("/_next/static/"):
            self.external_scripts = True
        if uri.startswith("/_next/static/"):
            path = uri.split("?", 1)[0]
            if path.endswith((".js", ".css", ".woff", ".woff2")):
                self.assets.add(path)


def _bytes(base: Path, relative: str, max_size: int) -> bytes:
    target = base / relative
    if (
        target.is_symlink()
        or not target.is_file()
        or target.stat().st_size > max_size
        or target.stat().st_size <= 0
    ):
        raise ValueError("candidate_asset_missing_or_untrusted")
    if not target.resolve().is_relative_to(base.resolve()):
        raise ValueError("candidate_asset_escaped_root")
    return target.read_bytes()


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def review(*, project: Path, live: Path) -> dict:
    source = {}
    page = {}
    parsed = _Refs()
    try:
        for path in SOURCES:
            source[path] = _hash(_bytes(project, path, MAX_BYTES))
        html_bytes = {}
        for name in PAGES:
            text = _bytes(project / "out", name, MAX_BYTES)
            html_bytes[name] = text
            page[name] = _hash(text)
            parsed.feed(text.decode("utf-8"))
        if parsed.external_scripts or not parsed.assets:
            raise ValueError("unreviewed_external_script_or_missing_assets")
        if any(p.startswith("/_next/static/agency/") for p in parsed.assets):
            raise ValueError("legacy_injected_bridge_still_in_staged_export")
        asset_hashes = {}
        js = []
        for uri in sorted(parsed.assets):
            raw = _bytes(project / "out", uri.removeprefix("/"), 10_000_000)
            asset_hashes[uri] = _hash(raw)
            if uri.endswith(".js"):
                js.append(raw)
        joined = b"\n".join(js)
        checks = {
            "source_bytes_present": len(source) == 3,
            "both_routes_built": len(page) == 2,
            "all_referenced_assets_present": len(asset_hashes) == len(parsed.assets),
            "compiled_nonbinding_buy_link_present": (
                b"REQUEST A PROPOSAL INSTEAD" in joined
                and b"commercial?product=" in joined
            ),
            "compiled_commercial_rejection_present": (
                b"The requested product is not available for a proposal" in joined
                and b"/v1/checkout/commercial/offers" in joined
            ),
            "no_untracked_static_product_overlay": (
                b"selected-product-bridge-20261020" not in html_bytes["buy.html"]
                and b"selected-product-bridge-20261020" not in html_bytes["commercial.html"]
            ),
            "no_external_scripts": not parsed.external_scripts,
        }
        live_matches = {}
        for name, digest in page.items():
            try:
                live_matches[name] = _hash(_bytes(live, name, MAX_BYTES)) == digest
            except (OSError, ValueError):
                live_matches[name] = False
        ready = all(checks.values())
        return {
            "schema_version": SCHEMA,
            "status": (
                "STAGED_SOURCE_BUILD_VERIFIED_OWNER_RELEASE_REVIEW_REQUIRED"
                if ready else "STAGED_BUILD_INTEGRITY_HOLD"
            ),
            "source_sha256": source,
            "page_html_sha256": page,
            "referenced_asset_sha256": asset_hashes,
            "checks": checks,
            "current_live_matches_staged_pages": live_matches,
            "existing_13_october_release_manifest_reapproved": False,
            "cinematic_homepage_replaced": False,
            "new_public_release_authorized": False,
            "form_or_order_submitted": False,
            "customer_data_disclosed": False,
            "outbound_sent": False,
            "payment_execution": False,
            "database_writes": False,
            "next_owner": "EXISTING_ASTRA_WEBSITE_RELEASE_OWNER",
        }
    except (OSError, ValueError, UnicodeError):
        return {
            "schema_version": SCHEMA,
            "status": "STAGED_BUILD_INTEGRITY_HOLD",
            "source_sha256": {},
            "page_html_sha256": {},
            "referenced_asset_sha256": {},
            "checks": {},
            "current_live_matches_staged_pages": {},
            "new_public_release_authorized": False,
            "form_or_order_submitted": False,
            "outbound_sent": False,
            "payment_execution": False,
            "database_writes": False,
            "next_owner": "EXISTING_ASTRA_WEBSITE_RELEASE_OWNER",
        }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--project", type=Path)
    parser.add_argument("--live", type=Path, default=Path("/srv/empire_os/apps/empire-public-site/out"))
    args = parser.parse_args(argv)
    if args.read_only is not True or args.project is None:
        parser.error("exact --read-only and --project required")
    result = review(project=args.project, live=args.live)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "STAGED_SOURCE_BUILD_VERIFIED_OWNER_RELEASE_REVIEW_REQUIRED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
