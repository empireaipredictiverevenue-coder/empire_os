"""Five real corporate business names, one official source, no sales leads."""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from pathlib import Path
from copy import deepcopy
import json
import pytest

import empire_os.jev_real_business_five_sample as module

ROOT=Path(__file__).resolve().parents[1]
ORIGINAL=ROOT/"docs/commercial/JEV_REAL_FIVE_BUSINESS_SITE_OBSERVATIONS_20261022.json"
OUTPUT=ROOT/"docs/commercial/JEV_REAL_FIVE_BUSINESS_QA_RECEIPT_20261022.json"
NOW=datetime(2026,10,22,14,0,tzinfo=timezone.utc)


def registry():
    rows=[]
    for name,(naics,_,_) in module.NAMES.items():
        rows.append({
            "uniqueid":module.EXPECTED_KEYS[name],
            "dba_name":name,
            "self_reported_naics_code":naics,
            "city":"San Francisco","state":"CA",
            "data_as_of":"2026-10-22T00:00:00.000",
        })
    # Multi-location company and older ended location must not be seven leads.
    rows.append({
        "uniqueid":"1391537-06-251-1128845",
        "dba_name":"Anatra Fire Protection Inc.",
        "self_reported_naics_code":"238220",
        "city":"San Francisco","state":"CA",
        "data_as_of":"2026-10-22T00:00:00.000",
    })
    rows.append({
        "uniqueid":"0193409-05-001-0193409",
        "dba_name":"Odonovan Plumbing Inc",
        "self_reported_naics_code":None,
        "city":"San Francisco","state":"CA",
        "data_as_of":"2026-10-22T00:00:00.000",
        "location_end_date":"2021-08-03T00:00:00.000",
    })
    return rows


def evidence():
    return json.loads(ORIGINAL.read_text())


def audit(monkeypatch,rows=None,observed=None,now=NOW):
    def response(url,max_bytes):
        assert url.startswith(module.API+"?")
        assert "dba_name" in url
        assert "full_business_address" not in url
        assert "mailing_address" not in url
        assert "contact_name" not in url
        assert "phone" not in url
        assert max_bytes<=100000
        return deepcopy(registry() if rows is None else rows)
    monkeypatch.setattr(module,"_fetch_json",response)
    return module.review_five_businesses(
        now=now, live_web_checks=False,
        observed_web=evidence() if observed is None else observed)


def test_registry_sample_is_five_distinct_legal_business_names(monkeypatch):
    r=audit(monkeypatch)
    assert r["status"]=="REAL_REGISTRY_BUSINESS_SAMPLE_INTERNAL_WEBSITE_RESEARCH_ONLY"
    assert r["official_registry_location_rows_seen"]==7
    assert r["unique_selected_businesses"]==5
    assert r["duplicate_or_ended_extra_location_rows"]==2
    assert len({x["business_name"] for x in r["businesses"]})==5
    assert sum(x["active_business_location_rows"] for x in r["businesses"])==6
    assert r["first_party_sites_directly_confirmed"]==2
    assert r["actual_no_website_leads_verified"]==0
    assert r["buyer_purchase_intent_verified"]==0
    assert r["customer_accepted_leads"]==0
    assert r["outbound_sent"]==0
    assert r["database_writes"] is False


def test_uncertain_site_and_rate_limit_are_not_missing_website_proof(monkeypatch):
    r=audit(monkeypatch)
    by={x["business_name"]:x for x in r["businesses"]}
    assert by["Lutz Plumbing Inc"]["first_party_site_review_status"]=="FIRST_PARTY_BRANDED_WEBSITE_OBSERVED"
    assert by["Vitality Remodeling LLC"]["first_party_site_review_status"]=="FIRST_PARTY_BRANDED_WEBSITE_OBSERVED"
    assert by["Anatra Fire Protection Inc."]["first_party_site_review_status"]=="FIRST_PARTY_SITE_ORIGIN_HTTP_429_LATEST_RECHECK"
    assert by["Anatra Fire Protection Inc."]["original_site_response_http"]==429
    assert by["Odonovan Plumbing Inc"]["first_party_site_review_status"]=="NO_ATTRIBUTABLE_FIRST_PARTY_SITE_CONFIRMED"
    assert by["J & K Pro Plumbing Inc"]["first_party_site_review_status"]=="NO_ATTRIBUTABLE_FIRST_PARTY_SITE_CONFIRMED"
    assert all(x["site_absent_proven"] is False
               and x["website_outdated_proven"] is False
               and x["outreach_authorized"] is False for x in r["businesses"])


@pytest.mark.parametrize("case",[
    "missing","duplicate","wrong_id","wrong_sector","personal_field",
    "ended_current","stale","wrong_city",
])
def test_forged_or_duplicate_registry_rows_fail_closed(monkeypatch,case):
    rows=registry()
    if case=="missing":rows.pop(0)
    if case=="duplicate":rows.append(deepcopy(rows[0]))
    if case=="wrong_id":rows[0]["uniqueid"]="9999999-01-001-9999999"
    if case=="wrong_sector":rows[0]["self_reported_naics_code"]="111111"
    if case=="personal_field":rows[0]["mailing_address_1"]="not selected"
    if case=="ended_current":rows[0]["location_end_date"]="2025-01-01"
    if case=="stale":rows[0]["data_as_of"]="2026-10-10T00:00:00.000"
    if case=="wrong_city":rows[0]["city"]="Los Angeles"
    with pytest.raises(ValueError):
        audit(monkeypatch,rows=rows)


@pytest.mark.parametrize("field,value",[
    ("contacts_collected",1),
    ("outbound_sent",1),
    ("source_method","automatic_scraped_contacts"),
    ("as_of_date","2026-10-23"),
])
def test_web_observation_packet_cannot_promote_contacts(monkeypatch,field,value):
    e=evidence()
    e[field]=value
    with pytest.raises(ValueError):
        audit(monkeypatch,observed=e)


def test_fake_website_positive_or_false_response_rejected(monkeypatch):
    e=evidence()
    e["website_results"]["Anatra Fire Protection Inc."]["status"]="FIRST_PARTY_BRANDED_WEBSITE_OBSERVED"
    with pytest.raises(ValueError):
        audit(monkeypatch,observed=e)


def test_registry_source_meta_and_commercial_rights_stay_separate(monkeypatch):
    r=audit(monkeypatch)
    assert r["licence_for_source_business_rows_observed"] is True
    assert r["individuals_or_contacts_reuse_rights_verified"] is False
    assert r["website_status_sold_or_delivered"]==0
    assert r["execution_authority"]=="none"


def test_immutable_real_sample_receipt_is_privacy_minimal():
    r=json.loads(OUTPUT.read_text())
    assert r["unique_selected_businesses"]==5
    assert r["official_registry_location_rows_seen"]==7
    assert r["first_party_sites_directly_confirmed"]==2
    assert r["no_marketing_data_or_person_contact_fields_requested"] is True
    assert r["sales_ready_customer_records"]==0
    assert r["pinned_first_party_site_observations_sha256"]==sha256(ORIGINAL.read_bytes()).hexdigest()
    assert r["crm_writes"] is False
    assert r["outbound_sent"]==0
    assert r["execution_authority"]=="none"
    text=OUTPUT.read_text()
    assert "@" not in text
    assert "mailing_address" not in text
    assert "contact_name" not in text
    assert "phone_number" not in text
