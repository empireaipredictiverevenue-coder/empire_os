"""Check the ACTUAL static-export SEO pilot, with zero public publishing.

No browser, network request, CMS mutation, live call routing or sitemap write.
Static HTML is the correct artifact for this site's output: export config.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


class SeoPilotGateHeld(ValueError):
    pass


def _load(root: Path, path: str) -> BeautifulSoup:
    rel = "index.html" if path == "/" else path.strip("/") + ".html"
    file = root / rel
    if (file.is_symlink() or not file.is_file()
            or not file.resolve().is_relative_to(root.resolve())
            or file.stat().st_size < 1000):
        raise SeoPilotGateHeld("MISSING_EXPORTED_PAGE_" + path.replace("/", "_"))
    return BeautifulSoup(file.read_text(encoding="utf-8"), "html.parser")


def verify(export: Path) -> dict[str, Any]:
    if export.is_symlink() or not export.is_dir():
        raise SeoPilotGateHeld("REAL_STATIC_EXPORT_DIRECTORY_REQUIRED")
    paths = (
        "/", "/predictive-revenue", "/industries/roofing",
        "/industries/solar", "/commercial", "/roofing",
        "/roofing/replacement-vs-repair",
    )
    pages = {p: _load(export, p) for p in paths}
    # The old AEO URL remains absent. Do not infer a redirect target from a slug.
    if (export / "aeo/empire/ai_lead_gen.html").exists():
        raise SeoPilotGateHeld("UNAPPROVED_LEGACY_AEO_RESTORATION")
    for path in ("/predictive-revenue", "/industries/roofing"):
        page = pages[path]
        if len(page.select("main")) != 1 or len(page.select("h1")) != 1:
            raise SeoPilotGateHeld("SEMANTIC_PAGE_STRUCTURE_INVALID")
        links = [x.get("href") for x in page.select('link[rel="canonical"]')]
        if links != ["https://empire-ai.co.uk" + path]:
            raise SeoPilotGateHeld("MISSING_SELF_CANONICAL")
        if any("noindex" in str(m.get("content", "")).lower()
               for m in page.select('meta[name="robots"]')):
            raise SeoPilotGateHeld("UNINTENDED_NOINDEX_B2B_PILLAR")
        if not page.select('a[href="/commercial"]'):
            raise SeoPilotGateHeld("B2B_CONVERSION_ROUTE_MISSING")
        if page.select('a[href^="tel:"],a[href^="http:"]'):
            raise SeoPilotGateHeld("UNAPPROVED_OUTBOUND_CALL_OR_INSECURE_LINK")
    revenue = pages["/predictive-revenue"]
    roofing = pages["/industries/roofing"]
    product_text = revenue.get_text(" ", strip=True)
    roofing_text = roofing.get_text(" ", strip=True)
    for phrase in (
        "How do you test a revenue forecast against actual results?",
        "dated snapshot", "an open invoice is not realised revenue",
        "independently measured customer result",
    ):
        if phrase not in product_text:
            raise SeoPilotGateHeld("PREDICTIVE_COPY_NOT_CRAWLABLE")
    for phrase in (
        "How to audit a roofing call from click to settlement",
        "buyer-leg connection", "unavailable evidence as unknown",
        "actual buyer connections",
    ):
        if phrase not in roofing_text:
            raise SeoPilotGateHeld("ROOFING_COPY_NOT_CRAWLABLE")
    if len(revenue.select("form")) != 1:
        raise SeoPilotGateHeld("EXISTING_INTAKE_FORM_INVALID")
    if (not revenue.select('form input[type="email"]')
            or not revenue.select('form input[type="checkbox"]')
            or not revenue.select('a[href="/privacy"]')):
        raise SeoPilotGateHeld("CONSENT_OR_PRIVACY_MISSING")
    if ("contract, payment request or production deployment" not in product_text
            or "I am not signing up for unrelated marketing" not in product_text):
        raise SeoPilotGateHeld("NONBINDING_AND_CONSENT_NOTICE_MISSING")
    title = revenue.title.get_text() if revenue.title else ""
    meta = revenue.select_one('meta[name="description"]')
    if ("B2B Pipeline Decisions" not in title
            or meta is None
            or "forecast pipeline outcomes" not in (meta.get("content") or "")):
        raise SeoPilotGateHeld("PREDICTIVE_METADATA_INCOMPLETE")
    if "Solar referrals only become revenue" not in pages["/industries/solar"].get_text(" ", strip=True):
        raise SeoPilotGateHeld("UNRELATED_SOLAR_EDITORIAL_MISSING")
    if "General homeowner information" not in pages["/roofing/replacement-vs-repair"].get_text(" ",strip=True):
        raise SeoPilotGateHeld("CONSUMER_SAFETY_NOTICE_MISSING")
    consumer_guide = pages["/roofing/replacement-vs-repair"]
    if not any("noindex" in str(m.get("content", "")).lower()
               for m in consumer_guide.select('meta[name="robots"]')):
        raise SeoPilotGateHeld("HELD_HOMEOwner_GUIDE_NOINDEX_LOST")
    if not any("index" in str(m.get("content","")).lower()
               for m in pages["/roofing"].select('meta[name="robots"]')):
        raise SeoPilotGateHeld("EXISTING_CONSUMER_ROOFING_POLICY_CHANGED")
    sections = [x for x in revenue.select("section") if "md:grid-cols-2" in " ".join(y.get("class","")[0] if isinstance(y.get("class"),str) else " ".join(y.get("class",[])) for y in x.find_all("div"))]
    # Responsive class source is present; not a claim of visual screenshot testing.
    if not sections:
        raise SeoPilotGateHeld("PREDICTIVE_RESPONSIVE_LAYOUT_HOOK_MISSING")
    return {
        "schema_version":"empire.search.predictive_roofing_static_pilot.v1",
        "status":"EXPORTED_HTML_CHECKED_NOT_DEPLOYED",
        "pages_checked":list(paths),
        "target_pages_semantics_verified":True,
        "target_pages_self_canonical_verified":True,
        "predictive_meta_title_and_description_verified":True,
        "original_useful_copy_present_in_prerendered_html":True,
        "existing_nonbinding_form_and_privacy_controls_present":True,
        "mobile_responsive_classes_present":True,
        "mobile_visual_qa_performed":False,
        "consumer_guide_noindex_preserved":True,
        "old_aeo_legacy_path_not_restored":True,
        "existing_solar_page_preserved":True,
        "new_phone_routes":False,
        "public_website_changed":False,
        "buyer_enquiries_verified":False,
        "gsc_uplift_verified":False,
        "execution_authority":"NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.export_dir),sort_keys=True))
    except (SeoPilotGateHeld,OSError,ValueError) as exc:
        print(json.dumps({"status":"CANDIDATE_HELD","reason":str(exc),
                          "public_website_changed":False,"execution_authority":"NONE"},sort_keys=True))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
