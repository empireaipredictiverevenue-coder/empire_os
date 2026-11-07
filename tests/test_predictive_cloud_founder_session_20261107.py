"""Synthetic founder acceptance using the ORIGINAL signed EmpireOS CRM verifier.

All principals are synthetic and the Data Cloud issuer key is ephemeral.
No actual CRM login, customer secret, live identity or production mutation.
"""
from __future__ import annotations
import json
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI,Request
from fastapi.testclient import TestClient
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
from empire_os.saas_scale import TenantMembership
from empire_os.predictive_cloud_founder_session import (
    DataCloudFounderAuthority,DataCloudPublicVerifier,attach_founder_session,enc,
)
from empire_os.predictive_cloud_gateway_attestation import verify_gateway_attestation

TENANT="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
USER="founder-test"
NOW=1711111111

def minted_crm(private_key,sub=USER,tenant=TENANT,claims=None):
    header={"alg":"EdDSA","typ":"JWT","kid":"crm_test"}
    body={"iss":"empire-os","aud":"empire-revenue-crm","sub":sub,
          "tenant_id":tenant,"scope":"crm:read","iat":NOW,"nbf":NOW,
          "exp":NOW+600,"jti":"crmtoken_abcdefghijklmnop"}
    if claims:body.update(claims)
    part=enc(json.dumps(header,separators=(",",":")).encode())+"."+enc(json.dumps(body,separators=(",",":")).encode())
    return part+"."+enc(private_key.sign(part.encode("ascii")))

@pytest.fixture
def chain():
    crm_key=Ed25519PrivateKey.generate()
    data_key=Ed25519PrivateKey.generate()
    state={"role":"owner","entitled":True,"active":True}
    def read_membership(subject,tenant):
        if not state["active"]:return None
        return TenantMembership(tenant_id=tenant,user_id=subject,role=state["role"])
    verifier=SignedCrmTenantVerifier(
        {"crm_test":crm_key.public_key()},load_membership=read_membership,now=lambda:NOW)
    authority=DataCloudFounderAuthority(
        crm_verifier=verifier,live_membership=read_membership,
        data_entitlement=lambda actor,tenant: state["entitled"] and actor==USER and tenant==TENANT,
        signing_key=data_key,pinned_public_keys={"data_test":data_key.public_key()},
        key_id="data_test",now=lambda:NOW)
    crm=minted_crm(crm_key)
    return authority,state,crm,crm_key

def test_existing_crm_login_exchanges_to_distinct_signed_data_cloud_audience(chain):
    authority,state,crm,key=chain
    proof=authority.exchange(crm)
    assert proof["scope"]=="data:read" and proof["expires_in"]==300
    assert proof["access_token"]!=crm
    principal=authority.verify(proof["access_token"])
    assert principal.tenant_id==TENANT and principal.actor_id==USER
    assert principal.audience=="empire-data-cloud" and principal.membership_checked is True

def test_crm_token_cannot_be_used_as_data_cloud_session(chain):
    authority,state,crm,key=chain
    with pytest.raises(ValueError):
        authority.verify(crm)

@pytest.mark.parametrize("role",["admin","operator","analyst","viewer"])
def test_only_verified_owner_can_exchange(chain,role):
    authority,state,crm,key=chain
    state["role"]=role
    with pytest.raises(PermissionError):
        authority.exchange(crm)

def test_independent_data_entitlement_required(chain):
    authority,state,crm,key=chain
    state["entitled"]=False
    with pytest.raises(PermissionError):
        authority.exchange(crm)

def test_malformed_invalid_signature_or_wrong_audience_rejected(chain):
    authority,state,crm,key=chain
    with pytest.raises(ValueError):
        authority.exchange(minted_crm(Ed25519PrivateKey.generate()))
    with pytest.raises(ValueError):
        authority.exchange(minted_crm(key,claims={"aud":"empire-data-cloud"}))
    proof=authority.exchange(crm)["access_token"]
    wrong=proof[:-3]+("aaa" if not proof.endswith("aaa") else "bbb")
    with pytest.raises(ValueError):
        authority.verify(wrong)

def test_revocation_enforced_on_every_data_session_request(chain):
    authority,state,crm,key=chain
    proof=authority.exchange(crm)["access_token"]
    state["entitled"]=False
    with pytest.raises(PermissionError):
        authority.verify(proof)
    state["entitled"]=True
    state["active"]=False
    with pytest.raises(PermissionError):
        authority.verify(proof)

def test_wrong_tenant_or_subject_denied_from_existing_session(chain):
    authority,state,crm,key=chain
    with pytest.raises(PermissionError):
        authority.exchange(minted_crm(key,tenant=OTHER))
    with pytest.raises(PermissionError):
        authority.exchange(minted_crm(key,sub="other-user"))

def test_expiry_checked_before_membership(chain):
    authority,state,crm,key=chain
    proof=authority.exchange(crm)["access_token"]
    authority.now=lambda:NOW+400
    with pytest.raises(ValueError):
        authority.verify(proof)

def test_gateway_attaches_without_altering_unrelated_routes(chain):
    authority,state,crm,key=chain
    host=FastAPI()
    @host.get("/existing")
    def existing():return {"ok":True}
    @host.get("/v1/data/usage")
    def usage(request:Request):
        principal=verify_gateway_attestation(request,tenant_id=TENANT)
        return {"identity":principal.actor_id}
    attach_founder_session(host,authority,expose_exchange=True)
    with TestClient(host) as client:
        assert client.get("/existing").status_code==200
        assert client.get("/v1/data/usage").status_code==401
        x=client.post("/v1/data/auth/exchange")
        assert x.status_code==401
        x=client.post("/v1/data/auth/exchange",headers={"Authorization":"Bearer "+crm})
        assert x.status_code==200 and x.headers["cache-control"]=="no-store"
        token=x.json()["access_token"]
        assert client.get("/v1/data/usage",headers={"Authorization":"Bearer "+crm}).status_code==401
        assert client.get("/v1/data/usage",headers={"X-Empire-Data-Session":token}).json()=={"identity":USER}
        assert client.get("/v1/data/usage",headers={"X-Empire-Data-Session":token}).headers["cache-control"]=="no-store"
        state["entitled"]=False
        assert client.get("/v1/data/usage",headers={"X-Empire-Data-Session":token}).status_code==403

def test_constructor_does_not_allow_wrong_signing_key(chain):
    authority,state,crm,key=chain
    with pytest.raises(ValueError,match="match pinned verifier"):
        DataCloudFounderAuthority(
            crm_verifier=authority.crm,live_membership=authority.membership,
            data_entitlement=authority.entitlement,signing_key=Ed25519PrivateKey.generate(),
            pinned_public_keys=authority.keys,key_id="data_test",now=lambda:NOW)



def test_public_gateway_verifier_never_possesses_signer_or_crm_private_credentials(chain):
    issuer,state,crm,key=chain
    verifier=DataCloudPublicVerifier(
        live_membership=issuer.membership,data_entitlement=issuer.entitlement,
        pinned_public_keys=issuer.keys,now=lambda:NOW)
    assert not hasattr(verifier, "signer") and not hasattr(verifier, "crm")
    token=issuer.exchange(crm)["access_token"]
    principal=verifier.verify(token)
    assert principal.actor_id==USER
    assert not hasattr(verifier, "exchange")
    app=FastAPI()
    @app.get("/health")
    def health():return {"ok":True}
    @app.get("/v1/data/usage")
    def usage(request:Request):
        p=verify_gateway_attestation(request,tenant_id=TENANT)
        return {"tenant":p.tenant_id}
    attach_founder_session(app,verifier)
    with TestClient(app) as c:
        assert c.get("/health").status_code==200
        assert c.post("/v1/data/auth/exchange",headers={"Authorization":"Bearer "+crm}).status_code==404
        assert c.get("/v1/data/usage").status_code==401
        assert c.get("/v1/data/usage",headers={"X-Empire-Data-Session":token}).status_code==200
        state["entitled"]=False
        assert c.get("/v1/data/usage",headers={"X-Empire-Data-Session":token}).status_code==403


def test_public_gateway_cannot_mount_issuer_routes(chain):
    issuer,state,crm,key=chain
    verifier=DataCloudPublicVerifier(
        live_membership=issuer.membership,data_entitlement=issuer.entitlement,
        pinned_public_keys=issuer.keys,now=lambda:NOW)
    with pytest.raises(ValueError,match="cannot expose token issuer"):
        attach_founder_session(FastAPI(),verifier,expose_exchange=True)


def test_public_verifier_rejects_unsigned_header_spoofing(chain):
    issuer,state,crm,key=chain
    verifier=DataCloudPublicVerifier(
        live_membership=issuer.membership,data_entitlement=issuer.entitlement,
        pinned_public_keys=issuer.keys,now=lambda:NOW)
    app=FastAPI()
    @app.get("/v1/data/usage")
    def usage(request:Request):
        verify_gateway_attestation(request,tenant_id=TENANT)
        return {"ok":True}
    attach_founder_session(app,verifier)
    with TestClient(app) as c:
        x=c.get("/v1/data/usage",headers={"X-Tenant-ID":TENANT,"X-Role":"owner"})
        assert x.status_code==401


def test_data_cloud_issuer_must_not_reuse_crm_signing_key(chain):
    authority,state,crm,crm_private_key=chain
    with pytest.raises(ValueError,match="separate signing keys"):
        DataCloudFounderAuthority(
            crm_verifier=authority.crm,live_membership=authority.membership,
            data_entitlement=authority.entitlement,signing_key=crm_private_key,
            pinned_public_keys={"data_test":crm_private_key.public_key()},
            key_id="data_test",now=lambda:NOW)
