from copy import deepcopy

import pytest
from empire_os.saas_scale import TenantMembership
from empire_os.predictive_revenue_company_timeline_v44 import build_authorized_company_review
from test_predictive_revenue_company_timeline_v44 import signed_export_fixture, TENANT, COMPANY, NOW
from test_predictive_revenue_brain_staging_v421 import v5_signal, v5_forecast


def inputs():
    payload, manifest, signature, trusted, _ = signed_export_fixture()
    signal = v5_signal(1, "PAY_PER_CALL", "WEATHER_STORM")
    signal["source_id"] = manifest["source_id"]
    forecast = v5_forecast(1, "PAY_PER_CALL", 30)
    for row in (signal, forecast):
        row.update(tenant_scope=TENANT, company_scope=COMPANY)
    forecast["currency"] = "GBP"
    return dict(payload=payload, signed_manifest=manifest, signature_b64=signature,
                trusted_source=trusted, signal_rows=[signal], issued_forecast_rows=[forecast])


def setup(bundle=None, member=None, allow=True):
    bundle = bundle or inputs()
    events = []
    member = member or TenantMembership(TENANT, "owner-test", "owner")
    def authenticate(request):
        events.append("auth")
        return member if request == "authenticated-request" else None
    def authorize(actual, **scope):
        events.append("authorize")
        assert actual is member
        assert scope == dict(company_scope=COMPANY, source_id=bundle["signed_manifest"]["source_id"], purpose="PREDICTIVE_REVENUE_OBSERVE")
        return allow
    def load(**scope):
        events.append("load")
        assert scope["tenant_scope"] == member.tenant_id
        return deepcopy(bundle)
    return build_authorized_company_review(resolve_membership=authenticate,
        authorize_company_review=authorize, load_review_inputs=load, now=lambda: NOW), events, bundle


def run(review, bundle, request="authenticated-request"):
    return review(request, company_scope=COMPANY, source_id=bundle["signed_manifest"]["source_id"])


def test_authorized_signed_intake_reaches_existing_v5_with_real_input_contracts():
    review, events, bundle = setup()
    result = run(review, bundle)
    assert events == ["auth", "authorize", "load"]
    v5 = result["v5_predictive_cloud_staging_read_only"]
    assert len(v5["signal_ingest_research_rows_unverified"]) == 1
    assert len(v5["issued_forecast_risk_screens_unverified"]) == 1
    assert v5["issued_forecast_risk_screens_unverified"][0]["forecast_id"] == bundle["issued_forecast_rows"][0]["forecast_id"]
    assert result["eligible_for_training_or_live_prediction"] is False
    assert result["source_registry_and_data_rights_independently_authenticated"] is False
    assert result["execution_authority"] == "none"
    assert run(review, bundle) == result
    assert events.count("auth") == 2


@pytest.mark.parametrize("incoming", [None, "forged", {"tenant_id": TENANT}])
def test_client_tenant_claim_never_loads_evidence(incoming):
    review, events, bundle = setup()
    with pytest.raises(PermissionError): run(review, bundle, incoming)
    assert events == ["auth"]


@pytest.mark.parametrize("allow", [False, None, 1, "true"])
def test_generic_read_membership_does_not_grant_company_source_authority(allow):
    review, events, bundle = setup(allow=allow)
    with pytest.raises(PermissionError): run(review, bundle)
    assert "load" not in events


def test_revoked_membership_never_reaches_loader():
    review, events, bundle = setup(member=TenantMembership(TENANT, "owner-test", "owner", "disabled"))
    with pytest.raises(PermissionError): run(review, bundle)
    assert events == ["auth"]


@pytest.mark.parametrize("field", ["signed_manifest", "trusted_source", "signal_rows", "issued_forecast_rows"])
def test_cross_tenant_records_are_rejected(field):
    bundle = inputs()
    row = bundle[field][0] if isinstance(bundle[field], list) else bundle[field]
    row["tenant_scope"] = "tenant:another"
    review, _, _ = setup(bundle)
    with pytest.raises((PermissionError, ValueError)): run(review, bundle)


def test_invalid_signature_cannot_reach_v5():
    bundle = inputs(); bundle["signature_b64"] = "forged"
    review, _, _ = setup(bundle)
    with pytest.raises(ValueError, match="signature"): run(review, bundle)


def test_duplicate_issued_forecast_is_rejected():
    bundle = inputs(); bundle["issued_forecast_rows"] *= 2
    review, _, _ = setup(bundle)
    with pytest.raises(ValueError, match="duplicate"): run(review, bundle)


def test_naive_server_clock_is_rejected_before_load():
    called = []
    review = build_authorized_company_review(
        resolve_membership=lambda _: TenantMembership(TENANT, "user", "owner"),
        authorize_company_review=lambda *a, **k: True,
        load_review_inputs=lambda **k: called.append(True), now=lambda: NOW.replace(tzinfo=None))
    with pytest.raises(ValueError, match="clock"): review(None, company_scope=COMPANY, source_id="source-001")
    assert called == []


def file_loader(tmp_path):
    import json
    from hashlib import sha256
    from empire_os.predictive_revenue_company_timeline_v44 import build_company_review_file_loader
    bundle = inputs()
    source = tmp_path / "exports"; source.mkdir()
    trust = tmp_path / "trusted"; trust.mkdir()
    (source / "payload.json").write_bytes(bundle["payload"])
    (source / "manifest.json").write_text(json.dumps(bundle["signed_manifest"]))
    (source / "signature.txt").write_text(bundle["signature_b64"])
    (trust / "source.json").write_text(json.dumps(bundle["trusted_source"]))
    signal = json.dumps(bundle["signal_rows"]).encode()
    forecast = json.dumps(bundle["issued_forecast_rows"]).encode()
    (source / "signals.json").write_bytes(signal)
    (source / "forecasts.json").write_bytes(forecast)
    cfg = dict(source_root=str(source), trusted_root=str(trust), payload_file="payload.json",
        manifest_file="manifest.json", signature_file="signature.txt", trusted_file="source.json",
        signal_file="signals.json", forecast_file="forecasts.json",
        signal_sha256=sha256(signal).hexdigest(), forecast_sha256=sha256(forecast).hexdigest())
    sid = bundle["signed_manifest"]["source_id"]
    return build_company_review_file_loader({(TENANT, COMPANY, sid):cfg}), cfg, sid


def http_client(loader, *, allow=True):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from empire_os.predictive_revenue_company_timeline_v44 import create_company_review_read_router
    # Test-only authentication stub. No production resolver is installed here.
    reviewer = build_authorized_company_review(
        resolve_membership=lambda req: TenantMembership(TENANT, "test-user", "owner")
            if req.headers.get("authorization") == "Bearer test-fixture" else None,
        authorize_company_review=lambda *a, **k: allow,
        load_review_inputs=loader, now=lambda: NOW)
    app = FastAPI(); app.include_router(create_company_review_read_router(review=reviewer))
    return TestClient(app)


def test_existing_signed_files_to_v5_http_result(tmp_path):
    loader, _, sid = file_loader(tmp_path)
    before = {str(p):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    client = http_client(loader)
    url = "/v1/predictive-revenue/company-review"
    params = dict(company_scope=COMPANY, source_id=sid)
    response = client.get(url, params=params, headers={"Authorization":"Bearer test-fixture"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["tenant_scope"] == TENANT
    assert len(data["v5_predictive_cloud_staging_read_only"]["issued_forecast_risk_screens_unverified"]) == 1
    assert "public_key_b64" not in response.text
    assert "signature_b64" not in response.text
    assert data["execution_authority"] == "none"
    assert {str(p):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before
    assert client.post(url, params=params).status_code == 405


def test_http_auth_denial_precedes_file_read(tmp_path):
    loaded=[]
    client = http_client(lambda **kwargs: loaded.append(kwargs))
    response = client.get("/v1/predictive-revenue/company-review", params={
        "company_scope": COMPANY,"source_id":"source-001", "tenant_id":TENANT})
    assert response.status_code == 403
    assert loaded == []
    assert response.headers["cache-control"] == "no-store"


def test_unconfigured_http_route_is_explicitly_unavailable():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from empire_os.predictive_revenue_company_timeline_v44 import create_company_review_read_router
    app=FastAPI(); app.include_router(create_company_review_read_router())
    result=TestClient(app).get("/v1/predictive-revenue/company-review", params={"company_scope":COMPANY,"source_id":"source-001"})
    assert result.status_code == 503
    assert result.json()["detail"] == "company_review_not_configured"


@pytest.mark.parametrize("filename", ["signals.json", "forecasts.json"])
def test_tampered_input_file_cannot_reach_http_result(tmp_path, filename):
    from pathlib import Path
    loader,cfg,sid=file_loader(tmp_path)
    (Path(cfg["source_root"])/filename).write_text("[]")
    result=http_client(loader).get("/v1/predictive-revenue/company-review",params={"company_scope":COMPANY,"source_id":sid},headers={"Authorization":"Bearer test-fixture"})
    assert result.status_code == 503
    assert str(tmp_path) not in result.text


def test_revoked_trust_is_reread_between_requests(tmp_path):
    import json
    from pathlib import Path
    loader,cfg,sid=file_loader(tmp_path)
    client=http_client(loader)
    params={"company_scope":COMPANY,"source_id":sid}; headers={"Authorization":"Bearer test-fixture"}
    assert client.get("/v1/predictive-revenue/company-review",params=params,headers=headers).status_code == 200
    path=Path(cfg["trusted_root"])/cfg["trusted_file"]
    obj=json.loads(path.read_text()); obj["status"]="REVOKED";path.write_text(json.dumps(obj))
    assert client.get("/v1/predictive-revenue/company-review",params=params,headers=headers).status_code == 503


def test_source_symlink_is_rejected(tmp_path):
    from pathlib import Path
    loader,cfg,sid=file_loader(tmp_path)
    path=Path(cfg["source_root"])/cfg["signal_file"]
    target=tmp_path/"outside.json";target.write_bytes(path.read_bytes());path.unlink();path.symlink_to(target)
    with pytest.raises(ValueError,match="symlink"):
        loader(tenant_scope=TENANT,company_scope=COMPANY,source_id=sid)


def test_other_tenant_has_no_binding(tmp_path):
    loader,_,sid=file_loader(tmp_path)
    with pytest.raises(PermissionError):loader(tenant_scope="tenant:other",company_scope=COMPANY,source_id=sid)


@pytest.mark.parametrize("source", ["source:unauthorized", None, ""])
def test_authorized_company_cannot_smuggle_another_source_signal(source, monkeypatch):
    import empire_os.predictive_revenue_company_timeline_v44 as module
    bundle = inputs()
    bundle["signal_rows"][0]["source_id"] = source
    called = []
    monkeypatch.setattr(module, "review_signed_company_export", lambda **kw: called.append(kw))
    reviewer, _, bundle = setup(bundle)
    with pytest.raises(PermissionError, match="signal_source_not_authorized"):
        run(reviewer, bundle)
    assert called == []


def test_http_cross_source_signal_denied_without_disclosing_evidence():
    bundle = inputs()
    bundle["signal_rows"][0]["source_id"] = "source:private-other"
    result = http_client(lambda **kw: deepcopy(bundle)).get(
        "/v1/predictive-revenue/company-review",
        params={"company_scope": COMPANY, "source_id": bundle["signed_manifest"]["source_id"]},
        headers={"Authorization": "Bearer test-fixture"})
    assert result.status_code == 403
    assert result.json() == {"detail": "company_review_access_denied"}
    assert "private-other" not in result.text
    assert result.headers["cache-control"] == "no-store"


@pytest.fixture
def cryptographic_client():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from test_revenue_crm_signed_auth import A, NOW as AUTH_NOW, token
    from empire_os.predictive_revenue_company_timeline_v44 import (
        build_company_review_membership_resolver, create_company_review_read_router)
    issuer = Ed25519PrivateKey.generate()
    state = {"active": True, "allow_source": True, "reads": 0, "loads": 0, "subjects": []}
    def membership(user, tenant):
        state["reads"] += 1
        return TenantMembership(tenant, user, "viewer", "active" if state["active"] else "disabled")
    resolver = build_company_review_membership_resolver(
        trusted_public_keys={"issuer-1": issuer.public_key()},
        load_membership=membership, now=lambda: AUTH_NOW)
    bundle = inputs()
    payload, manifest, _, trusted, sign = signed_export_fixture()
    manifest["tenant_scope"] = trusted["tenant_scope"] = A
    bundle.update(payload=payload, signed_manifest=manifest, trusted_source=trusted, signature_b64=sign(manifest))
    for name in ("signal_rows", "issued_forecast_rows"):
        for row in bundle[name]: row["tenant_scope"] = A
    def authorize(member, **scope):
        state["subjects"].append(member.user_id)
        assert scope["purpose"] == "PREDICTIVE_REVENUE_OBSERVE"
        return state["allow_source"]
    def load(**scope):
        state["loads"] += 1
        assert scope["tenant_scope"] == A
        return deepcopy(bundle)
    review = build_authorized_company_review(resolve_membership=resolver,
        authorize_company_review=authorize, load_review_inputs=load, now=lambda: NOW)
    app = FastAPI(); app.include_router(create_company_review_read_router(review=review))
    return TestClient(app), state, lambda **kw: token(issuer, **kw), {
        "company_scope": COMPANY, "source_id": manifest["source_id"]}


def test_original_signed_login_reaches_v5_and_revocation_is_immediate(cryptographic_client):
    client, state, issue, params = cryptographic_client
    headers = {"Authorization": "Bearer " + issue()}
    first = client.get("/v1/predictive-revenue/company-review", params=params, headers=headers)
    assert first.status_code == 200
    assert first.json()["v5_predictive_cloud_staging_read_only"]["issued_forecast_risk_screens_unverified"][0]["forecast_id"] == inputs()["issued_forecast_rows"][0]["forecast_id"]
    assert state["subjects"] == ["founder:verified"]
    assert state["reads"] == state["loads"] == 1
    state["active"] = False
    denied = client.get("/v1/predictive-revenue/company-review", params=params, headers=headers)
    assert denied.status_code == 403
    assert state["reads"] == 2 and state["loads"] == 1


@pytest.mark.parametrize("claims", [{"aud": "other"}, {"scope": "crm:write"}, {"exp": 1}])
def test_original_signed_login_rejects_invalid_claims_before_evidence(cryptographic_client, claims):
    client, state, issue, params = cryptographic_client
    result = client.get("/v1/predictive-revenue/company-review", params=params,
        headers={"Authorization": "Bearer " + issue(claims=claims)})
    assert result.status_code == 403
    assert state["loads"] == state["reads"] == 0


def test_signed_login_alone_never_grants_source_access(cryptographic_client):
    client, state, issue, params = cryptographic_client
    state["allow_source"] = False
    result = client.get("/v1/predictive-revenue/company-review", params=params,
        headers={"Authorization": "Bearer " + issue()})
    assert result.status_code == 403
    assert state["reads"] == 1 and state["loads"] == 0


def test_duplicate_bearers_cannot_select_a_principal(cryptographic_client):
    client, state, issue, params = cryptographic_client
    auth = "Bearer " + issue()
    result = client.get("/v1/predictive-revenue/company-review", params=params,
        headers=[("Authorization", auth), ("Authorization", auth)])
    assert result.status_code == 403
    assert state["reads"] == state["loads"] == 0


def test_concurrent_signed_principals_remain_request_local():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from starlette.requests import Request
    from test_revenue_crm_signed_auth import A, B, NOW as AUTH_NOW, token
    from empire_os.predictive_revenue_company_timeline_v44 import build_company_review_membership_resolver
    issuer = Ed25519PrivateKey.generate()
    barrier = Barrier(2)
    def membership(user, tenant):
        barrier.wait(timeout=5)
        return TenantMembership(tenant, user, "viewer")
    resolver = build_company_review_membership_resolver(
        trusted_public_keys={"issuer-1": issuer.public_key()},
        load_membership=membership, now=lambda: AUTH_NOW)
    def call(user, tenant):
        signed = token(issuer, claims={"sub": user, "tenant_id": tenant})
        request = Request({"type": "http", "headers": [(b"authorization", ("Bearer " + signed).encode())]})
        result = resolver(request)
        return result.user_id, result.tenant_id
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(call, "user:first", A)
        b = pool.submit(call, "user:second", B)
        assert a.result(timeout=8) == ("user:first", A)
        assert b.result(timeout=8) == ("user:second", B)


def test_untrusted_signature_never_reads_membership(cryptographic_client):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from test_revenue_crm_signed_auth import token
    client, state, _, params = cryptographic_client
    forged = token(Ed25519PrivateKey.generate())
    response = client.get("/v1/predictive-revenue/company-review", params=params,
        headers={"Authorization": "Bearer " + forged})
    assert response.status_code == 403
    assert state["reads"] == state["loads"] == 0
