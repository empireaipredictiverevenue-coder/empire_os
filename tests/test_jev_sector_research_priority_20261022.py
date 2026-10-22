"""Jev ranks only historical aggregate research, never marketable people."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import pytest

from empire_os.jev_sector_research_priority import prioritize_sector_research
from empire_os.typed_decision_provider import TypedDecisionResult

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT/"docs/commercial/JEV_LARGE_PROSPECT_DUMP_STREAM_20261021.json"
GPS=Path("/srv/empire_os/runtime/market_sweeps/revenue_gps_latest.json")
CAPACITY=Path("/srv/empire_os/runtime/buyer_capacity_readiness/latest.json")
NOW=datetime(2026,10,22,8,0,tzinfo=timezone.utc)


def inputs():
    a=json.loads(ARCHIVE.read_text())
    g=json.loads(GPS.read_text())
    b=json.loads(CAPACITY.read_text())
    g["generated_at"]=(NOW-timedelta(minutes=15)).isoformat()
    b["observed_at"]=(NOW-timedelta(minutes=14)).isoformat()
    # Fixture clock must be independent of parallel production refreshes.
    return a,g,b


def audit(*,archive=None,gps=None,buyer=None,provider=None,calls=0):
    a,g,b=inputs()
    return prioritize_sector_research(
        a if archive is None else archive,
        market_gps=g if gps is None else gps,
        buyer_capacity=b if buyer is None else buyer,
        as_of=NOW,provider=provider,max_shadow_calls=calls)


class LocalModel:
    def __init__(self,label="CHECK_RECENT_DEMAND",provider_key="laya_http",shadow=True,broken=False):
        self.label=label
        self.key=provider_key
        self.shadow=shadow
        self.broken=broken
        self.requests=[]

    def evaluate(self,req):
        self.requests.append(req)
        assert req.task_key=="sector_research_priority"
        assert set(req.state)=={
            "niche","historic_record_count","recent_gps_observations",
            "recent_gps_snapshot_current","current_prospect_identity_verified",
            "buyer_buybox_verified","rights_verified",
        }
        assert all(req.state[k] is False for k in (
            "current_prospect_identity_verified","buyer_buybox_verified",
            "rights_verified"))
        assert "http" not in json.dumps(req.state)
        if self.broken:
            raise RuntimeError("model unavailable")
        return TypedDecisionResult(
            provider_key=self.key,model_key="local-laya-fixture",
            task_key=req.task_key,decision_schema_ref=req.decision_schema_ref,
            state_ref=req.state_ref,label=self.label,confidence=.88,
            latency_ms=17.0,source_ref="local:shadow:synthetic",
            shadow_only=self.shadow,execution_authority="none",
        )


def test_all_32899_archived_rows_get_unambiguous_aggregate_sector_review():
    output=audit()
    assert output["historical_archive_rows"]==32899
    assert output["sector_count"]==28
    assert sum(r["historical_prospect_rows"] for r in output["sector_research_rows"])==32899
    assert output["market_gps_snapshot_current"] is True
    assert output["specific_buyer_capacity_verified"] is False
    assert output["research_lane_counts"]=={
        "CORROBORATE_RECENT_ORIGINAL_DEMAND":3,
        "VERIFY_ARCHIVE_SOURCE_AND_FRESHNESS":6,
        "REGULATED_SOURCE_RIGHTS_REVIEW":10,
        "BACKGROUND_RIGHTS_REVIEW":8,
        "REMAP_TAXONOMY":1,
    }
    assert [r["niche"] for r in output["sector_research_rows"][:3]]==[
        "general_contractor","roofing","hvac"]
    assert output["prospects_scored_individually"]==0
    assert output["personal_records_exported"]==0
    assert output["outreach_sent"]==0
    assert output["database_writes"] is False
    assert output["execution_authority"]=="none"


def test_no_recent_gps_proof_never_creates_demand_score():
    _,g,_=inputs()
    g["generated_at"]=(NOW-timedelta(days=2)).isoformat()
    out=audit(gps=g)
    assert out["market_gps_snapshot_current"] is False
    assert not any(r["research_lane"]=="CORROBORATE_RECENT_ORIGINAL_DEMAND"
                   for r in out["sector_research_rows"])
    assert all(r["recent_gps_observed_acquisitions_not_buyer_demand"] is None
               for r in out["sector_research_rows"])
    assert out["outreach_sent"]==0


def test_no_specific_capacity_even_if_aggregate_source_configured():
    _,_,b=inputs()
    b.update(capacity_verified=2,terms_verified=2,delivery_verified=2,
             commercially_activated=2)
    out=audit(buyer=b)
    assert out["buyer_capacity_source_status"]=="AGGREGATE_CAPACITY_NOT_SPECIFIC_BUYBOX"
    assert out["specific_buyer_capacity_verified"] is False
    assert all(not r["specific_buyer_buybox_verified"]
               for r in out["sector_research_rows"])


@pytest.mark.parametrize("field,new",[
    ("historical_independent_id_set_match",False),
    ("source_contacts_or_names_exported",True),
    ("source_rights_and_individual_consent_verified",True),
    ("commercial_leads_authorized",1),
    ("outreach_sent",1),
    ("source_file_sha256","bad"),
    ("database_writes",True),
])
def test_cannot_inflate_archive_data_or_commercial_authority(field,new):
    a,_,_=inputs()
    a[field]=new
    with pytest.raises(ValueError):
        audit(archive=a)


def test_modified_aggregate_totals_are_rejected():
    a,_,_=inputs()
    a["niche_aggregate_counts"]["roofing"]+=900
    with pytest.raises(ValueError,match="reconcile"):
        audit(archive=a)


@pytest.mark.parametrize("field,value",[
    ("buyer_intent_inferred",True),
    ("commercial_intent_inferred",True),
    ("revenue_inferred",True),
    ("outreach_enabled",True),
])
def test_gps_does_not_turn_acquisition_observation_into_buyer_claim(field,value):
    _,gps,_=inputs()
    gps[field]=value
    with pytest.raises(ValueError):
        audit(gps=gps)


def test_higher_level_local_model_is_advisory_only():
    model=LocalModel(label="VERIFY_BUYER_CAPACITY")
    output=audit(provider=model,calls=2)
    assert output["local_shadow_attempts"]==2
    assert len(model.requests)==2
    assert output["sector_research_rows"][0]["local_model_suggestion"]=="VERIFY_BUYER_CAPACITY"
    assert output["sector_research_rows"][0]["research_lane"]=="CORROBORATE_RECENT_ORIGINAL_DEMAND"
    assert all(not row["auto_contact_authority"] for row in output["sector_research_rows"])
    assert output["verified_contactable_leads"]==0


@pytest.mark.parametrize("options",[
    {"provider_key":"hosted_jev"},
    {"shadow":False},
    {"label":"SEND_OUTREACH"},
    {"broken":True},
])
def test_untrusted_or_unavailable_model_cannot_change_research_queue(options):
    model=LocalModel(**options)
    out=audit(provider=model,calls=1)
    assert out["local_shadow_attempts"]==1
    assert out["sector_research_rows"][0]["shadow_status"]=="SHADOW_UNAVAILABLE_HELD"
    assert out["sector_research_rows"][0]["research_lane"]=="CORROBORATE_RECENT_ORIGINAL_DEMAND"
    assert out["outreach_sent"]==0


def test_no_automatic_paid_model_budget():
    with pytest.raises(ValueError):
        audit(calls=1)
    with pytest.raises(ValueError):
        audit(calls=3)


def test_guarded_sector_queue_contains_no_person_ids():
    result=audit()
    body=json.dumps(result,sort_keys=True)
    for term in ("@", "prospect_id", "phone", "contact_name", "reddit.com",
                 "private.example","source_reference_sha256"):
        assert term not in body


def test_owner_review_packets_are_non_dispatching_and_non_overlapping():
    packet=audit()
    groups=packet["existing_owner_review_packets"]
    assert len(groups)==5
    assert sum(g["historical_rows_needing_research"] for g in groups)==32899
    assert sum(g["source_niche_count"] for g in groups)==28
    assert [g["lane"] for g in groups]==[
        "CORROBORATE_RECENT_ORIGINAL_DEMAND",
        "VERIFY_ARCHIVE_SOURCE_AND_FRESHNESS",
        "REGULATED_SOURCE_RIGHTS_REVIEW",
        "BACKGROUND_RIGHTS_REVIEW",
        "REMAP_TAXONOMY",
    ]
    assert all(g["dispatch_authorized"] is False
               and g["crm_or_outbound_authority"] is False
               and g["real_buyer_demand_verified"] is False
               and g["payable_buyer_capacity_verified"] is False
               and g["required_independent_evidence"]
               and g["existing_owner"]
               for g in groups)


def test_pinned_live_review_packet_is_aggregate_and_non_executable():
    from hashlib import sha256
    from scripts.review_jev_sector_research_priority_20261022 import ARCHIVE_SHA256
    receipt_file=ROOT/"docs/commercial/JEV_SECTOR_RESEARCH_PRIORITY_20261022.json"
    receipt=json.loads(receipt_file.read_text())
    assert receipt["original_source_receipt_sha256"]==ARCHIVE_SHA256
    assert sha256(ARCHIVE.read_bytes()).hexdigest()==ARCHIVE_SHA256
    assert receipt["status"]=="AUDITED_HISTORICAL_SECTOR_RESEARCH_QUEUE_ONLY"
    assert receipt["historical_archive_rows"]==32899
    assert receipt["sector_count"]==28
    assert len(receipt["existing_owner_review_packets"])==5
    assert receipt["local_shadow_attempts"]==1
    assert receipt["market_gps_snapshot_current"] is True
    assert receipt["buyer_capacity_source_status"]=="NO_VERIFIED_COMMERCIAL_CAPACITY"
    assert receipt["outreach_sent"]==0
    assert receipt["verified_contactable_leads"]==0
    assert receipt["automatic_research_dispatch"] is False
    assert receipt["prospects_scored_individually"]==0
    assert receipt["database_writes"] is False
    assert receipt["execution_authority"]=="none"
    data=receipt_file.read_text()
    for text in ("@", "reddit.com", "contact_name", "phone_number",
                 "buyer_email", "source_reference_sha256"):
        assert text not in data


def test_regulated_sector_never_selected_for_automatic_contact():
    p=audit()
    for row in p["sector_research_rows"]:
        if row["niche"] in {"medical_claims","debt_relief","auto_insurance",
                            "medicare_advantage_agent","home_health_agency"}:
            assert row["research_lane"]=="REGULATED_SOURCE_RIGHTS_REVIEW"
            assert row["auto_contact_authority"] is False
            assert row["local_model_suggestion"] is None
