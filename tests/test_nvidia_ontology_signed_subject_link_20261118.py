"""Original EmpireOS pinned Ed25519 issuer, signed NVIDIA identity link tests."""
from __future__ import annotations
import base64,json
from datetime import datetime,timezone,timedelta
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from empire_os.nvidia_ontology_tenant_policy import NvidiaTenantDenied,TenantDeployment
from empire_os.nvidia_ontology_signed_subject_link import (
    ApprovedNvidiaSubjectLink,PURPOSE,ISSUER,canonical_bytes
)

TENANT_A="10000000-0000-4000-8000-000000000001"
TENANT_B="20000000-0000-4000-8000-000000000002"
DEPLOY_A=TenantDeployment(TENANT_A,"dedicated-a","source-a")
NOW=datetime(2026,11,18,13,tzinfo=timezone.utc)
ISSUER_URL="http://localhost:33000/api/auth"
PRIVATE=Ed25519PrivateKey.generate()
PUB=PRIVATE.public_key()

def artifact(tmp_path,**mutations):
    payload={
      "purpose":PURPOSE,"iss":ISSUER,"kid":"existing-empire-issuer",
      "nvidia_issuer":ISSUER_URL,
      "nvidia_sub":"approved-nvidia-subject-a",
      "empire_sub":"existing-empire-user-a",
      "tenant_id":TENANT_A,
      "deployment_id":"dedicated-a",
      "issued_at":int(NOW.timestamp()),
      "expires_at":int((NOW+timedelta(minutes=30)).timestamp()),
      "founder_approval_ref":"existing-signed-approval-proof-a",
    }
    payload.update(mutations)
    message=PURPOSE.encode()+b"\0"+canonical_bytes(payload)
    signature=base64.urlsafe_b64encode(PRIVATE.sign(message)).rstrip(b"=").decode()
    path=tmp_path/"signed-link.json"
    path.write_text(json.dumps({"payload":payload,"signature":signature}))
    path.chmod(0o600)
    return path

def verifier(path,**kwargs):
    return ApprovedNvidiaSubjectLink(
        path,pinned_public_keys={"existing-empire-issuer":PUB},
        deployment=DEPLOY_A,nvidia_issuer=ISSUER_URL,
        now=lambda:NOW,**kwargs)

def test_verified_exact_original_nvidia_subject_to_empire_identity(tmp_path):
    link=verifier(artifact(tmp_path))
    assert link("approved-nvidia-subject-a")=="existing-empire-user-a"
    assert link("approved-nvidia-subject-b") is None
    assert link("existing-empire-user-a") is None

def test_signature_rejects_user_manipulated_identity_or_tenant(tmp_path):
    path=artifact(tmp_path)
    document=json.loads(path.read_text())
    for field,value in (("nvidia_sub","attacker"),("empire_sub","other-empire-user"),
                        ("tenant_id",TENANT_B),("deployment_id","deployment-b"),
                        ("founder_approval_ref","fake-approval")):
        original=document["payload"][field]
        document["payload"][field]=value
        path.write_text(json.dumps(document))
        with pytest.raises(NvidiaTenantDenied,match="LINK_SIGNATURE_INVALID"):
            verifier(path)
        document["payload"][field]=original

@pytest.mark.parametrize("field,value",[
    ("purpose","empire-crm-jwt"),
    ("iss","another-issuer"),
    ("nvidia_issuer","https://wrong-idp"),
    ("tenant_id",TENANT_B),
    ("deployment_id","another-deployment"),
    ("expires_at",int((NOW+timedelta(days=2)).timestamp())),
    ("issued_at",int((NOW+timedelta(minutes=1)).timestamp())),
    ("expires_at",int((NOW-timedelta(minutes=1)).timestamp())),
])
def test_rejected_even_if_validly_signed_when_wrong_purpose_scope_or_lifetime(tmp_path,field,value):
    with pytest.raises(NvidiaTenantDenied):
        verifier(artifact(tmp_path,**{field:value}))

def test_pinned_key_rotation_unknown_key_denied(tmp_path):
    path=artifact(tmp_path)
    with pytest.raises(NvidiaTenantDenied,match="UNTRUSTED_LINK_KEY"):
        ApprovedNvidiaSubjectLink(path,
             pinned_public_keys={"other-issuer":PUB},deployment=DEPLOY_A,
             nvidia_issuer=ISSUER_URL,now=lambda:NOW)

def test_world_readable_artifact_denied(tmp_path):
    path=artifact(tmp_path)
    path.chmod(0o644)
    with pytest.raises(NvidiaTenantDenied,match="NOT_PRIVATE"):
        verifier(path)

def test_missing_or_symlink_artifact_denied(tmp_path):
    missing=tmp_path/"unknown.json"
    with pytest.raises(NvidiaTenantDenied):
        verifier(missing)
    actual=artifact(tmp_path)
    link=tmp_path/"sym.json"
    link.symlink_to(actual)
    with pytest.raises(NvidiaTenantDenied):
        verifier(link)

def test_expiry_checked_at_each_call_without_new_token_or_cache(tmp_path):
    path=artifact(tmp_path)
    current=[NOW]
    policy=ApprovedNvidiaSubjectLink(
        path,pinned_public_keys={"existing-empire-issuer":PUB},
        deployment=DEPLOY_A,nvidia_issuer=ISSUER_URL,
        now=lambda:current[0])
    assert policy("approved-nvidia-subject-a")=="existing-empire-user-a"
    current[0]=NOW+timedelta(minutes=30)
    assert policy("approved-nvidia-subject-a") is None

def test_extra_fields_and_duplicate_json_props_fail_closed(tmp_path):
    path=artifact(tmp_path)
    signed=json.loads(path.read_text())
    signed["payload"]["untrusted_override"]=TENANT_B
    path.write_text(json.dumps(signed))
    with pytest.raises(NvidiaTenantDenied):
        verifier(path)
    path.write_text('{"payload":{},"payload":{},"signature":"x"}')
    with pytest.raises(NvidiaTenantDenied):
        verifier(path)

def test_original_crm_token_is_not_interchangeable_with_signed_link(tmp_path):
    from empire_os.revenue_crm_signed_auth import AUTHORIZATION_AUDIENCE
    assert AUTHORIZATION_AUDIENCE!="empire-os/nvidia-ontology-tenant-link/v1"
    with pytest.raises(NvidiaTenantDenied):
        verifier(artifact(tmp_path,purpose=AUTHORIZATION_AUDIENCE))
