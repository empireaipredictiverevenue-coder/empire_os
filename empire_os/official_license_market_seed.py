"""Official-license market seeds for zero-paid buyer discovery.

A license row is public company/person association evidence only. This module
uses it to discover likely first-party domains; it grants no buyer, outreach,
commercial, payment, or revenue authority.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from empire_os.official_license_identity import (
    TEXAS_TDLR_AC_CACHE,
    TEXAS_TDLR_SOURCE,
    _normalise_company,
    _parse_mmddyyyy,
    _parse_tdlr_owner,
)
from empire_os.search_fabric.search import search_domains_parallel


OUTPUT = Path(
    "runtime/buyer_acquisition/official_license_market_seeds.json"
)
SearchFn = Callable[[list[str], int], Mapping[str, list[str]]]

_BAD_HOSTS = {
    "google.com", "search.google", "bing.com", "duckduckgo.com",
    "facebook.com", "linkedin.com", "youtube.com", "reddit.com",
    "yelp.com", "angi.com", "homeadvisor.com", "bbb.org",
    "yellowpages.com", "mapquest.com", "houzz.com",
}


def _host(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else "https://" + text)
    host = parsed.netloc.split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _location_text(row: Mapping[str, Any]) -> str:
    value = " ".join(
        str(row.get("business_city_state_zip") or "").split()
    ).strip()
    value = re.sub(r"\b\d{5}(?:-\d{4})?\b", "", value).strip(" ,")
    return value or "TX"


def _eligible_records(
    payload: Mapping[str, Any],
    *,
    as_of: date,
) -> list[dict[str, Any]]:
    dedup: dict[str, dict[str, Any]] = {}
    for raw in payload.get("records") or []:
        if not isinstance(raw, Mapping):
            continue
        if str(raw.get("license_type") or "").strip() != "A/C Contractor":
            continue
        expiry = _parse_mmddyyyy(
            raw.get("license_expiration_date_mmddccyy")
        )
        if expiry is None or expiry < as_of:
            continue
        business = " ".join(
            str(raw.get("business_name") or "").split()
        ).strip()
        owner = _parse_tdlr_owner(raw.get("owner_name"))
        company_key = _normalise_company(business)
        if (
            not business
            or not company_key
            or not owner
            or _normalise_company(owner) == company_key
        ):
            continue
        row = dict(raw)
        row["_owner_person"] = owner
        existing = dedup.get(company_key)
        if existing is None:
            dedup[company_key] = row
            continue
        old_expiry = _parse_mmddyyyy(
            existing.get("license_expiration_date_mmddccyy")
        )
        if old_expiry is None or expiry > old_expiry:
            dedup[company_key] = row
    return sorted(
        dedup.values(),
        key=lambda row: (
            str(row.get("business_county") or ""),
            _normalise_company(row.get("business_name") or ""),
            str(row.get("license_number") or ""),
        ),
    )


def build_official_license_market_seeds(
    cache_payload: Mapping[str, Any],
    *,
    search_fn: SearchFn = search_domains_parallel,
    max_queries: int = 30,
    results_per_query: int = 4,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("observed_at must include timezone")

    eligible = _eligible_records(
        cache_payload,
        as_of=now.astimezone(timezone.utc).date(),
    )
    query_limit = max(1, min(int(max_queries), 60))
    if eligible:
        slot = int(now.timestamp() // 1800)
        start = (slot * query_limit) % len(eligible)
        selected = [
            eligible[(start + offset) % len(eligible)]
            for offset in range(min(query_limit, len(eligible)))
        ]
    else:
        selected = []

    query_rows: list[tuple[str, dict[str, Any]]] = []
    for row in selected:
        business = " ".join(
            str(row.get("business_name") or "").split()
        ).strip()
        location = _location_text(row)
        query = f'"{business}" "{location}"'
        query_rows.append((query, row))

    query_texts = [query for query, _ in query_rows]
    errors: list[str] = []
    try:
        domain_map = (
            search_fn(
                query_texts,
                num=max(1, min(int(results_per_query), 6)),
            )
            if query_texts
            else {}
        )
    except Exception as exc:
        domain_map = {}
        errors.append(
            f"search_fabric:{type(exc).__name__}:{str(exc)[:160]}"
        )

    by_domain: dict[str, dict[str, Any]] = {}
    for query, row in query_rows:
        for domain in domain_map.get(query, []) or []:
            host = _host(domain)
            if not host or host in _BAD_HOSTS:
                continue
            target = by_domain.setdefault(host, {
                "domain": host,
                "website": "https://" + host,
                "source_refs": [],
                "source_queries": [],
                "target_buyer_pools": [
                    "end_service_buyers",
                    "local_and_smb_buyers",
                ],
                "target_corridor_keys": [],
                "target_product_codes": ["managed_service"],
                "truth_class": "OBSERVED_OFFICIAL_LICENSE_RESEARCH",
                "identity_verified": False,
                "commercial_terms_verified": False,
                "buyer_capacity_verified": False,
                "buyer_price_verified": False,
                "outreach_authorized": False,
                "execution_authority": "none",
                "registry_business_name": row.get("business_name"),
                "registry_location": _location_text(row),
                "registry_identity_seed": {
                    "name": row.get("_owner_person"),
                    "title": "Licensed A/C Contractor",
                    "source": "texas_tdlr_ac_contractor",
                    "source_url": TEXAS_TDLR_SOURCE,
                    "license_number": row.get("license_number"),
                    "buyer_authority_proven": False,
                },
            })
            ref = (
                "official:texas_tdlr_ac:"
                + str(row.get("license_number") or "unknown")
            )
            if ref not in target["source_refs"]:
                target["source_refs"].append(ref)
            if query not in target["source_queries"]:
                target["source_queries"].append(query)

    seeds = sorted(by_domain.values(), key=lambda row: row["domain"])
    return {
        "schema_version": "empire.official-license-market-seeds.v1",
        "mode": "OBSERVE",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "registry_record_count": len(cache_payload.get("records") or []),
        "eligible_company_count": len(eligible),
        "query_count": len(query_rows),
        "seed_count": len(seeds),
        "error_count": len(errors),
        "errors": errors,
        "seeds": seeds,
        "database_write_performed": False,
        "outbound_sent": False,
        "commercial_authority": "none",
        "execution_authority": "none",
    }


def refresh_official_license_market_seeds(
    repo_root: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    cache_path = root / TEXAS_TDLR_AC_CACHE.relative_to("/srv/empire_os")
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    result = build_official_license_market_seeds(payload, **kwargs)
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return result
