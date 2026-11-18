"""Existing EmpireOS tenant-authority gate for NVIDIA Auto Ontology MCP.

This is a staged addition to the existing NVIDIA MCP service, not a new
identity/DB system. It reuses TenantMembership + authorize_tenant_resource
and requires independently verified OAuth subject linking and
tenant-dedicated/RLS-backed execution evidence.

No claim from a client, a user-supplied tenant ID, or an NLP question can
select or widen the deployment's datasource. Missing linkage/proof denies.
Nothing is activated simply by importing this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Literal
from uuid import UUID

from empire_os.saas_scale import TenantMembership
from empire_os.tenant_isolation import TenantResourceRef, authorize_tenant_resource

MODE = Literal["dedicated_database", "empiredb_forced_rls"]
# Multi-tenant Postgres RLS will only be enabled when its tenant proof is
# bound to the very same backend SQL session, not a separate metadata check.
VALID_MODES = frozenset({"dedicated_database"})
MAX_PROOF_AGE_SECONDS = 300


class NvidiaTenantDenied(PermissionError):
    """No bearer, no canonical binding or no tenant-dedicated data plane."""


def canonical_uuid(value: str) -> str:
    if not isinstance(value, str):
        raise NvidiaTenantDenied("TENANT_UUID_REQUIRED")
    try:
        text = str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise NvidiaTenantDenied("TENANT_UUID_REQUIRED") from exc
    if text != value:
        raise NvidiaTenantDenied("NONCANONICAL_TENANT_UUID")
    return text


@dataclass(frozen=True)
class TenantDeployment:
    tenant_id: str
    deployment_id: str
    datasource_id: str

    def __post_init__(self) -> None:
        canonical_uuid(self.tenant_id)
        if not self.deployment_id or not self.datasource_id:
            raise NvidiaTenantDenied("PINNED_DATASOURCE_REQUIRED")
        if any(len(x) > 128 or x.strip() != x for x in
               (self.deployment_id, self.datasource_id)):
            raise NvidiaTenantDenied("INVALID_PINNED_DEPLOYMENT")


@dataclass(frozen=True)
class DataPlaneAttestation:
    tenant_id: str
    deployment_id: str
    datasource_id: str
    mode: MODE
    verified_at_utc: datetime
    bound_connector_verified: bool
    no_global_datasource_fallback: bool
    database_isolation_verified: bool
    read_only: bool
    evidence_ref: str


@dataclass(frozen=True)
class TenantVerdict:
    allowed: bool
    status: str
    tenant_id: str | None = None


class NvidiaTenantAccessPolicy:
    """Enforce the original EmpireOS authority on every NVIDIA tool request.

    Every dependency is an *internal trusted server-side* function:
      - subject_linker: preapproved OAuth subject -> canonical EmpireOS subject;
        never a request header, email guess, browser-provided tenant or claim.
      - membership_reader: existing EmpireDbCrmMembershipReader callable with
        canonical subject and pinned deployment tenant, not a new registry.
      - attest_datasource: read-only runtime verifier of tenant-bound
        connector with no shared fallback; no callers can supply the result.

    A proper production integration must supply these functions and have
    platform approval for the actual data plane before enabling the gate.
    """

    def __init__(
        self,
        deployment: TenantDeployment,
        *,
        subject_linker: Callable[[str], str | None] | None = None,
        membership_reader: Callable[[str, str], TenantMembership | None] | None = None,
        attest_datasource: Callable[[TenantDeployment], DataPlaneAttestation | None] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.deployment = deployment
        self._subject_linker = subject_linker
        self._membership_reader = membership_reader
        self._attest_datasource = attest_datasource
        self._now = now or (lambda: datetime.now(timezone.utc))

    def authorize(self, verified_oauth_subject: str | None) -> TenantVerdict:
        """Only FastMCP's verified access-token subject is accepted by caller."""
        if not isinstance(verified_oauth_subject, str) or not verified_oauth_subject.strip():
            raise NvidiaTenantDenied("VERIFIED_OAUTH_SUBJECT_REQUIRED")
        if not all(callable(x) for x in (
            self._subject_linker, self._membership_reader, self._attest_datasource,
        )):
            raise NvidiaTenantDenied("CANONICAL_TENANT_AUTHORITY_NOT_CONNECTED")
        try:
            subject = self._subject_linker(verified_oauth_subject)
            if not isinstance(subject, str) or not subject or len(subject) > 128:
                raise NvidiaTenantDenied("TRUSTED_SUBJECT_LINK_MISSING")
            membership = self._membership_reader(subject, self.deployment.tenant_id)
            if not isinstance(membership, TenantMembership):
                raise NvidiaTenantDenied("CANONICAL_MEMBERSHIP_MISSING")
            if (membership.user_id != subject
                or membership.tenant_id != self.deployment.tenant_id):
                raise NvidiaTenantDenied("CANONICAL_MEMBERSHIP_MISMATCH")
            decision = authorize_tenant_resource(
                membership=membership,
                resource=TenantResourceRef(
                    tenant_id=self.deployment.tenant_id,
                    resource_type="nvidia_ontology_tenant_deployment",
                    resource_id=self.deployment.deployment_id,
                ),
                permission="read",
            )
            if not decision.allowed:
                raise NvidiaTenantDenied("CANONICAL_MEMBERSHIP_DENIED")
            proof = self._attest_datasource(self.deployment)
            if not isinstance(proof, DataPlaneAttestation):
                raise NvidiaTenantDenied("TENANT_DATAPLANE_PROOF_MISSING")
            if (canonical_uuid(proof.tenant_id) != self.deployment.tenant_id
                or proof.deployment_id != self.deployment.deployment_id
                or proof.datasource_id != self.deployment.datasource_id
                or proof.mode not in VALID_MODES
                or proof.bound_connector_verified is not True
                or proof.no_global_datasource_fallback is not True
                or proof.database_isolation_verified is not True
                or proof.read_only is not True
                or not isinstance(proof.evidence_ref, str)
                or not proof.evidence_ref.strip()
                or len(proof.evidence_ref) > 256):
                raise NvidiaTenantDenied("TENANT_DATAPLANE_SCOPE_MISMATCH")
            now = self._now()
            then = proof.verified_at_utc
            if (not isinstance(now, datetime)
                or not isinstance(then, datetime)
                or now.tzinfo is None or then.tzinfo is None):
                raise NvidiaTenantDenied("DATAPLANE_ATTESTATION_TIME_INVALID")
            age = (now.astimezone(timezone.utc) -
                   then.astimezone(timezone.utc)).total_seconds()
            if not 0 <= age <= MAX_PROOF_AGE_SECONDS:
                raise NvidiaTenantDenied("DATAPLANE_ATTESTATION_STALE")
            return TenantVerdict(
                allowed=True, status="CANONICAL_TENANT_DATAPLANE_AUTHORIZED",
                tenant_id=self.deployment.tenant_id,
            )
        except NvidiaTenantDenied:
            raise
        except Exception as exc:
            raise NvidiaTenantDenied("CANONICAL_TENANT_LOOKUP_UNAVAILABLE") from exc
