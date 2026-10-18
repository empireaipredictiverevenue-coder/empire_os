"""Dossier evidence delivered through existing EmpireOS specialist work items."""
import json
from datetime import datetime, timezone
from pathlib import Path

from empire_os.department_work_queue import DepartmentWorkQueue
from empire_os.source_intelligence_handoff import (
    build_source_intelligence_handoffs,
    dispatch_source_intelligence_handoffs,
    deliver_source_intelligence_review,
)

NOW = datetime(2026,10,18,9,30,tzinfo=timezone.utc)


def _root(root):
    inbox=root/"runtime/acquisition/signal_inbox.json"
    inbox.parent.mkdir(parents=True)
    inbox.write_text(json.dumps({
        "sig-123": {
            "signal_id":"sig-123","source":"permits_nyc",
            "created_at":NOW.isoformat(),
            "last_seen_at":NOW.isoformat(),
            "metro":"NYC", "status":"unresolved",
            "url":"https://a810-biswebportal.nyc.gov/bisweb/PropertyOverflowDetails.jsp?job=402424051",
            "raw":{
                "job__":"402424051","filing_date":"02/09/2007",
                "dobrundate":"2026-10-18T00:00:00.000",
                "job_type":"A2","work_type":"PL","permit_status":"IN PROCESS",
                "borough":"QUEENS","bbl":"4006810011","bin__":"4011278",
                "owner_s_business_name":"Sensitive Realty Holdings",
                "permittee_s_business_name":"Sensitive Trade Contractor",
                "owner_s_first_name":"Private","owner_s_phone__":"5559991000",
            },
        },
    }))
    return root


def test_existing_source_router_recognises_old_filing_not_a_new_sales_lead(tmp_path):
    root=_root(tmp_path)
    d=build_source_intelligence_handoffs(root,now=NOW)
    assert d["lane_count"]==5
    permit=d["routes"][0]
    property_=d["routes"][1]
    assert permit["counts"]["newly_imported_actual_filing_or_issuance_last_30d"]==0
    assert permit["counts"]["newly_imported_historical_filing_or_issuance"]==1
    assert "recent_imports_have_no_recent_filing_or_issuance" in permit["blockers"]
    assert property_["counts"]["recent_actual_filing_or_issuance_unverified"]==0
    dossier=d["permit_project_intelligence"]["review_dossiers"][0]
    assert dossier["date_truth_classification"]=="HISTORICAL_PROJECT_SOURCE_ONLY"
    assert dossier["route"]["sales_promotion_authorized"] is False
    serialized=json.dumps(d)
    for contact in ("Sensitive Realty Holdings", "Sensitive Trade Contractor",
                    "5559991000", "Private"):
        assert contact not in serialized


def test_existing_department_worker_receives_actual_dossier_and_market_context(tmp_path):
    root=_root(tmp_path)
    routed=dispatch_source_intelligence_handoffs(
        root,now=NOW,max_jobs=2,allow_noncanonical_test=True)
    assert routed["handoffs_enqueued"]==2
    queue=DepartmentWorkQueue(root)
    assert queue.counts()["ready"]==2
    packet=json.loads(
        (root/"runtime/departments/source_intelligence_latest.json").read_text())
    for row in packet["routes"][:2]:
        review=deliver_source_intelligence_review(
            root,lane=row["lane"],fingerprint=row["evidence_fingerprint"],
            department=row["department"],
        )
        assert review["project_intelligence_review"]["cohort"][
            "recent_original_filing_or_issuance"]==0
        assert not review["project_intelligence_review"][
            "real_business_buyer_or_property_identity_verified"]
        if row["lane"]=="permit":
            assert len(review["project_intelligence_review"]["review_dossiers"])==1
        if row["lane"]=="property":
            assert not review["project_intelligence_review"]["review_dossiers"]
        assert review["outbound_sent"] is False
        assert review["payable_buyer_verified"] is False
