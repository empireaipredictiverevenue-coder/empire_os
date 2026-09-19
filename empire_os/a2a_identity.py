"""Governed A2A discovery identity verification foundation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable


SignatureVerifier = Callable[[str, bytes, str], bool]


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
def verify_agent_identity(
    claim: AgentIdentityClaim,
    *,
    verifier: SignatureVerifier,
    trusted_key_ids: set[str] | frozenset[str],
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
