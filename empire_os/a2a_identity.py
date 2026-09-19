"""Governed A2A identity verification with freshness and replay protection."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Protocol


SignatureVerifier = Callable[[str, bytes, str], bool]
Clock = Callable[[], datetime]


class NonceRegistry(Protocol):
    def consume(
        self,
        *,
        agent_id: str,
        key_id: str,
        nonce: str,
        issued_at: str,
    ) -> bool:
        """Return True only when this nonce has not been consumed before."""
        ...


class InMemoryNonceRegistry:
    """Process-local registry intended for tests and local development only."""

    def __init__(self) -> None:
        self._seen: set[tuple[str, str, str]] = set()
        self._lock = Lock()

    def consume(
        self,
        *,
        agent_id: str,
        key_id: str,
        nonce: str,
        issued_at: str,
    ) -> bool:
        key = (str(agent_id), str(key_id), str(nonce))
        with self._lock:
            if key in self._seen:
                return False
            self._seen.add(key)
        return True


@dataclass(frozen=True)
class AgentIdentityClaim:
    agent_id: str
    key_id: str
    nonce: str
    issued_at: str
    signature: str
    requested_scope: str = "discovery"

    def validate(self) -> None:
        for name, value in (
            ("agent_id", self.agent_id),
            ("key_id", self.key_id),
            ("nonce", self.nonce),
            ("issued_at", self.issued_at),
            ("signature", self.signature),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{name} required")
        if self.requested_scope not in {"discovery", "commerce.intent"}:
            raise ValueError(
                "only discovery and commerce.intent scopes are supported"
            )

    def signing_payload(self) -> bytes:
        self.validate()
        return (
            f"{self.agent_id}\n{self.key_id}\n{self.nonce}\n"
            f"{self.issued_at}\n{self.requested_scope}"
        ).encode("utf-8")


@dataclass(frozen=True)
class AgentIdentityDecision:
    authenticated: bool
    agent_id: str | None
    key_id: str | None
    granted_scope: str | None
    reason: str
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_issued_at(value: str) -> datetime:
    raw = str(value or "").strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("issued_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("issued_at must include timezone")
    return parsed.astimezone(timezone.utc)


def verify_agent_identity(
    claim: AgentIdentityClaim,
    *,
    verifier: SignatureVerifier,
    trusted_key_ids: set[str] | frozenset[str],
    nonce_registry: NonceRegistry,
    now: Clock | None = None,
    max_age_seconds: int = 300,
    future_skew_seconds: int = 60,
) -> AgentIdentityDecision:
    claim.validate()
    trusted = {str(key).strip() for key in trusted_key_ids if str(key).strip()}
    if claim.key_id not in trusted:
        return AgentIdentityDecision(
            authenticated=False,
            agent_id=None,
            key_id=claim.key_id,
            granted_scope=None,
            reason="untrusted_key_id",
        )

    issued_at = _parse_issued_at(claim.issued_at)
    current = (now or (lambda: datetime.now(timezone.utc)))()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    age_seconds = (current - issued_at).total_seconds()
    if age_seconds > max(1, int(max_age_seconds)):
        return AgentIdentityDecision(
            authenticated=False,
            agent_id=None,
            key_id=claim.key_id,
            granted_scope=None,
            reason="claim_expired",
        )
    if age_seconds < -max(0, int(future_skew_seconds)):
        return AgentIdentityDecision(
            authenticated=False,
            agent_id=None,
            key_id=claim.key_id,
            granted_scope=None,
            reason="claim_from_future",
        )

    try:
        valid = bool(
            verifier(
                claim.key_id,
                claim.signing_payload(),
                claim.signature,
            )
        )
    except Exception:
        valid = False
    if not valid:
        return AgentIdentityDecision(
            authenticated=False,
            agent_id=None,
            key_id=claim.key_id,
            granted_scope=None,
            reason="signature_invalid",
        )

    try:
        fresh_nonce = bool(
            nonce_registry.consume(
                agent_id=claim.agent_id,
                key_id=claim.key_id,
                nonce=claim.nonce,
                issued_at=claim.issued_at,
            )
        )
    except Exception:
        return AgentIdentityDecision(
            authenticated=False,
            agent_id=None,
            key_id=claim.key_id,
            granted_scope=None,
            reason="nonce_registry_unavailable",
        )
    if not fresh_nonce:
        return AgentIdentityDecision(
            authenticated=False,
            agent_id=None,
            key_id=claim.key_id,
            granted_scope=None,
            reason="nonce_replayed",
        )

    granted_scope = claim.requested_scope
    reason = (
        "authenticated_discovery_only"
        if granted_scope == "discovery"
        else "authenticated_commerce_intent_only"
    )
    return AgentIdentityDecision(
        authenticated=True,
        agent_id=claim.agent_id,
        key_id=claim.key_id,
        granted_scope=granted_scope,
        reason=reason,
    )
