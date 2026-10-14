"""Pinned-IP, bounded first-party public HTML inspection.

No redirects, cookies, browser execution, proxies or arbitrary schemes.
All resolved IPs must be globally routable; one approved IP is pinned for
the actual socket connection while TLS validates the original hostname.
"""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import http.client
import ipaddress
import socket
import ssl
from typing import Any, Callable
from urllib.parse import urlsplit

from .deep_research_intake import _public_url

_MAX_BODY = 196_608
_ALLOWED_TYPES = {"text/html", "application/xhtml+xml"}


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.current = ""
        self.parts: list[str] = []
        self.headings: list[str] = []
        self.title = ""
        self._heading_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg", "template", "nav", "footer"}:
            self.skip += 1
        if not self.skip and tag in {"h1", "h2", "h3", "title"}:
            self.current = tag
            self._heading_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "template", "nav", "footer"}:
            self.skip = max(0, self.skip - 1)
        if not self.skip and tag == self.current:
            heading = " ".join(" ".join(self._heading_parts).split())[:180]
            if heading and tag == "title":
                self.title = heading
            elif heading and len(self.headings) < 8:
                self.headings.append(heading)
            self.current = ""
            self._heading_parts = []

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        cleaned = " ".join(data.split())
        if not cleaned:
            return
        if self.current:
            self._heading_parts.append(cleaned[:180])
        if len(self.parts) < 120:
            self.parts.append(cleaned[:350])

    @property
    def visible_text(self) -> str:
        return " ".join(self.parts)[:5000]


def resolve_public_ips(
    host: str,
    port: int,
    *,
    resolver: Callable[..., list[tuple]] = socket.getaddrinfo,
) -> tuple[str, ...]:
    """Fail close if DNS has no answer or ANY public/private ambiguity."""
    rows = resolver(host, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
    ips: list[str] = []
    for row in rows:
        addr = str(row[4][0]).split("%")[0]
        parsed = ipaddress.ip_address(addr)
        if not parsed.is_global:
            raise ValueError("nonpublic_dns_answer")
        if addr not in ips:
            ips.append(addr)
    if not ips:
        raise ValueError("no_dns_answers")
    return tuple(ips)


def _pinned_http_get(
    host: str,
    ip: str,
    port: int,
    path: str,
    *,
    https: bool,
    timeout: float,
) -> tuple[int, dict[str, str], bytes]:
    if https:
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=ctx)
    else:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
    # http.client retains the intended hostname for SNI and certificate checks.
    # Only the physical socket target is replaced by the DNS-vetted literal IP.
    conn._create_connection = lambda address, timeout, source_address=None: socket.create_connection(
        (ip, port), timeout=timeout, source_address=source_address
    )
    try:
        conn.request(
            "GET", path,
            headers={
                "Host": host,
                "User-Agent": "EmpireOS-Research-ReadOnly/1.0",
                "Accept": "text/html",
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
        )
        resp = conn.getresponse()
        headers = {k.lower(): v.strip() for k, v in resp.getheaders()}
        declared = headers.get("content-length")
        if declared and int(declared) > _MAX_BODY:
            return resp.status, headers, b""
        body = resp.read(_MAX_BODY + 1)
        return resp.status, headers, body
    finally:
        conn.close()


def inspect_public_html(
    url: str,
    *,
    resolver: Callable[..., list[tuple]] = socket.getaddrinfo,
    fetcher: Callable[..., tuple[int, dict[str, str], bytes]] = _pinned_http_get,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Inspect public page content; source inspection is not factual verification."""
    canonical = _public_url(url)
    if not canonical:
        return {"status": "UNSAFE_URL_REJECTED"}
    parts = urlsplit(canonical)
    host = parts.hostname or ""
    https = parts.scheme == "https"
    port = parts.port or (443 if https else 80)
    if port != (443 if https else 80):
        return {"status": "UNSAFE_PORT_REJECTED"}
    try:
        addresses = resolve_public_ips(host, port, resolver=resolver)
    except (ValueError, OSError, socket.gaierror):
        return {"status": "DNS_UNSAFE_OR_UNAVAILABLE"}
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    try:
        status, headers, body = fetcher(
            host, addresses[0], port, path, https=https,
            timeout=max(1.0, min(float(timeout), 8.0))
        )
    except (ValueError, OSError, ssl.SSLError, http.client.HTTPException):
        return {"status": "NETWORK_OR_TLS_UNAVAILABLE"}
    if status in {301, 302, 303, 307, 308}:
        return {"status": "REDIRECT_NOT_FOLLOWED", "http_status": status}
    if status != 200:
        return {"status": "HTTP_NOT_SUCCESS", "http_status": status}
    if len(body) > _MAX_BODY or not body:
        return {"status": "CONTENT_SIZE_REJECTED"}
    if headers.get("content-encoding", "identity").lower() not in {"", "identity"}:
        return {"status": "COMPRESSED_CONTENT_REJECTED"}
    mime = headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if mime not in _ALLOWED_TYPES:
        return {"status": "NON_HTML_REJECTED", "content_type": mime}
    try:
        parser = _VisibleText()
        parser.feed(body.decode("utf-8", errors="replace"))
        readable = parser.visible_text
    except (ValueError, UnicodeError):
        return {"status": "PARSE_FAILED"}
    if len(readable) < 100 or not (parser.title or parser.headings):
        return {"status": "PAGE_TOO_THIN"}
    return {
        "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
        "source_url": canonical,
        "http_status": 200,
        "content_sha256": hashlib.sha256(body).hexdigest(),
        "hash_scope": "complete_bounded_response",
        "document_truncated": False,
        "document_headings": parser.headings[:5] or [parser.title],
        "page_title": parser.title[:180],
        "visible_excerpt": readable[:1500],
        "publication_date_verified": False,
        "claim_accuracy_verified": False,
        "operator_actions_taken": False,
    }
