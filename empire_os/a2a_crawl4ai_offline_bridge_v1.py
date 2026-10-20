"""Crawl4AI isolated offline Markdown extraction for approved company pages.

Process the SAME already-fetched HTML bytes as Scrapling. No second web
fetch, no social login/browser, no raw markdown or personal data retained.
"""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any, Callable

from empire_os.a2a_first_party_site_recovery_v1 import _parse_site

SCHEMA="empire.a2a.crawl4ai_offline_markdown.v1"
EXECUTABLE=Path("/home/ubuntu/.local/share/empire_a2a_crawl4ai_venv/bin/python")
HELPER=Path(__file__).resolve().parents[1]/"scripts/offline_crawl4ai_parse_20261020.py"


def parse_crawl4ai_existing_html(
    html: bytes, *, source_url: str,
    run: Callable[...,Any] = subprocess.run,
) -> dict[str, Any]:
    if not isinstance(html,bytes) or not 0<len(html)<=400_000:
        raise ValueError("INVALID_APPROVED_SOURCE_HTML")
    _, canon=_parse_site(source_url)
    if source_url != canon:
        raise ValueError("EXACT_APPROVED_HOME_ROOT_REQUIRED")
    if not EXECUTABLE.is_file() or not HELPER.is_file() or HELPER.is_symlink():
        return _hold("CRAWL4AI_ISOLATED_RUNTIME_ABSENT")
    try:
        task=run(
            [str(EXECUTABLE),"-I","-B",str(HELPER),canon],
            input=html,capture_output=True,timeout=12,check=False,
            cwd="/",env={"PATH":"/usr/bin:/bin","HOME":"/tmp",
                         "PYTHONDONTWRITEBYTECODE":"1"},
        )
        if task.returncode != 0 or len(task.stdout)>10000:
            return _hold("CRAWL4AI_PROCESS_ERROR")
        data=json.loads(task.stdout)
        if (not isinstance(data,dict) or data.get("schema_version")!=SCHEMA
                or data.get("status")!="CRAWL4AI_MARKDOWN_EXTRACTED"
                or data.get("source_html_sha256")!=sha256(html).hexdigest()
                or data.get("raw_markdown_or_pii_exported") is not False
                or data.get("source_url_fetched_by_this_module") is not False
                or data.get("headless_browser_launched") is not False
                or data.get("records_promoted_to_crm")!=0
                or data.get("buyer_purchase_intent_verified") is not False):
            return _hold("CRAWL4AI_UNTRUSTED_PROCESS_OUTPUT")
        # Only known, aggregate, bounded fields cross the process boundary.
        chars=data.get("markdown_chars_bounded")
        headings=data.get("markdown_headings_bounded")
        if (type(chars) is not int or not 0<=chars<=1_000_000
                or type(headings) is not int or not 0<=headings<=2000):
            return _hold("CRAWL4AI_INVALID_AGGREGATE")
        return {
            "schema_version":SCHEMA,
            "status":"CRAWL4AI_MARKDOWN_EXTRACTED",
            "source_html_sha256":data["source_html_sha256"],
            "crawl4ai_version":str(data.get("crawl4ai_version"))[:30],
            "markdown_chars_bounded":chars,
            "markdown_headings_bounded":headings,
            "raw_markdown_or_pii_exported":False,
            "source_url_fetched_by_this_module":False,
            "headless_browser_launched":False,
            "records_promoted_to_crm":0,
            "buyer_purchase_intent_verified":False,
        }
    except (OSError,ValueError,TypeError,json.JSONDecodeError,subprocess.TimeoutExpired):
        return _hold("CRAWL4AI_OFFLINE_PROCESS_HOLD")


def _hold(state: str) -> dict[str, Any]:
    return {"schema_version":SCHEMA,"status":state,
            "source_html_sha256":None,
            "raw_markdown_or_pii_exported":False,
            "source_url_fetched_by_this_module":False,
            "headless_browser_launched":False,
            "records_promoted_to_crm":0,
            "buyer_purchase_intent_verified":False}
