"""Fail-closed two-tenant NVIDIA MCP policy over ORIGINAL EmpireOS roles.

Unit tests use disjoint synthetic-only datasource handles. These do NOT prove
live NVIDIA's global backend has tenant-isolated SQL connections; activation
requires separately verified canonical subject linkage and source isolation.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from empire_os.saas_scale import TenantMembership
from empire_os.nvidia_ontology_tenant_policy import (
    DataPlaneAttestation, MAX_PROOF_AGE_SECONDS, NvidiaTenantAccessPolicy,
    NvidiaTenantDenied, TenantDeployment,
)

A="10000000-0000-4000-8000-000000000001"
B="20000000-0000-4000-8000-000000000002"
NOW=datetime(2026,11,18,12,0,tzinfo=timezone.utc)
DEPLOY_A=TenantDeployment(tenant_id=A,deployment_id="nvidia-a",datasource_id="synthetic-a")
DEPLOY_B=TenantDeployment(tenant_id=B,deployment_id="nvidia-b",datasource_id="synthetic-b")

def proof(deployment,**updates):
    return replace(DataPlaneAttestation(
        tenant_id=deployment.tenant_id,
        deployment_id=deployment.deployment_id,
        datasource_id=deployment.datasource_id,
        mode="dedicated_database",
        verified_at_utc=NOW,
        bound_connector_verified=True,
        no_global_datasource_fallback=True,
        database_isolation_verified=True,
        read_only=True,
        evidence_ref="canonical-tenant-db-probe-only",
    ),**updates)

def harness(deployment=DEPLOY_A, *,
            linker=None, memberships=None, attestor=None,
            now=NOW):
    links={"oauth-a":"canonical-user-a","oauth-b":"canonical-user-b"}
    members={
        ("canonical-user-a",A):TenantMembership(
            tenant_id=A,user_id="canonical-user-a",role="viewer"),
        ("canonical-user-b",B):TenantMembership(
            tenant_id=B,user_id="canonical-user-b",role="viewer"),
    }
    if linker is None:linker=links.get
    if memberships is None:memberships=members.get
    if attestor is None:attestor=proof
    return NvidiaTenantAccessPolicy(
        deployment,
        subject_linker=linker,
        membership_reader=lambda subject,tenant:memberships((subject,tenant)),
        attest_datasource=attestor,
        now=lambda:now,
    )

def test_two_disjoint_tenants_are_authorized_only_on_own_deployment():
    a=harness(DEPLOY_A)
    b=harness(DEPLOY_B)
    assert a.authorize("oauth-a").allowed
    assert b.authorize("oauth-b").allowed
    with pytest.raises(NvidiaTenantDenied):
        a.authorize("oauth-b")
    with pytest.raises(NvidiaTenantDenied):
        b.authorize("oauth-a")

@pytest.mark.parametrize("subject",[None,"","unknown","tenant-a","canonical-user-a"])
def test_missing_or_client_forged_subject_denied(subject):
    with pytest.raises(NvidiaTenantDenied):
        harness().authorize(subject)

def test_missing_internal_link_denied_even_if_canonical_membership_exists():
    with pytest.raises(NvidiaTenantDenied,match="TRUSTED_SUBJECT_LINK_MISSING"):
        harness(linker=lambda _:None).authorize("oauth-a")

def test_absent_any_trusted_dependency_fails_closed():
    for attr in ("subject_linker","membership_reader","attest_datasource"):
        callbacks={"subject_linker":lambda _:"canonical-user-a",
                   "membership_reader":lambda u,t:TenantMembership(
                       tenant_id=t,user_id=u,role="viewer"),
                   "attest_datasource":proof}
        callbacks[attr]=None
        p=NvidiaTenantAccessPolicy(DEPLOY_A,**callbacks)
        with pytest.raises(NvidiaTenantDenied,match="AUTHORITY_NOT_CONNECTED"):
            p.authorize("oauth-a")

def test_disabled_canonical_membership_denies_own_tenant():
    m=TenantMembership(tenant_id=A,user_id="canonical-user-a",
                       role="viewer",status="disabled")
    with pytest.raises(NvidiaTenantDenied,match="MEMBERSHIP_DENIED"):
        harness(memberships=lambda _:m).authorize("oauth-a")

def test_canonical_membership_tenant_mismatch_denies():
    m=TenantMembership(tenant_id=B,user_id="canonical-user-a",role="owner")
    with pytest.raises(NvidiaTenantDenied,match="MEMBERSHIP_MISMATCH"):
        harness(memberships=lambda _:m).authorize("oauth-a")

def test_canonical_member_subject_mismatch_denies():
    m=TenantMembership(tenant_id=A,user_id="another-user",role="viewer")
    with pytest.raises(NvidiaTenantDenied,match="MEMBERSHIP_MISMATCH"):
        harness(memberships=lambda _:m).authorize("oauth-a")

@pytest.mark.parametrize("updates",[
    {"tenant_id":B},
    {"deployment_id":"nvidia-b"},
    {"datasource_id":"synthetic-b"},
    {"bound_connector_verified":False},
    {"no_global_datasource_fallback":False},
    {"database_isolation_verified":False},
    {"read_only":False},
    {"mode":"global_unscoped"},
    {"mode":"empiredb_forced_rls"},  # requires same-session SQL proof, not a separate preflight
    {"evidence_ref":""},
])
def test_wrong_or_unverified_datasource_proof_denies(updates):
    with pytest.raises(NvidiaTenantDenied):
        harness(attestor=lambda d:proof(d,**updates)).authorize("oauth-a")

def test_missing_or_stale_dataplane_proof_denies():
    with pytest.raises(NvidiaTenantDenied):
        harness(attestor=lambda _:None).authorize("oauth-a")
    with pytest.raises(NvidiaTenantDenied,match="STALE"):
        harness(attestor=lambda d:proof(d,verified_at_utc=NOW-timedelta(seconds=301))
                ).authorize("oauth-a")

def test_future_attestation_denies():
    with pytest.raises(NvidiaTenantDenied,match="STALE"):
        harness(attestor=lambda d:proof(d,verified_at_utc=NOW+timedelta(seconds=1))
                ).authorize("oauth-a")

def test_trusted_lookup_failure_fails_closed_not_open():
    def broken(_):
        raise TimeoutError("canonical membership offline")
    with pytest.raises(NvidiaTenantDenied,match="LOOKUP_UNAVAILABLE"):
        harness(memberships=broken).authorize("oauth-a")

@pytest.mark.parametrize("tenant_id",["tenant-a","NOT-A-UUID","10000000-0000-4000-8000-000000000001 "])
def test_deployment_requires_canonical_uuid(tenant_id):
    with pytest.raises(NvidiaTenantDenied):
        TenantDeployment(tenant_id=tenant_id,
                         deployment_id="nvidia-a",datasource_id="synthetic-a")

def test_unscoped_synthetic_existing_nvidia_deployment_is_denied():
    # An OAuth Viewer can be signed into NVIDIA without canonical EmpireOS
    # subject mapping or a tenant-isolated connector. That is not tenant auth.
    policy=NvidiaTenantAccessPolicy(DEPLOY_A)
    with pytest.raises(NvidiaTenantDenied):
        policy.authorize("founder-nvidia-oauth-subject")

def test_caller_selected_tenant_or_question_not_in_authority_method():
    import inspect
    signature=inspect.signature(NvidiaTenantAccessPolicy.authorize)
    assert list(signature.parameters)==["self","verified_oauth_subject"]
    # The caller never provides datasource_id/tenant_id/SQL question to
    # the policy; these come from pinned deployment + trusted callbacks.

def test_current_original_signed_crm_authority_not_replaced():
    from pathlib import Path
    from empire_os.tenant_isolation import authorize_tenant_resource
    source=(Path(__file__).resolve().parents[1]/"empire_os/revenue_crm_signed_auth.py").read_text()
    assert "class EmpireDbCrmMembershipReader" in source
    assert "public.empire_crm_read_member" in source
    assert callable(authorize_tenant_resource)
