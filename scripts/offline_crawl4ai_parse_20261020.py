#!/usr/bin/env python3
"""Isolated Crawl4AI Markdown *transformation* of stdin HTML, no browser/fetch.

Only emits non-identifying aggregate statistics and an input digest.
"""
from __future__ import annotations
import hashlib
import json
import re
import sys

SCHEMA="empire.a2a.crawl4ai_offline_markdown.v1"
CAP=400_000

def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].startswith("https://") or len(sys.argv[1])>180:
        raise ValueError("PUBLIC_COMPANY_HOME_ROOT_REQUIRED")
    raw=sys.stdin.buffer.read(CAP+1)
    if not 0 < len(raw) <= CAP:
        raise ValueError("INVALID_CRAWL4AI_INPUT_LENGTH")
    # This module never launches a browser or requests a URL.
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    from importlib.metadata import version
    result=DefaultMarkdownGenerator().generate_markdown(
        input_html=raw.decode("utf-8","replace"),
        base_url=sys.argv[1], citations=False,
    )
    markdown=result.raw_markdown or ""
    if not isinstance(markdown,str):
        raise ValueError("UNEXPECTED_MARKDOWN_RESULT")
    out={
        "schema_version":SCHEMA,
        "status":"CRAWL4AI_MARKDOWN_EXTRACTED",
        "source_html_sha256":hashlib.sha256(raw).hexdigest(),
        "crawl4ai_version":version("crawl4ai"),
        "markdown_chars_bounded":min(len(markdown),1_000_000),
        "markdown_headings_bounded":sum(bool(re.match(r"^\s{0,3}#{1,6}\s",line))
                                         for line in markdown.splitlines()[:2000]),
        "raw_markdown_or_pii_exported":False,
        "source_url_fetched_by_this_module":False,
        "headless_browser_launched":False,
        "records_promoted_to_crm":0,
        "buyer_purchase_intent_verified":False,
    }
    print(json.dumps(out,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
