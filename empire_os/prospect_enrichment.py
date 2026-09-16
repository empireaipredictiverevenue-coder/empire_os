"""Bounded public-web prospect enrichment for the canonical qualification rail.

The module is deliberately read-only:
- never mutates the source prospects table
- never invents contact names or email addresses
- records only fields supported by fetched public evidence
- keeps network work bounded per prospect
"""
from __future__ import annotations

import html
import json
import re
import socket
import urllib.parse
from datetime import datetime, timezone
from typing import Any
from urllib.request import Request, urlopen

from empire_os.search_fabric.fusion import fused_search
from empire_os.search_fabric.site_probe import probe_site
from empire_os.search_fabric.identity_guard import assess_first_party_identity

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/153.0.0.0 Safari/537.36"
)

DIRECTORY_DOMAINS = {
    "bbb.org",
    "yelp.com",
    "yellowpages.com",
    "manta.com",
    "nextdoor.com",
    "mapquest.com",
    "angi.com",
    "homeadvisor.com",
    "thumbtack.com",
    "facebook.com",
    "linkedin.com",
    "instagram.com",
    "youtube.com",
    "houzz.com",
    "expertise.com",
    "chamberofcommerce.com",
    "mapquest.com",
}

SOURCE_WEIGHTS = {
    # Conservative evidence contribution.
    # These are real acquisition/provenance sources only.
    "website": 20,
    "search_fabric": 15,
    "rdap": 10,
}


def _domain(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip()
    if "://" not in value:
        value = "https://" + value
    try:
        return (urllib.parse.urlparse(value).hostname or "").lower().strip(".")
    except Exception:
        return ""


def _is_directory(url: str | None) -> bool:
    domain = _domain(url)
    if not domain:
        return True
    return any(domain == d or domain.endswith("." + d) for d in DIRECTORY_DOMAINS)


def _get(url: str, timeout: int = 8) -> tuple[str, str]:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    with urlopen(req, timeout=timeout) as response:
        body = response.read(500_000).decode("utf-8", errors="replace")
        return body, response.geturl()


def _normalise_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    return url.rstrip("/")


def _discover_website(
    prospect: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    """
    Resolve a prospect to a likely first-party website through the
    canonical Empire Search Fabric.

    Existing non-directory websites are preserved without network search.
    Search results must already have passed Fusion relevance/entity/geo
    verification before becoming candidates here.
    """
    current = _normalise_url(
        str(prospect.get("website") or "")
    )

    if current and not _is_directory(current):
        return current, None

    name = str(
        prospect.get("business_name") or ""
    ).strip()

    metro = str(
        prospect.get("metro") or ""
    ).strip()

    niche = str(
        prospect.get("niche") or ""
    ).strip()

    if not name:
        return "", None

    query = " ".join(
        value
        for value in (name, metro, niche)
        if value
    )

    try:
        response = fused_search(
            query,
            num=10,
        )
    except Exception:
        return "", None

    for row in response.get("organic", []):
        # Direct businesses are preferred for canonical website discovery.
        if row.get("result_type") != "direct_business":
            continue

        candidate = _normalise_url(
            str(row.get("link") or "")
        )

        if not candidate:
            continue

        if _is_directory(candidate):
            continue

        confidence = float(
            row.get("confidence_score") or 0.0
        )

        # Conservative floor. The direct site will still be independently
        # verified by probe_site() before its fields are trusted.
        if confidence < 0.40:
            continue

        return candidate, {
            "source": "search_fabric",
            "query": query,
            "url": candidate,
            "confidence_score": confidence,
            "relevance_score": float(
                row.get("relevance_score") or 0.0
            ),
            "geo_score": float(
                row.get("geo_score") or 0.0
            ),
            "entity_score": float(
                row.get("entity_score") or 0.0
            ),
            "provenance": list(
                row.get("provenance") or []
            ),
        }

    return "", None


def _extract_site(
    url: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Extract evidence through the canonical bounded direct-site probe.

    The probe may inspect a small number of same-site public pages such as
    contact/about/location pages. It does not submit forms or bypass access
    controls.
    """
    probe = probe_site(
        url,
        max_pages=4,
    )

    if not probe.get("ok"):
        raise RuntimeError(
            str(probe.get("error") or "site_probe_failed")
        )

    website = _normalise_url(
        str(
            probe.get("canonical_url")
            or probe.get("final_url")
            or url
        )
    )

    result: dict[str, Any] = {
        "website": website,
    }

    title = str(
        probe.get("title") or ""
    ).strip()

    if title:
        result["site_title"] = title[:300]

    description = str(
        probe.get("description") or ""
    ).strip()

    if description:
        result["meta_description"] = description[:500]

    emails = [
        str(value).strip().lower()
        for value in probe.get("emails", [])
        if str(value).strip()
    ]

    if emails:
        domain = _domain(website)

        # Prefer same-domain first-party email when available, but retain a
        # publicly published site email even when the business uses another
        # mail provider.
        preferred = [
            email
            for email in emails
            if domain and email.endswith("@" + domain)
        ]

        result["email"] = (
            preferred[0]
            if preferred
            else emails[0]
        )

    phones = [
        str(value).strip()
        for value in probe.get("phones", [])
        if str(value).strip()
    ]

    if phones:
        result["phone"] = phones[0]

    addresses = [
        str(value).strip()
        for value in probe.get("addresses", [])
        if str(value).strip()
    ]

    # Address is stored only when explicitly published by the site/schema.
    # Do not infer street/city/state/ZIP components from partial text.
    if addresses:
        result["address"] = addresses[0]

    socials = [
        str(value).strip()
        for value in probe.get("socials", [])
        if str(value).strip()
    ]

    if socials:
        result["social_links"] = json.dumps(
            socials
        )

    return result, probe


def _rdap(url: str) -> dict[str, Any]:
    domain = _domain(url)
    if not domain or "." not in domain:
        return {}

    result: dict[str, Any] = {}
    try:
        addresses = socket.gethostbyname_ex(domain)[2]
        if addresses:
            result["domain_ip"] = addresses[0]
    except OSError:
        pass

    if domain.endswith(".com"):
        try:
            body, _ = _get(
                f"https://rdap.verisign.com/com/v1/domain/{domain}",
                timeout=8,
            )
            data = json.loads(body)
            for event in data.get("events", []):
                if event.get("eventAction") == "registration":
                    result["domain_created"] = str(event.get("eventDate", ""))[:10]
                    break
        except Exception:
            pass

    return result


def enrich_prospect_for_scoring(
    prospect: dict[str, Any],
) -> dict[str, Any]:
    """
    Return evidence-backed fields and a bounded enrichment quality score.

    Search Fabric performs discovery only. Existing Empire intelligence
    remains responsible for downstream qualification/scoring.
    """
    fields: dict[str, Any] = {}
    evidence: list[dict[str, Any]] = []
    source_names: list[str] = []

    site_evidence_score = 0.0

    website, discovery = _discover_website(
        prospect
    )

    if website:
        try:
            site_fields, probe = _extract_site(
                website
            )

            identity = assess_first_party_identity(
                prospect=prospect,
                candidate_url=website,
                probe=probe,
            )

            evidence.append(
                {
                    "source": "identity_guard",
                    **identity,
                }
            )

            if not identity["accepted"]:
                site_fields = {}
                site_evidence_score = 0.0
                website = ""
            else:
                site_evidence_score = float(
                    probe.get("evidence_score") or 0.0
                )

            for key, value in site_fields.items():
                if not value:
                    continue

                # A directory/profile URL is not a canonical business
                # website. A verified first-party site may replace it.
                if key == "website":
                    existing = str(
                        prospect.get("website") or ""
                    )

                    if (
                        not existing
                        or _is_directory(existing)
                    ):
                        fields[key] = value

                    continue

                if not prospect.get(key):
                    fields[key] = value

            if (
                identity["accepted"]
                and site_evidence_score > 0.0
            ):
                source_names.append("website")

            evidence.append(
                {
                    "source": "website",
                    "url": (
                        identity["candidate_url"]
                    ),
                    "accepted": identity["accepted"],
                    "canonical_url": probe.get(
                        "canonical_url"
                    ),
                    "domain": probe.get("domain"),
                    "evidence_score": site_evidence_score,
                    "pages_checked": [
                        page.get("url")
                        for page in probe.get(
                            "pages_checked",
                            [],
                        )
                        if page.get("url")
                    ],
                    "business_names": list(
                        probe.get(
                            "business_names",
                            [],
                        )
                    ),
                    "schema_types": list(
                        probe.get(
                            "schema_types",
                            [],
                        )
                    ),
                    "fields": sorted(
                        site_fields.keys()
                    ),
                }
            )

        except Exception as exc:
            # A discovered URL is only a candidate until the site probe
            # completes and the identity firewall makes a decision.
            #
            # Probe failure therefore fails closed: the candidate cannot
            # earn search provenance or become an RDAP target.
            failed_candidate = website

            evidence.append(
                {
                    "source": "website",
                    "url": failed_candidate,
                    "accepted": False,
                    "error": str(exc)[:200],
                }
            )

            website = ""

    if discovery:
        discovery_evidence = dict(
            discovery
        )

        discovery_evidence["accepted"] = bool(
            website
        )

        evidence.append(
            discovery_evidence
        )

        if website:
            source = str(
                discovery.get("source")
                or "search_fabric"
            )
            source_names.append(source)

    # Use the verified/discovered first-party site for RDAP rather than
    # falling back to a known directory profile.
    # RDAP is supporting evidence for an identity-accepted domain only.
    # A rejected candidate must not recover score via DNS/RDAP metadata.
    rdap_target = (
        fields.get("website")
        or website
    )

    if (
        rdap_target
        and not _is_directory(
            str(rdap_target)
        )
    ):
        rdap_fields = _rdap(
            str(rdap_target)
        )

        if rdap_fields:
            fields.update({
                key: value
                for key, value in rdap_fields.items()
                if value
            })

            source_names.append("rdap")

            evidence.append(
                {
                    "source": "rdap",
                    "domain": _domain(
                        str(rdap_target)
                    ),
                    "fields": sorted(
                        rdap_fields.keys()
                    ),
                }
            )

    unique_sources: list[str] = []

    for source in source_names:
        if source not in unique_sources:
            unique_sources.append(source)

    source_quality = sum(
        SOURCE_WEIGHTS.get(source, 0)
        for source in unique_sources
    )

    useful_fields = {
        "email",
        "phone",
        "website",
        "address",
        "street",
        "city",
        "state",
        "zip",
        "social_links",
        "domain_created",
    }

    field_coverage = len(
        useful_fields.intersection(
            fields.keys()
        )
    )

    # Evidence-backed quality:
    #   provenance    max 45 points
    #   field coverage max 40 points
    #   direct-site evidence max 15 points
    #
    # No synthetic "business_signals" source is created.
    quality = min(
        100.0,
        round(
            min(source_quality, 45)
            + min(field_coverage, 8) * 5
            + min(
                max(site_evidence_score, 0.0),
                1.0,
            ) * 15,
            1,
        ),
    )

    return {
        "fields": fields,
        "enrichment_score": quality,
        "sources": unique_sources,
        "evidence": evidence,
        "enriched_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }
