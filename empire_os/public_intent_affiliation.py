"""Evidence-only public affiliation notes for social-intent research.

The attached website and public profile must be independently inspected.
Presence of a note is not a live lookup, a verified contact, or demand approval.
"""
from __future__ import annotations
from pathlib import Path
from urllib.parse import urlsplit
import json
import re
from typing import Any, Mapping

SCHEMA = "empire.public_intent_affiliation_evidence.v1"
MAX_BYTES = 100_000
HOST = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)+$")


def host(url: Any) -> str:
    if not isinstance(url, str) or len(url) > 2048:
        return ""
    try:
        u = urlsplit(url)
        if u.scheme != "https" or u.username or u.password or u.port:
            return ""
        return (u.hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def validate_evidence(doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    if doc.get("schema_version") != SCHEMA or doc.get("origin") != "manual_public_evidence_review":
        raise ValueError("unsupported_affiliation_evidence")
    records = doc.get("records")
    if not isinstance(records, list) or len(records) > 25:
        raise ValueError("invalid_affiliation_count")
    results = []
    seen = set()
    for r in records:
        if not isinstance(r, Mapping):
            raise ValueError("invalid_affiliation_record")
        source = r.get("source_post_url")
        official = r.get("official_company_evidence_url")
        profile = r.get("social_profile_url")
        company_domain = r.get("company_domain")
        person = r.get("person_name")
        company = r.get("company_name")
        if (not isinstance(company_domain, str)
                or not HOST.fullmatch(company_domain)
                or host(official) != company_domain):
            raise ValueError("first_party_domain_mismatch")
        # LinkedIn publishes legitimate country subdomains (in.linkedin.com,
        # es.linkedin.com). Match a registrable platform suffix exactly;
        # never allow linkedin.com.attacker.example lookalikes.
        allowed = ("linkedin.com", "reddit.com")
        def trusted_social_url(value: Any) -> bool:
            domain = host(value)
            return any(domain == base or domain.endswith("." + base)
                       for base in allowed)
        if not trusted_social_url(source):
            raise ValueError("unsupported_social_post")
        if not trusted_social_url(profile):
            raise ValueError("unsupported_social_profile")
        if (not isinstance(person, str) or not 3 <= len(person) <= 100
                or not isinstance(company, str) or not 3 <= len(company) <= 150):
            raise ValueError("invalid_person_company_names")
        if source in seen:
            raise ValueError("conflicting_affiliation_evidence")
        seen.add(source)
        note = r.get("review_note")
        if not isinstance(note, str) or not 10 <= len(note) <= 320:
            raise ValueError("invalid_affiliation_note")
        results.append({
            "source_post_url": source,
            "company_name": company,
            "company_domain": company_domain,
            "person_name": person,
            "social_profile_url": profile,
            "official_company_evidence_url": official,
            "review_note": note,
            "first_party_evidence_inspected": True,
            "affiliation_evidence_type": "PUBLIC_COMPANY_AND_PROFILE_REFERENCES",
            "poster_authority_to_buy_verified": False,
            "current_buying_need_verified": False,
            "suppression_check_complete": False,
            "outbound_authorized": False,
        })
    return results


def load_evidence(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.is_symlink() or path.stat().st_size > MAX_BYTES or path.stat().st_mode & 0o077:
        raise ValueError("unsafe_affiliation_evidence_file")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, Mapping):
        raise ValueError("invalid_affiliation_evidence_json")
    return validate_evidence(doc)
