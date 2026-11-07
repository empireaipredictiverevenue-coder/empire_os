"""Guarded mount accepts only existing routes, and requires signed founder sessions."""
from __future__ import annotations
import json
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from empire_os.predictive_cloud_founder_session import (
    DataCloudPublicVerifier, DataCloudFounderAuthority, enc,
)
from empire_os.predictive_cloud_gateway_attestation import verify_gateway_attestation
from empire_os.predictive_cloud_route_assembly import (
    attach_existing_customer_routes, CUSTOMER_ROUTES, RELEASE_REQUIREMENTS, inspect_routes,
)
from empire_os.saas_scale import TenantMembership
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

TENANT="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ACTOR="founder-test"
NOW=1770480000

@pytest.fixture
def components():
    key=Ed25519PrivateKey.generate()
    state={"entitled":True}
    def membership(actor,tenant):
        return TenantMembership(tenant_id=tenant,user_id=actor,role="owner")
    verifier=DataCloudPublicVerifier(
        live_membership=membership,
        data_entitlement=lambda actor,tenant: state["entitled"] and actor==ACTOR and tenant==TENANT,
        pinned_public_keys={"pilot_data":key.public_key()},
        now=lambda:NOW,
    )
    def candidate(extra=False):
        app=FastAPI()
        @app.get("/v1/data/usage")
        def usage(request:Request):
            principal=verify_gateway_attestation(request,tenant_id=TENANT)
            return {"tenant":principal.tenant_id,"actor":principal.actor_id}
        @app.post("/v1/data/search")
        def search(request:Request):
            verify_gateway_attestation(request,tenant_id=TENANT)
            return {"status":"rights_held"}
        @app.post("/v1/data/site-audits")
        def site(request:Request):
            verify_gateway_attestation(request,tenant_id=TENANT)
            return {"status":"audit_adapter_held"}
        if extra:
            @app.get("/v1/data/admin")
            def admin():return {"error":"bad"}
        return app
    def evidence(override=None):
        good={k:True for k in RELEASE_REQUIREMENTS}
        good.update(override or {})
        return lambda:good
    def data_token():
        head={"alg":"EdDSA","typ":"JWT","kid":"pilot_data"}
        claims={"iss":"empire-os","aud":"empire-data-cloud","sub":ACTOR,"tenant_id":TENANT,
                "scope":"data:read","iat":NOW,"nbf":NOW,"exp":NOW+300,
                "jti":"pilot-signed-session-0123456789"}
        signing=enc(json.dumps(head,separators=(",",":")).encode())+"."+enc(json.dumps(claims,separators=(",",":")).encode())
        return signing+"."+enc(key.sign(signing.encode("ascii")))
    return verifier,state,candidate,evidence,data_token

def test_guards_missing_release_evidence_without_mutating_host(components):
    verifier,state,candidate,evidence,token=components
    host=FastAPI()
    baseline=inspect_routes(host)
    with pytest.raises(RuntimeError,match="release_preflight"):
        attach_existing_customer_routes(host,candidate(),verifier,release_evidence=evidence({"production_meter_role_verified":False}))
    assert inspect_routes(host)==baseline
    assert not hasattr(host.state,"data_cloud_routes_attached")

def test_rejects_any_extra_customer_endpoint(components):
    verifier,state,candidate,evidence,token=components
    host=FastAPI()
    with pytest.raises(RuntimeError,match="route_contract"):
        attach_existing_customer_routes(host,candidate(extra=True),verifier,release_evidence=evidence())

def test_rejects_duplicate_routes(components):
    verifier,state,candidate,evidence,token=components
    host=FastAPI()
    @host.get("/v1/data/usage")
    def existing():return {}
    with pytest.raises(RuntimeError,match="route_collision"):
        attach_existing_customer_routes(host,candidate(),verifier,release_evidence=evidence())

def test_only_public_verifier_allowed(components):
    verifier,state,candidate,evidence,token=components
    with pytest.raises(RuntimeError,match="public_verifier_only"):
        attach_existing_customer_routes(FastAPI(),candidate(),object(),release_evidence=evidence())

def test_live_route_contract_with_synthetic_signed_founder_token(components):
    verifier,state,candidate,evidence,token=components
    host=FastAPI()
    @host.get("/original")
    def original():return {"untouched":True}
    names=attach_existing_customer_routes(host,candidate(),verifier,release_evidence=evidence())
    assert names==("/v1/data/search","/v1/data/site-audits","/v1/data/usage")
    with TestClient(host) as client:
        assert client.get("/original").json()=={"untouched":True}
        assert client.get("/v1/data/usage").status_code==401
        assert client.get("/v1/data/usage",headers={"X-Tenant-ID":TENANT}).status_code==401
        r=client.get("/v1/data/usage",headers={"X-Empire-Data-Session":token()})
        assert r.status_code==200,r.text
        assert r.json()=={"tenant":TENANT,"actor":ACTOR}
        assert r.headers["cache-control"]=="no-store"
        state["entitled"]=False
        assert client.get("/v1/data/usage",headers={"X-Empire-Data-Session":token()}).status_code==403

def test_cannot_attach_twice(components):
    verifier,state,candidate,evidence,token=components
    host=FastAPI()
    attach_existing_customer_routes(host,candidate(),verifier,release_evidence=evidence())
    with pytest.raises(RuntimeError,match="already_attached"):
        attach_existing_customer_routes(host,candidate(),verifier,release_evidence=evidence())

def test_does_not_intercept_other_data_owner_routes(components):
    verifier,state,candidate,evidence,token=components
    host=FastAPI()
    @host.get("/v1/data/other-owner-health")
    def untouched():return {"other_owner":"preserved"}
    attach_existing_customer_routes(host,candidate(),verifier,release_evidence=evidence())
    with TestClient(host) as client:
        result=client.get("/v1/data/other-owner-health")
        assert result.status_code==200,result.text
        assert result.json()=={"other_owner":"preserved"}
        result=client.get("/v1/data/other-owner-health",headers={"X-Empire-Data-Session":"invalid"})
        assert result.status_code==200,result.text


@pytest.mark.parametrize("missing",[
    "fresh_local_restore_receipt_verified",
    "offhost_physical_recovery_verified",
    "dba_sql_and_acl_acceptance_verified",
    "existing_gateway_rollback_verified",
    "founder_only_pilot_verified",
    "billing_and_paid_provider_calls_disabled",
])
def test_real_release_requirements_cannot_be_bypassed(components,missing):
    verifier,state,candidate,evidence,token=components
    host=FastAPI()
    before=inspect_routes(host)
    with pytest.raises(RuntimeError,match="release_preflight"):
        attach_existing_customer_routes(host,candidate(),verifier,release_evidence=evidence({missing:False}))
    assert inspect_routes(host)==before
    assert len(host.user_middleware)==0


def test_live_gateway_rejects_late_mount_before_mutating_routes(components):
    verifier,state,candidate,evidence,token=components
    host=FastAPI()
    with TestClient(host) as client:
        assert client.get("/health").status_code==404
        before=inspect_routes(host)
        with pytest.raises(RuntimeError,match="before_startup"):
            attach_existing_customer_routes(host,candidate(),verifier,release_evidence=evidence())
        assert inspect_routes(host)==before
        assert len(host.user_middleware)==0
