"""Evidence-backed call-acquisition overlay for the ORIGINAL competitor feed.

This is a reviewed seed of public operator disclosures, not automated SERP
scraping, live campaign telemetry, a second agent, or a buyer routing decision.
The original market's resolved local companies remain separate entities.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "empire.competitor_call_acquisition_atlas.v1"
SOURCE_SCHEMA = "empire.competitor_call_acquisition_sources.v1"
SOURCE = Path("docs/commercial/call_acquisition_competitor_evidence_20261026.json")
DEST = Path("runtime/competitive_intelligence/call_acquisition_atlas_latest.json")
CHANNELS = frozenset({
    "paid_search", "organic_search", "owned_sites", "publisher_partners",
    "paid_social", "native_ads", "targeted_display", "offline_media",
    "local_search", "email", "content", "call_center", "referrals",
})
OUTCOMES = frozenset({"inbound_call", "live_transfer", "form_lead", "click", "appointment", "customer"})
QUALIFICATION = frozenset({"call_center", "ivr", "api_filter", "real_time_call_routing", "s2s_postback", "matching"})
PAYMENT = frozenset({"cpc", "cpl", "cpa", "pay_per_call", "revenue_share"})
DOMAINS = {
    "modernize": {"modernize.com"},
    "service_direct": {"blog.servicedirect.com"},
    "elocal": {"elocal.com", "www.elocal.com"},
    "quinstreet": {"investor.quinstreet.com", "www.publicnow.com"},
    "home_services_lead_group": {"homeservicesleadgroup.com"},
}
SENSOR_DOMAINS = {
    "support.google.com", "www.ncei.noaa.gov", "www.census.gov",
    "data.cityofchicago.org",
}


def _date(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("missing source review date")
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise ValueError("source review date must be UTC")
    return date.astimezone(timezone.utc)


def _url(url: str, allowed: set[str]) -> str:
    if not isinstance(url, str) or len(url) > 400:
        raise ValueError("missing or oversized source URL")
    p = urlsplit(url)
    if p.scheme != "https" or p.username or p.password or p.port or p.hostname not in allowed:
        raise ValueError("source URL not permitted for named operator")
    if p.fragment:
        raise ValueError("source URL fragments not permitted")
    return url


def _terms(row: dict, key: str, allowed: frozenset[str]) -> list[str]:
    terms = row.get(key)
    if not isinstance(terms, list) or len(terms) > 20 or len(set(terms)) != len(terms):
        raise ValueError("invalid taxonomy terms in " + key)
    if not all(type(v) is str and v in allowed for v in terms):
        raise ValueError("unknown acquisition taxonomy term in " + key)
    return terms


def build_atlas(source: dict, *, now: datetime | None = None) -> dict:
    """Construct an evidence-linked graph. No absence-of-evidence scoring."""
    if not isinstance(source, dict) or source.get("schema_version") != SOURCE_SCHEMA:
        raise ValueError("invalid original operator evidence schema")
    asof = _date(source.get("researched_at_utc"))
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or asof > now.astimezone(timezone.utc):
        raise ValueError("invalid future or naive review date")
    operators = source.get("operators")
    sensors = source.get("demand_sensors")
    if not isinstance(operators, list) or not 1 <= len(operators) <= 20:
        raise ValueError("invalid operator sample")
    if not isinstance(sensors, list) or len(sensors) > 10:
        raise ValueError("invalid demand sensor sample")
    profiles = []
    edges = []
    urls = set()
    seen = set()
    channel_operators: dict[str, set[str]] = {}
    for operator in operators:
        if not isinstance(operator, dict):
            raise ValueError("bad operator row")
        operator_id = operator.get("id")
        if operator_id not in DOMAINS or operator_id in seen:
            raise ValueError("duplicate or unknown operator identity")
        seen.add(operator_id)
        name = operator.get("name")
        if not isinstance(name, str) or not name or len(name) > 90:
            raise ValueError("invalid operator name")
        records = operator.get("observations")
        if not isinstance(records, list) or not 1 <= len(records) <= 6:
            raise ValueError("invalid operator evidence records")
        observed = {k: set() for k in ("channels", "outcomes", "qualification", "payment_models")}
        references = []
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("invalid source record")
            url = _url(record.get("url"), DOMAINS[operator_id])
            if url in urls:
                raise ValueError("reused operator source reference")
            urls.add(url)
            statement = record.get("statement")
            if not isinstance(statement, str) or not 20 <= len(statement) <= 280:
                raise ValueError("missing bounded evidence statement")
            references.append({"url": url, "claim": statement,
                               "source_class": "PUBLIC_OPERATOR_DISCLOSURE_OR_ANNUAL_REPORT",
                               "as_of": asof.date().isoformat()})
            for kind, taxonomy in (("channels", CHANNELS), ("outcomes", OUTCOMES),
                                   ("qualification", QUALIFICATION), ("payment_models", PAYMENT)):
                for item in _terms(record, kind, taxonomy):
                    observed[kind].add(item)
                    edges.append({"from": operator_id, "to": kind + ":" + item,
                                  "relationship": "PUBLICLY_DESCRIBES",
                                  "source_url": url, "source_claim": statement,
                                  "independently_measured": False})
                    if kind == "channels":
                        channel_operators.setdefault(item, set()).add(operator_id)
        profiles.append({
            "operator_id": operator_id, "operator_name": name,
            "domain": operator.get("domain"),
            **{k: sorted(v) for k, v in observed.items()},
            "sources": references,
            "geo_scope_verified": False,
            "publisher_eligibility_for_empire_verified": False,
            "live_traffic_or_conversion_verified": False,
        })
    if len(seen) != len(DOMAINS):
        raise ValueError("required operator research sample incomplete")

    sensor_rows = []
    sensor_seen = set()
    for sensor in sensors:
        if not isinstance(sensor, dict) or sensor.get("id") in sensor_seen:
            raise ValueError("invalid/duplicate demand sensor")
        sensor_seen.add(sensor.get("id"))
        source_ref = sensor.get("source")
        if sensor.get("type") != "first_party":
            _url(source_ref, SENSOR_DOMAINS)
        if not isinstance(sensor.get("limitations"), str) or not sensor.get("limitations"):
            raise ValueError("demand sensor caveat required")
        sensor_rows.append({**sensor, "live_market_demand_verified": False,
                            "individual_buyer_intent_verified": False})

    steps = [
        {"priority": 1, "task": "REVIEW_FIRST_PARTY_SEARCH_QUERIES",
         "owner": "original_search_intelligence", "evidence_required": "Fresh GSC query/page impressions and clicks",
         "reason": "Research first-party intent before producing more pages"},
        {"priority": 2, "task": "MAP_COMPETITOR_CONTENT_AND_PUBLISHER_ROUTES",
         "owner": "original_competitor_audience", "evidence_required": "Permitted public first-party URLs, sitemaps, link evidence",
         "reason": "Identify concrete sources used to reach homeowners without buying ads"},
        {"priority": 3, "task": "CROSSCHECK_GEOGRAPHIC_PUBLIC_DEMAND_SIGNALS",
         "owner": "original_permit_intelligence", "evidence_required": "Source-dated Chicago permits, NOAA reported events, and Trends indices by supported geography",
         "reason": "Find areas worth researching without treating permit addresses or storms as homeowner leads"},
        {"priority": 4, "task": "CROSSCHECK_BUYER_ZIP_AND_HOURS",
         "owner": "original_buyer_acquisition", "evidence_required": "Current, buyer-specific accepted ZIP/job-type and hours",
         "reason": "A high-demand area is worthless for call monetisation if no eligible buyer exists"},
        {"priority": 5, "task": "VALIDATE_FIRST_PARTY_CONVERSION_PATH",
         "owner": "original_lead_smart_pilot", "evidence_required": "Real visits, ZIP checks, consent, call choice, Ringba accepted disposition",
         "reason": "Turn verified site visits into genuine outcomes without invented call counts"},
    ]
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "source_researched_at": asof.isoformat(),
        "scope": source.get("scope"),
        "operator_count": len(profiles),
        "source_count": len(urls),
        "channel_evidence_edge_count": len(edges),
        "operator_profiles": sorted(profiles, key=lambda r: r["operator_id"]),
        "evidence_graph_edges": edges,
        "channel_observed_operator_counts": {k: len(v) for k, v in sorted(channel_operators.items())},
        "demand_sensor_catalog": sensor_rows,
        "research_market": "US roofing (Chicago pilot focus); market demand and buyer availability unverified",
        "next_research_actions": steps,
        "national_operator_roster_distinct_from_local_contractors": True,
        "actual_channel_traffic_mix_verified": False,
        "competitor_search_rank_verified": False,
        "competitor_keywords_verified": False,
        "payable_lead_or_revenue_verified": False,
        "buyer_intent_inferred": False, "commercial_intent_inferred": False,
        "market_share_inferred": False, "prospect_created": False,
        "outreach_enabled": False, "execution_authority": "none",
        "new_database_or_agent": False, "paid_traffic_authorized": False,
    }


def refresh(repo_root: Path) -> dict:
    source = json.loads((repo_root / SOURCE).read_text(encoding="utf-8"))
    payload = build_atlas(source)
    out = repo_root / DEST
    if out.parent.is_symlink() or out.is_symlink() or not out.parent.is_dir():
        raise ValueError("unsafe original competitive intelligence runtime path")
    fd, tmp = tempfile.mkstemp(prefix=".call-acquisition-", dir=out.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root)
    report = refresh(root) if args.refresh else build_atlas(json.loads((root / SOURCE).read_text()))
    print(json.dumps({
        "status": "ORIGINAL_COMPETITOR_CHANNEL_ATLAS_RECONCILED",
        "operators": report["operator_count"],
        "source_claims": report["source_count"],
        "evidence_edges": report["channel_evidence_edge_count"],
        "research_actions": len(report["next_research_actions"]),
        "written_to_original_runtime": args.refresh,
        "new_agent_or_database": False,
        "outbound_authorized": False,
        "paid_traffic_authorized": False,
        "accepted_calls_or_revenue_verified": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
