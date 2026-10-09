"""Fail-closed identity contract for purported first-party person/email evidence.

This only validates source ownership alignment. It never proves a person's
purchasing intent or grants contact, review, outbound or payment authority.
"""
from __future__ import annotations

from urllib.parse import urlsplit


def _hostname(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    try:
        parsed = urlsplit(raw)
        if parsed.scheme not in {"https", "http"}:
            return ""
        if parsed.username or parsed.password or parsed.port not in {None, 80, 443}:
            return ""
        host = (parsed.hostname or "").rstrip(".").lower()
        if not host or any(char.isspace() for char in host):
            return ""
        return host.removeprefix("www.")
    except ValueError:
        return ""


def first_party_contact_decision(
    *, website: object, source_url: object,
    email: object, direct_publication: object,
) -> tuple[bool, str]:
    """Check an exact company/site/email domain triplet; never guess aliases.

    Deliberately conservative: public-suffix or parent/subdomain similarity
    is not proof of common ownership. Legitimate domain aliases need a
    separate verified corporate-identity review.
    """
    expected = _hostname(website)
    if not expected:
        return False, "company_domain_unavailable"
    raw_source = str(source_url or "").strip()
    if not raw_source.lower().startswith(("https://", "http://")):
        return False, "source_url_not_http"
    source = _hostname(raw_source)
    if not source:
        return False, "source_url_invalid"
    if source != expected:
        return False, "source_company_domain_mismatch"
    raw_email = str(email or "").strip().lower()
    if raw_email.count("@") != 1:
        return False, "email_invalid"
    local, domain = raw_email.split("@", 1)
    if not local or not domain or domain.startswith(".") or any(c.isspace() for c in raw_email):
        return False, "email_invalid"
    if domain.rstrip(".") != expected:
        return False, "email_company_domain_mismatch"
    if direct_publication is not True:
        return False, "direct_publication_unverified"
    return True, "first_party_domain_alignment_confirmed"
