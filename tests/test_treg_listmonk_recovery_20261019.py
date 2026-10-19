"""TREG zero-spend review and original Listmonk contact safety gates."""
from datetime import datetime, timezone
import json

import pytest

from empire_os.treg_source_policy import (
    evaluate_treg_capability, review_treg_for_empire,
)
from empire_os.listmonk_recovery_boundary import (
    review_listmonk_audience_eligibility, inspect_legacy_listmonk,
)
from scripts.review_treg_and_listmonk_recovery_20261019 import main

NOW = datetime(2026, 10, 19, 17, 30, tzinfo=timezone.utc)


def test_treg_default_is_zero_spend_and_never_promotes_leads():
    manifest = review_treg_for_empire()
    assert len(manifest["capabilities"]) == 6
    assert manifest["paid_calls"] == 0
    assert manifest["external_crm_data_sent"] is False
    assert all(cap["tool_call_authorized"] is False
               and cap["canonical_empiredb_writes"] is False
               for cap in manifest["capabilities"])


@pytest.mark.parametrize("cap", [
    "web_search", "web_extract", "seo_keywords", "company_enrichment",
    "lead_signals", "social_trends",
])
def test_treg_data_rights_and_spend_gate_for_all(cap):
    result = evaluate_treg_capability(cap, estimated_price_usd="0.01")
    assert result["state"] == "HOLD_EXTERNAL_PROCESSOR_AND_DATA_RIGHTS"
    assert result["tool_call_authorized"] is False
    gated = evaluate_treg_capability(
        cap, estimated_price_usd="0.01", source_rights_verified=True,
        third_party_processing_approved=True, paid_budget_usd="0"
    )
    assert gated["state"] == "HOLD_INSUFFICIENT_APPROVED_BUDGET"
    assert gated["outbound_authorized"] is False


def test_treg_does_not_call_even_if_all_review_checks_true():
    d = evaluate_treg_capability(
        "company_enrichment", estimated_price_usd="0.00",
        source_rights_verified=True,
        third_party_processing_approved=True,
        paid_budget_usd="0", credentials_verified=True,
    )
    assert d["state"] == "REVIEW_ONLY_READY_FOR_SEPARATE_OPERATOR_GATE"
    assert d["tool_call_authorized"] is False


@pytest.mark.parametrize("price", ["NaN", "Infinity", "-0.10", "10001", "no price"])
def test_treg_refuses_invalid_or_unbounded_price(price):
    with pytest.raises(ValueError):
        evaluate_treg_capability("web_search", estimated_price_usd=price)


@pytest.mark.parametrize("purpose", ["personal_phone_finding", "mass_email_discovery",
                                     "consumer_claimants", "patient_enrichment"])
def test_treg_refuses_sensitive_contact_collection(purpose):
    with pytest.raises(ValueError):
        evaluate_treg_capability("web_extract", purpose=purpose)


def consent(**overrides):
    row = {
        "suppressed": False, "unsubscribed": False, "bounced": False,
        "double_opt_in_confirmed": True,
        "marketing_purpose_consented": True,
        "canonical_suppression_checked": True,
        "recipient_address_verified": True,
        "consent_purpose": "empire_ai_marketing_newsletter",
        "source_provenance_verified": True,
        "consented_at": "2026-10-17T13:00:00+00:00",
        "private_email": "must-never-publish@example.com",
    }
    row.update(overrides)
    return row


def test_legacy_audience_holds_contacts_without_optin_or_with_optout():
    rows = [
        consent(),
        consent(double_opt_in_confirmed=False),
        consent(unsubscribed=True),
        consent(suppressed=True),
        consent(bounced=True),
        {"old_imported_lead": True, "private_email": "legacy@example.com"},
        consent(consent_purpose="one_to_one_sales"),
        consent(consented_at="2040-01-01T00:00:00+00:00"),
    ]
    r = review_listmonk_audience_eligibility(rows, now=NOW)
    assert r["historical_records_checked"] == 8
    assert r["review_eligible_not_imported"] == 1
    assert r["held_count"] == 7
    assert r["campaign_send_authorized"] is False
    assert r["mailing_list_import_authorized"] is False
    assert r["canonical_empiredb_writes"] is False
    assert "must-never-publish" not in json.dumps(r)
    assert "legacy@example.com" not in json.dumps(r)


def test_listmonk_restore_checks_legacy_code_not_assumed_database(tmp_path):
    r = inspect_legacy_listmonk(
        tmp_path,
        port_probe=lambda _: False,
        git_probe=lambda ref: ref.endswith("empire_os/listmonk_import_leads.py"),
    )
    assert r["legacy_application_code_recoverable"] is True
    assert r["localhost_9000_listening"] is False
    assert r["original_audience_rows_recovered"] is None
    assert r["historic_secret_reuse_prohibited"] is True
    assert r["automatic_outbound_authorized"] is False
    assert r["database_recovery_verified"] is False


def test_listmonk_unbounded_or_invalid_audience_fails():
    with pytest.raises(ValueError):
        review_listmonk_audience_eligibility([consent()] * 1501, now=NOW)


def test_cli_never_prints_legacy_credentials_or_personal_contacts(tmp_path, capsys):
    code = main(["--read-only", "--repo-root", str(tmp_path)])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mailing_campaigns_sent"] == 0
    assert report["paid_external_api_calls"] == 0
    assert report["treg"]["tool_calls_authorized"] is False
    assert "password" not in json.dumps(report).lower()
    assert "private_email" not in json.dumps(report).lower()


def test_private_founder_tooling_route_returns_no_secret_or_paid_execution(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from empire_os.founder_lead_supply_api import (
        create_founder_lead_supply_router,
        read_marketing_tooling_recovery,
    )
    app = FastAPI()
    app.include_router(create_founder_lead_supply_router(
        report_path=tmp_path / "missing.json",
        exchange_path=tmp_path / "missing2.json",
    ))
    with pytest.MonkeyPatch.context() as mp:
        import empire_os.founder_lead_supply_api as api
        mp.setattr(api, "inspect_legacy_listmonk", lambda root: inspect_legacy_listmonk(
            tmp_path, port_probe=lambda _: False, git_probe=lambda _: False
        ))
        r = TestClient(app).get("/v1/founder-lead-supply/marketing-tooling")
    assert r.status_code == 200
    d = r.json()
    assert d["available"] is True
    assert d["treg"]["paid_calls"] == 0
    assert d["listmonk"]["automatic_outbound_authorized"] is False
    assert d["marketing_messages_sent"] == 0
    assert "api_token" not in r.text.lower()
