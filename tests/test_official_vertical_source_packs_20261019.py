"""Narrow official source API and file import, no PII/contact resale."""
from datetime import datetime, timedelta, timezone
import json
import pytest

from empire_os.official_vertical_source_packs import SOURCES, BY_ID, assess_source_access
from empire_os.nppes_dental_source import (
    review_nppes_org_records, sweep_nppes_dental, _url,
)
from empire_os.cslb_contractor_csv_source import review_official_cslb_csv

NOW = datetime(2026, 10, 19, 14, 20, tzinfo=timezone.utc)


def org(npi="1234567890", *, kind="NPI-2", code="122300000X"):
    return {
        "number": npi, "enumeration_type": kind,
        "basic": {
            "organization_name": "TEST DENTAL BUSINESS PLLC",
            "first_name": "SENSITIVE-NAME-NOT-TO-STORE",
            "last_name": "SENSITIVE-LAST-NOT-TO-STORE",
        },
        "addresses": [{
            "address_purpose": "LOCATION", "city": "Dallas",
            "state": "TX", "telephone_number": "999 PRIVATE"
        }],
        "taxonomies": [{"code": code, "desc": "Dentist"}],
    }


def payload(*rows):
    return {"result_count": len(rows), "results": list(rows)}


def test_catalog_has_all_required_sectors_and_gates():
    assert len(BY_ID) == len(SOURCES) == 8
    covered = set(n for s in SOURCES for n in s.sectors)
    assert {"roofing", "solar", "hvac", "dental", "insurance", "legal", "mass_torts"} <= covered
    assert assess_source_access("gb_sra_firm_api")["state"] == "HOLD_API_KEY_REQUIRED"
    assert assess_source_access("gb_fca_insurance_firm_api")["state"] == "HOLD_API_KEY_REQUIRED"
    assert assess_source_access("us_cslb_official_contractor_csv")["state"] == "HOLD_LOCAL_DATASET_REQUIRED"
    assert assess_source_access("us_cms_nppes_dental_npi2")["state"] == "BOUNDED_MANUAL_PILOT_READY"
    assert all(not assess_source_access(x.source_id)["canonical_empiredb_writes"] for x in SOURCES)


def test_nppes_only_organization_dental_no_provider_pii():
    data = review_nppes_org_records(
        payload(org(), org("9876543210", kind="NPI-1"),
                org("9876543211", code="207Q00000X")),
        state="TX", city="Dallas", observed_at=NOW,
    )
    assert len(data) == 1
    assert data[0]["organization_npi"] == "1234567890"
    assert data[0]["legal_entity_licensed_or_verified"] is False
    assert data[0]["consumer_or_patient_record"] is False
    output = json.dumps(data)
    assert "SENSITIVE" not in output and "PRIVATE" not in output
    assert "addresses" not in output and "telephone" not in output


def test_nppes_one_geo_once_day_and_private_ledger(tmp_path):
    requests = []
    def fake_fetch(url):
        requests.append(url)
        return payload(org())
    a = sweep_nppes_dental(tmp_path, now=NOW, fetch=fake_fetch)
    b = sweep_nppes_dental(tmp_path, now=NOW, fetch=fake_fetch)
    assert a["new_unique_business_observations"] == 1
    assert a["canonical_empiredb_additions"] == 0
    assert b["state"] == "QUERY_GEO_ALREADY_RUN_TODAY"
    assert len(requests) == 1
    rows = json.loads((tmp_path / "organizations.json").read_text())["organizations"]
    assert len(rows) == 1
    assert tmp_path.stat().st_mode & 0o777 == 0o700
    assert (tmp_path / "organizations.json").stat().st_mode & 0o777 == 0o600


def test_nppes_failure_consumes_request_budget(tmp_path):
    def fail(url):
        raise TimeoutError("private response")
    with pytest.raises(TimeoutError):
        sweep_nppes_dental(tmp_path, now=NOW, fetch=fail)
    count = sweep_nppes_dental(tmp_path, now=NOW, fetch=fail)
    assert count["state"] == "QUERY_GEO_ALREADY_RUN_TODAY"
    assert not (tmp_path / "organizations.json").exists()


def test_nppes_two_queries_daily_max_and_no_bulk(tmp_path):
    counter = []
    for city, state in [("Dallas", "TX"), ("Chicago", "IL")]:
        r = sweep_nppes_dental(
            tmp_path, city=city, state=state, now=NOW,
            fetch=lambda url: (counter.append(url), payload())[1],
        )
        assert r["state"] == "COMPLETED"
    third = sweep_nppes_dental(
        tmp_path, city="Miami", state="FL", now=NOW,
        fetch=lambda url: (_ for _ in ()).throw(AssertionError("third API call")),
    )
    assert third["state"] == "DAILY_QUERY_LIMIT_REACHED"
    assert len(counter) == 2


def test_nppes_disallow_unlisted_geos_and_invalid_response(tmp_path):
    with pytest.raises(ValueError):
        _url("Hollywood", "FL")
    with pytest.raises(ValueError):
        review_nppes_org_records(
            {"result_count": 999, "results": [org()]},
            city="Dallas", state="TX", observed_at=NOW,
        )


def test_cslb_filters_business_license_trade_and_no_emails():
    text = (
        "License Number,Business Name,Classification(s),License Status,City,Email\n"
        "123456,Acme Roof Systems,C-39,ACTIVE,Los Angeles,sensitive@example.com\n"
        "123457,Sunny Energy Inc,C-46,ACTIVE,San Diego,sensitive@example.com\n"
        "123458,AC Mechanical Ltd,C-20,ACTIVE,Oakland,sensitive@example.com\n"
        "123459,Some Food Shop,C-7,ACTIVE,Oakland,sensitive@example.com\n"
        "123460,Expired Roofing LLC,C-39,EXPIRED,Oakland,sensitive@example.com\n"
        "123461,Acme Roof Systems,C-39,ACTIVE,Los Angeles,sensitive@example.com\n"
    )
    r = review_official_cslb_csv(
        text, source_document_ref="official-download:synthetic-review",
        rights_review_ref="licence:synthetic-review",
    )
    assert r["distinct_business_licence_observations"] == 4
    assert r["niche_counts"] == {"roofing": 2, "solar": 1, "hvac": 1}
    assert r["canonical_empiredb_writes"] is False
    assert r["commercial_exchange_added"] == 0
    assert "sensitive@" not in json.dumps(r)
    assert all(not x["current_license_independently_verified"]
               for x in r["internal_observations"])


def test_cslb_missing_headers_and_missing_rights_are_hold():
    with pytest.raises(ValueError):
        review_official_cslb_csv("some,header\nx,y\n",
                                 source_document_ref="source:review123",
                                 rights_review_ref="rights:review123")
    with pytest.raises(ValueError):
        review_official_cslb_csv(
            "License Number,Business Name,Classification(s),License Status\n",
            source_document_ref="", rights_review_ref="",
        )
