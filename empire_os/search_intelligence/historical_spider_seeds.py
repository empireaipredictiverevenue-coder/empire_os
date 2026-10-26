"""Offline WAT anchor provenance -> bounded source-page seeds for the existing spider.

No crawling, DB writes or discovery beyond exact host scopes. Historical HTML
anchors are unverified until the guarded one-shot separately observes them.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from .targeted_referrer_spider import (
    MAX_HOSTS, MAX_PAGES_PER_HOST, SpiderHeld, _approved_target_host,
    page_url,
)

MAX_WAT_OBSERVATIONS = 1000


def add_wat_page_seeds(plan: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Add verified-as-archival candidate URLs, not verified-as-live backlinks."""
    sources = plan.get("approved_source_hosts")
    mapping = plan.get("target_by_source")
    if (plan.get("schema_version") != "empire.search.referrer_spider_plan.v1"
            or plan.get("status") != "BOUNDED_ONE_SHOT_SCOPE_READY"
            or plan.get("network_requests") != 0
            or plan.get("empiredb_writes") is not False
            or plan.get("scheduled_crawling") is not False
            or not isinstance(sources, list)
            or not 1 <= len(sources) <= MAX_HOSTS
            or len(sources) != len(set(sources))
            or not isinstance(mapping, dict) or set(mapping) != set(sources)):
        raise SpiderHeld("reviewed_source_plan_required")

    if (not isinstance(receipt, Mapping)
            or receipt.get("schema_version") != "empire.commoncrawl.wat_backlinks.review.v1"
            or receipt.get("source") != "commoncrawl_historical_wat"
            or receipt.get("mode") != "OBSERVE"
            or receipt.get("network_requests") != 0
            or receipt.get("database_writes") is not False
            or receipt.get("execution_authority") != "none"):
        raise SpiderHeld("read_only_historical_wat_receipt_required")
    rows = receipt.get("observations")
    if (not isinstance(rows, list) or len(rows) > MAX_WAT_OBSERVATIONS
            or type(receipt.get("candidate_backlink_edges")) is not int
            or receipt["candidate_backlink_edges"] != len(rows)):
        raise SpiderHeld("bounded_consistent_wat_observations_required")

    matches: dict[str, set[str]] = {host: set() for host in sources}
    ignored = 0
    for item in rows:
        if not isinstance(item, Mapping):
            raise SpiderHeld("invalid_wat_observation")
        provenance = item.get("provenance")
        if (item.get("source") != "commoncrawl_wat_archived_link"
                or not isinstance(provenance, (list, tuple))
                or "type:html_anchor" not in provenance
                or "status:historical_unverified" not in provenance):
            raise SpiderHeld("historical_anchor_provenance_required")
        source_url, target_url = item.get("source_url"), item.get("target_url")
        if not isinstance(source_url, str) or not isinstance(target_url, str):
            raise SpiderHeld("wat_source_target_urls_required")
        try:
            source_host = urlsplit(source_url).hostname
            target_host = urlsplit(target_url).hostname
        except ValueError as exc:
            raise SpiderHeld("wat_url_invalid") from exc
        if (source_host not in matches
                or _approved_target_host(target_host, frozenset(mapping[source_host])) is None):
            ignored += 1
            continue
        # No http->https rewriting, no credentials, query, deep path, or admin.
        if page_url(source_url, source_host) != source_url:
            ignored += 1
            continue
        matches[source_host].add(source_url)

    selected = {host: sorted(matches[host])[:MAX_PAGES_PER_HOST] for host in sources}
    return {
        **dict(plan),
        "historical_page_seeds": selected,
        "historical_page_seed_count": sum(map(len, selected.values())),
        "historical_wat_candidates_ignored": ignored,
        "historical_seed_provenance": "commoncrawl_wat_archived_html_anchor_unverified",
        "network_requests": 0,
        "empiredb_writes": False,
    }
