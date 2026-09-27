"""
MX Validator — verifies an email is deliverable WITHOUT a paid service.

Checks (in order):
1. Disposable domain blocklist (Mailcheck-style)
2. Role address filter (info@, admin@, noreply@ — not decision-makers)
3. DNS MX record lookup (the receiving domain must accept mail)
4. SMTP RCPT TO probe (optional)
   - Closes connection before DATA, never actually sends mail
   - Distinguishes explicit recipient rejection from transport/probe failure

Free, no API key, no per-validation cost.
"""
from __future__ import annotations

import logging
import re
import socket
from dataclasses import dataclass, field

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
    smtp_status: str = "not_run"
    smtp_code: int | None = None
    smtp_detail: str = ""
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

        # DNS + non-role/non-disposable checks establish MX-level validity.
        result.is_valid = True
        result.confidence = 0.75

        # Check 4: SMTP RCPT TO probe (optional)
        if self.do_smtp_probe:
            status, code, detail = self._smtp_probe(mx_hosts[0], email)
            result.smtp_status = status
            result.smtp_code = code
            result.smtp_detail = detail
            result.smtp_accepts = status == "accepted"

            if status == "accepted":
                result.checks.append(
                    f"smtp:accept:{code}" if code is not None else "smtp:accept"
                )
                result.confidence = 0.95
            elif status == "rejected":
                result.checks.append(
                    f"smtp:reject:{code}" if code is not None else "smtp:reject"
                )
                result.is_valid = False
                result.error = "smtp rejected"
                result.confidence = 0.5
                return result
            elif status == "temporary_reject":
                result.checks.append(
                    f"smtp:temporary:{code}"
                    if code is not None
                    else "smtp:temporary"
                )
                result.error = "smtp temporarily rejected"
                result.confidence = 0.70
            else:
                # Connection failures, blocked outbound port 25, TLS/HELO
                # problems and similar probe failures do not prove that the
                # recipient mailbox rejected the address.
                result.smtp_status = "unavailable"
                result.checks.append("smtp:unavailable")
                result.error = "smtp probe unavailable"
                result.confidence = 0.75

        return result

    def _mx_lookup(self, domain: str) -> list[str]:
        """Return MX hosts for the domain (empty list on failure)."""
        try:
            import dns.resolver  # type: ignore
            resolver = dns.resolver.Resolver(configure=True)
            resolver.timeout = max(0.5, min(float(self.smtp_timeout), 3.0))
            resolver.lifetime = max(0.5, min(float(self.smtp_timeout), 3.0))
            answers = resolver.resolve(domain, "MX")
            ordered = sorted(
                [
                    (
                        r.exchange.to_text().rstrip("."),
                        int(r.preference),
                    )
                    for r in answers
                ],
                key=lambda item: item[1],
            )
            return [host for host, _ in ordered]
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

    def _smtp_probe(
        self,
        mx_host: str,
        email: str,
    ) -> tuple[str, int | None, str]:
        """Probe RCPT TO and distinguish rejection from probe unavailability."""
        import smtplib

        try:
            with smtplib.SMTP(timeout=self.smtp_timeout) as smtp:
                smtp.connect(mx_host, 25)
                smtp.helo("empire-os.local")
                smtp.mail("probe@empire-os.local")
                code, message = smtp.rcpt(email)
                smtp.quit()

            detail = (
                message.decode("utf-8", errors="replace")
                if isinstance(message, bytes)
                else str(message or "")
            ).strip()

            if code in (250, 251):
                return "accepted", int(code), detail
            if 400 <= int(code) <= 499:
                return "temporary_reject", int(code), detail
            if int(code) >= 500:
                return "rejected", int(code), detail
            return "unavailable", int(code), detail
        except Exception as e:
            logger.debug("SMTP probe unavailable for %s: %s", email, e)
            return "unavailable", None, type(e).__name__


def extract_phones_from_text(text: str) -> list[str]:
    """Pull phone numbers from arbitrary text (free helper)."""
    return list(set(PHONE_REGEX.findall(text or "")))


def extract_emails_from_text(text: str) -> list[str]:
    """Pull email addresses from arbitrary text."""
    email_pat = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    found = email_pat.findall(text or "")
    # Filter out obvious junk
    return list({e for e in found if not e.startswith(".") and ".." not in e})
