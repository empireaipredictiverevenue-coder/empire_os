"""Bounded, robots-respecting public page fingerprint monitoring.

Reuses the original competitor refresh cycle; two allowlisted operator pages
per invocation. Stores hashes and citation URLs only, never scraped content,
personal contacts, new prospect rows or inferred traffic/revenue volumes.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit
from urllib import robotparser

import requests

from empire_os.competitor_call_channel_atlas import DOMAINS

SCHEMA = "empire.competitor_call_source_watch.v1"
ATLAS_SCHEMA = "empire.competitor_call_acquisition_atlas.v1"
DEST = Path("runtime/competitive_intelligence/call_source_watch_latest.json")
AGENT = "EmpireOS-Competitor-Research/1.0 (+https://empire-ai.co.uk)"
MAX_BYTES = 500_000


class _Visible(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip_depth and data.strip():
            self.parts.append(data)


def text_digest(source: str) -> str | None:
    if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_BYTES:
        return None
    parser = _Visible()
    parser.feed(source)
    normalized = " ".join(" ".join(parser.parts).lower().split())
    if len(normalized) < 120:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _source_url(url: str, operator_id: str) -> bool:
    try:
        parts = urlsplit(url)
        return (operator_id in DOMAINS and parts.scheme == "https"
                and parts.hostname in DOMAINS[operator_id]
                and not parts.username and not parts.password
                and parts.port is None and not parts.fragment
                and len(url) <= 400)
    except (TypeError, ValueError, AttributeError):
        return False


def permitted_by_robots(url: str) -> bool:
    """Respect site opt-outs. No 403/5xx/timeout fallback."""
    p = urlsplit(url)
    target = f"{p.scheme}://{p.netloc}/robots.txt"
    try:
        response = requests.get(
            target, headers={"User-Agent": AGENT, "Accept": "text/plain"},
            timeout=3.0, allow_redirects=False,
        )
        if response.status_code in (404, 410):
            return True
        if response.status_code != 200 or len(response.content) > 100_000:
            return False
        robots = robotparser.RobotFileParser()
        robots.parse(response.text.splitlines())
        return bool(robots.can_fetch(AGENT, url))
    except requests.RequestException:
        return False


def fetch_html(url: str) -> str | None:
    try:
        with requests.get(
            url, headers={"User-Agent": AGENT, "Accept": "text/html"},
            timeout=4.0, allow_redirects=False, stream=True,
        ) as response:
            if response.status_code != 200 or "html" not in response.headers.get("Content-Type", "").lower():
                return None
            data = bytearray()
            for chunk in response.iter_content(chunk_size=32768):
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    return None
            return data.decode("utf-8", errors="replace")
    except requests.RequestException:
        return None


def inspect_sources(
    atlas: dict, previous: dict | None = None, *,
    permitted: Callable[[str], bool] = permitted_by_robots,
    fetch: Callable[[str], str | None] = fetch_html,
    now: datetime | None = None,
    limit: int = 2,
) -> dict:
    if (atlas.get("schema_version") != ATLAS_SCHEMA
            or atlas.get("outreach_enabled") is not False
            or atlas.get("execution_authority") != "none"):
        raise ValueError("untrusted source atlas")
    if type(limit) is not int or not 1 <= limit <= 2:
        raise ValueError("public fetch must be bounded to max two pages")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone-aware time required")
    sources = []
    for profile in atlas.get("operator_profiles", []):
        operator = profile.get("operator_id")
        for source in profile.get("sources", []):
            url = source.get("url")
            if not _source_url(url, operator):
                raise ValueError("non-allowlisted operator source")
            sources.append((operator, url))
    sources.sort()
    if len(sources) != atlas.get("source_count") or not 1 <= len(sources) <= 30:
        raise ValueError("source count conflict")
    if len({url for _, url in sources}) != len(sources):
        raise ValueError("repeated source URL")
    previous = previous if isinstance(previous, dict) and previous.get("schema_version") == SCHEMA else {}
    prior = previous.get("fingerprints")
    prior = prior if isinstance(prior, dict) else {}
    fingerprints = {}
    for _, url in sources:
        value = prior.get(url)
        if isinstance(value, dict) and re.fullmatch(r"[a-f0-9]{64}", value.get("digest") or ""):
            fingerprints[url] = {
                "digest": value["digest"],
                "last_observed_at": value.get("last_observed_at"),
            }
    cursor = previous.get("cursor")
    cursor = cursor if type(cursor) is int and 0 <= cursor < len(sources) else 0
    changed = []
    baseline = []
    unavailable = []
    checked = []
    examined = 0
    visited_domains = set()
    attempts = 0
    while examined < limit and attempts < len(sources):
        operator, url = sources[(cursor + attempts) % len(sources)]
        attempts += 1
        hostname = urlsplit(url).hostname
        if hostname in visited_domains:
            continue
        visited_domains.add(hostname)
        examined += 1
        checked.append(url)
        try:
            eligible = permitted(url)
        except Exception:
            eligible = False
        if not eligible:
            unavailable.append({"url": url, "reason": "ROBOTS_UNAVAILABLE_OR_DISALLOWED"})
            continue
        try:
            body = fetch(url)
            digest = text_digest(body) if body is not None else None
        except (TypeError, ValueError, OSError):
            digest = None
        if digest is None:
            unavailable.append({"url": url, "reason": "PUBLIC_HTML_UNAVAILABLE_OR_INSUFFICIENT"})
            continue
        old = fingerprints.get(url, {}).get("digest")
        if old is None:
            baseline.append(url)
        elif old != digest:
            changed.append({"operator_id": operator, "url": url,
                            "previous_digest": old, "current_digest": digest,
                            "review_required": True, "buyer_intent_inferred": False})
        fingerprints[url] = {"digest": digest, "last_observed_at": now.isoformat()}
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE", "generated_at": now.isoformat(),
        "source_count": len(sources), "cursor": (cursor + attempts) % len(sources),
        "checked_urls": checked, "checked_this_cycle": len(checked),
        "first_baselines_this_cycle": baseline,
        "confirmed_text_changes_this_cycle": changed,
        "source_unavailable_this_cycle": unavailable,
        "existing_baseline_count": len(fingerprints),
        "fingerprints": fingerprints,
        "inference_scope": "PUBLIC_VISIBLE_PAGE_TEXT_DIGEST_ONLY",
        "source_change_requires_manual_review": True,
        "competitor_traffic_or_conversion_measured": False,
        "buyer_intent_inferred": False,
        "outreach_enabled": False,
        "paid_traffic_authorized": False,
        "execution_authority": "none",
    }


def refresh(repo_root: Path) -> dict:
    atlas_path = repo_root / "runtime/competitive_intelligence/call_acquisition_atlas_latest.json"
    atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
    dst = repo_root / DEST
    if not dst.parent.is_dir() or dst.parent.is_symlink() or dst.is_symlink():
        raise ValueError("unsafe original competitive intelligence output")
    try:
        previous = json.loads(dst.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    result = inspect_sources(atlas, previous)
    fd, tmp = tempfile.mkstemp(prefix=".call-source-watch-", dir=dst.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            json.dump(result, target, indent=2, sort_keys=True)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return result
