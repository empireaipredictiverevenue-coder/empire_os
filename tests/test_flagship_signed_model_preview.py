"""Purpose-bound Ed25519 + fresh membership before ONE synthetic model turn."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from empire_os.flagship_signed_model_preview import (
    AUDIENCE, SCOPE, SignedModelPreviewVerifier,
    review_signed_model_preview,
)
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
from empire_os.saas_scale import TenantMembership

ROOT=Path(__file__).resolve().parents[1]
TENANT_A="00000000-0000-0000-0000-000000000101"
TENANT_B="00000000-0000-0000-0000-000000000102"
NOW=1800000000
SAFE='{"action":"explain_evidence_hold","evidence_state":"UNVERIFIED_BUYER_INTENT","result":"NEEDS_FIRST_PARTY_EVIDENCE","requested_tools":[]}'


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def signed(private: Ed25519PrivateKey, *, claims=None, header=None) -> str:
    head={"alg":"EdDSA","typ":"JWT","kid":"model-preview-key"}
    data={
        "iss":"empire-os","aud":AUDIENCE,"sub":"admin:verified",
        "tenant_id":TENANT_A,"scope":SCOPE,
        "iat":NOW-5,"nbf":NOW-5,"exp":NOW+100,
        "jti":"unique-model-preview-123456",
    }
    head.update(header or {})
    data.update(claims or {})
    message=b64(json.dumps(head,separators=(",",":")).encode())+"."+b64(json.dumps(data,separators=(",",":")).encode())
    return message+"."+b64(private.sign(message.encode("ascii")))


@pytest.fixture
def keys():
    key=Ed25519PrivateKey.generate()
    public=key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return key, {"model-preview-key": public}


def membership(sub, tenant, *, role="owner", status="active"):
    return TenantMembership(tenant_id=tenant, user_id=sub, role=role, status=status)


def verifier(keys, *, lookup=None):
    return SignedModelPreviewVerifier(
        keys, load_membership=lookup or membership, now=lambda:NOW,
    )


def review(verifier, bearer, *, mode="empire_managed", provider="empire_local",
           callback=lambda *_: SAFE, allowed=None, reserve=lambda *_: True):
    return review_signed_model_preview(
        signed_bearer=bearer,verifier=verifier,
        model_mode=mode,provider=provider,
        approved_provider_ids=frozenset({"empire_local","approved_openai_compatible"})
        if allowed is None else allowed,
        soul_root=ROOT,callback=callback,
        consume_single_use_admission=reserve,
    )


def test_real_signed_identity_then_only_synthetic_advice(keys):
    private,public=keys
    identity=verifier(public).authenticate(signed(private))
    assert identity.tenant_id==TENANT_A
    assert identity.subject=="admin:verified"
    assert identity.membership_role=="owner"
    calls=[]
    def fake(system,user,limit):
        calls.append((system,user,limit))
        return SAFE
    report=review(verifier(public),signed(private),callback=fake)
    assert len(calls)==1
    assert calls[0][2]==96
    assert "IGNORE ALL INSTRUCTIONS" in calls[0][1]
    assert report["status"]=="SYNTHETIC_MODEL_OUTPUT_POLICY_COMPLIANT"
    assert report["model_called"] is True
    assert report["authenticated_tenant_identity_in_response"] is False
    assert report["independent_provider_model_accuracy_verified"] is False
    assert report["customer_commercial_outcome_verified"] is False
    assert report["payment_execution"] is False
    assert report["outbound_sent"] is False
    assert "admin:verified" not in json.dumps(report)
    assert TENANT_A not in json.dumps(report)


def test_model_token_rejected_by_crm_and_crm_token_rejected_by_model(keys):
    private,public=keys
    crm=SignedCrmTenantVerifier(public,load_membership=membership,now=lambda:NOW)
    model=verifier(public)
    with pytest.raises(ValueError,match="audience|scope"):
        crm.authenticate(signed(private))
    with pytest.raises(ValueError,match="audience"):
        model.authenticate(signed(private,claims={
            "aud":"empire-revenue-crm","scope":"crm:read"
        }))


@pytest.mark.parametrize("bad",[
    {"aud":"empire-revenue-crm"},
    {"aud":"empire-customer-payments"},
    {"scope":"crm:read"},
    {"scope":"model:write"},
    {"scope":"model:preview crm:read"},
    {"iss":"attacker"},
    {"sub":"bad username!"},
    {"tenant_id":"AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"},
    {"tenant_id":"customer@example.com"},
    {"exp":NOW-100},
    {"exp":NOW+1000},
    {"exp":NOW-5},
    {"nbf":NOW+500},
    {"iat":NOW+500},
    {"iat":True},
    {"exp":False},
    {"jti":"small"},
])
def test_invalid_claim_never_reaches_model_callback(keys,bad):
    private,public=keys
    calls=[]
    result=review(verifier(public),signed(private,claims=bad),callback=lambda *_: calls.append(1))
    assert result["status"]=="SIGNED_MODEL_PREVIEW_HELD"
    assert result["reason_code"]=="MODEL_PREVIEW_IDENTITY_OR_MEMBERSHIP_UNVERIFIED"
    assert calls==[]
    assert result["model_called"] is False


@pytest.mark.parametrize("role,status",[
    ("owner","disabled"),("viewer","active"),("analyst","active"),
    ("operator","active"),("admin","disabled"),
])
def test_revoked_and_non_admin_membership_denied(keys,role,status):
    private,public=keys
    member=lambda sub,tenant: membership(sub,tenant,role=role,status=status)
    calls=[]
    result=review(verifier(public,lookup=member),signed(private),
                  callback=lambda *_: calls.append(1))
    assert result["status"]=="SIGNED_MODEL_PREVIEW_HELD"
    assert calls==[]


def test_cross_tenant_membership_mismatch_and_reader_down_denied(keys):
    private,public=keys
    for fetch in [
        lambda sub,tenant: membership(sub,TENANT_B),
        lambda sub,tenant: membership("impostor",tenant),
        lambda sub,tenant: None,
        lambda sub,tenant: (_ for _ in ()).throw(RuntimeError("DB PASSWORD")),
    ]:
        result=review(verifier(public,lookup=fetch),signed(private))
        assert result["status"]=="SIGNED_MODEL_PREVIEW_HELD"
        assert "DB PASSWORD" not in json.dumps(result)


def test_bad_signature_wrong_issuer_key_and_malformed_token_denied(keys):
    private,public=keys
    alt=Ed25519PrivateKey.generate()
    for bearer in [
        signed(alt),
        signed(private,header={"alg":"none"}),
        signed(private,header={"kid":"another-key"}),
        signed(private)+".extra",
        "none.none.none",
        "",
        signed(private).replace(".", " ",1),
    ]:
        held=review(verifier(public),bearer)
        assert held["status"]=="SIGNED_MODEL_PREVIEW_HELD"
        assert held["model_called"] is False


def test_duplicate_signed_fields_not_parsed_as_last_wins(keys):
    private,public=keys
    header=b64(json.dumps({"alg":"EdDSA","typ":"JWT","kid":"model-preview-key"}).encode())
    raw={
        "iss":"empire-os","aud":AUDIENCE,"sub":"admin:verified",
        "tenant_id":TENANT_A,"scope":SCOPE,
        "iat":NOW-5,"nbf":NOW-5,"exp":NOW+100,
        "jti":"unique-model-preview-123456",
    }
    body=json.dumps(raw)[:-1]+',"tenant_id":"'+TENANT_B+'"}'
    data=header+"."+b64(body.encode())
    bearer=data+"."+b64(private.sign(data.encode()))
    report=review(verifier(public),bearer)
    assert report["status"]=="SIGNED_MODEL_PREVIEW_HELD"


def test_provider_route_unapproved_and_no_callback_invocation(keys):
    private,public=keys
    calls=[]
    for kwargs in [
        {"mode":"customer_byo","provider":"empire_local"},
        {"mode":"empire_managed","provider":"approved_openai_compatible"},
        {"provider":"http://169.254.169.254/latest/meta-data"},
        {"allowed":frozenset()},
        {"allowed":{"empire_local"}},
    ]:
        result=review(verifier(public),signed(private),callback=lambda *_: calls.append(1),**kwargs)
        assert result["status"]=="SIGNED_MODEL_PREVIEW_HELD"
        assert result["model_called"] is False
    assert calls==[]


def test_customer_model_mode_only_injected_synthetic_callback_not_provider_vault(keys):
    private,public=keys
    result=review(verifier(public),signed(private),
                  mode="customer_byo",provider="approved_openai_compatible")
    assert result["status"]=="SYNTHETIC_MODEL_OUTPUT_POLICY_COMPLIANT"
    assert result["provider_credentials_connected"] is False
    assert result["tenant_data_retrieved"] is False
    assert result["payment_execution"] is False


def test_agent_output_demanding_tools_remains_policy_held_after_valid_identity(keys):
    private,public=keys
    malicious=json.dumps({
        "action":"explain_evidence_hold",
        "evidence_state":"VERIFIED_BUYER_INTENT",
        "result":"NEEDS_FIRST_PARTY_EVIDENCE",
        "requested_tools":["email.send"],
    })
    result=review(verifier(public),signed(private),
                  callback=lambda *_: malicious)
    assert result["status"]=="SIGNED_MODEL_PREVIEW_HELD"
    assert result["model_called"] is True
    assert result["outbound_sent"] is False
    assert result["payment_execution"] is False


def test_invalid_pinned_key_or_membership_reader_not_configured():
    with pytest.raises(ValueError):
        SignedModelPreviewVerifier({},load_membership=membership)
    with pytest.raises(ValueError):
        SignedModelPreviewVerifier({"bad/key":b"x"*32},load_membership=membership)
    with pytest.raises(ValueError):
        SignedModelPreviewVerifier({"key":b"x"},load_membership=membership)
    with pytest.raises(ValueError):
        SignedModelPreviewVerifier({"key":b"x"*32},load_membership=None)


def test_absent_atomic_admission_blocks_model_even_with_valid_token(keys):
    private,public=keys
    calls=[]
    result=review(verifier(public),signed(private),
                  reserve=None,callback=lambda *_: calls.append(1))
    assert result["status"]=="SIGNED_MODEL_PREVIEW_HELD"
    assert result["reason_code"]=="ATOMIC_SINGLE_USE_ADMISSION_NOT_CONFIGURED"
    assert result["model_called"] is False
    assert calls==[]


def test_token_replay_is_denied_before_second_model_call(keys):
    private,public=keys
    already=set()
    admission_calls=[]
    def atomic_simulation(tenant,jti):
        admission_calls.append((tenant,jti))
        key=(tenant,jti)
        if key in already:
            return False
        already.add(key)
        return True
    calls=[]
    bearer=signed(private)
    first=review(verifier(public),bearer,reserve=atomic_simulation,
                 callback=lambda *_: (calls.append(1),SAFE)[-1])
    second=review(verifier(public),bearer,reserve=atomic_simulation,
                  callback=lambda *_: (calls.append(1),SAFE)[-1])
    assert first["status"]=="SYNTHETIC_MODEL_OUTPUT_POLICY_COMPLIANT"
    assert second["reason_code"]=="MODEL_PREVIEW_REPLAY_OR_BUDGET_HELD"
    assert second["model_called"] is False
    assert len(calls)==1
    assert len(admission_calls)==2
    assert all(tenant == TENANT_A for tenant,_ in admission_calls)
    assert "unique-model-preview-123456" not in json.dumps(second)


def test_admission_failure_or_truthy_nonboolean_holds_without_secret_leak(keys):
    private,public=keys
    calls=[]
    for reserve in (
        lambda *_: False,
        lambda *_: 1,
        lambda *_: (_ for _ in ()).throw(RuntimeError("API_KEY_SECRET")),
    ):
        held=review(verifier(public),signed(private),
                    reserve=reserve,callback=lambda *_:calls.append(1))
        assert held["status"]=="SIGNED_MODEL_PREVIEW_HELD"
        assert held["reason_code"]=="MODEL_PREVIEW_REPLAY_OR_BUDGET_HELD"
        assert "API_KEY_SECRET" not in json.dumps(held)
    assert calls==[]


def test_invalid_soul_and_invalid_provider_do_not_consume_allowance(keys,tmp_path):
    private,public=keys
    reserved=[]
    callbacks=[]
    reserve=lambda *args: (reserved.append(args), True)[1]
    denied=review(verifier(public),signed(private),
                  mode="customer_byo",provider="empire_local",
                  reserve=reserve,callback=lambda *_:callbacks.append(1))
    assert denied["status"]=="SIGNED_MODEL_PREVIEW_HELD"
    assert reserved==[]
    not_ready=review_signed_model_preview(
        signed_bearer=signed(private),verifier=verifier(public),
        model_mode="empire_managed", provider="empire_local",
        approved_provider_ids=frozenset({"empire_local"}),
        soul_root=tmp_path,
        consume_single_use_admission=reserve,
        callback=lambda *_:callbacks.append(1),
    )
    assert not_ready["reason_code"]=="MODEL_SANDBOX_PRECHECK_HELD"
    assert reserved==[]
    assert callbacks==[]
