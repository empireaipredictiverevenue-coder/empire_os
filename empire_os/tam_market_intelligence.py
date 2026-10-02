"""Evidence-backed TAM and market-expansion intelligence.

Observed entity coverage is never promoted to total addressable market. TAM is
known only when an explicit, provenance-bearing TAM observation is supplied.
All opportunity classes are research-only and carry no commercial authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _country(value: Any) -> str:
    code = _clean(value).upper()
    if len(code) != 2 or not code.isalpha():
        raise ValueError("country_code must be a two-letter code")
    return code


@dataclass(frozen=True)
class MarketEntityObservation:
    tenant_id: str
    entity_id: str
    company_name: str
    industry: str
    country_code: str
    source_ref: str
    observed_at: str

    def validate(self) -> None:
        for name in (
            "tenant_id",
            "entity_id",
            "company_name",
            "industry",
            "source_ref",
            "observed_at",
        ):
            if not _clean(getattr(self, name)):
                raise ValueError(f"{name} required")
        _country(self.country_code)


@dataclass(frozen=True)
class TamCountEvidence:
    tenant_id: str
    industry: str
    country_code: str
    entity_count: int
    source_ref: str
    observed_at: str
    evidence_class: str = "VERIFIED_OBSERVATION"

    def validate(self) -> None:
        if not _clean(self.tenant_id):
            raise ValueError("tenant_id required")
        if not _clean(self.industry):
            raise ValueError("industry required")
        _country(self.country_code)
        if int(self.entity_count) < 0:
            raise ValueError("entity_count must be nonnegative")
        if not _clean(self.source_ref) or not _clean(self.observed_at):
            raise ValueError("TAM evidence provenance required")
        if self.evidence_class != "VERIFIED_OBSERVATION":
            raise ValueError("TAM evidence must be verified observation")


def _scope_key(industry: str, country_code: str) -> str:
    return f"{industry.casefold()}::{country_code}"


def build_tam_market_intelligence(
    *,
    tenant_id: str,
    observations: Iterable[MarketEntityObservation],
    active_industries: Iterable[str] = (),
    active_countries: Iterable[str] = (),
    tam_evidence: Iterable[TamCountEvidence] = (),
) -> dict[str, Any]:
    tenant = _clean(tenant_id)
    if not tenant:
        raise ValueError("tenant_id required")

    active_industry_set = {
        _clean(value).casefold()
        for value in active_industries
        if _clean(value)
    }
    active_country_set = {
        _country(value)
        for value in active_countries
        if _clean(value)
    }

    scopes: dict[str, dict[str, Any]] = {}
    for item in observations:
        item.validate()
        if item.tenant_id != tenant:
            raise ValueError("mixed tenant observations are not allowed")
        industry = _clean(item.industry)
        country_code = _country(item.country_code)
        key = _scope_key(industry, country_code)
        scope = scopes.setdefault(
            key,
            {
                "industry": industry,
                "country_code": country_code,
                "entities": {},
                "evidence_refs": set(),
                "observed_at": set(),
            },
        )
        entity = scope["entities"].setdefault(
            item.entity_id,
            {
                "entity_id": item.entity_id,
                "company_name": _clean(item.company_name),
                "evidence_refs": set(),
            },
        )
        entity["evidence_refs"].add(_clean(item.source_ref))
        scope["evidence_refs"].add(_clean(item.source_ref))
        scope["observed_at"].add(_clean(item.observed_at))

    tam_by_scope: dict[str, TamCountEvidence] = {}
    for evidence in tam_evidence:
        evidence.validate()
        if evidence.tenant_id != tenant:
            raise ValueError("mixed tenant TAM evidence is not allowed")
        industry = _clean(evidence.industry)
        country_code = _country(evidence.country_code)
        key = _scope_key(industry, country_code)
        existing = tam_by_scope.get(key)
        if existing is not None and existing != evidence:
            raise ValueError("conflicting TAM evidence for market scope")
        tam_by_scope[key] = evidence

    market_scopes: list[dict[str, Any]] = []
    opportunities: list[dict[str, Any]] = []

    for key in sorted(scopes):
        raw = scopes[key]
        industry = raw["industry"]
        country_code = raw["country_code"]
        entities = raw["entities"]
        observed_count = len(entities)
        tam = tam_by_scope.get(key)

        if tam is not None and int(tam.entity_count) < observed_count:
            raise ValueError(
                "verified TAM count cannot be below observed canonical coverage"
            )

        tam_count = int(tam.entity_count) if tam is not None else None
        coverage_ratio = (
            round(observed_count / tam_count, 6)
            if tam_count not in (None, 0)
            else None
        )
        new_industry = industry.casefold() not in active_industry_set
        new_country = country_code not in active_country_set

        entity_rows = []
        for entity_id in sorted(entities):
            entity = entities[entity_id]
            entity_rows.append(
                {
                    "entity_id": entity_id,
                    "company_name": entity["company_name"],
                    "evidence_refs": sorted(entity["evidence_refs"]),
                }
            )

        evidence_refs = sorted(raw["evidence_refs"])
        market_scopes.append(
            {
                "scope_key": key,
                "industry": industry,
                "country_code": country_code,
                "observed_entity_count": observed_count,
                "tam_entity_count": tam_count,
                "tam_state": "VERIFIED" if tam is not None else "UNKNOWN",
                "tam_evidence_ref": tam.source_ref if tam is not None else None,
                "tam_observed_at": tam.observed_at if tam is not None else None,
                "coverage_ratio": coverage_ratio,
                "new_industry": new_industry,
                "new_country": new_country,
                "entities": entity_rows,
                "evidence_refs": evidence_refs,
            }
        )

        classes: list[str] = []
        if new_industry:
            classes.append("new_industry")
        if new_country:
            classes.append("new_country")
        if new_industry and new_country:
            classes.append("new_industry_country")

        for opportunity_class in classes:
            opportunities.append(
                {
                    "opportunity_key": (
                        f"tam:{tenant}:{opportunity_class}:"
                        f"{industry.casefold()}:{country_code}"
                    ),
                    "opportunity_class": opportunity_class,
                    "industry": industry,
                    "country_code": country_code,
                    "observed_entity_count": observed_count,
                    "tam_entity_count": tam_count,
                    "tam_state": "VERIFIED" if tam is not None else "UNKNOWN",
                    "evidence_refs": evidence_refs,
                    "decision": "research",
                    "next_event": "opportunity_research_requested",
                    "buyer_intent_proven": False,
                    "demand_proven": False,
                    "commercial_terms_verified": False,
                    "revenue_verified": False,
                    "execution_authority": "none",
                }
            )

    opportunities.sort(
        key=lambda row: (
            row["opportunity_class"],
            row["industry"].casefold(),
            row["country_code"],
        )
    )

    return {
        "schema_version": "empire.tam-market-intelligence.v1",
        "mode": "OBSERVE",
        "tenant_id": tenant,
        "market_scope_count": len(market_scopes),
        "observed_unique_entity_count": len(
            {
                row["entity_id"]
                for scope in market_scopes
                for row in scope["entities"]
            }
        ),
        "market_scopes": market_scopes,
        "opportunity_classes": opportunities,
        "tam_inferred_from_observed_roster": False,
        "buyer_intent_inferred": False,
        "demand_inferred": False,
        "pricing_inferred": False,
        "revenue_inferred": False,
        "prospect_created": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }
