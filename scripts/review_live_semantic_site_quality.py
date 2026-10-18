#!/usr/bin/env python3
"""Read-only quality + conversion-route inspection of four live Empire pages.

Checks actual HTML of four known commercial pages and the /commercial form.
Does not submit the form, change the website, claim leads or issue paid calls.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import argparse
import json
import sys
from typing import Any, Callable

import requests

from empire_os.search_intelligence.first_party_semantic_corpus import PRIORITY_PAGES
from empire_os.search_intelligence.semantic_site_quality import (
    inspect_owned_commercial_page, inspect_commercial_form_html,
)


PublicGet = Callable[[str], tuple[int, str]]


def _get_public_page(url: str) -> tuple[int, str]:
    permitted = {s.url for s in PRIORITY_PAGES} | {
        "https://empire-ai.co.uk/commercial"
    }
    if url not in permitted:
        raise ValueError("url outside bounded owned page allowlist")
    response = requests.get(url, timeout=12, allow_redirects=False)
    if len(response.content) > 2_000_000:
        raise ValueError("page body exceeds bounded HTML review limit")
    return response.status_code, response.text


def build_live_site_quality_review(
    public_get: PublicGet = _get_public_page,
) -> dict[str, Any]:
    pages = []
    errors = []
    for spec in PRIORITY_PAGES:
        try:
            code, html = public_get(spec.url)
            pages.append(inspect_owned_commercial_page(
                spec, http_status=code, html=html
            ))
        except (requests.RequestException, OSError, ValueError) as exc:
            errors.append({"url": spec.url, "reason": type(exc).__name__})
    form_url = "https://empire-ai.co.uk/commercial"
    try:
        code, html = public_get(form_url)
        form_status = inspect_commercial_form_html(html, http_status=code)
    except (requests.RequestException, OSError, ValueError) as exc:
        errors.append({"url": form_url, "reason": type(exc).__name__})
        form_status = {
            "url": form_url,
            "static_form_presence_observed": False,
            "submission_delivery_verified": False,
            "crm_record_verified": False,
            "status": "UNAVAILABLE",
        }

    actions = Counter(
        finding["action"]
        for page in pages
        for finding in page["editorial_review_candidates"]
    )
    route_to_form_observed = (
        form_status.get("static_form_presence_observed") is True
        and len(pages) == len(PRIORITY_PAGES)
        and all(p["observed_commercial_form_route_link"] for p in pages)
    )
    return {
        "schema_version": "live_semantic_site_quality_review.v1",
        "mode": "OBSERVE",
        "assessed_public_pages": len(pages),
        "intended_public_pages": len(PRIORITY_PAGES),
        "live_page_findings": pages,
        "commercial_form": form_status,
        "page_to_static_commercial_form_path_observed": route_to_form_observed,
        "editorial_candidate_counts": dict(sorted(actions.items())),
        "read_errors": errors,
        "source_type": "read_only_public_html",
        "observed_google_indexing": False,
        "submission_executed": False,
        "crm_receipt_verified": False,
        "revenue_verified": False,
        "site_mutated": False,
        "paid_api_requests": 0,
        "execution_authority": "none",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--format", choices=("json", "summary"), default="summary")
    args = p.parse_args(argv)
    report = build_live_site_quality_review()
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "schema_version": report["schema_version"],
            "assessed_public_pages": report["assessed_public_pages"],
            "page_to_static_commercial_form_path_observed":
                report["page_to_static_commercial_form_path_observed"],
            "commercial_form_present": report["commercial_form"].get(
                "static_form_presence_observed", False
            ),
            "editorial_candidate_counts": report["editorial_candidate_counts"],
            "page_review": [{
                "url": page["url"],
                "word_count_estimate": page["visible_word_count_estimate"],
                "h2_count": len(page["visible_h2_headings"]),
                "route_to_commercial": page["observed_commercial_form_route_link"],
                "editorial_candidates": [
                    finding["action"]
                    for finding in page["editorial_review_candidates"]
                ],
            } for page in report["live_page_findings"]],
            "crm_receipt_verified": False,
            "site_mutated": False,
            "paid_api_requests": 0,
            "read_errors": report["read_errors"],
        }, indent=2, sort_keys=True))
    return 0 if not report["read_errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
