"""Evidence-only import of an already-downloaded FREE Common Crawl graph review.

Uses existing archive bytes, not a paid API. The reviewed summary is a source
for existing Marketing & Growth intelligence, not canonical buyer entities,
live backlink claims, or a commercial/financial fact materializer.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any
import json

SCHEMA = "empire.free_dataset_intelligence.review.v1"
SOURCE_REPORT_SCHEMA = "empire.cc.graph.referrer_review_queue.v1"
DATASET_RELEASE = "cc-main-2026-jul-aug-sep"
SOURCE_REPORT = Path(
    "/home/ubuntu/empire_reviews/seo_roofing_solar_wat_pilot_20261016/"
    "approved-2026-domain-graph/approved-referrer-quality-review.json"
)
OFFICIAL_RELEASE_URL = (
    "https://data.commoncrawl.org/projects/hyperlinkgraph/"
    "cc-main-2026-jul-aug-sep/index.html"
)
APPROVED_MARKETS = (
    "freedomforever.com", "nationsroof.com",
    "sunrun.com", "tectaamerica.com",
)


def inspect_free_commoncrawl_dataset(
    path: Path = SOURCE_REPORT,
) -> dict[str, Any]:
    """Bounded read of the historical *review*, never the 9GB raw download."""
    base = {
        "schema_version": SCHEMA,
        "release": DATASET_RELEASE,
        "department": "marketing_growth",
        "report_kind": "HISTORICAL_DOMAIN_GRAPH_ONLY",
        "official_release_url": OFFICIAL_RELEASE_URL,
        "outbound_sent": False,
        "paid_api_invoked": False,
        "empiredb_writes": False,
        "confirmed_live_backlinks": 0,
        "source_was_independently_web_reverified": False,
        "recognized_revenue_proven": False,
        "execution_authority": "none",
    }
    try:
        raw = Path(path).read_bytes()
        if len(raw) > 2_000_000:
            raise ValueError("review_exceeds_bounded_size")
        obj = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return {**base, "status": "SOURCE_REVIEW_UNAVAILABLE"}
    if not isinstance(obj, dict):
        return {**base, "status": "INVALID_REVIEW_SOURCE"}
    if (obj.get("schema_version") != SOURCE_REPORT_SCHEMA
            or obj.get("source") != "commoncrawl_2026_domain_webgraph"
            or obj.get("mode") != "OBSERVE"
            or obj.get("empiredb_writes") is not False
            or obj.get("paid_api_calls") != 0
            or obj.get("outbound_sent") is not False
            or obj.get("manual_review_required_for_all") is not True
            or obj.get("no_page_level_backlink_proof") is not True
            or obj.get("verified_live_backlink_count") != 0):
        return {**base, "status": "REVIEW_TRUTH_GATES_FAILED"}
    by_target = obj.get("candidates_by_target")
    if (not isinstance(by_target, dict)
            or set(by_target) != set(APPROVED_MARKETS)
            or any(type(n) is not int or n < 0 or n > 100000
                   for n in by_target.values())):
        return {**base, "status": "REVIEW_TARGETS_OR_COUNTS_INVALID"}
    expected = sum(by_target.values())
    total = obj.get("historical_domain_relationships")
    domains = obj.get("distinct_historical_source_domains")
    manual = obj.get("manual_review_queue")
    if (type(total) is not int or total != expected
            or type(domains) is not int or not 0 <= domains <= total
            or not isinstance(manual, list) or len(manual) != domains):
        return {**base, "status": "REVIEW_RELATIONSHIP_COUNTS_INVALID"}
    # Hash the reviewed evidence bytes; the full source graph was downloaded
    # previously and remains untouched. Never put raw domain candidates in
    # automatic queue messages, LLM prompts or canonical CRM.
    digest = sha256(raw).hexdigest()
    return {
        **base,
        "status": "REVIEWED_HISTORICAL_RESEARCH_AVAILABLE",
        "historical_relation_count": total,
        "distinct_source_domain_count": domains,
        "cross_target_source_domain_count": int(
            obj.get("cross_target_source_domain_count") or 0),
        "target_domains": tuple(sorted(by_target)),
        "historical_relationships_by_target": dict(sorted(by_target.items())),
        "reviewed_at_utc": obj.get("reviewed_at_utc"),
        "review_sha256": digest,
        "manual_review_required": True,
        "no_page_level_html_backlink_proven": True,
        "buyer_identity_verified": False,
        "company_contract_verified": False,
        "resale_or_contact_authorized": False,
        "approved_free_dataset": True,
    }
