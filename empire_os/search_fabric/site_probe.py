"""Empire Search Fabric direct-site business evidence probe."""

from __future__ import annotations

import html as html_lib
import ipaddress
import re
import socket
import time
from typing import Any, Dict, Iterable, List
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request as UrlRequest, urlopen

import requests

from empire_os.phone_quality import is_commercially_usable_phone

from .decoder import clean_text, decode_document


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
    "leadership",
    "staff",
    "people",
    "management",
    "founder",
    "owner",
    "company",
    "service-area",
    "servicearea",
)

COMMON_PEOPLE_PATHS = (
    "/about-us/meet-the-team/",
    "/meet-the-team/",
    "/our-team/",
    "/team/",
    "/meet-our-team/",
    "/meet-the-owner/",
    "/about/our-team/",
    "/about/team/",
    "/leadership/",
    "/about/leadership/",
    "/company/leadership/",
    "/staff/",
    "/people/",
    "/management/",
    "/company/team/",
    "/who-we-are/",
    "/our-story/",
    "/about-us/",
    "/about/",
    "/contact-us/",
    "/contact/",
)

MAX_RESPONSE_BYTES = 2_000_000


def _public_url_allowed(url: str) -> bool:
    try:
        parsed = urlparse(str(url or "").strip())
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    try:
        port = parsed.port
    except ValueError:
        return False
    if port not in {None, 80, 443}:
        return False

    host = parsed.hostname.strip().lower().rstrip(".")
    if (
        host == "localhost"
        or host.endswith(".localhost")
        or host.endswith(".local")
        or host.endswith(".internal")
    ):
        return False

    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        return literal.is_global

    try:
        answers = socket.getaddrinfo(
            host,
            port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except OSError:
        return False

    addresses = []
    for answer in answers:
        try:
            addresses.append(ipaddress.ip_address(answer[4][0]))
        except (IndexError, TypeError, ValueError):
            continue
    return bool(addresses) and all(address.is_global for address in addresses)


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

_PEOPLE_TITLE_RE = re.compile(
    r"\b(?:co-founder|founder|owner|"
    r"chief\s+(?:[a-z][a-z&/-]*\s+){0,4}officer|ceo|coo|cto|cmo|cio|cdo|cro|cco|"
    r"managing director|president|principal|"
    r"(?:executive\s+|senior\s+|regional\s+)?vice president|vp(?:\s+of)?\s+[a-z&/-]+|"
    r"sales director|head of sales|head of growth|growth director|"
    r"commercial director|business development director|general manager)\b",
    re.I,
)

_OWNERSHIP_PHRASE_RE = re.compile(
    r"\b(?i:founded|co-founded|owned(?:\s+and\s+operated)?|started|led|run)"
    r"(?i:\s+by\s+)"
    r"(?P<name>[A-Z][A-Za-z.'’\-]+(?:\s+[A-Z][A-Za-z.'’\-]+){1,3})\b"
)

_ROLE_NAME_PHRASE_RE = re.compile(
    r"\b(?i:(?:our\s+)?)(?P<title>(?i:founder|co-founder|owner|president|"
    r"principal|chief executive officer|ceo|managing director|general manager))"
    r"(?i:\s*(?:is|:|,|-|–|—)?\s*)"
    r"(?P<name>[A-Z][A-Za-z.'’\-]+(?:\s+[A-Z][A-Za-z.'’\-]+){1,3})\b"
)

_NON_PERSON_WORDS = {
    "about", "contact", "company", "leadership", "management", "meet",
    "our", "staff", "team", "the", "people", "services", "service",
    "founder", "owner", "president", "principal", "director", "manager",
    "chief", "executive", "officer", "ceo", "cro", "cco",
}


def _looks_like_visible_person_name(value: str) -> bool:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" ,|:/–—-")
    words = text.split()
    if not 2 <= len(words) <= 4:
        return False
    lowered = {word.lower().strip(".'’\"-") for word in words}
    if lowered & _NON_PERSON_WORDS:
        return False
    for word in words:
        clean = word.strip(".'’\"-")
        if not clean:
            return False
        if len(clean) == 1:
            if not clean.isupper():
                return False
            continue
        if not clean[0].isupper():
            return False
        letters = clean.replace("'", "").replace("’", "").replace("-", "")
        if not letters.isalpha():
            return False
    return True


def _matching_person_email(name: str, emails: Iterable[str]) -> str:
    parts = [
        re.sub(r"[^a-z]", "", token.lower())
        for token in str(name or "").replace("-", " ").split()
    ]
    parts = [part for part in parts if part]
    if len(parts) < 2:
        return ""
    first, last = parts[0], parts[-1]
    expected = {
        first,
        f"{first}.{last}",
        f"{first}{last}",
        f"{first[0]}{last}",
        f"{first[0]}.{last}",
    }
    for email in emails or []:
        value = str(email or "").strip().lower()
        if "@" not in value:
            continue
        if value.split("@", 1)[0] in expected:
            return value
    return ""


def _visible_people_from_html(
    page: str,
    *,
    page_url: str,
    page_title: str = "",
    emails: Iterable[str] = (),
) -> List[Dict[str, str]]:
    """Recover named decision-makers from first-party visible page text."""
    raw = re.sub(
        r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>",
        " ",
        page or "",
        flags=re.I | re.S,
    )
    raw = re.sub(
        r"<\s*(?:br|/p|/div|/li|/h[1-6]|/section|/article|/tr|/td)\b[^>]*>",
        "\n",
        raw,
        flags=re.I,
    )
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html_lib.unescape(raw)
    blocks = [
        re.sub(r"\s+", " ", line).strip()
        for line in raw.splitlines()
        if re.sub(r"\s+", " ", line).strip()
    ]

    people: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(name: str, title: str) -> None:
        clean_name = re.sub(r"\s+", " ", name).strip(" ,|:/–—-")
        clean_title = re.sub(r"\s+", " ", title).strip(" ,|:/–—-")
        if not _looks_like_visible_person_name(clean_name) or not clean_title:
            return
        key = (clean_name.casefold(), clean_title.casefold())
        if key in seen:
            return
        seen.add(key)
        people.append({
            "name": clean_name,
            "title": clean_title,
            "email": _matching_person_email(clean_name, emails),
            "url": page_url,
        })

    for block in blocks:
        if len(block) > 360:
            continue
        for phrase in _OWNERSHIP_PHRASE_RE.finditer(block):
            add(phrase.group("name"), "owner")
        for phrase in _ROLE_NAME_PHRASE_RE.finditer(block):
            add(phrase.group("name"), phrase.group("title"))

    for index, block in enumerate(blocks):
        if len(block) > 220:
            continue
        match = _PEOPLE_TITLE_RE.search(block)
        if match:
            matched_title = match.group(0)
            remainder = block[match.end():].strip()
            if (
                match.start() == 0
                and len(block) <= 120
                and remainder
                and remainder[0] in ",&/–—-"
                and not any(mark in block for mark in ".!?")
            ):
                matched_title = block.strip(" ,|:/–—-")

            before = block[:match.start()].strip(" ,|:/–—-")
            words = before.split()
            for width in (2, 3, 4):
                if len(words) >= width:
                    candidate = " ".join(words[-width:])
                    if _looks_like_visible_person_name(candidate):
                        add(candidate, matched_title)
                        break

            after = block[match.end():].strip(" ,|:/–—-")
            words = after.split()
            for width in (2, 3, 4):
                if len(words) >= width:
                    candidate = " ".join(words[:width])
                    if _looks_like_visible_person_name(candidate):
                        add(candidate, matched_title)
                        break

            for neighbor_index in (index - 1, index - 2, index + 1, index + 2):
                if not 0 <= neighbor_index < len(blocks):
                    continue
                neighbor = blocks[neighbor_index]
                if len(neighbor) > 100:
                    continue
                if _looks_like_visible_person_name(neighbor):
                    add(neighbor, matched_title)
                    break
        elif _looks_like_visible_person_name(block):
            for neighbor_index in (index + 1, index + 2):
                if neighbor_index >= len(blocks):
                    continue
                title_match = _PEOPLE_TITLE_RE.search(blocks[neighbor_index])
                if title_match:
                    add(block, title_match.group(0))
                    break

    title_name = re.sub(r"\s+[|–—-].*$", "", str(page_title or "")).strip()
    if _looks_like_visible_person_name(title_name):
        visible = " ".join(blocks)[:6000]
        match = _PEOPLE_TITLE_RE.search(visible)
        if match:
            add(title_name, match.group(0))

    return people


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
    """Reject obvious fictional/template phone numbers."""
    return is_commercially_usable_phone(value)


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


def _internal_candidates(
    html: str,
    origin: str,
    *,
    priority: str = "default",
) -> List[str]:
    candidates: List[tuple[int, str]] = []

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
            rank = 10
            if priority == "people":
                if any(
                    term in text
                    for term in (
                        "meet-the-team",
                        "meet the team",
                        "leadership",
                        "our-team",
                        "our team",
                        "team",
                        "staff",
                        "people",
                        "management",
                    )
                ):
                    rank = 0
                elif "about" in text:
                    rank = 1
                elif "contact" in text:
                    rank = 2
                elif "location" in text:
                    rank = 4
                else:
                    rank = 3
            candidates.append(
                (rank, url.split("#", 1)[0])
            )

    ordered = sorted(
        candidates,
        key=lambda item: item[0],
    )
    return list(
        dict.fromkeys(url for _, url in ordered)
    )


def _common_candidates(origin: str, *, priority: str = "default") -> List[str]:
    if priority != "people":
        return []
    return [urljoin(origin, path) for path in COMMON_PEOPLE_PATHS]


_SITEMAP_PEOPLE_TERMS = (
    "team",
    "leadership",
    "staff",
    "people",
    "management",
    "founder",
    "owner",
    "about",
    "who-we-are",
    "our-story",
    "company",
)


def _sitemap_people_candidates(
    session: requests.Session,
    origin: str,
    *,
    timeout: float,
    deadline: float,
    max_urls: int = 12,
    public_only: bool = False,
) -> List[str]:
    """Discover hidden first-party people pages from bounded sitemap reads."""
    root = f"{urlparse(origin).scheme}://{urlparse(origin).netloc}"
    sitemap_urls = [
        urljoin(root + "/", "sitemap.xml"),
        urljoin(root + "/", "sitemap_index.xml"),
    ]
    discovered: List[str] = []
    nested: List[str] = []

    def locs(text: str) -> List[str]:
        return [
            html_lib.unescape(value.strip())
            for value in re.findall(
                r"<loc>\s*(.*?)\s*</loc>",
                text or "",
                flags=re.I | re.S,
            )
            if value.strip()
        ]

    for sitemap_url in sitemap_urls:
        if time.monotonic() >= deadline:
            break
        doc = _fetch(
            session,
            sitemap_url,
            timeout=min(timeout, 4.0),
            public_only=public_only,
        )
        if doc is None:
            continue
        for value in locs(doc.text):
            if not _same_site(value, origin):
                continue
            lower = value.lower()
            if lower.endswith(".xml"):
                if any(
                    token in lower
                    for token in ("page", "team", "people", "staff", "author")
                ):
                    nested.append(value)
                continue
            if any(term in lower for term in _SITEMAP_PEOPLE_TERMS):
                discovered.append(value.split("#", 1)[0])
        if discovered:
            break

    for nested_url in list(dict.fromkeys(nested))[:2]:
        if time.monotonic() >= deadline:
            break
        doc = _fetch(
            session,
            nested_url,
            timeout=min(timeout, 4.0),
            public_only=public_only,
        )
        if doc is None:
            continue
        for value in locs(doc.text):
            if (
                _same_site(value, origin)
                and any(
                    term in value.lower()
                    for term in _SITEMAP_PEOPLE_TERMS
                )
            ):
                discovered.append(value.split("#", 1)[0])
                if len(discovered) >= max_urls:
                    break

    return list(dict.fromkeys(discovered))[:max_urls]


def _fetch_with_urllib(url: str, *, timeout: float):
    request = UrlRequest(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urlopen(request, timeout=max(1.0, float(timeout))) as response:
            status = getattr(response, "status", None) or response.getcode()
            if int(status or 0) != 200:
                return None
            content_type = response.headers.get("Content-Type", "")
            if not any(
                kind in content_type.lower()
                for kind in ("html", "json", "xml", "text")
            ):
                return None
            data = response.read(MAX_RESPONSE_BYTES + 1)[:MAX_RESPONSE_BYTES]
            charset = None
            try:
                charset = response.headers.get_content_charset()
            except Exception:
                charset = None
            return decode_document(
                url=str(response.geturl()),
                data=data,
                content_type=content_type,
                content_encoding="",
                charset=charset,
            )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return None


def _fetch(
    session: requests.Session,
    url: str,
    *,
    timeout: float = 15.0,
    public_only: bool = False,
):
    current = url
    for _ in range(5):
        if public_only and not _public_url_allowed(current):
            return None
        try:
            response = session.get(
                current,
                timeout=max(1.0, float(timeout)),
                allow_redirects=not public_only,
            )
        except requests.RequestException:
            return None

        if public_only and response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location", "")
            if not location:
                return None
            current = urljoin(current, location)
            continue

        if response.status_code != 200:
            if response.status_code == 403 and not public_only:
                return _fetch_with_urllib(current, timeout=timeout)
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

    return None


def probe_site(
    url: str,
    *,
    max_pages: int = 4,
    request_timeout: float = 8.0,
    time_budget_seconds: float = 24.0,
    page_priority: str = "default",
    public_only: bool = False,
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

    max_pages = max(1, min(int(max_pages), 12))
    request_timeout = max(1.0, min(float(request_timeout), 30.0))
    time_budget_seconds = max(request_timeout, min(float(time_budget_seconds), 120.0))
    deadline = time.monotonic() + time_budget_seconds

    homepage = _fetch(
        session,
        url,
        timeout=request_timeout,
        public_only=public_only,
    )

    if homepage is None:
        fallback_url = (
            "https://" + url[len("http://"):]
            if url.startswith("http://")
            else (
                "http://" + url[len("https://"):]
                if url.startswith("https://")
                else ""
            )
        )
        if fallback_url:
            homepage = _fetch(
                session,
                fallback_url,
                timeout=request_timeout,
                public_only=public_only,
            )

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
        internal = _internal_candidates(
            homepage.text,
            homepage.url,
            priority=page_priority,
        )
        if page_priority == "people" and max_pages >= 12:
            queue.extend(internal[:6])
            queue.extend(
                _sitemap_people_candidates(
                    session,
                    origin,
                    timeout=request_timeout,
                    deadline=deadline,
                    max_urls=12,
                    public_only=public_only,
                )
            )
            queue.extend(internal[6:])
        else:
            queue.extend(internal)
        queue.extend(
            _common_candidates(
                homepage.url,
                priority=page_priority,
            )
        )

    queue = list(dict.fromkeys(queue))
    queued = set(queue)

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
        if index >= max_pages:
            break
        if index == 0:
            document = homepage
        else:
            if not _same_site(page_url, origin):
                continue
            if time.monotonic() >= deadline:
                break

            time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
            remaining = max(1.0, deadline - time.monotonic())
            document = _fetch(
                session,
                page_url,
                timeout=min(request_timeout, remaining),
                public_only=public_only,
            )

            if document is None:
                continue

        if page_priority == "people" and document.format == "html":
            discovered = _internal_candidates(
                document.text,
                document.url,
                priority="people",
            )
            inject = []
            for candidate_url in discovered:
                if (
                    candidate_url not in queued
                    and _same_site(candidate_url, origin)
                ):
                    queued.add(candidate_url)
                    inject.append(candidate_url)
            if inject:
                queue[index + 1:index + 1] = inject

        schema = _schema_evidence(
            document.structured_data
        )
        visible_people = (
            _visible_people_from_html(
                document.text,
                page_url=document.url,
                page_title=document.title,
                emails=document.emails,
            )
            if document.format == "html"
            else []
        )

        names.extend(schema["business_names"])
        emails.extend(document.emails)
        emails.extend(schema["emails"])
        phones.extend(document.phones)
        phones.extend(schema["phones"])
        addresses.extend(schema["addresses"])
        socials.extend(document.socials)
        schema_types.extend(schema["schema_types"])
        people.extend(
            {
                **person,
                "source_kind": "structured_data",
                "page_url": document.url,
            }
            for person in schema["people"]
        )
        people.extend(
            {
                **person,
                "source_kind": "visible_text",
                "page_url": document.url,
            }
            for person in visible_people
        )

        page_emails = [
            value
            for value in dict.fromkeys(document.emails)
            if _valid_email(value)
        ]
        visible_text = (
            clean_text(document.text)[:12_000]
            if document.format == "html"
            else ""
        )
        pages.append({
            "url": document.url,
            "canonical_url": document.canonical_url,
            "title": document.title,
            "format": document.format,
            "emails_found": len(document.emails),
            "emails": page_emails[:50],
            "visible_text": visible_text,
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
        "time_budget_seconds": round(time_budget_seconds, 2),
        "budget_exhausted": time.monotonic() >= deadline,
    }
