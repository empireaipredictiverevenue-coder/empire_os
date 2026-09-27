"""First-party business identity validation for Empire Search Fabric."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


_GENERIC_TERMS = {
    "a", "an", "and", "at", "best", "business", "businesses",
    "by", "for", "from", "in", "on", "or", "to", "with",
    "co", "corp", "corporation", "inc", "incorporated",
    "llc", "llp", "lp", "ltd", "limited", "pc", "plc",
    "company", "companies", "contractor", "contractors",
    "general", "home", "local", "near", "of",
    "professional", "professionals",
    "roof", "roofer", "roofers", "roofing",
    "service", "services", "solutions",
    "the", "tx", "texas", "usa", "us",
    "hvac", "solar", "plumbing", "restoration",
}


_SERVICE_IDENTITY_TERMS = {
    "builder",
    "builders",
    "care",
    "commercial",
    "concrete",
    "construction",
    "contractor",
    "contractors",
    "cooling",
    "damage",
    "electrical",
    "electrician",
    "general",
    "handyman",
    "heating",
    "home",
    "homes",
    "hvac",
    "landscaping",
    "mitigation",
    "painter",
    "painters",
    "painting",
    "plumber",
    "plumbing",
    "professional",
    "remodeler",
    "remodeling",
    "residential",
    "restoration",
    "roofer",
    "roofing",
    "service",
    "services",
    "solar",
    "tree",
    "water",
}


_DIRECTORY_PHRASES = {
    "browse local",
    "compare local",
    "directory updated",
    "find licensed",
    "find local",
    "local professionals",
    "professionals near you",
    "contractors near you",
    "service providers",
    "business directory",
}

_AGGREGATION_SCHEMA_TYPES = {
    "CollectionPage",
    "ItemList",
    "SearchAction",
}

_FIRST_PARTY_SCHEMA_TYPES = {
    "Organization",
    "Corporation",
    "LocalBusiness",
    "HomeAndConstructionBusiness",
    "ProfessionalService",
}


_KNOWN_THIRD_PARTY_DOMAINS = {
    "angi.com",
    "bbb.org",
    "bark.com",
    "chamberofcommerce.com",
    "expertise.com",
    "facebook.com",
    "homeadvisor.com",
    "houzz.com",
    "instagram.com",
    "linkedin.com",
    "manta.com",
    "mapquest.com",
    "nextdoor.com",
    "thumbtack.com",
    "yellowpages.com",
    "yelp.com",
    "youtube.com",
}

_PROFILE_PATH_PREFIXES = (
    "/business/",
    "/businesses/",
    "/company/",
    "/directory/",
    "/listing/",
    "/listings/",
    "/pages/",
    "/profile/",
    "/profiles/",
)


def _tokens(value: Any) -> list[str]:
    return re.findall(
        r"[a-z0-9]+",
        str(value or "").lower(),
    )


def _domain(value: str) -> str:
    try:
        host = urlparse(value).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _meaningful_name_terms(
    *,
    business_name: str,
    metro: str = "",
    niche: str = "",
) -> list[str]:
    """
    Return identity-bearing business-name tokens.

    Category/location words are deliberately removed because matching
    "roofing", "services", "Dallas", etc. is not proof of identity.
    """
    name_tokens = _tokens(business_name)

    exclusions = set(_GENERIC_TERMS)
    exclusions.update(_tokens(metro))
    exclusions.update(_tokens(niche))

    return list(dict.fromkeys(
        token
        for token in name_tokens
        if (
            token not in exclusions
            and len(token) >= 2
        )
    ))


def assess_first_party_identity(
    *,
    prospect: dict[str, Any],
    candidate_url: str,
    probe: dict[str, Any],
) -> dict[str, Any]:
    """
    Decide whether a discovered site plausibly belongs to the prospect.

    This is a conservative gate: ambiguity means reject rather than
    promoting directory or marketplace data as first-party evidence.
    """
    business_name = str(
        prospect.get("business_name") or ""
    ).strip()

    metro = str(
        prospect.get("metro") or ""
    ).strip()

    niche = str(
        prospect.get("niche") or ""
    ).strip()

    identity_terms = _meaningful_name_terms(
        business_name=business_name,
        metro=metro,
        niche=niche,
    )

    domain = (
        str(probe.get("domain") or "")
        or _domain(candidate_url)
    ).lower()

    parsed_candidate = urlparse(candidate_url)
    candidate_path = (
        parsed_candidate.path or "/"
    ).lower()

    root_like = candidate_path in {
        "",
        "/",
        "/index.html",
        "/index.htm",
    }

    profile_path = any(
        candidate_path.startswith(prefix)
        for prefix in _PROFILE_PATH_PREFIXES
    )

    known_third_party_domain = any(
        domain == item
        or domain.endswith("." + item)
        for item in _KNOWN_THIRD_PARTY_DOMAINS
    )

    title = str(
        probe.get("title") or ""
    )

    description = str(
        probe.get("description") or ""
    )

    names = [
        str(value)
        for value in probe.get(
            "business_names",
            [],
        )
        if value
    ]

    schema_types = {
        str(value)
        for value in probe.get(
            "schema_types",
            [],
        )
        if value
    }

    searchable = " ".join(
        [domain, title, description, *names]
    ).lower()

    searchable_tokens = set(
        _tokens(searchable)
    )

    domain_tokens = set(
        _tokens(
            domain.split(".")[0]
            if domain
            else ""
        )
    )

    matched_terms = [
        term
        for term in identity_terms
        if term in searchable_tokens
    ]

    domain_matches = [
        term
        for term in identity_terms
        if (
            term in domain_tokens
            or term in (
                domain.split(".")[0]
                if domain
                else ""
            )
        )
    ]

    if identity_terms:
        name_match_score = (
            len(matched_terms)
            / len(identity_terms)
        )
        domain_match_score = (
            len(domain_matches)
            / len(identity_terms)
        )
    else:
        name_match_score = 0.0
        domain_match_score = 0.0

    lower_text = (
        title + " " + description
    ).lower()

    phrase_hits = sorted(
        phrase
        for phrase in _DIRECTORY_PHRASES
        if phrase in lower_text
    )

    aggregation_types = sorted(
        schema_types
        & _AGGREGATION_SCHEMA_TYPES
    )

    first_party_types = sorted(
        schema_types
        & _FIRST_PARTY_SCHEMA_TYPES
    )

    directory_score = 0.0

    directory_score += min(
        0.75,
        len(phrase_hits) * 0.25,
    )

    directory_score += min(
        0.30,
        len(aggregation_types) * 0.10,
    )

    # Lots of independently named entities on one candidate page is a
    # marketplace/listing signal, not business identity proof.
    if len(names) >= 10:
        directory_score += 0.20
    elif len(names) >= 5:
        directory_score += 0.10

    directory_score = min(
        1.0,
        directory_score,
    )

    identity_score = (
        name_match_score * 0.65
        + domain_match_score * 0.35
    )

    # Existing first-party URL supplied with the prospect is supporting
    # evidence, but never enough to override strong directory signals.
    existing = str(
        prospect.get("website") or ""
    ).strip()

    existing_domain = _domain(
        existing
        if "://" in existing
        else (
            "https://" + existing
            if existing
            else ""
        )
    )

    existing_domain_match = bool(
        existing_domain
        and domain
        and existing_domain == domain
    )

    # A prospect-supplied site is meaningful supporting evidence,
    # but only when the domain also carries at least one distinctive
    # business-name term and the candidate does not look aggregated.
    existing_first_party_support = bool(
        existing_domain_match
        and domain_matches
        and directory_score < 0.50
    )

    if existing_first_party_support:
        identity_score = max(
            identity_score,
            0.65,
        )

    discovered_candidate = not bool(existing)

    # Service/category words such as "concrete", "roofing", or
    # "contractor" describe what a business does; they do not establish
    # which business it is.
    distinctive_identity_terms = [
        term
        for term in identity_terms
        if term not in _SERVICE_IDENTITY_TERMS
    ]

    matched_distinctive_terms = [
        term
        for term in matched_terms
        if term in distinctive_identity_terms
    ]

    distinctive_domain_matches = [
        term
        for term in domain_matches
        if term in distinctive_identity_terms
    ]

    distinctive_match_ratio = (
        len(matched_distinctive_terms)
        / len(distinctive_identity_terms)
        if distinctive_identity_terms
        else 0.0
    )

    discovered_generic_identity = bool(
        discovered_candidate
        and not distinctive_identity_terms
    )

    # A discovered URL needs evidence that the DOMAIN belongs to the
    # business, not merely that a page contains the same service words.
    #
    # Primary path:
    #   distinctive business identity appears in the domain.
    #
    # Conservative fallback:
    #   root/home page, strong DISTINCTIVE name match, low aggregation,
    #   and only a small set of named entities.
    strong_root_identity = bool(
        root_like
        and distinctive_identity_terms
        and distinctive_match_ratio >= 0.75
        and directory_score < 0.25
        and len(names) <= 4
    )

    discovery_domain_supported = bool(
        distinctive_domain_matches
        or strong_root_identity
    )

    generic_identity = not bool(
        identity_terms
    )

    reasons: list[str] = []

    if generic_identity:
        reasons.append(
            "prospect_name_has_no_distinctive_identity_terms"
        )

    if directory_score >= 0.50:
        reasons.append(
            "candidate_has_directory_or_aggregation_signals"
        )

    if identity_score < 0.45:
        reasons.append(
            "candidate_identity_does_not_match_prospect"
        )

    if discovered_generic_identity:
        reasons.append(
            "prospect_identity_too_generic_for_discovery"
        )

    if known_third_party_domain:
        reasons.append(
            "candidate_is_known_third_party_platform"
        )

    if (
        discovered_candidate
        and profile_path
        and not domain_matches
    ):
        reasons.append(
            "discovered_candidate_is_profile_or_listing_page"
        )

    if (
        discovered_candidate
        and not discovery_domain_supported
    ):
        reasons.append(
            "discovered_domain_not_supported_by_business_identity"
        )

    accepted = (
        not generic_identity
        and directory_score < 0.50
        and identity_score >= 0.45
        and not known_third_party_domain
        and not discovered_generic_identity
        and (
            not discovered_candidate
            or discovery_domain_supported
        )
        and not (
            discovered_candidate
            and profile_path
            and not domain_matches
        )
    )

    return {
        "accepted": accepted,
        "business_name": business_name,
        "candidate_url": candidate_url,
        "domain": domain,
        "identity_terms": identity_terms,
        "matched_terms": matched_terms,
        "domain_matches": domain_matches,
        "identity_score": round(
            identity_score,
            4,
        ),
        "directory_score": round(
            directory_score,
            4,
        ),
        "directory_phrase_hits": phrase_hits,
        "aggregation_schema_types": aggregation_types,
        "first_party_schema_types": first_party_types,
        "generic_identity": generic_identity,
        "existing_domain_match": existing_domain_match,
        "existing_first_party_support": existing_first_party_support,
        "discovered_candidate": discovered_candidate,
        "candidate_path": candidate_path,
        "profile_path": profile_path,
        "root_like": root_like,
        "known_third_party_domain": known_third_party_domain,
        "distinctive_identity_terms": distinctive_identity_terms,
        "matched_distinctive_terms": matched_distinctive_terms,
        "distinctive_domain_matches": distinctive_domain_matches,
        "distinctive_match_ratio": round(
            distinctive_match_ratio,
            4,
        ),
        "discovered_generic_identity": discovered_generic_identity,
        "strong_root_identity": strong_root_identity,
        "discovery_domain_supported": discovery_domain_supported,
        "reasons": reasons,
    }
