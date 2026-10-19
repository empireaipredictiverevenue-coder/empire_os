"""Dedicated signed customer model-preview identity, NOT CRM scope reuse.

Trust: independently provisioned Ed25519 public key -> strictly validated
model:preview token -> live canonical membership check -> synthetic no-tool
Empire-model/BYOM policy. There is no public endpoint, issuer, API credential,
hosted inference route, persistence or production activation in this module.

DO NOT use SignedCrmTenantVerifier as a model tool authorizer: its audience
and scope are deliberately different, to prevent confused-deputy access.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Any
from uuid import UUID
import re
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from empire_os.revenue_crm_signed_auth import (
    _decode, _object, _KEY_ID, _SUBJECT, _JTI,
    MAX_TOKEN_BYTES, MAX_LIFETIME_SECONDS, ALLOWED_CLOCK_SKEW_SECONDS,
)
from empire_os.saas_scale import TenantMembership
from empire_os.flagship_customer_agent_sandbox import (
    ALLOWED_MODELS, TrustedSandboxSession, sandbox_preflight,
    run_synthetic_model_sandbox,
)
from pathlib import Path

AUDIENCE = "empire-predictive-model-preview"
SCOPE = "model:preview"
ISSUER = "empire-os"
SCHEMA = "empire.flagship_signed_model_preview.v1"
AUTHENTICATED_PREVIEW_ROLES = frozenset({"owner", "admin"})


@dataclass(frozen=True)
class VerifiedModelPreviewIdentity:
    """Internal evidence from real verifier; not accepted from any user JSON."""
    tenant_id: str
    subject: str
    membership_role: str
    token_id: str


class SignedModelPreviewVerifier:
    """Model-specific key ring and audience; never store signing secrets."""

    def __init__(
        self,
        public_keys: Mapping[str, bytes | Ed25519PublicKey],
        *,
        load_membership: Callable[[str, str], TenantMembership | None],
        now: Callable[[], int] | None = None,
    ) -> None:
        if not callable(load_membership):
            raise ValueError("trusted tenant membership reader required")
        if not isinstance(public_keys, Mapping) or not public_keys:
            raise ValueError("model-preview pinned issuer key required")
        keys = {}
        for key_id, raw in public_keys.items():
            if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
                raise ValueError("invalid model-preview key ID")
            if isinstance(raw, Ed25519PublicKey):
                key = raw
            elif isinstance(raw, bytes) and len(raw) == 32:
                key = Ed25519PublicKey.from_public_bytes(raw)
            else:
                raise ValueError("invalid model-preview public key")
            keys[key_id] = key
        self._keys = keys
        self._member = load_membership
        self._now = now or (lambda: int(time.time()))

    def authenticate(self, token: str) -> VerifiedModelPreviewIdentity:
        if not isinstance(token, str) or not 1 <= len(token) <= MAX_TOKEN_BYTES:
            raise ValueError("invalid model-preview bearer")
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("malformed model-preview bearer")
        header = _object(parts[0], 384)
        if (set(header) != {"alg", "typ", "kid"}
                or header["alg"] != "EdDSA" or header["typ"] != "JWT"):
            raise ValueError("model-preview header or algorithm rejected")
        kid = header["kid"]
        if not isinstance(kid, str) or not _KEY_ID.fullmatch(kid):
            raise ValueError("invalid model-preview key identifier")
        key = self._keys.get(kid)
        if key is None:
            raise ValueError("untrusted model-preview key")
        signature = _decode(parts[2], 64)
        if len(signature) != 64:
            raise ValueError("invalid model-preview signature")
        try:
            key.verify(signature, (parts[0] + "." + parts[1]).encode("ascii"))
        except InvalidSignature as exc:
            raise ValueError("invalid model-preview signature") from exc

        claims = _object(parts[1], 1536)
        if set(claims) != {
            "iss", "aud", "sub", "tenant_id", "scope",
            "iat", "nbf", "exp", "jti",
        }:
            raise ValueError("unexpected model-preview signed claims")
        if (claims["iss"] != ISSUER or claims["aud"] != AUDIENCE
                or claims["scope"] != SCOPE):
            raise ValueError("model-preview issuer/scope/audience mismatch")
        if (not isinstance(claims["sub"], str)
                or not _SUBJECT.fullmatch(claims["sub"])
                or not isinstance(claims["jti"], str)
                or not _JTI.fullmatch(claims["jti"])):
            raise ValueError("invalid model-preview subject or token ID")
        iat, nbf, exp = (claims[key] for key in ("iat", "nbf", "exp"))
        if any(type(value) is not int for value in (iat, nbf, exp)):
            raise ValueError("integer model-preview token times required")
        now = int(self._now())
        if (iat > now + ALLOWED_CLOCK_SKEW_SECONDS
                or nbf > now + ALLOWED_CLOCK_SKEW_SECONDS
                or exp <= now - ALLOWED_CLOCK_SKEW_SECONDS
                or exp <= iat or exp - iat > MAX_LIFETIME_SECONDS
                or nbf > exp):
            raise ValueError("model-preview token lifetime invalid")
        try:
            tenant = str(UUID(str(claims["tenant_id"])))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("invalid model-preview tenant UUID") from exc
        if tenant != claims["tenant_id"]:
            raise ValueError("noncanonical model-preview tenant")

        # Signature alone can outlive revoked memberships. Always confirm
        # this user's exact tenant scope from the existing read-only reader.
        try:
            membership = self._member(claims["sub"], tenant)
            valid = (
                isinstance(membership, TenantMembership)
                and membership.tenant_id == tenant
                and membership.user_id == claims["sub"]
                and membership.role in AUTHENTICATED_PREVIEW_ROLES
                and membership.can("read")
            )
        except Exception:
            valid = False
        if not valid:
            raise ValueError("active model-preview membership required")
        return VerifiedModelPreviewIdentity(
            tenant_id=tenant, subject=claims["sub"],
            membership_role=membership.role, token_id=claims["jti"],
        )


def review_signed_model_preview(
    *,
    signed_bearer: str,
    verifier: SignedModelPreviewVerifier,
    model_mode: str,
    provider: str,
    callback: Callable[[str, str, int], str],
    soul_root: Path,
    approved_provider_ids: frozenset[str],
    consume_single_use_admission: Callable[[str, str], bool] | None = None,
) -> dict[str, Any]:
    """Only one synthetic evaluation; authorization is not model authority.

    The installed client/router is NOT invoked here unless an operator
    explicitly injects a trusted callback. No customer data or API secret
    accepted as input and no public request handler is wired.
    """
    def denied(reason: str) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA,
            "status": "SIGNED_MODEL_PREVIEW_HELD",
            "reason_code": reason,
            "authenticated_tenant_identity_in_response": False,
            "model_called": False,
            "provider_credentials_connected": False,
            "tenant_data_retrieved": False,
            "outbound_sent": False,
            "payment_execution": False,
            "database_writes": False,
            "execution_authority": "none",
        }
    if not isinstance(verifier, SignedModelPreviewVerifier):
        return denied("DEDICATED_VERIFIER_REQUIRED")
    try:
        identity = verifier.authenticate(signed_bearer)
    except (ValueError, TypeError):
        return denied("MODEL_PREVIEW_IDENTITY_OR_MEMBERSHIP_UNVERIFIED")
    if (not isinstance(approved_provider_ids, frozenset)
            or provider not in approved_provider_ids
            or model_mode not in ALLOWED_MODELS
            or provider not in ALLOWED_MODELS[model_mode]
            or not callable(callback)):
        return denied("TENANT_PROVIDER_APPROVAL_UNVERIFIED")
    session = TrustedSandboxSession(
        tenant_id=identity.tenant_id,
        authenticated_tenant_id=identity.tenant_id,
        authenticated_server_session=True,
        mode=model_mode,
        provider=provider,
        provider_config_approved=True,
        max_tokens=96, max_cycles=1,
        external_spend_limit_cents=0,
        use_real_customer_data=False, tool_execution_enabled=False,
        outbound_enabled=False, payments_enabled=False,
    )
    preflight = sandbox_preflight(session, soul_root=soul_root)
    if preflight.get("status") != "SYNTHETIC_SINGLE_TURN_TEST_READY":
        return denied("MODEL_SANDBOX_PRECHECK_HELD")
    # An issuer-signed bearer is replayable until expiry. No model call may
    # happen without a server-side single-use reservation. In production
    # this MUST be an atomic durable tenant-keyed operation, not a set.
    if not callable(consume_single_use_admission):
        return denied("ATOMIC_SINGLE_USE_ADMISSION_NOT_CONFIGURED")
    try:
        reserved = consume_single_use_admission(identity.tenant_id, identity.token_id)
    except Exception:
        reserved = False
    if reserved is not True:
        return denied("MODEL_PREVIEW_REPLAY_OR_BUDGET_HELD")
    report = run_synthetic_model_sandbox(
        session, soul_root=soul_root, model_callback=callback,
    )
    return {
        "schema_version": SCHEMA,
        "status": (
            "SYNTHETIC_MODEL_OUTPUT_POLICY_COMPLIANT"
            if report.get("status") == "POLICY_COMPLIANT_SYNTHETIC_RESPONSE"
            else "SIGNED_MODEL_PREVIEW_HELD"
        ),
        "reason_code": report.get("reason_code", "UNKNOWN_MODEL_HOLD"),
        "model_mode": model_mode,
        "provider": provider,
        "soul_digest": report.get("soul_digest"),
        "model_called": report.get("model_called") is True,
        "synthetic_output_checked": True,
        "authenticated_tenant_identity_in_response": False,
        "independent_provider_model_accuracy_verified": False,
        "customer_commercial_outcome_verified": False,
        "provider_credentials_connected": False,
        "tenant_data_retrieved": False,
        "outbound_sent": False,
        "payment_execution": False,
        "database_writes": False,
        "execution_authority": "none",
    }


def review_signed_model_preview_readiness() -> dict[str, Any]:
    """Safe Founder-only release gap status, not a provider health test."""
    return {
        "schema_version": SCHEMA,
        "status": "DEDICATED_SIGNED_PREVIEW_TESTED_NOT_DEPLOYED",
        "signed_audience": AUDIENCE,
        "signed_scope": SCOPE,
        "existing_crm_read_scope_is_separate": True,
        "fresh_canonical_membership_required": True,
        "owner_or_admin_only": True,
        "independent_preview_public_keys_deployed": False,
        "signed_issuer_active": False,
        "durable_atomic_nonce_and_quota_admission_active": False,
        "server_tenant_binding_connected": False,
        "hosted_byom_secret_vault_connected": False,
        "public_model_preview_route_created": False,
        "customer_data_to_model_authorized": False,
        "customer_model_activation_authorized": False,
        "model_tool_execution_authorized": False,
        "outbound_authorized": False,
        "payments_authorized": False,
        "model_accuracy_proven": False,
        "execution_authority": "none",
    }
