"""Bounded CRM anonymous-boundary canary; no private customer read or login."""
import json
from urllib.error import HTTPError

import pytest

from scripts import probe_first_party_sales_http_readonly as canary

GOOD_HEALTH = {
    "ok": True, "service": "empire-crm-first-party-pilot",
    "mode": "APPROVED_READ_ONLY_PILOT",
    "outbound_authority": "none",
    "payment_authority": "none",
    "database_provisioning": False,
}
HEADERS = {
    "Cache-Control": "no-store", "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
}


def fixture(*, leak=False, weak_header=False, wrong_health=False, denied=401):
    calls = []

    def fake(path):
        calls.append(path)
        if path == "/health":
            data = {**GOOD_HEALTH}
            if wrong_health:
                data["outbound_authority"] = "auto"
            return 200, "application/json", HEADERS, json.dumps(data).encode()
        if path in canary.PRIVATE_CRM_PATHS:
            protection = {**HEADERS}
            if weak_header:
                protection["Cache-Control"] = "public"
            return 200 if leak else denied, "", protection, (
                b'{"private_prospect_email":"buyer@example.test"}' if leak else b""
            )
        raise AssertionError("UNEXPECTED_PRIVATE_PATH:" + path)

    return fake, calls


def test_existing_private_crm_healthy_and_both_anonymous_routes_fail_closed():
    fetch, calls = fixture()
    report = canary.inspect_private_crm_auth(fetch)
    assert report["private_crm_auth_boundary_verified"] is True
    assert report["private_crm_healthy"] is True
    assert report["anonymous_prospect_access_denied"] is True
    assert report["anonymous_buyer_access_denied"] is True
    assert report["founder_login_authenticated"] is False
    assert report["private_crm_customer_rows_read"] is False
    assert report["founder_crm_delivery_verified"] is False
    assert calls == list(canary.PRIVATE_CRM_PATHS)
    assert "buyer@example.test" not in json.dumps(report)


@pytest.mark.parametrize("kwargs,reason", [
    ({"leak":True}, "PRIVATE_CRM_ANONYMOUS_ACCESS_NOT_VERIFIED"),
    ({"weak_header":True}, "PRIVATE_CRM_ANONYMOUS_ACCESS_NOT_VERIFIED"),
    ({"wrong_health":True}, "PRIVATE_CRM_HEALTH_UNVERIFIED"),
])
def test_weak_auth_or_drift_never_becomes_delivered_customer(kwargs,reason):
    fetch, calls=fixture(**kwargs)
    report=canary.inspect_private_crm_auth(fetch)
    assert report["private_crm_auth_boundary_verified"] is False
    assert report["private_crm_reason_code"] == reason
    assert report["founder_crm_delivery_verified"] is False
    assert report["private_crm_customer_rows_read"] is False


def test_anonymous_403_also_counts_as_refusal_not_logged_in():
    report=canary.inspect_private_crm_auth(fixture(denied=403)[0])
    assert report["private_crm_auth_boundary_verified"] is True
    assert report["founder_login_authenticated"] is False


def test_missing_credentialless_crm_is_not_zero_buyer_count():
    def offline(_):
        raise canary.CanaryHeld("PRIVATE_CRM_AUTH_BOUNDARY_UNAVAILABLE")
    report=canary.inspect_private_crm_auth(offline)
    assert report["private_crm_auth_boundary_verified"] is False
    assert report["private_crm_reason_code"] == "PRIVATE_CRM_AUTH_BOUNDARY_UNAVAILABLE"
    assert "visible_total_prospects" not in report


def test_private_transport_strict_allowlist_no_redirect_or_post(monkeypatch):
    monkeypatch.setattr(canary, "build_opener",lambda *_: (
        (_ for _ in ()).throw(AssertionError("FORBIDDEN_IO"))))
    for path in [
        "//host", "/v1/revenue-crm/../secrets", "/docs",
        "/v1/revenue-crm/prospects?all=true", "/v1/revenue-crm/login",
        "http://localhost:8783/health",
    ]:
        with pytest.raises(canary.CanaryHeld,match="UNAPPROVED_PRIVATE_CRM_PATH"):
            canary.fetch_private_crm_get(path)


def test_unauthenticated_transport_uses_get_and_never_follow_redirect(monkeypatch):
    seen=[]
    class Response:
        status=200
        headers={"Content-Type":"application/json",**HEADERS}
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def read(self,n):
            assert n==4097
            return json.dumps(GOOD_HEALTH).encode()
    class Opener:
        def open(self,request,timeout):
            seen.append((request.full_url,request.get_method(),timeout))
            return Response()
    monkeypatch.setattr(canary,"build_opener",lambda *_:Opener())
    code,ctype,headers,data=canary.fetch_private_crm_get("/health")
    assert (code,ctype)==(200,"application/json")
    assert headers==HEADERS
    assert json.loads(data)==GOOD_HEALTH
    assert seen==[("http://127.0.0.1:8783/health","GET",5)]


def test_cli_rejects_unknown_options_rather_than_silently_ignoring(monkeypatch):
    with pytest.raises(SystemExit) as exc:
        canary.main(["--check-founder-private-customer-rows"])
    assert exc.value.code==2


def test_cli_private_mode_does_not_upgrade_buyer_delivery(monkeypatch,capsys):
    monkeypatch.setattr(canary,"inspect",lambda:{
        "status":"PUBLIC_ENQUIRY_SURFACE_VERIFIED_CRM_DELIVERY_UNPROVEN",
        "founder_crm_delivery_verified":False,"database_writes":False,
    })
    original = canary.inspect_private_crm_auth
    monkeypatch.setattr(canary,"inspect_private_crm_auth",
                        lambda:original(fixture()[0]))
    assert canary.main(["--check-private-inbox"])==0
    report=json.loads(capsys.readouterr().out)
    assert report["status"]=="PRIVATE_CRM_AUTH_GATE_READY_NO_RECEIPT_READ"
    assert report["founder_crm_delivery_verified"] is False
    assert report["founder_login_authenticated"] is False
    assert report["database_writes"] is False


def test_cli_private_mode_status_held_on_auth_failure(monkeypatch,capsys):
    monkeypatch.setattr(canary,"inspect",lambda:{
        "status":"PUBLIC_ENQUIRY_SURFACE_VERIFIED_CRM_DELIVERY_UNPROVEN",
        "founder_crm_delivery_verified":False,
    })
    original = canary.inspect_private_crm_auth
    monkeypatch.setattr(canary,"inspect_private_crm_auth",
                        lambda:original(fixture(leak=True)[0]))
    assert canary.main(["--check-private-inbox"])==2
    report=json.loads(capsys.readouterr().out)
    assert report["status"]=="HELD_PRIVATE_CRM_AUTH_BOUNDARY_UNVERIFIED"
    assert report["founder_crm_delivery_verified"] is False
