"""Signed NVIDIA-to-EmpireOS identity + ORIGINAL CRM membership integration.

The subject link and datasource attestor in this module are TEST-ONLY synthetic
approval and dedicated-connector fixtures. The canonical founder membership is
read from the existing EmpireDB via its original dedicated reader on the host.
Never count synthetic attestation as a deployed production connector.
"""
from __future__ import annotations
import base64,json,os
from datetime import datetime,timedelta,timezone
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from empire_os.nvidia_ontology_tenant_policy import (
    DataPlaneAttestation,NvidiaTenantDenied,TenantDeployment,
)
from empire_os.nvidia_ontology_signed_subject_link import PURPOSE,canonical_bytes
from empire_os.nvidia_canonical_membership_adapter import ExistingCrmMembershipAdapter
from empire_os.nvidia_tenant_runtime_factory import build_existing_nvidia_tenant_policy
from empire_os.saas_scale import TenantMembership

TENANT="708efd4b-53b2-43d7-961d-1cecab67f17a"
OTHER="20000000-0000-4000-8000-000000000002"
NOW=datetime(2026,11,18,13,tzinfo=timezone.utc)
ISSUER="http://localhost:33000/api/auth"
DEPLOY=TenantDeployment(TENANT,"synthetic-founder-isolated","synthetic-only-tenant-a")
KEY=Ed25519PrivateKey.generate()
PKEY={"synthetic-issuer-test":KEY.public_key()}


def make_link(tmp_path,*,deployment=DEPLOY,sub="synthetic-oauth-a",
              enterprise_subject="founder:phil_livesley"):
    payload={
      "purpose":PURPOSE,"iss":"empire-os","kid":"synthetic-issuer-test",
      "nvidia_issuer":ISSUER,
      "nvidia_sub":sub,"empire_sub":enterprise_subject,
      "tenant_id":deployment.tenant_id,
      "deployment_id":deployment.deployment_id,
      "issued_at":int(NOW.timestamp()),
      "expires_at":int((NOW+timedelta(minutes=15)).timestamp()),
      "founder_approval_ref":"TEST_ONLY_EPHEMERAL_NOT_FOR_LIVE",
    }
    digest=PURPOSE.encode()+b"\0"+canonical_bytes(payload)
    signature=base64.urlsafe_b64encode(KEY.sign(digest)).rstrip(b"=").decode()
    path=tmp_path/("synthetic-"+deployment.deployment_id+".json")
    path.write_text(json.dumps({"payload":payload,"signature":signature}))
    path.chmod(0o600)
    return path


def data_proof(deployment,*,live=False):
    # A test-only attestor demonstrates the exact required policy interface,
    # NOT runtime backend verification.
    return DataPlaneAttestation(
        tenant_id=deployment.tenant_id,
        deployment_id=deployment.deployment_id,
        datasource_id=deployment.datasource_id,
        mode="dedicated_database",
        verified_at_utc=NOW,
        bound_connector_verified=True,
        no_global_datasource_fallback=True,
        database_isolation_verified=True,
        read_only=True,evidence_ref="TEST_ONLY_NOT_PRODUCTION")
def factory(tmp_path,*,reader=None,attestor=data_proof):
    return build_existing_nvidia_tenant_policy(
        DEPLOY,
        founder_approved_link=make_link(tmp_path),
        existing_empire_issuer_public_keys=PKEY,
        nvidia_oauth_issuer=ISSUER,
        verify_actual_tenant_executor=attestor,
        canonical_reader=reader or ExistingCrmMembershipAdapter(),
        now=lambda:NOW)


def test_full_signed_identity_chain_with_real_original_empiredb_member(tmp_path):
    if not Path("/var/lib/empire-crm-first-party/pilot-runtime.json").is_file():
        pytest.skip("Original live CRM membership source unavailable")
    policy=factory(tmp_path)
    result=policy.authorize("synthetic-oauth-a")
    assert result.allowed is True
    assert result.tenant_id==TENANT
    assert result.status=="CANONICAL_TENANT_DATAPLANE_AUTHORIZED"
    # Do not mistake this for production: synthetic signed link and
    # test-only attestor, genuine CRM member database read.

def test_cross_provider_subject_spoof_cannot_bypass_signed_mapping(tmp_path):
    policy=factory(tmp_path,reader=lambda s,t:TenantMembership(
        tenant_id=t,user_id=s,role="owner"))
    with pytest.raises(NvidiaTenantDenied):
        policy.authorize("different-oauth-subject")
    with pytest.raises(NvidiaTenantDenied):
        policy.authorize("founder:phil_livesley")

def test_dedicated_source_mismatch_denied_even_correct_signed_identity(tmp_path):
    def bad(d):
        from dataclasses import replace
        return replace(data_proof(d),datasource_id="other-tenant-source")
    policy=factory(tmp_path,
        reader=lambda s,t:TenantMembership(tenant_id=t,user_id=s,role="viewer"),
        attestor=bad)
    with pytest.raises(NvidiaTenantDenied):
        policy.authorize("synthetic-oauth-a")

def test_two_proofs_for_different_tenants_not_interchangeable(tmp_path):
    other=TenantDeployment(OTHER,"synthetic-b","tenant-b-source")
    path=make_link(tmp_path,deployment=other,sub="synthetic-oauth-b",
        enterprise_subject="test-user-b")
    with pytest.raises(NvidiaTenantDenied,match="LINK_TENANT_OR_ISSUER_MISMATCH"):
        build_existing_nvidia_tenant_policy(
            DEPLOY,founder_approved_link=path,
            existing_empire_issuer_public_keys=PKEY,
            nvidia_oauth_issuer=ISSUER,
            verify_actual_tenant_executor=data_proof,
            now=lambda:NOW,
        )

def test_missing_actual_sql_execution_attestor_cannot_build(tmp_path):
    with pytest.raises(ValueError,match="actual SQL execution proof"):
        build_existing_nvidia_tenant_policy(
            DEPLOY,founder_approved_link=make_link(tmp_path),
            existing_empire_issuer_public_keys=PKEY,
            nvidia_oauth_issuer=ISSUER,
            verify_actual_tenant_executor=None,
            now=lambda:NOW,
        )

def test_canonical_membership_reader_denies_cross_tenant_even_signed_link(tmp_path):
    # A properly signed link to a tenant without an active EmpireDB
    # membership must not grant permission.
    reader=lambda s,t:None
    policy=factory(tmp_path,reader=reader)
    with pytest.raises(NvidiaTenantDenied):
        policy.authorize("synthetic-oauth-a")

def test_no_new_authority_secrets_or_signer_in_nvidia_factory():
    source=(Path(__file__).resolve().parents[1]/
            "empire_os/nvidia_tenant_runtime_factory.py").read_text()
    assert "Ed25519PrivateKey" not in source
    assert "postgres password" not in source.lower()
    assert "subprocess" not in source
    assert "ExistingCrmMembershipAdapter" in source
    assert "ApprovedNvidiaSubjectLink" in source
