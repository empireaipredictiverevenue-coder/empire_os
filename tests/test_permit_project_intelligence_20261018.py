"""Permit imports are not automatically current projects or paying buyers."""
import json
from datetime import datetime, timedelta, timezone
import pytest
from empire_os.permit_project_intelligence import analyze_permit_project_intelligence

NOW = datetime(2026, 10, 18, 9, 30, tzinfo=timezone.utc)


def record(job="402424051", filing="02/09/2007", issued=None, status="IN PROCESS"):
    return {
        "signal_id": "sig-" + job, "source": "permits_nyc",
        "created_at": NOW.isoformat(), "last_seen_at": NOW.isoformat(),
        "url": ("https://a810-biswebportal.nyc.gov/bisweb/"
                "PropertyOverflowDetails.jsp?job=" + job),
        "raw": {
            "job__": job, "filing_date": filing, "issuance_date": issued,
            "dobrundate": "2026-10-18T00:00:00.000",
            "permit_status": status, "filing_status": "INITIAL",
            "job_type": "A2", "work_type": "PL", "borough": "QUEENS",
            "bbl": "4006810011", "bin__": "4011278",
            "owner_s_business_name": "Private Owner Corporation",
            "owner_s_first_name": "Private Person",
            "owner_s_phone__": "5551118899",
            "permittee_s_business_name": "Private Builder",
            "permittee_s_phone__": "5552228899",
            "street_name": "PRIVATE STREET",
        },
    }


def fixture(root, rows, market=True):
    p = root / "runtime/acquisition/signal_inbox.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({r["signal_id"]:r for r in rows}))
    if market:
        m=root / "runtime/market_sweeps/revenue_gps_latest.json"
        m.parent.mkdir(parents=True, exist_ok=True)
        m.write_text(json.dumps({
            "generated_at": NOW.isoformat(), "execution_authority": "none",
            "markets": [
                {"metro":"nyc", "niche":"plumbing",
                 "commercial_demand_state":"not_observed",
                 "commercial_reply_count":0,"approved_buyer_count":0,
                 "verified_payment_count":0},
            ],
        }))


def test_new_import_of_decades_old_filing_not_buyer(tmp_path):
    fixture(tmp_path,[record()])
    d=analyze_permit_project_intelligence(tmp_path,now=NOW)
    c=d["cohort"]
    assert c["first_imported_last_24h"]==1
    assert c["recent_original_filing_or_issuance"]==0
    assert c["historical_project_source_only"]==1
    a=d["review_dossiers"][0]
    assert a["original_filing_date"]=="2007-02-09"
    assert a["official_source_run_date"]=="2026-10-18"
    assert a["date_truth_classification"]=="HISTORICAL_PROJECT_SOURCE_ONLY"
    assert a["route"]["sales_promotion_authorized"] is False
    assert a["market_gps_context"]["commercial_demand_state"]=="not_observed"
    assert a["market_gps_context"]["matched_to_this_specific_project"] is False
    assert a["identity_roles"]["owner_and_permittee_must_not_be_conflated"]


def test_recent_filing_and_recent_issuance_both_require_review(tmp_path):
    records=[
        record(job="402424052",filing="10/15/2026"),
        record(job="402424053",issued="10/17/2026",status="ISSUED"),
    ]
    fixture(tmp_path,records)
    d=analyze_permit_project_intelligence(tmp_path,now=NOW)
    assert d["cohort"]["recent_original_filing_or_issuance"]==2
    assert {a["date_truth_classification"] for a in d["review_dossiers"]}=={
        "RECENT_FILING_FOR_PROJECT_REVIEW","RECENT_ISSUANCE_FOR_PROJECT_REVIEW"}
    assert all(not a["route"]["sales_promotion_authorized"]
               for a in d["review_dossiers"])


@pytest.mark.parametrize("bad", [
    "https://a810-biswebportal.nyc.gov.evil.example/bisweb/PropertyOverflowDetails.jsp?job=402424051",
    "http://a810-biswebportal.nyc.gov/bisweb/PropertyOverflowDetails.jsp?job=402424051",
    "https://a810-biswebportal.nyc.gov/bisweb/PropertyOverflowDetails.jsp?job=402424052",
    "https://a810-biswebportal.nyc.gov/bisweb/PropertyOverflowDetails.jsp?job=402424051&token=x",
    "javascript:alert(1)",
])
def test_spoofed_or_wrong_url_never_verified(tmp_path,bad):
    r=record()
    r["url"]=bad
    fixture(tmp_path,[r])
    a=analyze_permit_project_intelligence(tmp_path,now=NOW)["review_dossiers"][0]
    assert a["source_evidence_url"] is None
    assert a["date_truth_classification"]=="UNTRUSTED_SOURCE_OR_MISSING_FILING_DATE"


def test_no_pii_export_max_three_dossiers(tmp_path):
    rows=[record(job=str(402424051+n)) for n in range(18)]
    fixture(tmp_path,rows)
    d=analyze_permit_project_intelligence(tmp_path,now=NOW,max_dossiers=3)
    assert d["review_dossier_count"]==3
    assert d["cohort"]["first_imported_last_24h"]==18
    serialized=json.dumps(d)
    for sensitive in ("Private Owner Corporation","Private Person",
                      "5551118899","5552228899","PRIVATE STREET"):
        assert sensitive not in serialized
    assert d["paid_model_invoked"] is False
    assert d["automatic_sales_promotion"] is False
    assert d["recognised_revenue_proven"] is False


def test_meaningful_filing_change_detected_and_time_aging_not_a_change(tmp_path):
    r=record()
    fixture(tmp_path,[r])
    old=analyze_permit_project_intelligence(tmp_path,now=NOW)
    aged=analyze_permit_project_intelligence(tmp_path,now=NOW+timedelta(hours=1))
    assert old["total_retained_source_semantics_digest"]==aged["total_retained_source_semantics_digest"]
    r["raw"]["issuance_date"]="10/18/2026"
    r["raw"]["permit_status"]="ISSUED"
    fixture(tmp_path,[r])
    update=analyze_permit_project_intelligence(tmp_path,now=NOW)
    assert old["total_retained_source_semantics_digest"]!=update["total_retained_source_semantics_digest"]


def test_missing_own_source_keeps_unknown_and_does_not_write(tmp_path):
    d=analyze_permit_project_intelligence(tmp_path,now=NOW)
    assert d["cohort"]["first_imported_last_24h"]==0
    assert d["review_dossiers"]==[]
    assert not list(tmp_path.iterdir())


def test_future_issuance_conflict_never_promotes_even_when_filing_recent(tmp_path):
    fixture(tmp_path, [record(job="402424054", filing="10/17/2026",
                              issued="11/18/2026", status="ISSUED")])
    d = analyze_permit_project_intelligence(tmp_path, now=NOW)
    assert d["cohort"]["recent_original_filing_or_issuance"] == 0
    sample = d["review_dossiers"][0]
    assert sample["date_truth_classification"] == "SOURCE_DATE_CONFLICT"
    assert sample["route"]["sales_promotion_authorized"] is False
