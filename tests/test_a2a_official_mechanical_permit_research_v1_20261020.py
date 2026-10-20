"""No permit source metadata can become a qualified buyer/contact."""
from __future__ import annotations
from datetime import datetime, timezone
from copy import deepcopy
import json
import pytest

from empire_os.a2a_official_mechanical_permit_research_v1 import (
    collect_little_rock_permit_business_research,
    _company,
)

NOW=datetime(2026,10,20,12,tzinfo=timezone.utc)
class Response:
    status_code=200
    headers={"Content-Type":"application/json"}
    def __init__(self,data):self.data=data;self.closed=False
    def iter_content(self,chunk_size=16384):
        yield json.dumps(self.data).encode()
    def close(self):self.closed=True

class Session:
    def __init__(self,records):
        self.records=records
        self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        return Response({"features":[{"attributes":x} for x in self.records]})

def permit(idx,contractor="ACME MECHANICAL LLC",date="2026-09-25T16:31:47"):
    return {"OBJECTID":idx,"PermitType":"MEC","ContractorTrade":"Mechanical",
            "Contractor":contractor,"PermitIssueDate":date}

def run(rows):
    s=Session(rows)
    result=collect_little_rock_permit_business_research(session=s,now=NOW)
    return result,s


def test_single_official_request_and_no_person_data_or_contact():
    evidence,s=run([permit(101),permit(102),permit(103,"Jane Smith"),
                    permit(104,"Someone@example.org")])
    assert len(s.calls)==1
    url,kwargs=s.calls[0]
    assert "maps.littlerock.gov" in url
    assert kwargs["allow_redirects"] is False and kwargs["stream"] is True
    assert kwargs["params"]["returnGeometry"]=="false"
    assert "PropertyAddress" not in kwargs["params"]["outFields"]
    assert evidence["source_records_scanned"]==4
    assert evidence["conservative_business_names_retained"]==1
    assert evidence["contractor_company_research_records"][0]["official_permit_object_ids"]==[101,102]
    assert "Jane Smith" not in str(evidence)
    assert evidence["not_an_hvac_lead_feed"] is True
    assert evidence["verified_local_hvac_lead_buyers"]==0
    assert not evidence["personal_contacts_or_property_addresses_exported"]


def test_recent_public_permit_source_could_be_fresh_but_still_not_buyer():
    e,s=run([permit(105,date="2026-10-17T10:10:10")])
    assert e["source_fresh_within_14_days"]
    assert e["newest_permit_age_days"]==3
    assert not e["source_terms_and_commercial_redistribution_cleared"]
    assert e["verified_purchase_requirements"]==0


def test_out_of_scope_permit_type_fails_closed():
    with pytest.raises(ValueError,match="GOV_DATA_SCOPE_MISMATCH"):
        run([dict(permit(104),PermitType="ELE")])


def test_invalid_company_and_future_date_does_not_promote():
    assert _company("john@example.com") is None
    assert _company("John Smith") is None
    assert _company("123-456-7890 Air Conditioning") is None
    with pytest.raises(ValueError,match="FUTURE_PERMIT_DATE"):
        run([permit(102,date="2027-01-12T03:44:22")])


def test_response_rejects_http_error_and_keeps_no_extra_pages():
    class BadSession:
        def get(self,*a,**k):
            r=Response({});r.status_code=403;return r
    with pytest.raises(ValueError,match="GOV_DATA_HTTP_403"):
        collect_little_rock_permit_business_research(session=BadSession(),now=NOW)
