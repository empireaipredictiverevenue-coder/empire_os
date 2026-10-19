"""In-memory, OFFLINE-ONLY session/consent authority prototype.

Purpose: exercise the existing first-party event contract's two *server*
resolvers while preserving a deny-by-default, revocable purpose-specific
consent state and attributed acquisition source.

NOT a production session issuer, consent management platform, lawfulness
attestation, signed receipt, or authoritative persistent ledger. No real
analytics may consume the counts; no cookies, HTTP routes, DB or network
are implemented here. All examples in this module are simulations.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import re
import secrets
import threading

from empire_os.analytics.first_party_event_contract import (
    ALLOWED_CHANNELS,
    EventContractHeld,
)

SCHEMA = "empire.analytics.offline_session_authority.v1"
ORIGIN = "https://empire-ai.co.uk"
PURPOSE = "website_analytics_measurement"
MAX_SESSIONS = 500
MAX_SESSION_DURATION = timedelta(minutes=30)
MAX_POLICY_LENGTH = 48
_POLICY = re.compile(r"^[a-z][a-z0-9._-]{3,47}$")


class AuthorityHeld(EventContractHeld):
    """A consent, source authority, quota or event-time prerequisite failed."""


@dataclass(frozen=True)
class SessionRecord:
    session_nonce: str
    site: str
    acquired_channel: str
    acquired_from: str
    opened_at: datetime
    expiry: datetime
    policy_revision: str
    consent_state: str = "unknown"
    consent_revision: int = 0
    terminal_revoked: bool = False


@dataclass(frozen=True)
class OfflineDecision:
    status: str
    consent_revision: int
    purpose: str = PURPOSE
    simulation_only: bool = True
    lawful_consent_verified: bool = False
    storage_active: bool = False


def _clock(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise AuthorityHeld("ANALYTICS_TIMEZONE_REQUIRED")
    return value.astimezone(timezone.utc)


def _site(value: str) -> None:
    if type(value) is not str or value != ORIGIN:
        raise AuthorityHeld("ANALYTICS_SITE_ORIGIN_UNAPPROVED")


def _policy(value: str) -> None:
    if type(value) is not str or not _POLICY.fullmatch(value):
        raise AuthorityHeld("ANALYTICS_POLICY_REVISION_INVALID")


class OfflineSessionAuthority:
    """Bounded, process-memory-only simulated consent and acquisition records.

    An offline operator supplies a trusted acquisition classifier on
    construction; raw campaign/query/referrer strings are never accepted.
    No default analytics-consent grant is possible. Revocation is terminal
    for a session and invalidates every subsequent event for that nonce.
    """

    def __init__(
        self,
        *,
        policy_revision: str,
        resolve_trusted_acquisition: Callable[[], tuple[str, str]] | None,
        clock: Callable[[], datetime] | None,
        enable_offline_simulation: bool = False,
    ) -> None:
        _policy(policy_revision)
        if enable_offline_simulation is not True:
            raise AuthorityHeld("ANALYTICS_SESSION_AUTHORITY_OFFLINE_ONLY")
        if not callable(resolve_trusted_acquisition) or not callable(clock):
            raise AuthorityHeld("ANALYTICS_SERVER_DEPENDENCIES_REQUIRED")
        self._policy_revision = policy_revision
        self._resolve_acquisition = resolve_trusted_acquisition
        self._clock = clock
        self._records: dict[str, SessionRecord] = {}
        self._lock = threading.RLock()

    def _now(self) -> datetime:
        return _clock(self._clock())

    def open_session(self, *, site: str) -> str:
        """Create an opaque, random SIMULATED session; consent starts UNKNOWN."""
        _site(site)
        now = self._now()
        try:
            channel, evidence_kind = self._resolve_acquisition()
        except Exception:
            raise AuthorityHeld("ANALYTICS_ACQUISITION_AUTHORITY_UNAVAILABLE") from None
        if (type(channel) is not str or channel not in ALLOWED_CHANNELS
                or type(evidence_kind) is not str
                or evidence_kind not in {
                    "server_observed_direct",
                    "server_verified_referral",
                    "signed_campaign_binding",
                    "server_unknown",
                }):
            raise AuthorityHeld("ANALYTICS_ACQUISITION_SOURCE_UNTRUSTED")
        required_evidence = {
            "direct": "server_observed_direct",
            "organic_search": "server_verified_referral",
            "organic_social": "server_verified_referral",
            "referral": "server_verified_referral",
            "email": "signed_campaign_binding",
            "unknown": "server_unknown",
        }
        if evidence_kind != required_evidence[channel]:
            raise AuthorityHeld("ANALYTICS_ACQUISITION_EVIDENCE_MISMATCH")

        with self._lock:
            # No eviction pretending a session has vanished silently. In
            # production this becomes capacity/retention policy in EmpireDB.
            if len(self._records) >= MAX_SESSIONS:
                raise AuthorityHeld("ANALYTICS_OFFLINE_SESSION_QUOTA_EXCEEDED")
            nonce = secrets.token_hex(16)
            while nonce in self._records:
                nonce = secrets.token_hex(16)
            self._records[nonce] = SessionRecord(
                session_nonce=nonce, site=ORIGIN,
                acquired_channel=channel, acquired_from=evidence_kind,
                opened_at=now, expiry=now + MAX_SESSION_DURATION,
                policy_revision=self._policy_revision,
            )
            return nonce

    def decide(
        self,
        *,
        session_nonce: str,
        decision: str,
        trusted_server_decision: bool,
        policy_revision: str,
    ) -> OfflineDecision:
        """Simulate a SERVER-recorded decision; browser flag not sufficient.

        No decision is evidence of statutory consent. That requires a
        separate CMP/consent ledger and privacy approval before activation.
        """
        if trusted_server_decision is not True:
            raise AuthorityHeld("ANALYTICS_VERIFIED_SERVER_DECISION_REQUIRED")
        if decision not in ("granted", "denied", "revoked"):
            raise AuthorityHeld("ANALYTICS_CONSENT_DECISION_UNSUPPORTED")
        _policy(policy_revision)
        if policy_revision != self._policy_revision:
            raise AuthorityHeld("ANALYTICS_CONSENT_POLICY_MISMATCH")
        now = self._now()
        with self._lock:
            record = self._records.get(session_nonce)
            if record is None:
                raise AuthorityHeld("ANALYTICS_UNKNOWN_SESSION")
            if not record.opened_at <= now < record.expiry:
                raise AuthorityHeld("ANALYTICS_SESSION_EXPIRED_OR_CLOCK_ROLLBACK")
            if record.terminal_revoked:
                raise AuthorityHeld("ANALYTICS_SESSION_REVOKED_NEW_SESSION_REQUIRED")
            if decision == "granted" and record.consent_state == "revoked":
                raise AuthorityHeld("ANALYTICS_SESSION_REVOKED_NEW_SESSION_REQUIRED")
            if decision == "granted" and record.consent_state == "granted":
                raise AuthorityHeld("ANALYTICS_REPEATED_GRANT_REQUIRES_NEW_EVIDENCE")
            new = replace(
                record,
                consent_state=decision,
                consent_revision=record.consent_revision + 1,
                terminal_revoked=decision == "revoked",
            )
            self._records[session_nonce] = new
            return OfflineDecision(status="SIMULATED_SERVER_CONSENT_" + decision.upper(),
                                   consent_revision=new.consent_revision)

    def resolve_consent(self, session_nonce: str) -> bool:
        """Injected into simulate_verified_batch only; deny by default."""
        now = self._now()
        with self._lock:
            rec = self._records.get(session_nonce)
            return bool(
                rec and rec.site == ORIGIN
                and rec.policy_revision == self._policy_revision
                and rec.opened_at <= now < rec.expiry
                and rec.consent_state == "granted"
                and not rec.terminal_revoked
            )

    def resolve_acquisition(self, session_nonce: str) -> str:
        """Fail-closed source resolution only for a consented live record."""
        with self._lock:
            if not self.resolve_consent(session_nonce):
                raise AuthorityHeld("ANALYTICS_CHANNEL_SESSION_UNVERIFIED")
            return self._records[session_nonce].acquired_channel

    def revoke(self, *, session_nonce: str, trusted_server_decision: bool,
               policy_revision: str) -> OfflineDecision:
        return self.decide(
            session_nonce=session_nonce, decision="revoked",
            trusted_server_decision=trusted_server_decision,
            policy_revision=policy_revision,
        )

    def erase(self, *, session_nonce: str) -> None:
        """Offline-only deletion; no retained event history."""
        with self._lock:
            if self._records.pop(session_nonce, None) is None:
                raise AuthorityHeld("ANALYTICS_UNKNOWN_SESSION")

    def readiness(self) -> dict[str, object]:
        """Never publish nonce, session totals or simulated consent grants."""
        return {
            "schema_version": SCHEMA,
            "status": "OFFLINE_SESSION_AUTHORITY_ONLY",
            "site": "empire-ai.co.uk",
            "purpose": PURPOSE,
            "backend_store": "process_memory_simulation",
            "session_issuer_production_active": False,
            "session_cookie_set": False,
            "website_consent_legally_verified": False,
            "durable_empiredb_consent_ledger_active": False,
            "real_website_sessions_verified": False,
            "crm_conversion_verified": False,
            "revenue_verified": False,
            "database_writes": False,
            "outbound_sent": False,
            "execution_authority": "NONE",
        }
