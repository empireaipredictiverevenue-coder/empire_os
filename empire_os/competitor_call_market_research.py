"""Original competitor intelligence: sourced how-pay-per-call-operators-acquire traffic.

A static, reviewed primary-source disclosure dossier, NOT estimated keyword
share, verified call volume or a second prospect/agent/marketing pipeline.
"""
from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

SCHEMA = "empire.call_acquisition_operator_research.v1"
SOURCE_SCHEMA = "empire.call_acquisition_operator_research_sources.v1"
SOURCE = Path("docs/commercial/call_acquisition_full_market_research_20261027.json")
DEST = Path("runtime/competitive_intelligence/call_acquisition_market_research_latest.json")
OPERATORS = frozenset({
    "angi", "quinstreet", "modernize", "elocal", "service_direct",
    "aragon", "ringpartner", "marketcall",
})
CHANNELS = frozenset({
    "organic_search", "paid_search", "paid_social", "display",
    "affiliate_publishers", "offline", "retail_referral", "owned_media",
    "native_ads", "call_center", "influencer",
})
OUTCOMES = frozenset({
    "service_request", "click", "form_lead", "inbound_call",
    "application", "customer", "live_transfer",
})
PAYMENTS = frozenset({
    "lead_fee", "advertising", "subscription", "cpc", "cpl", "cpa",
    "revenue_share", "pay_per_call", "duration_based_cpl",
    "qualified_campaign_payout",
})
DOMAIN_MAP = {
    "angi": {"www.sec.gov"},
    "quinstreet": {"www.otcmarkets.com"},
    "modernize": {"modernize.com"},
    "elocal": {"www.elocal.com"},
    "service_direct": {"blog.servicedirect.com"},
    "aragon": {"aragon-advertising.com"},
    "ringpartner": {"www.ringpartner.com"},
    "marketcall": {"www.marketcall.com"},
}
POLICY_DOMAINS = {"support.ringba.com", "support.google.com", "support.google.com",
                  "developers.google.com"}


def _url(uri: Any, allowed: set[str]) -> str:
    if not isinstance(uri, str) or len(uri) > 500:
        raise ValueError("untrusted research URL")
    parsed = urlsplit(uri)
    if (parsed.scheme != "https" or parsed.hostname not in allowed
            or parsed.username or parsed.password or parsed.port is not None):
        raise ValueError("source URL is not an accepted primary publisher")
    return uri


def _terms(items: Any, allowed: frozenset[str]) -> list[str]:
    if (not isinstance(items, list) or len(items) > 20
            or any(type(i) is not str or i not in allowed for i in items)
            or len(items) != len(set(items))):
        raise ValueError("invalid observed commercial taxonomy")
    return sorted(items)


def _date(raw: Any) -> datetime:
    if not isinstance(raw, str):
        raise ValueError("review date missing")
    date = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise ValueError("research date must be offset-aware")
    return date.astimezone(timezone.utc)


def build_market_research(source: dict, *, now: datetime | None = None) -> dict:
    if (not isinstance(source, dict)
            or source.get("schema_version") != SOURCE_SCHEMA
            or source.get("scope") != "PUBLIC_VERIFIED_BUSINESS_MODEL_DISCLOSURES_NOT_LIVE_TRAFFIC"):
        raise ValueError("bad original market research contract")
    review_at = _date(source.get("observed_at_utc"))
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or review_at > now.astimezone(timezone.utc):
        raise ValueError("research date not yet valid")
    records = source.get("operators")
    if not isinstance(records, list) or len(records) != len(OPERATORS):
        raise ValueError("missing operator comparisons")
    roster = []
    sources = set()
    counts = defaultdict(int)
    indicator_count = 0
    seen = set()
    for original in records:
        if not isinstance(original, dict) or original.get("id") not in OPERATORS:
            raise ValueError("unexpected operator record")
        op = original["id"]
        if op in seen:
            raise ValueError("duplicate operator record")
        seen.add(op)
        name = original.get("name")
        if not isinstance(name, str) or not 2 <= len(name) <= 120:
            raise ValueError("invalid public operator name")
        urls = original.get("source_urls")
        if not isinstance(urls, list) or not 1 <= len(urls) <= 5:
            raise ValueError("missing primary evidence")
        canonical = [_url(url, DOMAIN_MAP[op]) for url in urls]
        if len(set(canonical)) != len(canonical):
            raise ValueError("repeated evidence URL")
        for url in canonical:
            sources.add(url)
        channels = _terms(original.get("channel_families"), CHANNELS)
        products = _terms(original.get("conversion_products"), OUTCOMES)
        payments = _terms(original.get("business_models"), PAYMENTS)
        observations = original.get("observations")
        if (not isinstance(observations, list) or not 1 <= len(observations) <= 8
                or any(not isinstance(x, str) or not 20 <= len(x) <= 330 for x in observations)):
            raise ValueError("operator statements lack cited source")
        indicators = original.get("reported_indicators")
        if not isinstance(indicators, list) or len(indicators) > 3:
            raise ValueError("invalid reported indicator inventory")
        for item in indicators:
            if not isinstance(item, dict) or item.get("source_class") not in {
                "REGULATORY_FILING", "OPERATOR_MARKETING_CLAIM",
            }:
                raise ValueError("undisclosed numerical claim source")
            if (type(item.get("value")) is not int or item["value"] < 0
                    or not isinstance(item.get("limitations"), str)
                    or not item.get("limitations")):
                raise ValueError("non-grounded quantitative marketing claim")
            indicator_count += 1
        for channel in channels:
            counts[channel] += 1
        roster.append({
            "operator_id": op, "operator_name": name,
            "source_urls": canonical, "channel_families": channels,
            "conversion_products": products, "business_models": payments,
            "evidence_statements": observations, "reported_indicators": indicators,
            "actual_paid_or_organic_channel_mix_observed": False,
            "qualified_calls_audited": False,
            "publisher_terms_available_to_empire": False,
        })
    if seen != OPERATORS:
        raise ValueError("operator source inventory incomplete")
    policies = source.get("platform_and_policy_sources")
    if not isinstance(policies, list) or not 3 <= len(policies) <= 8:
        raise ValueError("platform policy evidence absent")
    for item in policies:
        _url(item.get("url"), POLICY_DOMAINS)
        if not isinstance(item.get("evidence"), str) or not item.get("evidence"):
            raise ValueError("policy claim not documented")
    priorities = source.get("zero_paid_spend_priority")
    if not isinstance(priorities, list) or [v.get("priority") for v in priorities] != list(range(1, 6)):
        raise ValueError("must retain original zero-spend priority ranking")
    for item in priorities:
        if (not isinstance(item.get("requires"), str) or
                not isinstance(item.get("execution_owner"), str)):
            raise ValueError("missing original owner/evidence requirement")
    guards = source.get("prohibitions")
    if (not isinstance(guards, dict) or
            set(guards.values()) != {False} or len(guards) != 9):
        raise ValueError("research cannot contain execution authority")
    metrics = source.get("measurement_contract")
    if not isinstance(metrics, dict) or any(
        metrics.get(key) != "UNKNOWN"
        for key in (
            "first_party_sessions",
            "source_channel_attributed_sessions",
            "eligible_zip_page_views",
            "consented_call_choices",
            "connected_calls",
            "buyer_accepted_payable_calls",
            "independently_paid_settlement_usd",
            "true_per_channel_cost_usd",
        )
    ):
        raise ValueError("real traffic metrics must stay UNKNOWN")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE", "generated_at": now.astimezone(timezone.utc).isoformat(),
        "reviewed_public_sources_at": review_at.isoformat(),
        "operator_count": len(roster),
        "distinct_primary_sources_count": len(sources),
        "documented_reported_indicator_count": indicator_count,
        "operators": sorted(roster, key=lambda row: row["operator_id"]),
        "operators_by_observed_channel": dict(sorted(counts.items())),
        "platform_policy_sources": policies,
        "research_actions": priorities,
        "measurement_contract": metrics,
        "business_model_research_pass_complete": True,
        "channel_conversion_performance_established": False,
        "media_or_publisher_contract_terms_verified": False,
        "actual_visitor_to_payable_call_rates_calibrated": False,
        "ranking_of_profitable_channels_verified": False,
        "financial_reported_indicators_not_our_revenue": True,
        "live_call_traffic_authorized": False,
        "outbound_enabled": False, "paid_traffic_enabled": False,
        "execution_authority": "none",
        "existing_empiredb_and_agents_reused": True,
    }


def refresh(repo_root: Path) -> dict:
    raw = json.loads((repo_root / SOURCE).read_text(encoding="utf-8"))
    payload = build_market_research(raw)
    dest = repo_root / DEST
    if not dest.parent.is_dir() or dest.parent.is_symlink() or dest.is_symlink():
        raise ValueError("unsafe original competitor intelligence output")
    fd, tmp = tempfile.mkstemp(prefix=".call-research-", dir=dest.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as w:
            json.dump(payload, w, indent=2, sort_keys=True)
            w.write("\n")
            w.flush()
            os.fsync(w.fileno())
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return payload
