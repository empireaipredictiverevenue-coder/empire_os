"""Source-rights UI/endpoint tests: original signed CRM, rights reader, founder.

Fixture-only Ed25519 keys and fake read-only DB connection. No production keys,
company data, identity records, source rights changes or service restarts.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import time
from pathlib import Path

import empire_os

EXTENSION=Path("/opt/empire-ai/data-cloud-founder-pilot-20261107/empire_os")
if str(EXTENSION) not in empire_os.__path__:
    empire_os.__path__.insert(0,str(EXTENSION))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.testclient import TestClient
from starlette.routing import Route
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
from empire_os.saas_scale import TenantMembership
from empire_os.predictive_cloud_founder_session import DataCloudFounderAuthority
from empire_os.predictive_cloud_v410_rights_reader import EmpireDbHeldSourceRightsReader

SCRIPT=Path(__file__).resolve().parents[1]/(
    "scripts/private_crm_original_v411_source_review_candidate_20261108.py")
S=importlib.util.spec_from_file_location("original_v411_live_held_overlay_staged",SCRIPT)
m=importlib.util.module_from_spec(S)
S.loader.exec_module(m)

TENANT="00000000-0000-0000-0000-000000000101"
OTHER="00000000-0000-0000-0000-000000000102"
ACTOR="first-party-founder-test"
NOW=int(time.time())
FAKE_HTML='<button id="verify-data-cloud" type="button" disabled>Verify Data Cloud</button>'
FAKE_JS='''  async function base() {
    sessionBearer = null; sessionUntil = 0; sessionGeneration++;
    byId("verify-data-cloud").disabled = true;
      byId("verify-data-cloud").disabled = false;
  }
  byId("verify-data-cloud").addEventListener("click", verifyDataCloudExchange);
'''


def encode(x):
    return base64.urlsafe_b64encode(x).rstrip(b"=").decode()


def signed_token(key, *, actor=ACTOR, tenant=TENANT, exp=NOW+300):
    h={"alg":"EdDSA","typ":"JWT","kid":"local"}
    p={"iss":"empire-os","aud":"empire-revenue-crm","sub":actor,
       "tenant_id":tenant,"scope":"crm:read","iat":NOW-5,"nbf":NOW-5,
       "exp":exp,"jti":"source-review-test-session-0001"}
    head=encode(json.dumps(h,separators=(",",":")).encode())
    body=encode(json.dumps(p,separators=(",",":")).encode())
    msg=(head+"."+body)
    return msg+"."+encode(key.sign(msg.encode()))


class Cursor:
    def __init__(self,*,decision,tenant,source):
        self.values=iter([
            ("empire_predictive_rights_login",),
            (decision,tenant,source,"PRIVATE_PREDICTIVE_RESEARCH_ONLY",
             decision=="REVOKED_HELD",False,False,"none"),
            None,
        ])
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def execute(self,sql,params=None):pass
    def fetchone(self):return next(self.values)

class Connection:
    def __init__(self,**k):self.kw=k
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def cursor(self):return Cursor(**self.kw)


def app(*,role="owner",entitled=True,reader_unavailable=False,decision="PENDING_HELD"):
    key=Ed25519PrivateKey.generate()
    cloud=Ed25519PrivateKey.generate()
    def member(actor,tenant):
        if actor!=ACTOR or tenant!=TENANT:return None
        return TenantMembership(user_id=actor,tenant_id=tenant,
                                role=role,status="active")
    crm=SignedCrmTenantVerifier({"local":key.public_key()},
                                 load_membership=member,now=lambda:NOW)
    authority=DataCloudFounderAuthority(
        crm_verifier=crm, live_membership=member,
        data_entitlement=lambda actor,tenant:entitled and actor==ACTOR and tenant==TENANT,
        signing_key=cloud,pinned_public_keys={"cloud":cloud.public_key()},
        key_id="cloud",now=lambda:NOW)
    def connect(_dsn):
        if reader_unavailable:raise OSError("research fixture disconnected")
        return Connection(decision=decision,tenant=TENANT,source=m.SOURCE_DIGEST)
    reader=EmpireDbHeldSourceRightsReader("synthetic-dsn",connect_factory=connect)
    api=FastAPI()
    for path,content,media in (
        (m.HTML_PATH,FAKE_HTML,"text/html"),
        (m.JS_PATH,FAKE_JS,"text/javascript"),
    ):
        api.router.routes.insert(0,Route(
            path,endpoint=lambda request,text=content,kind=media:Response(
                text,media_type=kind,headers={"Cache-Control":"no-store",
                    "Content-Security-Policy":"default-src 'none'; script-src 'self'"}),
            methods=["GET"]))
    m.attach_private_source_review(
        api,crm,authority,reader,
        expected_html_sha=__import__("hashlib").sha256(FAKE_HTML.encode()).hexdigest(),
        expected_js_sha=__import__("hashlib").sha256(FAKE_JS.encode()).hexdigest())
    return TestClient(api),key


def test_original_signed_crm_owner_can_read_only_held_without_new_authority():
    client,key=app()
    token=signed_token(key)
    res=client.post(m.SOURCE_PATH,headers={"Authorization":"Bearer "+token})
    assert res.status_code==200
    assert res.json()=={
        "schema_version":"empire.private_crm.v411.source_review.v1",
        "mode":"OBSERVE","rights_decision":"PENDING_HELD",
        "source_rights_verified":False,"customer_delivery_authorized":False,
        "customer_forecast_verified":False,"execution_authority":"none"
    }
    assert res.headers["cache-control"]=="no-store"
    assert "content-length" in res.headers
    assert TENANT not in res.text and token not in res.text
    assert "dsn" not in res.text and "password" not in res.text


def test_existing_crm_page_is_additive_and_browser_token_stays_in_closure():
    client,_=app()
    html=client.get(m.HTML_PATH)
    js=client.get(m.JS_PATH)
    assert html.status_code==200 and js.status_code==200
    assert html.text.count('id="verify-predictive-source"')==1
    assert html.text.count('id="verify-data-cloud"')==1
    assert js.text.count('byId("verify-predictive-source").addEventListener')==1
    assert js.text.count('byId("verify-data-cloud").addEventListener')==1
    assert js.text.count('byId("verify-predictive-source").disabled = false;')==1
    assert "sessionBearer" in js.text
    assert "localStorage" not in js.text and "sessionStorage" not in js.text
    assert "navigator.clipboard" not in js.text
    assert html.headers["cache-control"]=="no-store"
    assert js.headers["cache-control"]=="no-store"


def test_missing_malformed_invalid_expired_tokens_denied():
    client,key=app()
    assert client.post(m.SOURCE_PATH).status_code==401
    assert client.post(m.SOURCE_PATH,headers={"Authorization":"Bearer invalid"}).status_code==401
    bad=signed_token(Ed25519PrivateKey.generate())
    assert client.post(m.SOURCE_PATH,headers={"Authorization":"Bearer "+bad}).status_code==401
    expired=signed_token(key,exp=NOW-100)
    assert client.post(m.SOURCE_PATH,headers={"Authorization":"Bearer "+expired}).status_code==401


def test_nonfounder_and_revoked_entitlement_denied():
    client,key=app(role="viewer")
    assert client.post(m.SOURCE_PATH,headers={"Authorization":"Bearer "+signed_token(key)}).status_code in (401,403)
    client,key=app(entitled=False)
    assert client.post(m.SOURCE_PATH,headers={"Authorization":"Bearer "+signed_token(key)}).status_code==403


def test_other_tenant_denied_not_reflected():
    client,key=app()
    res=client.post(m.SOURCE_PATH,headers={
        "Authorization":"Bearer "+signed_token(key,tenant=OTHER)})
    assert res.status_code==401
    assert TENANT not in res.text and OTHER not in res.text


def test_original_restricted_reader_unavailable_returns_503_held():
    client,key=app(reader_unavailable=True)
    res=client.post(m.SOURCE_PATH,headers={"Authorization":"Bearer "+signed_token(key)})
    assert res.status_code==503
    assert "reader_unavailable" in res.text
    assert "source rights verified" not in res.text.lower()


def test_revoked_source_never_accepted_for_customer_output():
    client,key=app(decision="REVOKED_HELD")
    r=client.post(m.SOURCE_PATH,headers={"Authorization":"Bearer "+signed_token(key)})
    assert r.status_code==200
    assert r.json()["rights_decision"]=="REVOKED_HELD"
    assert r.json()["customer_forecast_verified"] is False


def test_body_and_query_parameters_forbidden():
    client,key=app()
    auth={"Authorization":"Bearer "+signed_token(key)}
    assert client.post(m.SOURCE_PATH+"?tenant="+OTHER,headers=auth).status_code==400
    assert client.post(m.SOURCE_PATH,headers=auth,content=b"forbidden").status_code==400


def test_no_customer_routes_or_double_mount():
    client,key=app()
    assert client.get("/v1/data/search").status_code==404
    assert client.get("/v1/data/site-audits").status_code==404
    assert client.get(m.SOURCE_PATH).status_code==405


def test_private_crm_source_overlay_rejects_missing_original_anchor():
    try:m.patch_html("<html>changed</html>")
    except RuntimeError as e:assert "contract_changed" in str(e)
    else:raise AssertionError("untrusted CRM page accepted")
    try:m.patch_js("changed")
    except RuntimeError as e:assert "contract_changed" in str(e)
    else:raise AssertionError("untrusted CRM js accepted")
