"""Empire Search Fabric response decoding and structured extraction."""

from __future__ import annotations

import base64
import gzip
import html
import json
import re
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import (
    parse_qs,
    unquote,
    urljoin,
    urlparse,
    urlunparse,
)


@dataclass
class DecodedDocument:
    url: str
    content_type: str
    text: str
    format: str
    title: str = ""
    description: str = ""
    canonical_url: str = ""
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    socials: List[str] = field(default_factory=list)
    structured_data: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?1[\s.\-]?)?"
    r"(?:\(?\d{3}\)?[\s.\-]?)"
    r"\d{3}[\s.\-]?\d{4}(?!\d)"
)

SOCIAL_HOSTS = (
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
)


def _safe_text(data: bytes, encoding: Optional[str] = None) -> str:
    """Decode bytes conservatively without throwing on dirty web content."""
    candidates = []

    if encoding:
        candidates.append(encoding)

    if data.startswith(b"\xef\xbb\xbf"):
        candidates.append("utf-8-sig")
    elif data.startswith((b"\xff\xfe", b"\xfe\xff")):
        candidates.append("utf-16")

    candidates.extend(("utf-8", "windows-1252", "latin-1"))

    seen = set()

    for candidate in candidates:
        candidate = candidate.lower().strip()

        if candidate in seen:
            continue

        seen.add(candidate)

        try:
            return data.decode(candidate)
        except (LookupError, UnicodeDecodeError):
            continue

    return data.decode("utf-8", errors="replace")


def decompress_payload(
    data: bytes,
    content_encoding: str = "",
) -> bytes:
    """
    Decode standard HTTP compression.

    Brotli is optional and only used when a compatible module is installed.
    """
    encoding = (content_encoding or "").lower().strip()

    if not encoding or encoding == "identity":
        return data

    try:
        if encoding == "gzip":
            return gzip.decompress(data)

        if encoding == "deflate":
            try:
                return zlib.decompress(data)
            except zlib.error:
                return zlib.decompress(data, -zlib.MAX_WBITS)

        if encoding == "br":
            try:
                import brotli  # optional
                return brotli.decompress(data)
            except (ImportError, Exception):
                return data

    except Exception:
        return data

    return data


def detect_format(
    content_type: str,
    text: str,
) -> str:
    ct = (content_type or "").lower()
    sample = text.lstrip()[:500].lower()

    if "json" in ct or sample.startswith(("{", "[")):
        return "json"

    if (
        "xml" in ct
        or "rss" in ct
        or sample.startswith("<?xml")
        or sample.startswith("<rss")
        or sample.startswith("<feed")
    ):
        return "xml"

    if "html" in ct or "<html" in sample or "<!doctype html" in sample:
        return "html"

    return "text"


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def canonicalise_url(
    value: str,
    base_url: str = "",
) -> str:
    value = html.unescape((value or "").strip())

    if not value:
        return ""

    if base_url:
        value = urljoin(base_url, value)

    try:
        parsed = urlparse(value)

        scheme = parsed.scheme.lower()
        host = parsed.netloc.lower()

        if scheme not in ("http", "https"):
            return value

        if host.startswith("www."):
            host = host[4:]

        path = re.sub(r"/{2,}", "/", parsed.path or "/")

        # Strip fragment while retaining meaningful query parameters.
        return urlunparse(
            (
                scheme,
                host,
                path,
                "",
                parsed.query,
                "",
            )
        )
    except Exception:
        return value


def decode_redirect_url(value: str) -> str:
    """
    Decode known search redirect wrappers without following them.

    Supports Bing and DuckDuckGo wrappers.
    """
    value = html.unescape(value or "")

    if value.startswith("//"):
        value = "https:" + value

    try:
        parsed = urlparse(value)
        host = parsed.netloc.lower()
        params = parse_qs(parsed.query)

        if "duckduckgo.com" in host:
            target = params.get("uddg", [""])[0]

            if target:
                return unquote(target)

        if "bing.com" in host and parsed.path.startswith("/ck/"):
            encoded = params.get("u", [""])[0]

            if encoded.startswith("a1"):
                encoded = encoded[2:]

            if encoded:
                encoded += "=" * (-len(encoded) % 4)

                try:
                    decoded = base64.urlsafe_b64decode(
                        encoded
                    ).decode("utf-8", errors="ignore")

                    if decoded.startswith(("http://", "https://")):
                        return decoded
                except Exception:
                    pass

    except Exception:
        pass

    return value


def extract_json_ld(page: str) -> List[Dict[str, Any]]:
    """Extract schema.org / JSON-LD records from HTML."""
    records: List[Dict[str, Any]] = []

    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>'
        r'(.*?)</script>',
        page,
        re.I | re.S,
    ):
        raw = html.unescape(match.group(1)).strip()

        try:
            data = json.loads(raw)
        except Exception:
            continue

        if isinstance(data, dict):
            records.append(data)
        elif isinstance(data, list):
            records.extend(
                item for item in data
                if isinstance(item, dict)
            )

    return records


def extract_next_data(page: str) -> Optional[Dict[str, Any]]:
    """Extract Next.js __NEXT_DATA__ payload when publicly embedded."""
    match = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>'
        r'(.*?)</script>',
        page,
        re.I | re.S,
    )

    if not match:
        return None

    try:
        data = json.loads(html.unescape(match.group(1)))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def extract_html_metadata(
    page: str,
    base_url: str,
) -> Dict[str, Any]:
    title = ""
    description = ""
    canonical = ""

    match = re.search(
        r"<title[^>]*>(.*?)</title>",
        page,
        re.I | re.S,
    )
    if match:
        title = clean_text(match.group(1))[:500]

    match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        page,
        re.I | re.S,
    )

    if not match:
        match = re.search(
            r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
            page,
            re.I | re.S,
        )

    if match:
        description = clean_text(match.group(1))[:1000]

    match = re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'](.*?)["\']',
        page,
        re.I | re.S,
    )

    if match:
        canonical = canonicalise_url(
            match.group(1),
            base_url,
        )

    links = re.findall(
        r'href=["\']([^"\']+)["\']',
        page,
        re.I,
    )

    socials = []

    for link in links:
        resolved = canonicalise_url(
            decode_redirect_url(link),
            base_url,
        )

        host = urlparse(resolved).netloc.lower()

        if any(domain in host for domain in SOCIAL_HOSTS):
            socials.append(resolved)

    visible = clean_text(page)

    return {
        "title": title,
        "description": description,
        "canonical_url": canonical,
        "emails": sorted(set(EMAIL_RE.findall(page))),
        "phones": sorted(set(PHONE_RE.findall(visible))),
        "socials": list(dict.fromkeys(socials)),
        "structured_data": extract_json_ld(page),
        "next_data": extract_next_data(page),
    }


def decode_document(
    *,
    url: str,
    data: bytes,
    content_type: str = "",
    content_encoding: str = "",
    charset: Optional[str] = None,
) -> DecodedDocument:
    """
    Convert an HTTP payload into a normalized Empire document.
    """
    payload = decompress_payload(
        data,
        content_encoding,
    )

    text = _safe_text(
        payload,
        charset,
    )

    fmt = detect_format(
        content_type,
        text,
    )

    document = DecodedDocument(
        url=url,
        content_type=content_type,
        text=text,
        format=fmt,
        canonical_url=canonicalise_url(url),
    )

    if fmt == "html":
        metadata = extract_html_metadata(
            text,
            url,
        )

        document.title = metadata["title"]
        document.description = metadata["description"]
        document.canonical_url = (
            metadata["canonical_url"]
            or document.canonical_url
        )
        document.emails = metadata["emails"]
        document.phones = metadata["phones"]
        document.socials = metadata["socials"]
        document.structured_data = metadata["structured_data"]

        if metadata["next_data"] is not None:
            document.metadata["next_data"] = metadata["next_data"]

    elif fmt == "json":
        try:
            document.metadata["json"] = json.loads(text)
        except Exception:
            pass

    return document
