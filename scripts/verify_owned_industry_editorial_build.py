"""Read-only verification of reviewed Next.js HTML for industry SEO copy.

Does not build, upload, serve, index, change routes or enable commercial
behaviour. Caller must point to an actual local static export directory.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

EXPECTED = {
    "roofing": (
        "From a roofing search to a qualified commercial opportunity.",
        "What makes a roofing call payable?",
        "Are organic roofing clicks paid pay-per-call events?",
    ),
    "solar": (
        "Solar referrals only become revenue when the buyer accepts the outcome.",
        "Separate clicks, leads, appointments and installs",
        "Does every solar website click earn a PPC commission?",
    ),
}


def _read_html(path: Path) -> BeautifulSoup:
    if path.is_symlink() or not path.is_file() or not 1 <= path.stat().st_size <= 1_000_000:
        raise ValueError("bounded_real_static_export_file_required")
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")


def verify_build(root: Path) -> dict[str, Any]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("build_directory_required")
    result = {}
    for slug, phrases in EXPECTED.items():
        page = _read_html(root / "industries" / f"{slug}.html")
        text = page.get_text(" ", strip=True)
        headings = {e.get_text(" ", strip=True) for e in page.select("h1,h2,h3")}
        if len(page.select("main")) != 1 or len(page.select("h1")) != 1:
            raise ValueError(f"{slug}_invalid_semantic_structure")
        if any(phrase not in text for phrase in phrases):
            raise ValueError(f"{slug}_expected_editorial_missing")
        if phrases[0] not in headings or phrases[1] not in headings:
            raise ValueError(f"{slug}_editorial_heading_not_crawlable")
        if not page.select('a[href="/commercial"]'):
            raise ValueError(f"{slug}_existing_founder_form_link_missing")
        if page.select('a[href^="/r/"],a[href^="tel:"],a[href^="http:"]'):
            raise ValueError(f"{slug}_unapproved_click_or_call_destination")
        canonicals = [x.get("href") for x in page.select('link[rel="canonical"]')]
        if canonicals != [f"https://empire-ai.co.uk/industries/{slug}"]:
            raise ValueError(f"{slug}_incorrect_canonical")
        if any("noindex" in str(x.get("content", "")).casefold()
               for x in page.select('meta[name="robots"]')):
            raise ValueError(f"{slug}_approved_b2b_pillar_unintentionally_noindexed")
        result[slug] = {
            "editorial_readable_in_html": True,
            "semantic_main_count": len(page.select("main")),
            "h1_count": len(page.select("h1")),
            "canonical_present": True,
            "existing_nonbinding_form_link": True,
            "new_payable_links_or_phone_routes": False,
            "production_published": False,
        }
    for slug in ("hvac", "property"):
        page = _read_html(root / "industries" / f"{slug}.html")
        if any(phrase in page.get_text(" ",strip=True)
               for items in EXPECTED.values() for phrase in items):
            raise ValueError("industry_copy_spread_to_unrelated_page")
    consumer = _read_html(root / "roofing.html")
    if not any("noindex" in str(x.get("content", "")).casefold()
               for x in consumer.select('meta[name="robots"]')):
        raise ValueError("consumer_roofing_noindex_hold_missing")
    return {
        "schema_version": "empire.seo.industry_editorial_build_proof.v1",
        "status": "STATIC_EXPORT_REVIEWED_NOT_LIVE",
        "industry_pages": result,
        "other_industries_unchanged_by_editorial": True,
        "buyer_roofing_noindex_held": True,
        "commercial_form_remains_existing_first_party": True,
        "public_site_deployed": False,
        "paid_click_routing": False,
        "lead_delivery_enabled": False,
        "funds_moved": False,
        "execution_authority": "none",
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out",required=True,type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify_build(args.out),sort_keys=True))
    except (ValueError, OSError, UnicodeError) as exc:
        print(json.dumps({"status":"EVIDENCE_HOLD", "reason":str(exc),
                          "public_site_deployed":False,"execution_authority":"none"},
                         sort_keys=True))
        raise SystemExit(2)
