import json
from copy import deepcopy
from datetime import date
from pathlib import Path
import pytest

from empire_os.storm_contractor_independent_evidence import (
    review_official_state_dataset,
)
from empire_os.storm_contractor_review import build_contractor_review

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 10, 10)


def load(name):
    return json.loads((ROOT / name).read_text())


def sources():
    cohort=load("runtime/revenue_strike/dfw_storm_2026-09-20.json")
    sites=load("docs/DFW_SITE_OBSERVATIONS_20261009.json")
    signals=load("docs/DFW_CONTRACTOR_PUBLIC_SIGNALS_20261009.json")
    third=load("docs/DFW_CONTRACTOR_INDEPENDENT_EVIDENCE_20261009.json")
    official=load("docs/DFW_CONTRACTOR_TEXAS_PUBLIC_ENTITY_RESEARCH_20261010.json")
    return cohort, sites, signals, third, official


def review(inp):
    a,b,c,d,e=inp
    return build_contractor_review(
        a,b,c,as_of=TODAY,independent_evidence=d,state_registry_evidence=e,
    )


def test_official_data_three_exact_names_do_not_clear_commercial_or_legal_gates():
    r=review(sources())
    s=r["summary"]
    assert s["historical_contractor_companies"]==8
    assert s["official_state_dataset_name_matches"]==3
    assert s["official_state_code_review_holds"]==1
    assert s["official_live_account_status_verified"]==0
    assert s["verified_company_legal_registrations"]==0
    assert s["independently_verified_purchase_intent"]==0
    assert [p["company_domain"] for p in r["packets"][:2]]==[
        "maxexteriors.com","spcroofs.com",
    ]
    for domain in ("maxexteriors.com","spcroofs.com"):
        row=next(x for x in r["packets"] if x["company_domain"]==domain)
        assert row["research_priority_score"]==75
        assert row["official_state_entity_research"]["right_to_transact_business_code_raw"]=="A"
        assert row["official_state_entity_research"]["live_official_account_status_verified"] is False
        assert row["official_state_entity_research"]["website_entity_control_verified"] is False
        assert not row["founder_review_ready"] and not row["outbound_authorized"]


def test_non_a_official_code_blocks_one_180_roofing_candidate_without_interpreting_it():
    out=review(sources())
    row=next(p for p in out["packets"] if p["company_domain"]=="180roofing.com")
    assert row["qualification"]=="OFFICIAL_STATE_CODE_REVIEW_HOLD"
    assert row["research_priority_score"]==0
    assert "RECHECK_CURRENT_TEXAS_FRANCHISE_RIGHT_TO_TRANSACT_NO_CONTACT" in row["review_tasks"]
    data=row["official_state_entity_research"]
    assert data["right_to_transact_business_code_raw"]=="N"
    assert data["status"]=="STATE_CODE_REVIEW_HOLD"
    assert data["live_official_account_status_verified"] is False
    assert not row["outbound_authorized"]


def test_multiple_broad_results_never_auto_merge_max_exteriors_lookalikes():
    out=review(sources())
    row=next(p for p in out["packets"] if p["company_domain"]=="maxexteriors.com")
    assert row["official_state_entity_research"]["broad_similar_name_row_count"]==3
    assert row["official_state_entity_research"]["official_name_match_count"]==1


def test_source_unavailable_is_explicit_unverified_not_legal_registration():
    a,b,c,d,_=sources()
    out=build_contractor_review(a,b,c,as_of=TODAY,independent_evidence=d)
    assert out["summary"]["official_state_dataset_name_matches"]==0
    assert out["summary"]["verified_company_legal_registrations"]==0


@pytest.mark.parametrize("tamper",[
    ("source_url","https://evil.example.com/data.json"),
    ("dataset_id","other-dataset"),
    ("outbound_authorized",True),
    ("official_live_account_status_verified",True),
    ("status_codes_uninterpreted",False),
])
def test_untrusted_official_payload_fails_closed(tamper):
    a=list(sources())
    a[4][tamper[0]]=tamper[1]
    with pytest.raises(ValueError):
        review(a)


def test_misassigned_official_entity_file_not_promoted():
    a=list(sources())
    a[4]["records"][0]["company_domain"]="spcroofs.com"
    with pytest.raises(ValueError):
        review(a)


def test_official_exact_match_not_unique_rejected():
    a=list(sources())
    a[4]["records"][0]["exact_normalized_name_matches"]=2
    with pytest.raises(ValueError):
        review(a)


def test_official_dataset_staleness_cannot_drive_auto_authorisation():
    a=list(sources())
    a[4]["dataset_last_reported_update_date"]="2025-01-01"
    with pytest.raises(ValueError,match="DATASET_NOT_CURRENT"):
        review(a)


def test_fabricated_official_identity_or_suppression_flag_rejected():
    a=list(sources())
    a[4]["records"][0]["verified_web_domain_is_same_entity"]=True
    with pytest.raises(ValueError,match="AUTHORITY"):
        review(a)


def test_state_parser_no_direct_pii_or_marketing_email_created():
    a,b,c,d,e=sources()
    names={r["company_domain"]:r["listed_business_name"] for r in d["records"]}
    result=review_official_state_dataset(e,approved_bbb_names=names,as_of=TODAY)
    assert set(result)=={"maxexteriors.com","180roofing.com","spcroofs.com"}
    assert not any(row["outbound_authorized"] for row in result.values())
    assert all(row["named_recipient_suppression_verified"] is False for row in result.values())
