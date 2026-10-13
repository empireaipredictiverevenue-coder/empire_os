from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Mapping

from empire_os.buyer_scout_review_readiness import reliable_business_name
from empire_os.predictive_revenue_enterprise_targets import TARGETS

PROMOTION_PLAN = Path("runtime/buyer_acquisition/promotion_plan_latest.json")
OUTPUT = Path("runtime/predictive_revenue/enterprise_pool_latest.json")

NOISE_TOKENS = (
    "press release",
    "newswire",
    "news release",
    "google search",
    "lifecycle policy",
    "search results",
    "media directory",
    "best press release",
    "investor relations",
    "business news",
    "agriculture news",
    "news leader",
    "news, profiles",
    "statistics & reports",
    "architecture/décoration",
    "get smarter delivering",
    "the business impact platform",
    "local news, sports",
    "global industry association",
)


# These are observed editorial/search-result domains, not verified buyers.
NON_BUYER_DOMAINS = frozenset({
    "newsbreak.com", "peprofessional.com", "pulse2.com",
    "pr.capitalpress.com", "investors.beyond.com",
    "forbes.com", "aijourn.com", "aol.com", "github.com",
    "financialcontent.com", "pr.hermistonherald.com",
})

BUYER_TYPE_WEIGHT = {
    "qualified_end_buyer": 5,
    "enterprise_buyer": 5,
    "data_buyer": 4,
    "software_buyer": 4,
    "white_label_agency": 2,
    "agency": 2,
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _valid_domain(value: Any) -> bool:
    domain = _clean(value).lower().strip(".")
    return bool(re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{1,251}[a-z0-9])?\.[a-z]{2,24}", domain))


def _website_matches_domain(website: Any, domain: str) -> bool:
    try:
        parsed = urlparse(_clean(website))
        if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
            return False
        host = (parsed.hostname or "").lower()
    except ValueError:
        return False
    return host == domain or host.endswith("." + domain)


def _score(row: Mapping[str, Any]) -> int:
    pools = {str(v) for v in (row.get("target_buyer_pools") or [])}
    products = {str(v) for v in (row.get("target_product_codes") or [])}
    emails = [str(v) for v in (row.get("first_party_emails_preserved_for_identity_resolution") or []) if str(v).strip()]
    score = BUYER_TYPE_WEIGHT.get(_clean(row.get("buyer_type")).lower(), 0)
    if "enterprise_and_data_buyers" in pools:
        score += 6
    if "software_and_advisory_buyers" in pools:
        score += 3
    if products:
        score += min(len(products), 3) * 2
    if emails:
        score += 3
    if len(emails) >= 2:
        score += 1
    return score


def assess_commercial_readiness(row: Mapping[str, Any]) -> dict[str, Any]:
    """Prioritise research for human verification; never infer buying intent.

    Promotion proposals contain inferred fit, not authenticated commercial
    demand, and cannot grant outbound or revenue authority.
    """
    product_values = row.get("target_product_codes")
    products = [str(v).strip() for v in product_values if str(v).strip()] if isinstance(product_values, (list, tuple)) else []
    domain = _clean(row.get("domain")).lower()
    person_values = row.get("target_people_for_enrichment")
    people = person_values if isinstance(person_values, (list, tuple)) else []
    corroborated_people = [
        person for person in people
        if isinstance(person, Mapping)
        and _clean(person.get("name"))
        and _website_matches_domain(person.get("evidence_url"), domain)
    ]
    missing = []
    if not products:
        missing.append("PRODUCT_MAPPING_REQUIRED")
    if not corroborated_people:
        missing.append("FIRST_PARTY_PERSON_EVIDENCE_REQUIRED")
    missing.append("BUYING_INTENT_NOT_VERIFIED")
    return {
        "state": "FIT_REVIEW" if products and corroborated_people else "RESEARCH_ONLY",
        "product_mapping_present": bool(products),
        "first_party_person_observed": bool(corroborated_people),
        "verified_buying_intent": False,
        "commercially_qualified": False,
        "missing_evidence": missing,
        "outreach_authorized": False,
    }


def build_rolling_enterprise_pool(
    promotion_plan: Mapping[str, Any],
    *,
    limit: int = 25,
) -> dict[str, Any]:
    limit = max(1, min(int(limit), 50))
    seed_names = {t.account_name.casefold() for t in TARGETS}
    seed_keys = {t.account_key for t in TARGETS}

    candidates: list[dict[str, Any]] = []
    seen_domains: set[str] = set()

    for raw in promotion_plan.get("proposals") or []:
        if not isinstance(raw, Mapping):
            continue
        payload = raw.get("proposed_prospect_payload")
        if not isinstance(payload, Mapping):
            continue

        name = _clean(payload.get("business_name"))
        domain = _clean(raw.get("domain")).lower()
        website = _clean(payload.get("website"))

        if not reliable_business_name(name):
            continue
        if name.casefold() in seed_names:
            continue
        if not _valid_domain(domain) or domain in seen_domains:
            continue
        if domain in NON_BUYER_DOMAINS:
            continue
        if not _website_matches_domain(website, domain):
            continue
        lowered = name.casefold()
        if any(token in lowered for token in NOISE_TOKENS):
            continue

        score = _score(raw)
        pools = [str(v) for v in (raw.get("target_buyer_pools") or [])]
        if score < 6:
            continue
        if "enterprise_and_data_buyers" not in pools and "software_and_advisory_buyers" not in pools:
            continue

        seen_domains.add(domain)
        candidates.append({
            "candidate_id": _clean(raw.get("candidate_id")),
            "account_name": name,
            "domain": domain,
            "website": website,
            "buyer_type": _clean(raw.get("buyer_type")) or "unknown",
            "selection_score": score,
            "target_buyer_pools": pools,
            "target_product_codes": [str(v) for v in (raw.get("target_product_codes") or [])],
            "first_party_email_count": len(raw.get("first_party_emails_preserved_for_identity_resolution") or []),
            "source": "buyer_scout_promotion_plan",
            "classification": "ROLLING_ENTERPRISE_RESEARCH_CANDIDATE",
            "commercial_readiness": assess_commercial_readiness(raw),
            "review_ready": False,
            "outreach_authorized": False,
            "payment_action": False,
            "actual_revenue": False,
            "execution_authority": "none",
        })

    candidates.sort(key=lambda r: (-int(r["selection_score"]), r["domain"]))
    selected = candidates[:limit]

    return {
        "schema_version": "empire.predictive-revenue-enterprise-pool.v1",
        "mode": "OBSERVE",
        "seed_target_count": len(TARGETS),
        "seed_account_keys": sorted(seed_keys),
        "rolling_addition_limit": limit,
        "eligible_rolling_candidate_count": len(candidates),
        "rolling_addition_count": len(selected),
        "fit_review_count": sum(
            row["commercial_readiness"]["state"] == "FIT_REVIEW" for row in selected
        ),
        "commercially_qualified_count": 0,
        "total_enterprise_candidate_count": len(TARGETS) + len(selected),
        "rolling_candidates": selected,
        "outreach_authorized": False,
        "payment_action": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def refresh(root: Path = Path("."), *, limit: int = 25) -> dict[str, Any]:
    plan = json.loads((root / PROMOTION_PLAN).read_text(encoding="utf-8"))
    payload = build_rolling_enterprise_pool(plan, limit=limit)
    out = root / OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(out)
    return payload
