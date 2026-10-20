"""Synthetic-only API tests, no emails sent, no production DB access."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os import public_gateway
from empire_os.roofing_guide_optin_api import create_roofing_optin_router


ROOT=Path(__file__).resolve().parents[1]
SQL=ROOT/"migrations/empiredb/057_consumer_roofing_optin_staged_20261020.sql"
ORIGIN={"origin":"https://empire-ai.co.uk",
        "sec-fetch-site":"same-origin",
        "content-type":"application/json"}


def payload(**changes):
    x=dict(offer_slug="roofing-cost-guide",
           email="synthetic-only-person@example.test",
           optional_empire_email_updates=True,
           optional_named_buyer_referral=False,
           notice_version="roofing-homeowner-updates-v1",
           website="")
    x.update(changes)
    return x


class SyntheticTestBackend:
    def __init__(self):
        self.enabled=True
        self.received=[]
        self.withdrawal=[]
    def independently_ready(self):
        return self.enabled
    def request_verification(self, **kwargs):
        self.received.append(kwargs)
        return True
    def withdraw_with_token(self, **kwargs):
        self.withdrawal.append(kwargs)


def client(backend=None,allowed=True):
    app=FastAPI()
    app.include_router(create_roofing_optin_router(
        backend=backend,limiter=lambda _:allowed
    ))
    return TestClient(app)


def test_real_gateway_closes_all_routes_without_subscriber_backend():
    with TestClient(public_gateway.app) as app:
        r=app.get("/v1/consumer-optin/roofing/status")
        assert r.status_code==503
        assert r.json()=={"status":"OPTIN_COLLECTION_HELD"}
        assert r.headers["cache-control"]=="no-store"
        assert r.headers["x-robots-tag"]=="noindex, nofollow"
        r=app.post("/v1/consumer-optin/roofing",json=payload(),headers=ORIGIN)
        assert r.status_code==503
        r=app.post("/v1/consumer-optin/roofing/unsubscribe",
                   json={"unsubscribe_token":"a"*40})
        assert r.status_code==503


def test_test_backend_exposes_status_only_when_it_is_ready():
    backend=SyntheticTestBackend()
    with client(backend) as app:
        status=app.get("/v1/consumer-optin/roofing/status")
        assert status.status_code==200
        assert status.json()["notice_version"]=="roofing-homeowner-updates-v1"
        assert status.json()["subscription_product"]=="EMPIRE_AI_OWN_BRAND_HOMEOWNER_UPDATES"
        backend.enabled=False
        assert app.get("/v1/consumer-optin/roofing/status").status_code==503
        assert app.post("/v1/consumer-optin/roofing",
                        headers=ORIGIN,json=payload()).status_code==503
    assert backend.received==[]


def test_synthetic_first_party_own_brand_consent_to_private_backend_only():
    backend=SyntheticTestBackend()
    with client(backend) as app:
        response=app.post("/v1/consumer-optin/roofing",
                          headers=ORIGIN,json=payload())
    assert response.status_code==202
    assert response.json()=={"status":"OPTIN_RECORDED_PENDING_VERIFICATION"}
    assert "synthetic-only-person" not in response.text
    assert len(backend.received)==1
    args=backend.received[0]
    assert args["email"]=="synthetic-only-person@example.test"
    assert args["consent_receipt"]["own_brand_updates"]=="explicit_true"
    assert args["consent_receipt"]["third_party_buyer_sharing"]=="explicit_false"


def test_required_own_brand_consent_separate_from_buyer_sharing():
    backend=SyntheticTestBackend()
    with client(backend) as app:
        for mutation in (
            {"optional_empire_email_updates":False},
            {"optional_named_buyer_referral":True},
            {"website":"robot"},
            {"notice_version":"obsolete"},
            {"offer_slug":"invented-guide"},
        ):
            result=app.post("/v1/consumer-optin/roofing",
                            headers=ORIGIN,json=payload(**mutation))
            assert result.status_code==422
    assert backend.received==[]


def test_bad_headers_payloads_and_untrusted_origin_never_reach_storage():
    backend=SyntheticTestBackend()
    with client(backend) as app:
        for args in (
            {"headers":{**ORIGIN,"origin":"https://untrusted.example"}},
            {"headers":{**ORIGIN,"sec-fetch-site":"cross-site"}},
            {"headers":{**ORIGIN,"content-type":"text/plain"}},
        ):
            r=app.post("/v1/consumer-optin/roofing",json=payload(),**args)
            assert r.status_code in (403,422)
        for invalid in (
            {"email":"not an email"},
            {"email":"x"*270+"@example.test"},
            {"email":"\ncontact@example.test"},
            {"unrequested_field":"should-not-be-saved"},
        ):
            r=app.post("/v1/consumer-optin/roofing",
                       json=payload(**invalid),headers=ORIGIN)
            assert r.status_code==422
    assert not backend.received


def test_rate_limiter_required_and_denied_requests_never_contact_backend():
    backend=SyntheticTestBackend()
    with client(backend,allowed=False) as app:
        r=app.post("/v1/consumer-optin/roofing",
                   json=payload(),headers=ORIGIN)
    assert r.status_code==429
    assert not backend.received


def test_withdrawal_is_opaque_post_only_and_cannot_disclose_person_identity():
    backend=SyntheticTestBackend()
    with client(backend) as app:
        assert app.get("/v1/consumer-optin/roofing/unsubscribe").status_code==405
        cross_site=app.post("/v1/consumer-optin/roofing/unsubscribe",
                     json={"unsubscribe_token":"S"*48},
                     headers={**ORIGIN,"origin":"https://attacker.example"})
        assert cross_site.status_code==403
        bad=app.post("/v1/consumer-optin/roofing/unsubscribe",
                     json={"email":"synthetic-only-person@example.test"},headers=ORIGIN)
        assert bad.status_code==422
        good=app.post("/v1/consumer-optin/roofing/unsubscribe",
                      json={"unsubscribe_token":"S"*48},headers=ORIGIN)
        assert good.status_code==202
        assert good.json()=={"status":"REQUEST_RECEIVED_IF_TOKEN_VALID"}
        assert "synthetic-only-person" not in good.text
    assert backend.withdrawal==[{"token":"S"*48}]


def test_staged_db_is_separate_locked_and_contains_no_public_writes():
    sql=SQL.read_text()
    assert "STAGED ONLY" in sql
    assert "SET LOCAL ROLE empiredb_migrator" in sql
    assert "public.empire_consumer_subscriptions" in sql
    assert "public.empire_consumer_consent_events" in sql
    assert "public.empire_consumer_email_suppressions" in sql
    assert "email_lookup_hmac" in sql and "email_ciphertext bytea" in sql
    assert "pending_verification" in sql
    assert "opt_in_verified" in sql and "unsubscribed" in sql
    assert "BEFORE UPDATE OR DELETE" in sql
    for table in ("subscriptions","consent_events","email_suppressions"):
        assert "ALTER TABLE public.empire_consumer_"+table+" FORCE ROW LEVEL SECURITY" in sql
    assert "GRANT INSERT" not in sql
    assert "GRANT EXECUTE" not in sql
    assert "CREATE POLICY" not in sql
    assert "buyer_subscriptions" not in sql
    assert "prospect_acquisitions" not in sql
    assert "outbound_sent" not in sql


def test_page_never_reuses_business_crm_or_buyer_optin_implicitly():
    site=ROOT/"apps/empire-public-site/src/app/roofing/cost-guide/signup.tsx"
    text=site.read_text()
    assert "optional_named_buyer_referral: false" in text
    assert '"/v1/consumer-optin/roofing/status"' in text
    assert "privacy_notice_url === \"/privacy\"" in text
    assert "unsubscribe" in text.lower()
    for forbidden in ("/v1/checkout/commercial/interests","/v1/leads/direct-intake"):
        assert forbidden not in text
