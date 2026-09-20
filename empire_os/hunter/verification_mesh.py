"""Evidence-first native email verification mesh.

No third-party verification provider is required. Mailbox probing is optional
and injected; lack of SMTP reachability remains UNKNOWN/PROBABLE rather than
being misreported as verified.
"""
from __future__ import annotations

import re
from typing import Callable

from empire_os.hunter.models import ContactEvidence, VerificationState
from empire_os.mx_validator import (
    DISPOSABLE_DOMAINS,
    ROLE_PREFIXES,
    MxValidator,
)


MailboxProbe = Callable[[str, tuple[str, ...]], str]
EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)


class VerificationMesh:
    def __init__(
        self,
        *,
        mx_validator: MxValidator | None = None,
        mailbox_probe: MailboxProbe | None = None,
    ):
        self.mx_validator = mx_validator or MxValidator(
            do_smtp_probe=False
        )
        self.mailbox_probe = mailbox_probe

    def verify(
        self,
        email: str,
        *,
        source: str,
        source_url: str | None = None,
        person_name: str | None = None,
        person_title: str | None = None,
        person_bound: bool = False,
        first_party: bool = False,
        delivered_evidence: bool = False,
        bounced_evidence: bool = False,
    ) -> ContactEvidence:
        normalized = str(email or "").strip().lower()
        reasons: list[str] = []

        syntax_ok = bool(EMAIL_RE.fullmatch(normalized))
        if not syntax_ok:
            return ContactEvidence(
                email=normalized,
                state=VerificationState.REJECTED,
                confidence=0.0,
                source=source,
                source_url=source_url,
                person_name=person_name,
                person_title=person_title,
                person_bound=person_bound,
                first_party=first_party,
                reasons=("invalid_format",),
            )

        local, domain = normalized.rsplit("@", 1)
        disposable = domain in DISPOSABLE_DOMAINS
        role = local in ROLE_PREFIXES

        if disposable:
            return ContactEvidence(
                email=normalized,
                state=VerificationState.REJECTED,
                confidence=0.0,
                source=source,
                source_url=source_url,
                person_name=person_name,
                person_title=person_title,
                person_bound=person_bound,
                first_party=first_party,
                syntax_ok=True,
                disposable=True,
                reasons=("disposable_domain",),
            )

        mx = self.mx_validator.validate(normalized)
        mx_ok = bool(mx.has_mx)

        if bounced_evidence:
            return ContactEvidence(
                email=normalized,
                state=VerificationState.REJECTED,
                confidence=0.05,
                source=source,
                source_url=source_url,
                person_name=person_name,
                person_title=person_title,
                person_bound=person_bound,
                first_party=first_party,
                syntax_ok=True,
                mx_ok=mx_ok,
                bounced_evidence=True,
                role_address=role,
                reasons=("verified_bounce",),
            )

        if not mx_ok:
            return ContactEvidence(
                email=normalized,
                state=VerificationState.REJECTED,
                confidence=0.1,
                source=source,
                source_url=source_url,
                person_name=person_name,
                person_title=person_title,
                person_bound=person_bound,
                first_party=first_party,
                syntax_ok=True,
                role_address=role,
                reasons=("no_mx",),
            )

        mailbox_status = "not_checked"
        if self.mailbox_probe is not None:
            hosts = tuple(self.mx_validator._mx_lookup(domain))
            try:
                mailbox_status = str(
                    self.mailbox_probe(normalized, hosts)
                ).strip().lower()
            except Exception:
                mailbox_status = "unreachable"

        if delivered_evidence:
            reasons.append("delivered_evidence")
            state = VerificationState.CONFIRMED
            confidence = 0.99
        elif first_party and person_bound and not role:
            reasons.extend(("first_party", "person_bound", "mx"))
            state = VerificationState.CONFIRMED
            confidence = 0.96
        elif mailbox_status == "accepted" and person_bound and not role:
            reasons.extend(("mailbox_accept", "person_bound", "mx"))
            state = VerificationState.CONFIRMED
            confidence = 0.95
        elif person_bound and not role:
            reasons.extend(("person_bound", "mx"))
            state = VerificationState.PROBABLE
            confidence = 0.78
        elif role:
            reasons.extend(("role_address", "mx"))
            state = VerificationState.PROBABLE
            confidence = 0.55
        else:
            reasons.append("mx_only")
            state = VerificationState.PROBABLE
            confidence = 0.62

        return ContactEvidence(
            email=normalized,
            state=state,
            confidence=confidence,
            source=source,
            source_url=source_url,
            person_name=person_name,
            person_title=person_title,
            person_bound=person_bound,
            first_party=first_party,
            syntax_ok=True,
            mx_ok=True,
            mailbox_status=mailbox_status,
            delivered_evidence=delivered_evidence,
            bounced_evidence=False,
            role_address=role,
            disposable=False,
            reasons=tuple(reasons),
        )
