"""Empire Search Fabric geo/entity verification."""

from __future__ import annotations

import re
from urllib.parse import urlparse


DIRECTORY_DOMAINS = {
    "angi.com",
    "bbb.org",
    "bark.com",
    "chamberofcommerce.com",
    "expertise.com",
    "homeadvisor.com",
    "houzz.com",
    "manta.com",
    "nextdoor.com",
    "mapquest.com",
    "thumbtack.com",
    "yellowpages.com",
    "yelp.com",
    "facebook.com",
    "linkedin.com",
    "instagram.com",
    "youtube.com",
}

ARTICLE_HINTS = {
    "best",
    "top",
    "ranking",
    "rankings",
    "companies",
    "list",
    "guide",
    "reviews",
    "vetted",
}

US_STATES = {
    "alabama": "al", "alaska": "ak", "arizona": "az",
    "arkansas": "ar", "california": "ca", "colorado": "co",
    "connecticut": "ct", "delaware": "de", "florida": "fl",
    "georgia": "ga", "hawaii": "hi", "idaho": "id",
    "illinois": "il", "indiana": "in", "iowa": "ia",
    "kansas": "ks", "kentucky": "ky", "louisiana": "la",
    "maine": "me", "maryland": "md", "massachusetts": "ma",
    "michigan": "mi", "minnesota": "mn", "mississippi": "ms",
    "missouri": "mo", "montana": "mt", "nebraska": "ne",
    "nevada": "nv", "newhampshire": "nh", "newjersey": "nj",
    "newmexico": "nm", "newyork": "ny",
    "northcarolina": "nc", "northdakota": "nd",
    "ohio": "oh", "oklahoma": "ok", "oregon": "or",
    "pennsylvania": "pa", "rhodeisland": "ri",
    "southcarolina": "sc", "southdakota": "sd",
    "tennessee": "tn", "texas": "tx", "utah": "ut",
    "vermont": "vt", "virginia": "va", "washington": "wa",
    "westvirginia": "wv", "wisconsin": "wi", "wyoming": "wy",
}

_NON_GEO = {
    "contractor", "contractors", "company", "companies",
    "service", "services", "roofing", "roof", "roofer",
    "roofers", "hvac", "solar", "plumbing", "restoration",
    "insurance", "legal", "near", "best", "top",
}


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (value or "").lower())


def _domain(value: str) -> str:
    try:
        text = str(value or "").strip()
        if not text:
            return ""
        if "://" not in text:
            text = "https://" + text
        host = urlparse(text).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def is_directory_url(url: str | None) -> bool:
    """True when a URL is a known directory/social platform, not first-party."""
    domain = _domain(str(url or ""))
    if not domain:
        return False
    return any(
        domain == item or domain.endswith("." + item)
        for item in DIRECTORY_DOMAINS
    )


def infer_geo_terms(query: str) -> list[str]:
    """
    Infer simple US city/state terms from the query.

    This is deliberately conservative. Explicit structured location
    context can replace this heuristic later.
    """
    tokens = _tokens(query)
    compact = "".join(tokens)

    terms: list[str] = []

    for state, abbreviation in US_STATES.items():
        state_parts = re.findall(r"[a-z]+", state)

        if state in compact:
            terms.extend(state_parts)
            terms.append(abbreviation)

            # City is usually immediately before the state expression.
            first_state_token = state_parts[0]
            if first_state_token in tokens:
                index = tokens.index(first_state_token)
                if index > 0:
                    city = tokens[index - 1]
                    if city not in _NON_GEO:
                        terms.append(city)

        elif abbreviation in tokens:
            terms.append(abbreviation)
            index = tokens.index(abbreviation)

            if index > 0:
                city = tokens[index - 1]
                if city not in _NON_GEO:
                    terms.append(city)

    # Stable dedupe.
    return list(dict.fromkeys(terms))


def classify_result(
    *,
    title: str,
    url: str,
) -> str:
    """Classify discovery results before lead promotion."""
    domain = _domain(url)
    title_tokens = set(_tokens(title))

    if is_directory_url(url):
        return "directory"

    if title_tokens & ARTICLE_HINTS:
        return "article"

    # Root/home pages on a non-directory commercial domain are a strong
    # direct-business signal. Subpages can still be direct businesses.
    if domain:
        return "direct_business"

    return "unknown"


def score_geo(
    *,
    query: str,
    title: str,
    snippet: str,
    url: str,
) -> float:
    geo_terms = infer_geo_terms(query)

    # No explicit geography -> neutral, not failure.
    if not geo_terms:
        return 0.5

    title_tokens = set(_tokens(title))
    snippet_tokens = set(_tokens(snippet))
    url_tokens = set(_tokens(url))

    matched = 0.0

    for term in geo_terms:
        if term in title_tokens:
            matched += 1.0
        elif term in url_tokens:
            matched += 0.8
        elif term in snippet_tokens:
            matched += 0.6

    return round(
        min(1.0, matched / max(1, len(geo_terms))),
        4,
    )


def score_entity(result_type: str) -> float:
    return {
        "direct_business": 1.0,
        "unknown": 0.5,
        "directory": 0.25,
        "article": 0.15,
    }.get(result_type, 0.25)


def verify_result(
    *,
    query: str,
    title: str,
    snippet: str,
    url: str,
) -> dict:
    result_type = classify_result(
        title=title,
        url=url,
    )

    return {
        "result_type": result_type,
        "geo_score": score_geo(
            query=query,
            title=title,
            snippet=snippet,
            url=url,
        ),
        "entity_score": score_entity(result_type),
        "geo_terms": infer_geo_terms(query),
        "domain": _domain(url),
    }
