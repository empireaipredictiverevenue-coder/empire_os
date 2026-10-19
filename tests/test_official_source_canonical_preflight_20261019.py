"""Three real source shapes -> EXISTING canonical ingest preparation only."""
from datetime import datetime, timezone
import json

import pytest

from empire_os.official_source_canonical_preflight import preflight_official_source_ledgers
from scripts.preflight_official_source_empiredb_20261019 import main

NOW = datetime(2026, 10, 19, 15, 25, tzinfo=timezone.utc)


def ledgers():
    solar = {
        "schema_version": "empire.recc_solar_supply_sweep.v1",
        "observations": [
            {
                "business_name": f"Verified Test Solar Co {i}",
                "source_id": "gb_recc_solar", "niche": "solar",
                "member_url": f"https://www.recc.org.uk/scheme/members/test-{i}",
                "observed_at": NOW.isoformat(),
                "source_internal_use_only": True, "source_raw_resale_allowed": False,
                "territory": "GB", "verified_canonical_prospect_id": None,
                "outbound_authorized": False,
                "email": "REDACT-PRIVATE@email.test",
            } for i in range(3)
        ],
    }
    dental = {
        "schema_version": "empire.cms_nppes_dental_org_sweep.v1",
        "organizations": [{
            "source_id": "us_cms_nppes_dental_npi2",
            "organization_npi": "1234567890",
            "business_name": "Sample Dental Provider LLC",
            "country_code": "US", "niche": "dental",
            "canonical_empiredb_prospect_id": None,
            "consumer_or_patient_record": False,
            "has_confirmed_buyer_intent": False,
            "outbound_authorized": False,
        }],
    }
    nyc = {
        "schema_version": "empire.us_nyc_home_improvement_company_pilot.v1",
        "businesses": [{
            "source_id": "us_nyc_dcwp_home_improvement_companies",
            "license_number": "1234567-DCA",
            "business_name": "Sample Renovations LLC",
            "country_code": "US", "state": "NY",
            "niche": "general_contractor",
            "specific_roofing_solar_hvac_trade_verified": False,
            "real_business_independently_verified": False,
            "canonical_empiredb_prospect_id": None,
            "outbound_authorized": False,
        }],
    }
    return {
        "gb_recc_solar": solar,
        "us_cms_nppes_dental_npi2": dental,
        "us_nyc_dcwp_home_improvement_companies": nyc,
    }


def test_prepares_only_recc_internal_acquisition_and_no_buyer_intent():
    result = preflight_official_source_ledgers(ledgers(), now=NOW)
    assert result["source_rows_observed"] == 5
    assert result["company_source_rows_prepared_not_ingested"] == 3
    assert result["held_source_rows"] == 2
    assert result["canonical_lookup_state"] == "NOT_REQUESTED"
    assert result["verified_net_new_empiredb_prospects"] == 0
    assert result["buying_intent_verified"] == 0
    assert result["exchange_inventory_added"] == 0
    assert result["canonical_insert_authorized"] is False
    assert result["canonical_empiredb_writes"] is False
    out = json.dumps(result)
    assert "REDACT-PRIVATE" not in out
    assert "Sample Dental Provider" not in out
    assert "Verified Test Solar" not in out


def test_reader_bounded_and_existing_prepare_candidate_sets_intent_zero():
    class FakeReader:
        def __init__(self):
            self.calls = []
        def lookup_existing(self, prepared):
            self.calls.append(prepared)
            assert prepared["prospect"]["buy_signal_score"] == 0
            assert prepared["prospect"]["contact_source"] == "recc_solar"
            assert prepared["prospect"]["niche"] == "solar"
            assert "website" not in prepared["prospect"]
            assert prepared["evidence"]["source"] == "recc_solar"
            assert prepared["ingest_key"]
            return {"decision": "new", "reason": "not_seen_in_fake_reader"}
        def ingest_atomic(self, payload):
            raise AssertionError("NEVER insert into EmpireDB")
    reader = FakeReader()
    review = preflight_official_source_ledgers(
        ledgers(), reader=reader, max_canonical_lookups=2, now=NOW
    )
    assert len(reader.calls) == 2
    assert review["canonical_lookup_state"] == "CANONICAL_READ_ONLY_PARTIAL"
    assert review["canonical_lookup_decisions_not_verified_new_inventory"] == {
        "deferred_after_lookup_cap": 1, "new": 2
    }
    assert review["verified_net_new_empiredb_prospects"] == 0


def test_reader_error_holds_without_inserting():
    class BadReader:
        def lookup_existing(self, prepared):
            raise PermissionError("do not leak credentials")
    review = preflight_official_source_ledgers(
        ledgers(), reader=BadReader(), max_canonical_lookups=2, now=NOW
    )
    assert review["canonical_lookup_state"] == "CANONICAL_READER_HOLD"
    assert review["canonical_lookup_decisions_not_verified_new_inventory"]["read_failed_or_incomplete"] == 2
    assert "credentials" not in json.dumps(review)


def test_duplicate_recc_ids_and_false_rights_not_promoted():
    data = ledgers()
    a = data["gb_recc_solar"]["observations"]
    a[1]["member_url"] = a[0]["member_url"]
    a[2]["source_raw_resale_allowed"] = True
    review = preflight_official_source_ledgers(data, now=NOW)
    assert review["company_source_rows_prepared_not_ingested"] == 1
    assert review["held_source_rows"] == 4
    why = review["sources"][0]["hold_reasons"]
    assert why["duplicate_or_missing_source_business_id"] == 1
    assert why["recc_source_provenance_invalid"] == 1


def test_false_buyer_contact_and_source_schema_fail():
    data = ledgers()
    data["gb_recc_solar"]["observations"][0]["outbound_authorized"] = True
    review = preflight_official_source_ledgers(data, now=NOW)
    assert review["company_source_rows_prepared_not_ingested"] == 2
    data = ledgers()
    data["us_cms_nppes_dental_npi2"]["schema_version"] = "untrusted"
    with pytest.raises(ValueError):
        preflight_official_source_ledgers(data, now=NOW)


def test_unbounded_ledger_and_lookup_budget_fails():
    data = ledgers()
    data["gb_recc_solar"]["observations"] = data["gb_recc_solar"]["observations"] * 15
    with pytest.raises(ValueError, match="unbounded"):
        preflight_official_source_ledgers(data, now=NOW)
    with pytest.raises(ValueError, match="lookup_budget"):
        preflight_official_source_ledgers(ledgers(), max_canonical_lookups=100, now=NOW)


def test_offline_cli_reports_aggregate_no_raw_companies(tmp_path, capsys):
    data = ledgers()
    data["gb_recc_solar"]["observations"] = [
        {**row, "observed_at": datetime.now(timezone.utc).isoformat()}
        for row in data["gb_recc_solar"]["observations"]
    ]
    cli = []
    for name, flag in [
        ("gb_recc_solar","--recc"),
        ("us_cms_nppes_dental_npi2","--nppes"),
        ("us_nyc_dcwp_home_improvement_companies","--nyc"),
    ]:
        path = tmp_path / (name+".json")
        path.write_text(json.dumps(data[name]))
        cli.extend([flag, str(path)])
    # The fixture timestamp is 19 October, the real runtime is same day.
    assert main(["--read-only", *cli]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["company_source_rows_prepared_not_ingested"] == 3
    assert result["exchange_inventory_added"] == 0
    assert "REDACT-PRIVATE" not in json.dumps(result)


def test_invalid_json_cli_does_not_echo_customer_data(tmp_path, capsys):
    path = tmp_path/"bad.json"
    path.write_text("PRIVATE CUSTOMER DATA, NOT A JSON SOURCE")
    assert main(["--read-only", "--recc", str(path),
                 "--nppes", str(path), "--nyc", str(path)]) == 2
    out = capsys.readouterr().out
    assert "PRIVATE CUSTOMER" not in out
    assert json.loads(out)["execution_authority"] == "none"


def test_private_founder_source_readiness_api_never_reveals_contact(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from empire_os.founder_lead_supply_api import create_founder_lead_supply_router
    data = ledgers()
    data["gb_recc_solar"]["observations"] = [
        {**row, "observed_at": datetime.now(timezone.utc).isoformat()}
        for row in data["gb_recc_solar"]["observations"]
    ]
    paths = {}
    for sid, val in data.items():
        path = tmp_path / (sid+".json")
        path.write_text(json.dumps(val))
        paths[sid] = path
    app = FastAPI()
    app.include_router(create_founder_lead_supply_router(
        report_path=tmp_path/"missing-census.json",
        exchange_path=tmp_path/"missing-exchange.json",
        source_ledger_paths=paths,
    ))
    response = TestClient(app).get("/v1/founder-lead-supply/source-readiness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["source_rows_observed"] == 5
    assert payload["company_source_rows_prepared_not_ingested"] == 3
    assert payload["exchange_inventory_added"] == 0
    assert payload["canonical_empiredb_writes"] is False
    assert "REDACT-PRIVATE" not in response.text
    assert "Verified Test Solar Co" not in response.text
    assert "Sample Dental Provider LLC" not in response.text


def test_private_founder_api_missing_ledger_holds():
    from empire_os.founder_lead_supply_api import read_official_source_readiness
    result = read_official_source_readiness({})
    assert result["available"] is False
    assert result["exchange_inventory_added"] == 0
    assert result["execution_authority"] == "none"
