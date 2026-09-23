"""Country-native pricing for Empire commercial products.

Localized prices are commercial display/pricing proposals, not FX conversions.
Only explicitly founder-approved market prices may enter the governed catalog
with VERIFIED price evidence. Other market prices remain PROPOSED and cannot
become binding terms through the deterministic catalog verifier.

No buyer approval, outbound, payment mutation or revenue recognition occurs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping

from empire_os.qualification_worker_v2 import request_json


Request = Callable[..., Any]
BASE_PRODUCT_CODE = "solar_opportunity_map"


@dataclass(frozen=True)
class MarketPrice:
    country_code: str
    currency: str
    amount_minor: int
    display_price: str
    locale: str
    approval_state: str
    source_type: str
    rationale: str

    @property
    def product_code(self) -> str:
        return f"{BASE_PRODUCT_CODE}_{self.country_code.lower()}"

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "product_code": self.product_code,
            "binding_terms_ready": False,
            "actual_revenue": False,
        }


# GB is the only founder-approved localized price at present.
# All other values are deliberate local-market price proposals, not live FX
# conversions and not binding commercial terms.
SOLAR_OPPORTUNITY_MAP_PRICES: dict[str, MarketPrice] = {
    "GB": MarketPrice(
        "GB", "GBP", 24900, "£249", "en-GB",
        "FOUNDER_APPROVED", "founder_approved",
        "Founder-agreed UK Solar Opportunity Map price.",
    ),
    "US": MarketPrice(
        "US", "USD", 29900, "$299", "en-US",
        "PROPOSED", "empire_pricing_draft",
        "Localized US price-point proposal; founder ratification required.",
    ),
    "CA": MarketPrice(
        "CA", "CAD", 39900, "C$399", "en-CA",
        "PROPOSED", "empire_pricing_draft",
        "Localized Canadian price-point proposal; founder ratification required.",
    ),
    "AU": MarketPrice(
        "AU", "AUD", 49900, "A$499", "en-AU",
        "PROPOSED", "empire_pricing_draft",
        "Localized Australian price-point proposal; founder ratification required.",
    ),
    "NZ": MarketPrice(
        "NZ", "NZD", 49900, "NZ$499", "en-NZ",
        "PROPOSED", "empire_pricing_draft",
        "Localized New Zealand price-point proposal; founder ratification required.",
    ),
    "IE": MarketPrice(
        "IE", "EUR", 29900, "€299", "en-IE",
        "PROPOSED", "empire_pricing_draft",
        "Localized Irish euro price-point proposal; founder ratification required.",
    ),
    "DE": MarketPrice(
        "DE", "EUR", 29900, "€299", "de-DE",
        "PROPOSED", "empire_pricing_draft",
        "Localized German euro price-point proposal; founder ratification required.",
    ),
    "FR": MarketPrice(
        "FR", "EUR", 29900, "€299", "fr-FR",
        "PROPOSED", "empire_pricing_draft",
        "Localized French euro price-point proposal; founder ratification required.",
    ),
    "ES": MarketPrice(
        "ES", "EUR", 24900, "€249", "es-ES",
        "PROPOSED", "empire_pricing_draft",
        "Localized Spanish euro price-point proposal; founder ratification required.",
    ),
    "IT": MarketPrice(
        "IT", "EUR", 24900, "€249", "it-IT",
        "PROPOSED", "empire_pricing_draft",
        "Localized Italian euro price-point proposal; founder ratification required.",
    ),
    "NL": MarketPrice(
        "NL", "EUR", 29900, "€299", "nl-NL",
        "PROPOSED", "empire_pricing_draft",
        "Localized Dutch euro price-point proposal; founder ratification required.",
    ),
    "BE": MarketPrice(
        "BE", "EUR", 29900, "€299", "nl-BE",
        "PROPOSED", "empire_pricing_draft",
        "Localized Belgian euro price-point proposal; founder ratification required.",
    ),
    "PT": MarketPrice(
        "PT", "EUR", 24900, "€249", "pt-PT",
        "PROPOSED", "empire_pricing_draft",
        "Localized Portuguese euro price-point proposal; founder ratification required.",
    ),
}


_SOURCE_COUNTRY = {
    "recc_solar": "GB",
    "gb_recc_solar": "GB",
    "gb_mcs": "GB",
    "gb_trustmark": "GB",
    "au_saa_solar": "AU",
    "ie_seai_solar": "IE",
    "de_mastr": "DE",
    "fr_france_renov_rge": "FR",
}


def market_price(country_code: str) -> MarketPrice:
    code = str(country_code or "").strip().upper()
    if code not in SOLAR_OPPORTUNITY_MAP_PRICES:
        raise KeyError(f"solar market price not configured: {code}")
    return SOLAR_OPPORTUNITY_MAP_PRICES[code]


def infer_country_code(
    *,
    country_code: str | None = None,
    source: str | None = None,
    metro: str | None = None,
    address: str | None = None,
) -> str | None:
    explicit = str(country_code or "").strip().upper()
    if explicit in SOLAR_OPPORTUNITY_MAP_PRICES:
        return explicit

    src = str(source or "").strip().casefold()
    if src in _SOURCE_COUNTRY:
        return _SOURCE_COUNTRY[src]

    haystack = " ".join(
        str(value or "").strip().casefold()
        for value in (metro, address)
    )
    aliases = (
        ("GB", ("united kingdom", "great britain", "england", "scotland", "wales")),
        ("US", ("united states", "usa", "u.s.", "u.s.a.")),
        ("CA", ("canada",)),
        ("AU", ("australia",)),
        ("NZ", ("new zealand",)),
        ("IE", ("ireland",)),
        ("DE", ("germany", "deutschland")),
        ("FR", ("france",)),
        ("ES", ("spain", "españa")),
        ("IT", ("italy", "italia")),
        ("NL", ("netherlands", "nederland")),
        ("BE", ("belgium", "belgië", "belgique")),
        ("PT", ("portugal",)),
    )
    for code, names in aliases:
        if any(name in haystack for name in names):
            return code
    return None


def pricing_matrix() -> dict[str, Any]:
    rows = [
        SOLAR_OPPORTUNITY_MAP_PRICES[code].as_dict()
        for code in (
            "GB", "US", "CA", "AU", "NZ", "IE",
            "DE", "FR", "ES", "IT", "NL", "BE", "PT",
        )
    ]
    return {
        "schema_version": "empire.market-pricing.v1",
        "base_product_code": BASE_PRODUCT_CODE,
        "market_count": len(rows),
        "founder_approved_count": sum(
            row["approval_state"] == "FOUNDER_APPROVED"
            for row in rows
        ),
        "proposed_count": sum(
            row["approval_state"] == "PROPOSED"
            for row in rows
        ),
        "markets": rows,
        "fx_conversion_used": False,
        "binding_terms_ready": False,
        "actual_revenue": False,
    }


def _catalog_rows(
    request: Request,
    product_code: str,
) -> list[dict[str, Any]]:
    rows = request(
        "POST",
        "/rest/v1/rpc/get_commercial_product_catalog",
        payload={
            "p_product_code": product_code,
            "p_limit": 1,
        },
    ) or []
    if isinstance(rows, Mapping):
        rows = [rows]
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _matching_price_version(
    row: Mapping[str, Any],
    price: MarketPrice,
) -> bool:
    basis = row.get("price_basis")
    if not isinstance(basis, Mapping):
        return False
    expected_state = (
        "VERIFIED"
        if price.approval_state == "FOUNDER_APPROVED"
        else "PROPOSED"
    )
    try:
        amount = int(basis.get("amount_cents"))
    except (TypeError, ValueError):
        return False
    return (
        str(row.get("version_state") or "").upper()
        in {"PENDING", "VERIFIED"}
        and str(row.get("billing_model") or "") == "one_time"
        and str(basis.get("state") or "").upper() == expected_state
        and str(basis.get("currency") or "").upper() == price.currency
        and str(basis.get("unit") or "") == "per_map"
        and amount == price.amount_minor
    )


def sync_market_price(
    price: MarketPrice,
    *,
    request: Request = request_json,
) -> dict[str, Any]:
    existing = _catalog_rows(request, price.product_code)
    if existing and _matching_price_version(existing[0], price):
        return {
            "product_code": price.product_code,
            "country_code": price.country_code,
            "currency": price.currency,
            "display_price": price.display_price,
            "approval_state": price.approval_state,
            "decision": "existing",
            "version_id": existing[0].get("version_id"),
            "version_state": existing[0].get("version_state"),
            "binding_terms_ready": bool(
                existing[0].get("binding_terms_ready") is True
            ),
            "actual_revenue": False,
        }

    identity = request(
        "POST",
        "/rest/v1/rpc/register_commercial_product_identity",
        payload={
            "p_product_code": price.product_code,
            "p_product_name": (
                f"Solar Opportunity Map — {price.country_code}"
            ),
            "p_product_family": "search_intelligence",
            "p_billing_model": "one_time",
            "p_configuration": {
                "parent_product_code": BASE_PRODUCT_CODE,
                "country_code": price.country_code,
                "currency": price.currency,
                "locale": price.locale,
                "delivery": "evidence_backed_opportunity_map",
                "pricing_scope": "market_localized",
            },
            "p_provenance": {
                "source": "empire_os.market_pricing",
                "price_source_type": price.source_type,
                "approval_state": price.approval_state,
                "fx_conversion_used": False,
            },
            "p_actor": "market-pricing-sync",
        },
    ) or {}

    price_state = (
        "VERIFIED"
        if price.approval_state == "FOUNDER_APPROVED"
        else "PROPOSED"
    )
    version = request(
        "POST",
        "/rest/v1/rpc/propose_commercial_product_version",
        payload={
            "p_product_code": price.product_code,
            "p_billing_model": "one_time",
            "p_currency": price.currency,
            "p_price_basis": {
                "state": price_state,
                "amount_cents": price.amount_minor,
                "currency": price.currency,
                "unit": "per_map",
                "billing_model": "one_time",
                "source_type": price.source_type,
                "approval_state": price.approval_state,
                "rationale": price.rationale,
            },
            "p_acquisition_cost_basis": {
                "state": "UNKNOWN",
                "reason": "market_acquisition_cost_not_yet_verified",
            },
            "p_fulfilment_cost_basis": {
                "state": "UNKNOWN",
                "reason": "market_fulfilment_cost_not_yet_verified",
            },
            "p_margin_policy": {
                "state": "UNKNOWN",
                "reason": "market_margin_policy_not_yet_verified",
            },
            "p_provenance": {
                "source": "empire_os.market_pricing",
                "country_code": price.country_code,
                "approval_state": price.approval_state,
                "fx_conversion_used": False,
                "binding_terms_ready": False,
            },
            "p_evidence_refs": [
                (
                    f"market_price:{BASE_PRODUCT_CODE}:"
                    f"{price.country_code}:{price.approval_state}"
                ),
            ],
            "p_effective_from": None,
            "p_effective_until": None,
            "p_actor": "market-pricing-sync",
        },
    ) or {}

    return {
        "product_code": price.product_code,
        "country_code": price.country_code,
        "currency": price.currency,
        "display_price": price.display_price,
        "approval_state": price.approval_state,
        "decision": version.get("decision") or "proposed",
        "identity": identity,
        "version": version,
        "binding_terms_ready": False,
        "actual_revenue": False,
    }


def sync_solar_market_pricing(
    request: Request = request_json,
) -> dict[str, Any]:
    results = []
    errors = []
    for price in SOLAR_OPPORTUNITY_MAP_PRICES.values():
        try:
            results.append(sync_market_price(price, request=request))
        except Exception as exc:
            errors.append({
                "country_code": price.country_code,
                "error": f"{type(exc).__name__}:{str(exc)[:240]}",
            })

    return {
        "schema_version": "empire.market-pricing-sync.v1",
        "base_product_code": BASE_PRODUCT_CODE,
        "attempted": len(SOLAR_OPPORTUNITY_MAP_PRICES),
        "synchronized": len(results),
        "error_count": len(errors),
        "results": results,
        "errors": errors,
        "fx_conversion_used": False,
        "binding_terms_ready": False,
        "outbound_sent": False,
        "payment_mutation": False,
        "recognized_revenue": False,
        "actual_revenue": False,
    }
