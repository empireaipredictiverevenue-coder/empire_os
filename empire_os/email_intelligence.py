#!/usr/bin/env python3
"""
email_intelligence — self-hosted Hunter.io alternative.

Free email discovery + verification API. No API key needed, no per-call cost.
Runs inside empire-hub alongside the core API.

Endpoints (FastAPI):
  GET  /v1/email/verify?email=...    — verify a single email
  GET  /v1/domain/search?domain=... — find emails for a domain
  GET  /v1/domain/count?domain=...  — count emails on a domain
  GET  /v1/email/find?domain=...&first_name=...&last_name=... — find person's email

Integrates with:
  - mx_validator (DNS MX + SMTP RCPT TO probe)
  - host_b2b_hunter (Brave/Bing/Marginalia web search)
  - Common email patterns (first@domain, first.last@domain, etc.)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import socket
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("email_intelligence")

# ── Config ───────────────────────────────────────────────────────────

SMTP_TIMEOUT = 5
HTTP_TIMEOUT = 10
UA = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# Known email patterns by provider size (permissive, not exhaustive)
PATTERNS = [
    "{first}@{domain}",
    "{first}.{last}@{domain}",
    "{f}{last}@{domain}",
    "{first}{last}@{domain}",
    "{last}.{first}@{domain}",
    "{first}_{last}@{domain}",
    "{f}.{last}@{domain}",
    "{first}-{last}@{domain}",
    "{fi}{last}@{domain}",
    "{last}@{domain}",
]

COMMON_EMAILS = [
    "info", "contact", "sales", "hello", "support",
    "admin", "office", "team", "careers", "press",
    "billing", "accounts", "marketing", "partners",
]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


# ── Data models ──────────────────────────────────────────────────────

@dataclass
class VerificationResult:
    email: str
    status: str  # valid | risky | invalid | unknown
    score: float  # 0.0-1.0
    mx_found: bool = False
    smtp_ok: bool = False
    is_disposable: bool = False
    is_role: bool = False
    did_you_mean: str = ""
    checks: list = field(default_factory=list)


@dataclass
class DomainSearchResult:
    domain: str
    emails: list = field(default_factory=list)
    total: int = 0
    source: str = ""


# ── Verifier (wraps mx_validator.MxValidator) ────────────────────────

class EmailVerifier:
    """Multi-layer email verification without paid APIs."""

    def __init__(self):
        self._mx_validator = None  # lazy import

    def _get_validator(self):
        if self._mx_validator is None:
            from empire_os.mx_validator import MxValidator
            self._mx_validator = MxValidator(smtp_timeout=SMTP_TIMEOUT, do_smtp_probe=True)
        return self._mx_validator

    def verify(self, email: str) -> VerificationResult:
        result = VerificationResult(email=email, status="unknown", score=0.0)

        if not email or "@" not in email:
            result.status = "invalid"
            result.score = 0.0
            result.checks.append("format:invalid")
            return result

        local, domain = email.split("@", 1)

        # Run mx_validator
        v = self._get_validator()
        mx_result = v.validate(email)

        result.mx_found = mx_result.has_mx
        result.smtp_ok = mx_result.smtp_accepts
        result.is_disposable = mx_result.is_disposable
        result.is_role = mx_result.is_role_address
        result.checks = mx_result.checks[:]

        if mx_result.is_disposable:
            result.status = "invalid"
            result.score = 0.0
            return result

        if mx_result.is_role_address:
            result.status = "risky"
            result.score = 0.4
            result.checks.append("role:risky")
            return result

        if not mx_result.has_mx:
            result.status = "invalid"
            result.score = 0.0
            return result

        if self._smtp_probe_sync(email):
            result.status = "valid"
            result.score = 0.95
            result.checks.append("smtp:accept")
        else:
            result.status = "risky"
            result.score = 0.5
            result.checks.append("smtp:reject")

        return result

    def _smtp_probe_sync(self, email: str) -> bool:
        """Lightweight SMTP check (blocks, short timeout)."""
        try:
            import smtplib
            local, domain = email.split("@", 1)
            mx_hosts = self._mx_lookup(domain)
            if not mx_hosts:
                return False
            with smtplib.SMTP(timeout=SMTP_TIMEOUT) as smtp:
                smtp.connect(mx_hosts[0], 25)
                smtp.helo("empire-os.local")
                smtp.mail("probe@empire-os.local")
                code, _ = smtp.rcpt(email)
                smtp.quit()
                return code in (250, 251)
        except Exception:
            return False

    def _mx_lookup(self, domain: str) -> list:
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, "MX")
            return sorted(
                [(r.exchange.to_text().rstrip("."), r.preference) for r in answers],
                key=lambda x: x[1],
            )[:1]
        except ImportError:
            # fallback: try to resolve A record
            try:
                socket.getaddrinfo(domain, 25)
                return [domain]
            except Exception:
                return []
        except Exception:
            return []


# ── Domain Searcher ──────────────────────────────────────────────────

class DomainSearcher:
    """Find email addresses associated with a domain."""

    def __init__(self):
        self.verifier = EmailVerifier()

    def search_domain(self, domain: str, limit: int = 20) -> DomainSearchResult:
        result = DomainSearchResult(domain=domain, emails=[])
        emails = set()

        # Method 1: scrape contact pages
        for path in ["", "/contact", "/contact-us", "/about", "/team", "/about-us"]:
            found = self._scrape_page(domain, path)
            emails.update(found)
            if len(emails) >= limit * 2:
                break

        # Method 2: search engines for this domain
        q = f"site:{domain} email | contact | @{domain}"
        found = self._search_emails(q)
        emails.update(found)

        # Method 3: common email addresses
        for prefix in COMMON_EMAILS:
            emails.add(f"{prefix}@{domain}")
            if len(emails) >= limit * 2:
                break

        # Verify and rank
        verified = []
        for e in sorted(emails)[:limit * 3]:
            vr = self.verifier.verify(e)
            verified.append({
                "email": e,
                "status": vr.status,
                "score": vr.score,
                "is_role": vr.is_role,
                "checks": vr.checks,
            })

        # Sort: valid first, then risky, then unknown
        score_map = {"valid": 0, "risky": 1, "unknown": 2, "invalid": 3}
        verified.sort(key=lambda x: (score_map.get(x["status"], 9), -x["score"]))

        result.emails = verified[:limit]
        result.total = len(verified)
        result.source = "web_scrape+pattern+search"
        return result

    def _scrape_page(self, domain: str, path: str) -> set:
        emails = set()
        url = f"https://{domain}{path}"
        try:
            html = urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=HTTP_TIMEOUT
            ).read().decode("utf-8", "ignore")
            for e in EMAIL_RE.findall(html):
                local, dm = e.split("@", 1)
                if dm.lower() == domain.lower() and not e.endswith((".png", ".jpg", ".svg", ".webp")):
                    emails.add(e.lower())
        except Exception:
            pass
        return emails

    def _search_emails(self, query: str) -> set:
        emails = set()
        q = urllib.parse.quote(query)
        for url in [
            f"https://search.brave.com/search?q={q}",
            f"https://www.bing.com/search?q={q}&count=10",
        ]:
            try:
                html = urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=HTTP_TIMEOUT
                ).read().decode("utf-8", "ignore")
                for e in EMAIL_RE.findall(html):
                    if not e.endswith((".png", ".jpg", ".svg", ".webp")):
                        emails.add(e.lower())
            except Exception:
                continue
        return emails


# ── Email Finder (domain + name → email) ──────────────────────────────

class EmailFinder:
    """Given a domain + person name, find their email."""

    def __init__(self):
        self.verifier = EmailVerifier()

    def find(self, domain: str, first_name: str, last_name: str = "") -> dict:
        candidates = []

        f = first_name.strip().lower()
        l = last_name.strip().lower() if last_name else ""
        fi = f[0] if f else ""
        li = l[0] if l else ""

        # Generate pattern candidates
        for pattern in PATTERNS:
            email = pattern.format(
                first=f, last=l, domain=domain,
                f=fi, l=li, fi=fi, li=li,
            )
            if email not in [c["email"] for c in candidates]:
                candidates.append({"email": email, "pattern": pattern})

        # Verify each candidate
        results = []
        for c in candidates:
            vr = self.verifier.verify(c["email"])
            results.append({
                "email": c["email"],
                "pattern": c["pattern"],
                "status": vr.status,
                "score": vr.score,
                "checks": vr.checks,
            })

        # Sort valid first
        score_map = {"valid": 0, "risky": 1, "unknown": 2, "invalid": 3}
        results.sort(key=lambda x: (score_map.get(x["status"], 9), -x["score"]))

        # Also try scraping their about/team page
        scraped = self._scrape_person(domain, first_name, last_name)
        if scraped and scraped not in [r["email"] for r in results]:
            vr = self.verifier.verify(scraped)
            results.insert(0, {
                "email": scraped,
                "pattern": "scraped",
                "status": vr.status,
                "score": vr.score,
                "checks": vr.checks,
            })

        return {
            "domain": domain,
            "first_name": first_name,
            "last_name": last_name,
            "candidates": results,
            "total": len(results),
        }

    def _scrape_person(self, domain: str, first: str, last: str) -> str:
        """Try to find the person's email on their company site."""
        for path in ["/team", "/about", "/about-us", "/company"]:
            try:
                html = urllib.request.urlopen(
                    urllib.request.Request(f"https://{domain}{path}", headers=UA),
                    timeout=HTTP_TIMEOUT,
                ).read().decode("utf-8", "ignore")
                for e in EMAIL_RE.findall(html):
                    local, dm = e.split("@", 1)
                    if dm.lower() == domain.lower():
                        if first.lower() in local.lower() or (last and last.lower() in local.lower()):
                            return e.lower()
            except Exception:
                continue
        return ""


# ── Singleton instances ──────────────────────────────────────────────

_verifier: Optional[EmailVerifier] = None
_searcher: Optional[DomainSearcher] = None
_finder: Optional[EmailFinder] = None


def get_verifier() -> EmailVerifier:
    global _verifier
    if _verifier is None:
        _verifier = EmailVerifier()
    return _verifier


def get_searcher() -> DomainSearcher:
    global _searcher
    if _searcher is None:
        _searcher = DomainSearcher()
    return _searcher


def get_finder() -> EmailFinder:
    global _finder
    if _finder is None:
        _finder = EmailFinder()
    return _finder


# ── FastAPI app ──────────────────────────────────────────────────────

try:
    from fastapi import APIRouter, FastAPI, Query
    from fastapi.responses import JSONResponse

    router = APIRouter(prefix="/v1/email", tags=["email_intelligence"])

    @router.get("/verify")
    async def verify_email(email: str = Query(..., description="Email to verify")):
        """Verify a single email address (MX check + SMTP probe)."""
        v = get_verifier()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, v.verify, email)
        return {
            "data": {
                "email": result.email,
                "status": result.status,
                "score": result.score,
                "mx_found": result.mx_found,
                "smtp_ok": result.smtp_ok,
                "is_disposable": result.is_disposable,
                "is_role": result.is_role,
                "checks": result.checks,
            }
        }

    @router.get("/domain/search")
    async def search_domain(
        domain: str = Query(..., description="Domain to search for emails"),
        limit: int = Query(20, description="Max results"),
    ):
        """Find all email addresses associated with a domain."""
        s = get_searcher()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, s.search_domain, domain, limit)
        return {
            "data": {
                "domain": result.domain,
                "emails": result.emails,
                "total": result.total,
                "source": result.source,
            }
        }

    @router.get("/domain/count")
    async def count_domain(domain: str = Query(..., description="Domain to count")):
        """Count how many emails are found for a domain."""
        s = get_searcher()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, s.search_domain, domain, 50)
        return {
            "data": {
                "domain": result.domain,
                "total": result.total,
                "source": result.source,
            }
        }

    @router.get("/find")
    async def find_email(
        domain: str = Query(..., description="Company domain"),
        first_name: str = Query(..., description="First name"),
        last_name: str = Query("", description="Last name (optional)"),
    ):
        """Find a person's email from domain + name."""
        f = get_finder()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, f.find, domain, first_name, last_name)
        return {"data": result}

    email_intelligence_router = router

except ImportError:
    email_intelligence_router = None
    logger.info("FastAPI not available — email_intelligence running in standalone mode")


# ── CLI mode ─────────────────────────────────────────────────────────

def cli():
    import argparse
    parser = argparse.ArgumentParser(description="Email Intelligence CLI")
    sub = parser.add_subparsers(dest="cmd")

    verify_p = sub.add_parser("verify", help="Verify an email")
    verify_p.add_argument("email")

    search_p = sub.add_parser("search", help="Search domain for emails")
    search_p.add_argument("domain")
    search_p.add_argument("--limit", type=int, default=10)

    count_p = sub.add_parser("count", help="Count emails for domain")
    count_p.add_argument("domain")

    find_p = sub.add_parser("find", help="Find email from name + domain")
    find_p.add_argument("domain")
    find_p.add_argument("--first", required=True)
    find_p.add_argument("--last", default="")

    args = parser.parse_args()

    if args.cmd == "verify":
        v = get_verifier()
        r = v.verify(args.email)
        print(json.dumps({
            "email": r.email,
            "status": r.status,
            "score": r.score,
            "mx_found": r.mx_found,
            "smtp_ok": r.smtp_ok,
            "is_disposable": r.is_disposable,
            "is_role": r.is_role,
            "checks": r.checks,
        }, indent=2))

    elif args.cmd == "search":
        s = get_searcher()
        r = s.search_domain(args.domain, args.limit)
        print(json.dumps({
            "domain": r.domain,
            "total": r.total,
            "source": r.source,
            "emails": r.emails,
        }, indent=2))

    elif args.cmd == "count":
        s = get_searcher()
        r = s.search_domain(args.domain, 50)
        print(json.dumps({"domain": r.domain, "total": r.total, "source": r.source}, indent=2))

    elif args.cmd == "find":
        f = get_finder()
        r = f.find(args.domain, args.first, args.last)
        print(json.dumps(r, indent=2))


if __name__ == "__main__":
    cli()
