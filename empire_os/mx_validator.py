"""
MX Validator — verifies an email is deliverable WITHOUT a paid service.

Checks (in order):
1. Disposable domain blocklist (Mailcheck-style)
2. Role address filter (info@, admin@, noreply@ — not decision-makers)
3. DNS MX record lookup (the receiving domain must accept mail)
4. SMTP RCPT TO probe (the server must accept the address)
   - Closes connection before DATA, never actually sends mail

Free, no API key, no per-validation cost.
"""
from __future__ import annotations

import logging
import re
import socket
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("mx_validator")


# ── Disposable / role-address lists ─────────────────────────────────

DISPOSABLE_DOMAINS = {
    # Top disposable providers — extend as needed
    "mailinator.com", "guerrillamail.com", "tempmail.com", "10minutemail.com",
    "throwawaymail.com", "yopmail.com", "trashmail.com", "fakeinbox.com",
    "maildrop.cc", "sharklasers.com", "getnada.com", "tempinbox.com",
    "dispostable.com", "mintemail.com", "spambog.com", "filzmail.com",
    "spam4.me", "burnermail.io", "mohmal.com", "tempemail.co",
    "discard.email", "tempr.email", "temp-mail.org", "mt2014.com",
}

ROLE_PREFIXES = {
    "info", "admin", "administrator", "noreply", "no-reply", "postmaster",
    "support", "help", "contact", "sales", "marketing", "webmaster",
    "abuse", "root", "mailer-daemon", "hostmaster", "usenet", "news",
    "uucp", "ftp", "operator", "list", "subscribe", "unsubscribe",
    "billing", "accounts", "press", "media", "team", "hello",
}

EMAIL_REGEX = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)

PHONE_REGEX = re.compile(
    r"(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"
)


# ── Result types ────────────────────────────────────────────────────

@dataclass
class MxValidationResult:
    """Outcome of validating a single email."""
    email: str
    is_valid: bool = False
    confidence: float = 0.0
    is_disposable: bool = False
    is_role_address: bool = False
    has_mx: bool = False
    smtp_accepts: bool = False
    error: str = ""
    checks: list = field(default_factory=list)


# ── Validator ───────────────────────────────────────────────────────

class MxValidator:
    """Validates email deliverability using DNS + SMTP (no external API)."""

    def __init__(self, smtp_timeout: int = 5, do_smtp_probe: bool = True):
        self.smtp_timeout = smtp_timeout
        self.do_smtp_probe = do_smtp_probe

    def validate(self, email: str) -> MxValidationResult:
        """Run all checks on one email."""
        result = MxValidationResult(email=email)

        if not email or "@" not in email:
            result.error = "invalid format"
            return result

        local, _, domain = email.partition("@")
        local_lower = local.lower()

        # Check 1: disposable domain
        if domain.lower() in DISPOSABLE_DOMAINS:
            result.is_disposable = True
            result.error = "disposable domain"
            result.checks.append("disposable:blocked")
            return result

        # Check 2: role address
        if local_lower in ROLE_PREFIXES:
            result.is_role_address = True
            result.error = "role address"
            result.checks.append("role:blocked")
            return result

        result.checks.append("format:ok")

        # Check 3: DNS MX lookup
        mx_hosts = self._mx_lookup(domain)
        if not mx_hosts:
            result.error = "no MX record"
            result.checks.append("mx:none")
            return result
        result.has_mx = True
        result.checks.append(f"mx:found:{mx_hosts[0]}")

        # Check 4: SMTP RCPT TO probe (optional)
        if self.do_smtp_probe:
            accepts = self._smtp_probe(mx_hosts[0], email)
            result.smtp_accepts = accepts
            if accepts:
                result.checks.append("smtp:accept")
            else:
                result.checks.append("smtp:reject")
                # If SMTP rejects, downgrade confidence but don't fail outright
                # (some servers intentionally lie to probes)
                result.error = "smtp rejected"
                result.confidence = 0.5
                return result

        # Passed all checks
        result.is_valid = True
        result.confidence = 0.95 if self.do_smtp_probe else 0.75
        return result

    def _mx_lookup(self, domain: str) -> list[str]:
        """Return MX hosts for the domain (empty list on failure)."""
        try:
            import dns.resolver  # type: ignore
            answers = dns.resolver.resolve(domain, "MX")
            return sorted(
                [(r.exchange.to_text().rstrip("."), r.preference) for r in answers],
                key=lambda x: x[1],
            )[0:1]  # just the primary
        except ImportError:
            # Fall back to socket-based check if dnspython not available
            return self._fallback_mx(domain)
        except Exception as e:
            logger.debug("MX lookup failed for %s: %s", domain, e)
            return []

    def _fallback_mx(self, domain: str) -> list[str]:
        """Socket-based fallback (no dnspython dependency)."""
        try:
            # Try to resolve via getaddrinfo — not as reliable as MX but works
            socket.getaddrinfo(domain, None)
            # If we got here, the domain resolves; assume MX exists
            # (a real check would query DNS MX records specifically)
            return [domain]
        except Exception:
            return []

    def _smtp_probe(self, mx_host: str, email: str) -> bool:
        """Connect to SMTP server, send RCPT TO, close before DATA."""
        import smtplib
        try:
            with smtplib.SMTP(timeout=self.smtp_timeout) as smtp:
                smtp.connect(mx_host, 25)
                smtp.helo("empire-os.local")
                smtp.mail("probe@empire-os.local")
                code, _ = smtp.rcpt(email)
                smtp.quit()
                # 250 = accepted, 251 = user not local (still accepted)
                return code in (250, 251)
        except Exception as e:
            logger.debug("SMTP probe failed for %s: %s", email, e)
            return False


def extract_phones_from_text(text: str) -> list[str]:
    """Pull phone numbers from arbitrary text (free helper)."""
    return list(set(PHONE_REGEX.findall(text or "")))


def extract_emails_from_text(text: str) -> list[str]:
    """Pull email addresses from arbitrary text."""
    email_pat = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    found = email_pat.findall(text or "")
    # Filter out obvious junk
    return list({e for e in found if not e.startswith(".") and ".." not in e})