"""Evidence-backed competitive intelligence for Empire Strategy.

Search presence, AI citation presence and observed competitive facts are
strategic signals. They are never treated as market share unless explicit,
external market-share evidence is supplied.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit


def _text(value: Any) -> str:
    return str(value or "").strip()


def _domain(value: Any) -> str:
    text = _text(value).lower()
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    host = (urlsplit(text).hostname or "").lower().rstrip(".")
    return host.removeprefix("www.")


def _position(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        position = int(value)
    except (TypeError, ValueError):
        return None
    return position if position >= 1 else None


def _weight_for_position(position: int | None) -> float:
    # Explicit, deterministic reciprocal-position weighting.
    return 1.0 if position is None else 1.0 / position


@dataclass(frozen=True)
class CompetitiveFact:
    fact_type: str
    summary: str
    source_ref: str
    observed_at: str
    confidence: float | None = None

    def validate(self) -> None:
        if not _text(self.fact_type):
            raise ValueError("fact_type required")
        if not _text(self.summary):
            raise ValueError("fact summary required")
        if not _text(self.source_ref):
            raise ValueError("fact source_ref required")
        if not _text(self.observed_at):
            raise ValueError("fact observed_at required")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("fact confidence must be between 0 and 1")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def review_competitor_profile(raw: Mapping[str, Any]) -> dict[str, Any]:
    competitor_key = _text(raw.get("competitor_key"))
    domain = _domain(raw.get("domain"))
    blockers: list[str] = []
    if not competitor_key:
        blockers.append("competitor_key_required")
    if not domain:
        blockers.append("competitor_domain_required")

    facts: list[dict[str, Any]] = []
    for item in raw.get("observed_facts", ()) or ():
        if not isinstance(item, Mapping):
            continue
        fact = CompetitiveFact(
            fact_type=_text(item.get("fact_type")),
            summary=_text(item.get("summary")),
            source_ref=_text(item.get("source_ref")),
            observed_at=_text(item.get("observed_at")),
            confidence=(
                float(item["confidence"])
                if item.get("confidence") is not None
                else None
            ),
        )
        try:
            facts.append(fact.as_dict())
        except (TypeError, ValueError) as exc:
            blockers.append(f"invalid_fact:{exc}")

    hypotheses = []
    for item in raw.get("hypotheses", ()) or ():
        if not isinstance(item, Mapping):
            continue
        summary = _text(item.get("summary"))
        evidence_refs = [
            _text(x) for x in item.get("evidence_refs", ()) if _text(x)
        ]
        if not summary:
            continue
        hypotheses.append({
            "summary": summary,
            "evidence_refs": evidence_refs,
            "verified_fact": False,
        })

    if not facts:
        blockers.append("observed_competitor_facts_required")

    observed_market_share = raw.get("observed_market_share")
    if observed_market_share is not None:
        try:
            observed_market_share = float(observed_market_share)
        except (TypeError, ValueError):
            blockers.append("observed_market_share_invalid")
            observed_market_share = None
        else:
            if not 0 <= observed_market_share <= 1:
                blockers.append("observed_market_share_invalid")
                observed_market_share = None
            if not _text(raw.get("market_share_source_ref")):
                blockers.append("market_share_source_ref_required")

    return {
        "schema_version": "competitive_profile.v1",
        "competitor_key": competitor_key or None,
        "domain": domain or None,
        "review_ready": not blockers,
        "blockers": blockers,
        "observed_facts": facts,
        "hypotheses": hypotheses,
        "observed_market_share": observed_market_share,
        "market_share_source_ref": (
            _text(raw.get("market_share_source_ref")) or None
            if observed_market_share is not None
            else None
        ),
        "market_share_inferred": False,
        "execution_authority": "none",
    }


def observed_search_presence_share(
    observations: Iterable[Mapping[str, Any]],
    *,
    empire_domains: Iterable[str],
    competitor_domains: Iterable[str],
) -> dict[str, Any]:
    empire = {_domain(x) for x in empire_domains if _domain(x)}
    competitors = {_domain(x) for x in competitor_domains if _domain(x)}
    if not empire:
        raise ValueError("at least one Empire domain required")
    if not competitors:
        raise ValueError("at least one competitor domain required")

    empire_weight = 0.0
    competitor_weight = 0.0
    evidence_count = 0
    queries: set[str] = set()
    ignored_domains: set[str] = set()

    for raw in observations:
        if not isinstance(raw, Mapping):
            continue
        domain = _domain(raw.get("domain") or raw.get("url"))
        query = _text(raw.get("query"))
        observed_at = _text(raw.get("observed_at"))
        provenance = raw.get("provenance")
        position = _position(raw.get("position"))

        if not domain or not query or not observed_at or not provenance:
            continue

        weight = _weight_for_position(position)
        queries.add(query)
        evidence_count += 1

        if domain in empire:
            empire_weight += weight
        elif domain in competitors:
            competitor_weight += weight
        else:
            ignored_domains.add(domain)

    relevant_weight = empire_weight + competitor_weight
    if relevant_weight <= 0:
        return {
            "available": False,
            "reason": "no_observed_empire_or_competitor_search_presence",
            "query_count": len(queries),
            "evidence_count": evidence_count,
            "empire_search_presence_share": None,
            "competitor_search_presence_share": None,
            "market_share": None,
            "market_share_inferred": False,
            "execution_authority": "none",
        }

    return {
        "available": True,
        "method": "reciprocal_position_weighted_observed_presence",
        "query_count": len(queries),
        "evidence_count": evidence_count,
        "empire_weight": round(empire_weight, 6),
        "competitor_weight": round(competitor_weight, 6),
        "empire_search_presence_share": round(empire_weight / relevant_weight, 6),
        "competitor_search_presence_share": round(competitor_weight / relevant_weight, 6),
        "ignored_domain_count": len(ignored_domains),
        "market_share": None,
        "market_share_inferred": False,
        "execution_authority": "none",
    }


def observed_ai_citation_share(
    observations: Iterable[Mapping[str, Any]],
    *,
    empire_domains: Iterable[str],
    competitor_domains: Iterable[str],
) -> dict[str, Any]:
    empire = {_domain(x) for x in empire_domains if _domain(x)}
    competitors = {_domain(x) for x in competitor_domains if _domain(x)}
    if not empire:
        raise ValueError("at least one Empire domain required")
    if not competitors:
        raise ValueError("at least one competitor domain required")

    empire_weight = 0.0
    competitor_weight = 0.0
    evidence_count = 0
    queries: set[str] = set()
    engines: set[str] = set()

    for raw in observations:
        if not isinstance(raw, Mapping):
            continue
        domain = _domain(raw.get("cited_domain") or raw.get("cited_url"))
        query = _text(raw.get("query"))
        engine = _text(raw.get("engine"))
        observed_at = _text(raw.get("observed_at"))
        provenance = raw.get("provenance")
        position = _position(raw.get("citation_position"))

        if not domain or not query or not engine or not observed_at or not provenance:
            continue

        weight = _weight_for_position(position)
        queries.add(query)
        engines.add(engine)
        evidence_count += 1
        if domain in empire:
            empire_weight += weight
        elif domain in competitors:
            competitor_weight += weight

    relevant_weight = empire_weight + competitor_weight
    if relevant_weight <= 0:
        return {
            "available": False,
            "reason": "no_observed_empire_or_competitor_ai_citations",
            "query_count": len(queries),
            "engine_count": len(engines),
            "evidence_count": evidence_count,
            "empire_ai_citation_share": None,
            "competitor_ai_citation_share": None,
            "market_share": None,
            "market_share_inferred": False,
            "execution_authority": "none",
        }

    return {
        "available": True,
        "method": "reciprocal_position_weighted_observed_citation_presence",
        "query_count": len(queries),
        "engine_count": len(engines),
        "evidence_count": evidence_count,
        "empire_weight": round(empire_weight, 6),
        "competitor_weight": round(competitor_weight, 6),
        "empire_ai_citation_share": round(empire_weight / relevant_weight, 6),
        "competitor_ai_citation_share": round(competitor_weight / relevant_weight, 6),
        "market_share": None,
        "market_share_inferred": False,
        "execution_authority": "none",
    }


def build_competitive_landscape(
    *,
    competitor_profiles: Iterable[Mapping[str, Any]],
    search_observations: Iterable[Mapping[str, Any]],
    ai_citation_observations: Iterable[Mapping[str, Any]],
    empire_domains: Iterable[str],
) -> dict[str, Any]:
    profiles = []
    competitor_domains = []

    for raw in competitor_profiles:
        profile = review_competitor_profile(raw)
        profiles.append(profile)
        if profile["domain"]:
            competitor_domains.append(profile["domain"])

    if not competitor_domains:
        return {
            "schema_version": "competitive_landscape.v1",
            "mode": "OBSERVE",
            "execution_authority": "none",
            "profiles": profiles,
            "search_presence": {
                "available": False,
                "reason": "no_competitor_domains",
            },
            "ai_citation_presence": {
                "available": False,
                "reason": "no_competitor_domains",
            },
            "market_share_inferred": False,
            "market_entry_execution": False,
        }

    search = observed_search_presence_share(
        search_observations,
        empire_domains=empire_domains,
        competitor_domains=competitor_domains,
    )
    ai = observed_ai_citation_share(
        ai_citation_observations,
        empire_domains=empire_domains,
        competitor_domains=competitor_domains,
    )

    observed_market_shares = [
        {
            "competitor_key": profile["competitor_key"],
            "observed_market_share": profile["observed_market_share"],
            "source_ref": profile["market_share_source_ref"],
        }
        for profile in profiles
        if profile["observed_market_share"] is not None
    ]

    return {
        "schema_version": "competitive_landscape.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "profiles": profiles,
        "search_presence": search,
        "ai_citation_presence": ai,
        "observed_competitor_market_shares": observed_market_shares,
        "market_share_inferred": False,
        "market_entry_execution": False,
        "publishing_enabled": False,
        "outreach_enabled": False,
    }


# ---------------------------------------------------------------------------
# Competitor Audience Graph
# ---------------------------------------------------------------------------

COMPETITOR_AUDIENCE_EVIDENCE_TYPES = frozenset({
    "customer_case_study",
    "testimonial_company",
    "partner_ecosystem",
    "public_review_company",
    "search_overlap",
    "comparison_mention",
    "event_participant",
    "public_competitor_activity",
})


def _normalise_audience_domain(value: Any) -> str:
    value = str(value or "").strip().lower()
    value = value.removeprefix("https://").removeprefix("http://")
    value = value.split("/", 1)[0]
    return value.removeprefix("www.")


def review_competitor_audience_evidence(
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate public company-level competitor-audience evidence.

    This establishes an observed relationship/evidence item only. It never
    establishes buyer intent, commercial intent, prospect status or execution
    authority.
    """
    competitor_key = str(raw.get("competitor_key") or "").strip()
    competitor_domain = _normalise_audience_domain(
        raw.get("competitor_domain")
    )
    company_name = str(raw.get("company_name") or "").strip()
    company_domain = _normalise_audience_domain(raw.get("company_domain"))
    evidence_type = str(raw.get("evidence_type") or "").strip()
    summary = str(raw.get("summary") or "").strip()
    source_ref = str(raw.get("source_ref") or "").strip()
    observed_at = str(raw.get("observed_at") or "").strip()

    blockers: list[str] = []

    if not competitor_key:
        blockers.append("competitor_key_required")
    if not competitor_domain:
        blockers.append("competitor_domain_required")
    if not company_name and not company_domain:
        blockers.append("company_identity_required")
    if evidence_type not in COMPETITOR_AUDIENCE_EVIDENCE_TYPES:
        blockers.append("unsupported_evidence_type")
    if not summary:
        blockers.append("summary_required")
    if not source_ref:
        blockers.append("source_ref_required")
    if not observed_at:
        blockers.append("observed_at_required")

    confidence = raw.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            blockers.append("confidence_invalid")
            confidence = None
        else:
            if not 0.0 <= confidence <= 1.0:
                blockers.append("confidence_invalid")

    return {
        "schema_version": "competitor_audience_evidence.v1",
        "competitor_key": competitor_key,
        "competitor_domain": competitor_domain,
        "company_name": company_name,
        "company_domain": company_domain,
        "evidence_type": evidence_type,
        "summary": summary,
        "source_ref": source_ref,
        "observed_at": observed_at,
        "confidence": confidence,
        "review_ready": not blockers,
        "blockers": blockers,
        "relationship_observed": not blockers,
        "buyer_intent": False,
        "commercial_intent": False,
        "prospect_created": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


def build_competitor_audience_graph(
    evidence: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a deduplicated company-level graph from public evidence.

    Companies are research candidates only. Canonical prospect promotion must
    occur through EmpireOS identity-resolution and commercial governance.
    """
    reviewed = [
        review_competitor_audience_evidence(row)
        for row in evidence
    ]

    companies: dict[str, dict[str, Any]] = {}

    for row in reviewed:
        if not row["review_ready"]:
            continue

        identity = (
            f"domain:{row['company_domain']}"
            if row["company_domain"]
            else f"name:{row['company_name'].casefold()}"
        )

        company = companies.setdefault(identity, {
            "company_name": row["company_name"],
            "company_domain": row["company_domain"],
            "research_candidate": True,
            "buyer_intent": False,
            "commercial_intent": False,
            "prospect_created": False,
            "execution_authority": "none",
            "competitors": set(),
            "evidence": [],
        })

        company["competitors"].add(row["competitor_key"])
        company["evidence"].append({
            "competitor_key": row["competitor_key"],
            "competitor_domain": row["competitor_domain"],
            "evidence_type": row["evidence_type"],
            "summary": row["summary"],
            "source_ref": row["source_ref"],
            "observed_at": row["observed_at"],
            "confidence": row["confidence"],
        })

    graph_companies = []
    for identity, company in sorted(companies.items()):
        graph_companies.append({
            **company,
            "identity_key": identity,
            "competitors": sorted(company["competitors"]),
            "evidence_count": len(company["evidence"]),
        })

    rejected = [row for row in reviewed if not row["review_ready"]]

    return {
        "schema_version": "competitor_audience_graph.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "company_count": len(graph_companies),
        "evidence_count": sum(
            company["evidence_count"] for company in graph_companies
        ),
        "rejected_evidence_count": len(rejected),
        "companies": graph_companies,
        "rejected_evidence": rejected,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "prospect_creation_enabled": False,
        "outreach_enabled": False,
    }


def competitor_audience_intelligence_signal(
    company: Mapping[str, Any],
    *,
    entity_id: str | None,
    source_id: str | None = None,
) -> dict[str, Any]:
    """Adapt a resolved audience-graph company to Intelligence Fabric input.

    This is an OBSERVE-only adapter. It does not persist the signal and cannot
    create a prospect, infer buyer intent or authorize outreach.
    """
    resolved_entity_id = str(entity_id or "").strip()
    if not resolved_entity_id:
        raise ValueError("resolved_entity_id_required")

    if not isinstance(company, Mapping):
        raise ValueError("company_mapping_required")

    evidence = company.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("competitor_audience_evidence_required")

    valid_evidence = []
    observed_times = []
    competitor_keys = set()

    for item in evidence:
        if not isinstance(item, Mapping):
            raise ValueError("invalid_competitor_audience_evidence")

        source_ref = str(item.get("source_ref") or "").strip()
        observed_at = str(item.get("observed_at") or "").strip()
        evidence_type = str(item.get("evidence_type") or "").strip()
        competitor_key = str(item.get("competitor_key") or "").strip()

        if not source_ref:
            raise ValueError("source_ref_required")
        if not observed_at:
            raise ValueError("observed_at_required")
        if evidence_type not in COMPETITOR_AUDIENCE_EVIDENCE_TYPES:
            raise ValueError("unsupported_evidence_type")
        if not competitor_key:
            raise ValueError("competitor_key_required")

        observed_times.append(observed_at)
        competitor_keys.add(competitor_key)
        valid_evidence.append({
            "competitor_key": competitor_key,
            "competitor_domain": str(
                item.get("competitor_domain") or ""
            ).strip(),
            "evidence_type": evidence_type,
            "summary": str(item.get("summary") or "").strip(),
            "source_ref": source_ref,
            "observed_at": observed_at,
            "confidence": item.get("confidence"),
        })

    resolved_source_id = str(source_id or "").strip()
    if not resolved_source_id:
        raise ValueError("resolved_source_id_required")

    confidences = [
        float(item["confidence"])
        for item in valid_evidence
        if item.get("confidence") is not None
    ]
    if not confidences:
        raise ValueError("evidence_confidence_required")

    confidence = round(sum(confidences) / len(confidences), 6)

    return {
        "schema_version": "intelligence_signal_candidate.v1",
        "entity_id": resolved_entity_id,
        "signal_type": "competitor_audience_evidence",
        "signal_domain": "competitive_intelligence",
        "observed_at": max(observed_times),
        "source_id": resolved_source_id,
        "strength": min(1.0, len(valid_evidence) / 3.0),
        "confidence": confidence,
        "payload": {
            "company_name": str(company.get("company_name") or "").strip(),
            "company_domain": _normalise_audience_domain(
                company.get("company_domain")
            ),
            "competitor_keys": sorted(competitor_keys),
            "evidence_count": len(valid_evidence),
            "evidence": valid_evidence,
            "research_candidate": True,
            "buyer_intent": False,
            "commercial_intent": False,
            "prospect_created": False,
            "outreach_enabled": False,
        },
        "persistence_performed": False,
        "prospect_created": False,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }
