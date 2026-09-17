"""Empire Search Fabric direct-site business evidence probe."""

from __future__ import annotations

import re
import time
from typing import Any, Dict, Iterable, List
from urllib.parse import urljoin, urlparse

import requests

from .decoder import decode_document


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

INTERESTING_LINK_TERMS = (
    "contact",
    "about",
    "location",
    "locations",
    "team",
    "company",
    "service-area",
    "servicearea",
)

MAX_RESPONSE_BYTES = 2_000_000


_PLACEHOLDER_EMAILS = {
    "your@email.com",
    "name@example.com",
    "email@example.com",
    "test@test.com",
    "user@example.com",
}

_PLACEHOLDER_EMAIL_DOMAINS = {
    "example.com",
    "example.net",
    "example.org",
}


def _valid_email(value: str) -> bool:
    """Reject obvious template/test email addresses."""
    value = (value or "").strip().lower()

    if not value:
        return False

    if value in _PLACEHOLDER_EMAILS:
        return False

    if "@" not in value:
        return False

    local, domain = value.rsplit("@", 1)

    if not local or "." not in domain:
        return False

    if domain in _PLACEHOLDER_EMAIL_DOMAINS:
        return False

    suffix = (
        domain.rsplit(".", 1)[-1].lower()
        if "." in domain
        else ""
    )

    if suffix in {
        "css",
        "gif",
        "ico",
        "jpeg",
        "jpg",
        "js",
        "png",
        "svg",
        "ttf",
        "webp",
        "woff",
        "woff2",
    }:
        return False

    return True


def _valid_phone(value: str) -> bool:
    """Reject obvious fictional/template NANP phone numbers."""
    digits = re.sub(r"\D", "", value or "")

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    if len(digits) != 10:
        return False

    # 555 is not a valid NANP area code and commonly appears in templates.
    if digits[:3] == "555":
        return False

    if digits in {
        "0000000000",
        "1111111111",
        "1234567890",
        "0123456789",
    }:
        return False

    return True


def _host(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _same_site(url: str, origin: str) -> bool:
    return bool(_host(url)) and _host(url) == _host(origin)


def _walk_json(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        yield value

        for child in value.values():
            yield from _walk_json(child)

    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _format_address(value: Any) -> str:
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()

    if not isinstance(value, dict):
        return ""

    fields = (
        "streetAddress",
        "addressLocality",
        "addressRegion",
        "postalCode",
        "addressCountry",
    )

    parts = [
        str(value.get(field, "")).strip()
        for field in fields
        if value.get(field)
    ]

    return ", ".join(parts)


def _schema_evidence(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    names: List[str] = []
    phones: List[str] = []
    emails: List[str] = []
    addresses: List[str] = []
    types: List[str] = []
    people: List[Dict[str, str]] = []

    for root in records:
        for item in _walk_json(root):
            schema_type = item.get("@type")
            item_types = (
                [str(x) for x in schema_type]
                if isinstance(schema_type, list)
                else ([str(schema_type)] if schema_type else [])
            )
            types.extend(item_types)
            is_person = any(value.lower() == "person" for value in item_types)

            name = item.get("name")
            if isinstance(name, str) and name.strip():
                if is_person:
                    people.append({
                        "name": name.strip(),
                        "title": str(item.get("jobTitle") or "").strip(),
                        "email": str(item.get("email") or "").removeprefix("mailto:").strip(),
                        "url": str(item.get("url") or "").strip(),
                    })
                else:
                    names.append(name.strip())

            phone = item.get("telephone")
            if isinstance(phone, str) and phone.strip():
                phones.append(phone.strip())

            email = item.get("email")
            if isinstance(email, str) and email.strip():
                emails.append(
                    email.removeprefix("mailto:").strip()
                )

            address = _format_address(item.get("address"))
            if address:
                addresses.append(address)

    return {
        "business_names": list(dict.fromkeys(names)),
        "phones": list(dict.fromkeys(phones)),
        "emails": list(dict.fromkeys(emails)),
        "addresses": list(dict.fromkeys(addresses)),
        "schema_types": list(dict.fromkeys(types)),
        "people": list({
            (p["name"], p["title"], p["email"], p["url"]): p for p in people
        }.values()),
    }


def _internal_candidates(html: str, origin: str) -> List[str]:
    candidates: List[str] = []

    for match in re.finditer(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        html,
        re.I | re.S,
    ):
        href, label = match.groups()

        text = (
            href
            + " "
            + re.sub(r"<[^>]+>", " ", label)
        ).lower()

        if not any(term in text for term in INTERESTING_LINK_TERMS):
            continue

        url = urljoin(origin, href)

        if (
            url.startswith(("http://", "https://"))
            and _same_site(url, origin)
        ):
            candidates.append(url.split("#", 1)[0])

    return list(dict.fromkeys(candidates))


def _fetch(session: requests.Session, url: str):
    try:
        response = session.get(
            url,
            timeout=15,
            allow_redirects=True,
        )
    except requests.RequestException:
        return None

    if response.status_code != 200:
        return None

    content_type = response.headers.get("Content-Type", "")

    if not any(
        kind in content_type.lower()
        for kind in ("html", "json", "xml", "text")
    ):
        return None

    data = response.content[:MAX_RESPONSE_BYTES]

    return decode_document(
        url=str(response.url),
        data=data,
        content_type=content_type,
        content_encoding="",
        charset=response.encoding,
    )


def probe_site(
    url: str,
    *,
    max_pages: int = 4,
) -> dict:
    """
    Inspect a public business site and return normalized evidence.

    No authentication bypass, paywall bypass, form submission,
    Hub writes or database writes are performed.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    })

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    homepage = _fetch(session, url)

    if homepage is None:
        return {
            "ok": False,
            "requested_url": url,
            "error": "homepage_fetch_failed",
        }

    origin = homepage.canonical_url or homepage.url
    origin_host = _host(origin)

    queue = [homepage.url]

    if homepage.format == "html":
        queue.extend(
            _internal_candidates(
                homepage.text,
                homepage.url,
            )
        )

    queue = list(dict.fromkeys(queue))[:max_pages]

    names: List[str] = []
    emails: List[str] = []
    phones: List[str] = []
    addresses: List[str] = []
    socials: List[str] = []
    schema_types: List[str] = []
    people: List[Dict[str, str]] = []
    pages: List[dict] = []

    best_title = homepage.title
    best_description = homepage.description

    for index, page_url in enumerate(queue):
        if index == 0:
            document = homepage
        else:
            if not _same_site(page_url, origin):
                continue

            time.sleep(0.4)
            document = _fetch(session, page_url)

            if document is None:
                continue

        schema = _schema_evidence(
            document.structured_data
        )

        names.extend(schema["business_names"])
        emails.extend(document.emails)
        emails.extend(schema["emails"])
        phones.extend(document.phones)
        phones.extend(schema["phones"])
        addresses.extend(schema["addresses"])
        socials.extend(document.socials)
        schema_types.extend(schema["schema_types"])
        people.extend(schema["people"])

        pages.append({
            "url": document.url,
            "canonical_url": document.canonical_url,
            "title": document.title,
            "format": document.format,
            "emails_found": len(document.emails),
            "phones_found": len(document.phones),
            "schema_records": len(
                document.structured_data
            ),
        })

    def unique(values: List[str]) -> List[str]:
        return [
            value
            for value in dict.fromkeys(
                v.strip()
                for v in values
                if isinstance(v, str) and v.strip()
            )
        ]

    names = unique(names)

    emails = [
        value
        for value in unique(emails)
        if _valid_email(value)
    ]

    phones = [
        value
        for value in unique(phones)
        if _valid_phone(value)
    ]

    addresses = unique(addresses)
    socials = unique(socials)
    schema_types = unique(schema_types)
    people = list({
        (p.get("name", ""), p.get("title", ""), p.get("email", ""), p.get("url", "")): p
        for p in people
        if p.get("name")
    }.values())

    evidence_score = 0.0

    if names or best_title:
        evidence_score += 0.20

    if phones:
        evidence_score += 0.20

    if emails:
        evidence_score += 0.20

    if addresses:
        evidence_score += 0.15

    if schema_types:
        evidence_score += 0.15

    if socials:
        evidence_score += 0.10

    return {
        "ok": True,
        "requested_url": url,
        "final_url": homepage.url,
        "canonical_url": homepage.canonical_url,
        "domain": origin_host,
        "title": best_title,
        "description": best_description,
        "business_names": names,
        "emails": emails,
        "phones": phones,
        "addresses": addresses,
        "socials": socials,
        "schema_types": schema_types,
        "people": people,
        "pages_checked": pages,
        "evidence_score": round(evidence_score, 4),
    }
