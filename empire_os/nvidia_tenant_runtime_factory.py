"""Compose existing verified EmpireOS and NVIDIA tenant authorities.

No new account authority, token issuer, registry or database.
The only identity crosswalk is separately approved and signed by the
original EmpireOS issuer; original CRM membership remains checked fresh on
each MCP tool call through its dedicated least-privilege reader. Data-plane
attestation must be from the actual tenant-dedicated backend executor.

This factory does not activate itself, create users, or expose services.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable,Mapping
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from empire_os.nvidia_ontology_signed_subject_link import ApprovedNvidiaSubjectLink
from empire_os.nvidia_canonical_membership_adapter import ExistingCrmMembershipAdapter
from empire_os.nvidia_ontology_tenant_policy import (
    DataPlaneAttestation,NvidiaTenantAccessPolicy,TenantDeployment,
)


def build_existing_nvidia_tenant_policy(
    deployment:TenantDeployment,
    *,
    founder_approved_link:Path,
    existing_empire_issuer_public_keys:Mapping[str,Ed25519PublicKey|bytes],
    nvidia_oauth_issuer:str,
    verify_actual_tenant_executor:Callable[
        [TenantDeployment],DataPlaneAttestation|None
    ]|None,
    canonical_reader:ExistingCrmMembershipAdapter|None=None,
    now=None,
)->NvidiaTenantAccessPolicy:
    """No implicit fallback: absent attestor/identity/key = hard refusal."""
    if not isinstance(deployment,TenantDeployment):
        raise TypeError("preapproved immutable tenant deployment required")
    if not callable(verify_actual_tenant_executor):
        raise ValueError("tenant-exclusive actual SQL execution proof required")
    link=ApprovedNvidiaSubjectLink(
        founder_approved_link,
        pinned_public_keys=existing_empire_issuer_public_keys,
        deployment=deployment,
        nvidia_issuer=nvidia_oauth_issuer,
        now=now,
    )
    reader=canonical_reader or ExistingCrmMembershipAdapter()
    if not callable(reader):
        raise ValueError("original canonical CRM membership reader required")
    return NvidiaTenantAccessPolicy(
        deployment,
        subject_linker=link,
        membership_reader=reader,
        attest_datasource=verify_actual_tenant_executor,
        now=now,
    )
