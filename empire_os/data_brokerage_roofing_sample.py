"""Original Empire AI roofing competitor research from reviewed free graph evidence.

This is an UNSENT, founder-review-only $199 service SAMPLE. The historical
Common Crawl domain graph is not page-level backlink, SERP ranking, traffic,
qualified buyer, contract, license-to-resell or lead evidence.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json
import re

from empire_os.free_dataset_intelligence import (
    APPROVED_MARKETS, SOURCE_REPORT, SOURCE_REPORT_SCHEMA,
    inspect_free_commoncrawl_dataset,
)

SCHEMA = "empire.data_brokerage.roofing_competitor_sample.v1"
GRAPH_CANDIDATES = SOURCE_REPORT.with_name(
    "approved-historical-referring-domain-candidates.json"
)
TARGET_NATIONS = "nationsroof.com"
TARGET_TECTA = "tectaamerica.com"
TRUSTED_CANDIDATES_SCHEMA = "empire.cc.graph.verified_referring_domain_candidates.v1"
_REVIEW_DOMAINS = (
    "iibec.org", "rooferscoffeeshop.com", "gaf.com", "roofingalliance.net",
)
_DOMAIN = re.compile(
    r"(?=.{4,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:[a-z]{2,24}|xn--[a-z0-9-]{2,20})\Z"
)
MAX_JSON_BYTES = 2_000_000


def _json_source(path: Path) -> tuple[dict[str, Any], str]:
    if Path(path).is_symlink():
        raise ValueError("symlink_archive_not_authorized")
    raw = Path(path).read_bytes()
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("bounded_archive_limit_exceeded")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("archive_not_a_dict")
    return data, sha256(raw).hexdigest()


def build_roofing_competitor_sample(
    *, review_path: Path = SOURCE_REPORT,
    candidates_path: Path = GRAPH_CANDIDATES,
) -> dict[str, Any]:
    """Cross-check independently reviewed historical source/candidate cohorts."""
    reviewed = inspect_free_commoncrawl_dataset(Path(review_path))
    if reviewed.get("status") != "REVIEWED_HISTORICAL_RESEARCH_AVAILABLE":
        raise ValueError("review_evidence_failed")
    candidates, candidates_sha = _json_source(Path(candidates_path))
    if (candidates.get("schema_version") != TRUSTED_CANDIDATES_SCHEMA
            or candidates.get("source") != "commoncrawl_2026_domain_webgraph"
            or candidates.get("mode") != "OBSERVE"
            or candidates.get("database_writes") is not False
            or candidates.get("live_backlink_verification_completed") is not False
            or candidates.get("production_changed") is not False):
        raise ValueError("candidate_source_claims_not_allowed")
    rows = candidates.get("historical_domain_candidates")
    if (not isinstance(rows, list)
            or candidates.get("candidate_count") != len(rows)
            or len(rows) != reviewed["historical_relation_count"]):
        raise ValueError("candidate_count_mismatch")
    target_sets: dict[str, set[str]] = defaultdict(set)
    count_by_target: Counter[str] = Counter()
    for item in rows:
        if not isinstance(item, Mapping):
            raise ValueError("candidate_record_not_mapping")
        target = item.get("target_domain")
        source = item.get("source_domain")
        if (target not in APPROVED_MARKETS
                or not isinstance(source, str) or not _DOMAIN.fullmatch(source)
                or source == target or item.get("verified_live_backlink") is not False
                or item.get("source_page_url") not in (None, "")):
            raise ValueError("candidate_untrusted_or_claims_verified_links")
        count_by_target[target] += 1
        if source in target_sets[target]:
            raise ValueError("duplicate_source_edge_in_archive")
        target_sets[target].add(source)
    expected = reviewed["historical_relationships_by_target"]
    if (dict(count_by_target) != expected
            or {k:len(v) for k,v in target_sets.items()} != expected):
        raise ValueError("candidate_cohort_not_matching_independent_review")
    all_domains = set().union(*target_sets.values())
    if len(all_domains) != reviewed["distinct_source_domain_count"]:
        raise ValueError("review_distinct_domain_mismatch")
    cross_target = sum(
        len([t for t in target_sets if domain in target_sets[t]]) > 1
        for domain in all_domains
    )
    if cross_target != reviewed["cross_target_source_domain_count"]:
        raise ValueError("cross_target_domain_count_mismatch")
    a, b = target_sets[TARGET_NATIONS], target_sets[TARGET_TECTA]
    shared = a & b
    followups = [
        {
            "source_domain": domain,
            "historically_associated_targets": [
                TARGET_NATIONS, TARGET_TECTA,
            ],
            "page_level_link_currently_verified": False,
            "domain_relation_may_be_technical": True,
            "next_check": "Verify current page URL, editorial context, link target and date",
        }
        for domain in _REVIEW_DOMAINS
        if domain in shared
    ]
    evidence = {
        "schema_version": SCHEMA,
        "report_kind": "FOUNDER_REVIEW_SAMPLE_NOT_SENT",
        "original_service_code": "competitor_search_gap",
        "approved_list_price_usd": 199,
        "fixed_scope_sale_accepted": False,
        "scope": "US commercial roofing, national-domain historical source discovery",
        "comparison_targets": [TARGET_NATIONS, TARGET_TECTA],
        "source": {
            "publisher": "Common Crawl",
            "source_kind": "HISTORICAL_DOMAIN_GRAPH",
            "release": reviewed["release"],
            "source_review_sha256": reviewed["review_sha256"],
            "candidate_rows_sha256": candidates_sha,
            "reviewed_at_utc": reviewed["reviewed_at_utc"],
            "historical_total_relationships": reviewed["historical_relation_count"],
            "historical_distinct_source_domains": reviewed[
                "distinct_source_domain_count"],
            "historical_cross_target_source_domains": cross_target,
            "independently_verified_current_link_count": 0,
            "verified_search_positions": None,
            "verified_organic_traffic": None,
            "source_licence_for_reselling_raw_records_verified": False,
        },
        "comparison": {
            "nations_source_domain_count": len(a),
            "tecta_source_domain_count": len(b),
            "shared_source_domain_count": len(shared),
            "nations_only_count": len(a - b),
            "tecta_only_count": len(b - a),
            "union_source_domain_count": len(a | b),
            "historical_domain_samples_not_current_links": followups,
        },
        "interpretation": [
            "Domain-level historical co-occurrence provides research leads, not proven live editorial backlinks",
            "Overlap can inform manual verification of relevant industry sources; it does not prove SEO advantage",
            "Search visibility and traffic gaps require current SERP/GSC measurement, which is not supplied by this graph",
        ],
        "research_next_actions": [
            "Verify 3-4 sample domains at the page level before calling any link earned or active",
            "Choose one commercial roofing service and one metro to audit current organic search results",
            "Review official service/location pages and recommend original intent-matched content without copying source text",
            "Compare measured SERP positions and page-level content only after fresh authorized evidence is collected",
        ],
        "original_analysis": True,
        "ai_assistance_disclosed": True,
        "founder_review_required": True,
        "founder_author_ownership_independently_verified": False,
        "c2pa_signed": False,
        "source_citations_required": True,
        "prospect_or_buyer_verified": False,
        "do_not_contact_via_supplier_portals": True,
        "outbound_sent": False,
        "customer_delivery_authorized": False,
        "checkout_activated": False,
        "received_payment_verified": False,
        "recognized_revenue_verified": False,
        "raw_dataset_resale_authorized": False,
        "paid_api_calls": 0,
        "empiredb_writes": False,
        "execution_authority": "none",
    }
    # Integrity checksum of structured evidence, not proof of authorship.
    evidence["internal_evidence_sha256"] = sha256(json.dumps(
        evidence, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    return evidence


def render_roofing_sample_markdown(report: Mapping[str, Any]) -> str:
    if (report.get("schema_version") != SCHEMA
            or report.get("report_kind") != "FOUNDER_REVIEW_SAMPLE_NOT_SENT"
            or report.get("approved_list_price_usd") != 199
            or report.get("customer_delivery_authorized") is not False
            or report.get("independently_verified_current_link_count", 0) not in (0, None)
            or report.get("source", {}).get(
                "independently_verified_current_link_count"
            ) != 0):
        raise ValueError("untrusted_report_preflight")
    c = report["comparison"]
    s = report["source"]
    examples = c["historical_domain_samples_not_current_links"]
    example_lines = "\n".join(
        f"- `{p['source_domain']}` — **historical association only**; "
        "check the live source page, target and context before using it"
        for p in examples
    ) or "- No preselected source domains met the small demonstration shortlist."
    return f"""# Empire AI | US Commercial Roofing Competitor Research — Sample

**Founder review only · Not sent or sold · 18 October 2026**
**Existing product:** Competitor Search Gap · **$199 one-time USD**
**Evidence class:** Archived Common Crawl domain-level graph. This is a sample of our analytical method, **not a commissioned SEO audit or customer-specific diagnosis**.

## Executive finding

The archived {s['release']} Common Crawl domain-graph review associated **{c['nations_source_domain_count']} historical source domains** with `nationsroof.com` and **{c['tecta_source_domain_count']}** with `tectaamerica.com`. **{c['shared_source_domain_count']}** source domains appeared in both samples. {c['nations_only_count']} were observed only with Nations Roof in this bounded sample, and {c['tecta_only_count']} only with Tecta America.

That creates a useful research starting point, **not evidence that either company outranks the other, has more working links, or would benefit from purchasing backlinks**.

| Historical source-domain measure | Nations Roof | Tecta America |
|---|---:|---:|
| Domains associated in bounded archived graph | {c['nations_source_domain_count']} | {c['tecta_source_domain_count']} |
| Appearing with both competitors | {c['shared_source_domain_count']} | {c['shared_source_domain_count']} |
| Only in that target's bounded sample | {c['nations_only_count']} | {c['tecta_only_count']} |
| Page-level live editorial links verified | **0** | **0** |

**Combined roofing-source universe:** {c['union_source_domain_count']} distinct domains. Sampling is historical, bounded and not a census of all websites or current links.

## Short source-verification queue

These domain names appeared in both historical sets and are provided **only** as candidates for a manual page-level source check:

{example_lines}

Do not contact these sites as link-placement sellers or claim they still link to either firm. The graph contains **no source-page URLs, verified link dates, or current ranking data**.

## Commercial roofing buyer questions worth investigating next

1. **Commercial roof maintenance:** Which local contractor pages actually appear for facilities teams searching for scheduled maintenance, inspections and roof asset management?
2. **Geographic relevance:** Where do a national brand's location-specific service pages compete with local commercial roofing firms for the same verified intent?
3. **Evidence-backed content:** Can an original, locally useful explanation of maintenance versus replacement answer questions not served by the existing pages?
4. **Relevant earned coverage:** Which trade associations, manufacturer directories or industry publications demonstrably reference current pages—verified live, not inferred from old graph edges?

These are research hypotheses, **not claims that either named company has an SEO fault**.

## What a paid $199 Competitor Search Gap would actually include

A buyer-approved **one service + one target market/metro** scope; dated search-engine results from permitted sources; the customer's relevant service/location pages; 3–5 actual competitor comparisons; a small source-verified opportunity checklist; an original concise written report; and the evidence/measurement date for every claim. We do not guarantee a ranking or click volume.

Before accepting an order, confirm the specific buyer need, written scope, actual deliverability and permitted research methods. This *sample* establishes none of those conditions.

## Data custody & Empire AI provenance

- **Primary source:** Common Crawl domain hyperlink graph, `{s['release']}`. Dataset background: https://commoncrawl.org/
- **Existing reviewed source digest (SHA-256):** `{s['source_review_sha256']}`
- **Existing candidate cohort digest (SHA-256):** `{s['candidate_rows_sha256']}`
- **Domain-level review:** {s['historical_total_relationships']} historical source-target relationships across {s['historical_distinct_source_domains']} distinct source domains for four original targets; this sample examines two of them.
- **Current backlink proof:** none; **current SERP proof:** none; **traffic proof:** none.
- **Authorship:** original Empire AI analysis prepared through a founder-directed, AI-assisted workflow. No cryptographic authorship certificate, C2PA signature or independent rights attestation is claimed.
- **Distribution:** internal founder review. Raw third-party data is not offered for resale; external sending, checkout and payment recognition remain disabled.

**Internal evidence digest:** `{report['internal_evidence_sha256']}`

**Next internal action:** select a genuine prospective customer/market, check the recipient and suppression records, verify fresh SERP/source evidence, then share a separately approved and genuinely personalized scope. No outbound has been sent.
"""
