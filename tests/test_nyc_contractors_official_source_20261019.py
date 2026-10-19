"""Company-only official NYC home improvement licences, no person/customer data."""
from datetime import datetime, timezone
import json
import pytest
from empire_os.nyc_contractors_official_source import (
    review_nyc_company_licences,sweep_nyc_companies,_url
)

NOW=datetime(2026,10,19,14,35,tzinfo=timezone.utc)

def row(name="ACME RENOVATIONS LLC", licence="1234567-DCA",state="NY",
        status="Active",expires="2027-10-20T00:00:00.000"):
    return {
        "license_nbr":licence,"business_name":name,"address_city":"New York",
        "address_state":state,"license_status":status,"lic_expir_dd":expires,
        "contact_phone":"PERSONAL PHONE OMIT ME",
        "license_type":"Premises",
    }

def test_business_only_and_active_date():
    accepted=review_nyc_company_licences([
        row(),row(name="JOHN SMITH",licence="88888-DCA"),
        row(name="EXPIRED LLC",licence="99999-DCA",expires="2020-01-01"),
        row(name="INACTIVE INC.",licence="77777-DCA",status="Expired"),
        row(name="FOREIGN LLC",licence="66666-DCA",state="NJ"),
    ],now=NOW)
    assert len(accepted)==1
    assert accepted[0]["niche"]=="general_contractor"
    assert accepted[0]["specific_roofing_solar_hvac_trade_verified"] is False
    assert accepted[0]["canonical_empiredb_prospect_id"] is None
    assert "PERSONAL PHONE" not in json.dumps(accepted)

def test_one_narrow_query_per_day(tmp_path):
    calls=[]
    def fetch(url):
        calls.append(url)
        return [row(),row(name="JOHN PRIVATE",licence="77777-DCA")]
    first=sweep_nyc_companies(tmp_path,now=NOW,fetch=fetch)
    next=sweep_nyc_companies(tmp_path,now=NOW,fetch=fetch)
    assert first["corporate_business_licences_observed"]==1
    assert first["commercial_exchange_inventory_additions"]==0
    assert next["state"]=="DAILY_REQUEST_ALREADY_CONSUMED"
    assert len(calls)==1
    assert tmp_path.stat().st_mode & 0o777 == 0o700
    assert (tmp_path/"private_business_observations.json").stat().st_mode & 0o777 == 0o600

def test_failed_query_reserves_daily_call(tmp_path):
    def fail(url):raise RuntimeError("source unavailable")
    with pytest.raises(RuntimeError):
        sweep_nyc_companies(tmp_path,now=NOW,fetch=fail)
    assert sweep_nyc_companies(tmp_path,now=NOW,fetch=fail)["state"]=="DAILY_REQUEST_ALREADY_CONSUMED"

def test_reject_oversized_response_and_wrong_schema():
    with pytest.raises(ValueError):review_nyc_company_licences([row()]*21,now=NOW)
    with pytest.raises(ValueError):review_nyc_company_licences(None,now=NOW)
    assert "%24limit=20" in _url(NOW)
