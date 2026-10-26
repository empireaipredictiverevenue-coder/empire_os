from copy import deepcopy

import pytest
from empire_os.saas_scale import TenantMembership
from empire_os.predictive_revenue_company_timeline_v44 import build_authorized_company_review
from test_predictive_revenue_company_timeline_v44 import signed_export_fixture, TENANT, COMPANY, NOW
from test_predictive_revenue_brain_staging_v421 import v5_signal, v5_forecast


def inputs():
    payload, manifest, signature, trusted, _ = signed_export_fixture()
    signal = v5_signal(1, "PAY_PER_CALL", "WEATHER_STORM")
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
