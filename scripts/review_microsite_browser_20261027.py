#!/usr/bin/env python3
"""Offline Playwright desktop/mobile acceptance review of a staged HTML microsite.

Requires an existing Playwright + Chromium install. No downloads, external
navigation, production deploy, or model calls. Screenshots are draft-only.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any


SIZES = (("desktop", 1440, 900), ("mobile", 390, 844))


def _check_html(html: str, *, path: Path, screenshot_dir: Path) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "status": "BROWSER_QA_UNAVAILABLE",
            "reason": "Playwright is not installed on this QA worker",
            "independent_browser_test_passed": False,
        }
    records = []
    with sync_playwright() as runner:
        try:
            browser = runner.chromium.launch(headless=True)
        except Exception as exc:
            return {
                "status": "BROWSER_QA_UNAVAILABLE",
                "reason": type(exc).__name__,
                "independent_browser_test_passed": False,
            }
        try:
            for name, width, height in SIZES:
                page = browser.new_page(
                    viewport={"width": width, "height": height},
                    device_scale_factor=1, reduced_motion="reduce",
                )
                # Network is disabled even if an untrusted HTML preview embeds a URL.
                page.route("**/*", lambda route: route.abort())
                page.set_content(html, wait_until="load", timeout=15000)
                measured = page.evaluate("""() => {
                    const anchors = [...document.querySelectorAll('a.action')];
                    return {
                        h1_count: document.querySelectorAll('h1').length,
                        main_count: document.querySelectorAll('main').length,
                        form_count: document.querySelectorAll('form').length,
                        viewport_width: innerWidth,
                        document_scroll_width: document.documentElement.scrollWidth,
                        horizontal_overflow: document.documentElement.scrollWidth > innerWidth,
                        actionable_elements: anchors.map(a => ({
                            width: Math.round(a.getBoundingClientRect().width * 10) / 10,
                            height: Math.round(a.getBoundingClientRect().height * 10) / 10
                        }))
                    };
                }""")
                checked = (
                    measured["h1_count"] == 1
                    and measured["main_count"] == 1
                    and measured["form_count"] == 0
                    and measured["horizontal_overflow"] is False
                    and measured["actionable_elements"]
                    and all(a["height"] >= 44 for a in measured["actionable_elements"])
                )
                shot = screenshot_dir / f"{path.stem}.{name}.png"
                page.screenshot(path=str(shot), full_page=True)
                records.append({
                    "viewport": name, "width": width, "height": height,
                    "passed": bool(checked), "metrics": measured,
                    "screenshot_file": shot.name,
                    "screenshot_sha256": sha256(shot.read_bytes()).hexdigest(),
                })
                page.close()
        finally:
            browser.close()
    return {
        "status": "BROWSER_QA_PASS" if all(r["passed"] for r in records) else "BROWSER_QA_REVIEW",
        "independent_browser_test_passed": all(r["passed"] for r in records),
        "records": records,
    }


def review(path: Path, output_dir: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".html":
        raise ValueError("regular HTML candidate file required")
    if path.stat().st_size > 400_000 or path.stat().st_size == 0:
        raise ValueError("HTML input is too large or empty")
    out = output_dir.expanduser().resolve()
    blocked = (Path("/srv/empire_os"), Path("/var/www"))
    if any(out == x or x in out.parents for x in blocked):
        raise ValueError("cannot write browser QA output in production")
    html = path.read_text(encoding="utf-8")
    if '<meta name="robots" content="noindex,nofollow,noarchive">' not in html:
        raise ValueError("preview is missing explicit noindex meta")
    out.mkdir(parents=True, exist_ok=True)
    result = _check_html(html, path=path, screenshot_dir=out)
    result.update({
        "schema_version": "empire.microsite.browser_review.v1",
        "source_sha256": sha256(path.read_bytes()).hexdigest(),
        "mode": "PRIVATE_QA", "published": False,
        "production_changes": 0, "outbound_sent": False,
    })
    (out / "browser-review.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = review(args.input, args.output_dir)
        print(json.dumps({
            "status": data["status"],
            "passed": data["independent_browser_test_passed"],
            "source_sha256": data["source_sha256"],
            "published": data["published"],
        }))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"browser QA error: {exc}", file=sys.stderr)
        sys.exit(2)
