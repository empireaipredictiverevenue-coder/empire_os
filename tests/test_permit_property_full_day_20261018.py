"""Complete-date source coverage and safe Property Intelligence projection."""
import json
from datetime import datetime,timezone
from pathlib import Path
import pytest
from empire_os.permit_property_full_day_review import review_full_official_day
from empire_os.permit_property_source_join import review_official_building_landuse
from empire_os.property_source_evidence_runtime import FULL_DAY_FILENAME, load_property_reference_summary
from empire_os.vertical_intelligence_runtime import build_property_intelligence_runtime
from empire_os.source_intelligence_handoff import build_source_intelligence_handoffs

NOW=datetime.now(timezone.utc)
DAY="2026-10-16"

class Pages:
    def __init__(self): self.calls=[]
    def count(self,day):
        assert day==DAY
        self.calls.append("count")
        return {"count":85,"sha256":"c"*64}
    def page(self,*,now,issued_day,after_source_row_id):
        assert issued_day==DAY and now==NOW
        i={None:0,"row-cursor.0":1,"row-cursor.1":2}[after_source_row_id]
        self.calls.append(("page",i))
        return {
            "issued_day":DAY,"mode":"OBSERVE","no_sales_authority":True,
            "query_rows":40 if i<2 else 5,
            "last_source_row_id":f"row-cursor.{i}",
            "source_response_sha256":{"permits":"a"*64,"filings":"b"*64},
            "events":[{
                "job_filing_number":f"B{i:08d}-I1",
                "filing_date":"2026-01-01","first_permit_date":DAY,
                "issued_date":DAY,"filing_reason":"Initial Permit",
                "permit_status":"Permit Issued","work_type":"General Construction",
                "work_types":["General Construction"],"underlying_permit_row_count":1,
                "borough":"Brooklyn","bin":"3002642","bbl":"3002697501",
                "solar_work_type":False,"general_construction_work_type":True,
                "official_event_crosscheck":True,
            }],
        }

class Response:
    def __init__(self,rows,url):
        self.content=json.dumps(rows).encode()
        self.url=url+"?bounded=1"
    def raise_for_status(self): pass

class Client:
    def get(self,url,*,params,timeout,headers):
        if "5zhs-2jue" in url:
            return Response([{"bin":"3002642","base_bbl":"3002697501","doitt_id":"40000"}],url)
        return Response([{"bbl":"3002697501.00000000","borough":"BK",
                          "landuse":"6","bldgclass":"E1"}],url)

def full_review(f,count=None):
    return review_full_official_day(
        DAY,now=NOW,fetch_page=f.page,count_source_rows=count or f.count,
        join_property=lambda events,*,now:review_official_building_landuse(
            events,now=now,client=Client()),
    )

def test_entire_source_day_reconciles_and_routes_counts_without_prospects(tmp_path):
    f=Pages();r=full_review(f)
    assert (r["source_permit_row_count"],r["permit_event_count"],r["source_page_count"])==(85,3,3)
    assert r["official_day_count_before_scan"]==r["official_day_count_after_scan"]==85
    assert r["event_level_join_status_counts"]=={"TRI_AGENCY_BIN_AND_LOT_MATCH":3}
    assert r["event_level_industrial_lot_context_count"]==3
    assert f.calls==["count",("page",0),("page",1),("page",2),"count"]
    p=tmp_path/FULL_DAY_FILENAME;p.parent.mkdir(parents=True)
    p.write_text(json.dumps(r))
    got=load_property_reference_summary(tmp_path,now=NOW)
    assert got["status"]=="FULL_ISSUED_DAY_PROPERTY_REFERENCES_REVIEWED"
    assert got["official_source_row_count"]==85
    assert got["three_agency_bin_bbl_reference_match_count"]==3
    assert got["warehouse_operation_verified_count"]==0
    assert got["verified_property_opportunity_count"] is None
    project=build_property_intelligence_runtime(tmp_path)
    assert project["three_agency_source_reference_review"]["reviewed_permit_event_count"]==3
    assert project["opportunity_count"] is None
    routes={x["lane"]:x for x in build_source_intelligence_handoffs(tmp_path,now=NOW)["routes"]}
    assert routes["warehouse"]["counts"]["industrial_manufacturing_lot_context_only_count"]==3
    assert routes["warehouse"]["counts"]["warehouse_operation_verified_count"]==0

def test_source_count_changed_at_end_fails_closed():
    f=Pages();calls=[]
    def varying(day):
        calls.append(day)
        return {"count":85 if len(calls)==1 else 86,"sha256":"c"*64}
    with pytest.raises(ValueError,match="SOURCE_DAY_COUNT_CHANGED_OR_MISMATCHED"):
        full_review(f,count=varying)

def test_source_row_count_overrun_and_undercount_fail_closed():
    with pytest.raises(ValueError,match="SOURCE_ROW_COUNT_OVERRUN"):
        full_review(Pages(),count=lambda day:{"count":45,"sha256":"a"*64})
    with pytest.raises(ValueError,match="SOURCE_DAY_COUNT_CHANGED_OR_MISMATCHED"):
        full_review(Pages(),count=lambda day:{"count":86,"sha256":"a"*64})

def test_date_and_source_budget_input_validation():
    with pytest.raises(ValueError,match="INVALID_OFFICIAL_PERMIT_DATE"):
        review_full_official_day("2026-10-16' OR TRUE",now=NOW)
    with pytest.raises(ValueError,match="PERMIT_DATE_OUTSIDE_BOUNDED_WINDOW"):
        review_full_official_day("2025-10-16",now=NOW)
    with pytest.raises(ValueError,match="SOURCE_DAY_EXCEEDS_BOUNDED_RESEARCH_CAP"):
        review_full_official_day(DAY,now=NOW,count_source_rows=lambda day:{"count":1000000,"sha256":"a"*64})

def test_reader_refuses_forged_volume_buyer_date_and_chunk_claims(tmp_path):
    r=full_review(Pages());p=tmp_path/FULL_DAY_FILENAME;p.parent.mkdir(parents=True)
    for edit in (
      lambda x:x.update(official_day_count_after_scan=84),
      lambda x:x.update(input_dob_sample_may_be_incomplete=True),
      lambda x:x["diagnostics"][0].update(verified_business_buyer=True),
      lambda x:x["diagnostics"][0].update(permit_job_filing_ref="B00000001-I1"),
      lambda x:x["source_page_receipts"][0].update(official_rows=39),
      lambda x:x["property_chunks"][0].update(job_count=2),
    ):
        data=json.loads(json.dumps(r));edit(data);p.write_text(json.dumps(data))
        assert load_property_reference_summary(tmp_path,now=NOW)["status"]=="UNTRUSTED_REVIEW_FILE"

def test_v1_sample_reader_still_accepted(tmp_path):
    from empire_os.property_source_evidence_runtime import FILENAME
    ev={"job_filing_number":"B01222111-I1","issued_date":DAY,
        "bin":"3002642","bbl":"3002697501","borough":"Brooklyn",
        "official_event_crosscheck":True,"filing_reason":"Initial Permit",
        "permit_status":"Permit Issued"}
    r=review_official_building_landuse([ev],now=NOW,client=Client())
    p=tmp_path/FILENAME;p.parent.mkdir(parents=True);p.write_text(json.dumps(r))
    assert load_property_reference_summary(tmp_path,now=NOW)["status"]=="OFFICIAL_SOURCE_REFERENCES_REVIEWED"
