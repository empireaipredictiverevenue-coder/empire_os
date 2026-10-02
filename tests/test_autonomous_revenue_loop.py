from empire_os.autonomous_revenue_os import (
    build_inventory_snapshot,
    diagnose_next_revenue_action,
)
from empire_os.revenue_inventory import (
    RAW_LEAD, PREQUALIFIED_LEAD, QUALIFIED_CALL,
    BOOKED_APPOINTMENT, CPA_OUTCOME,
)

PID="11111111-1111-4111-8111-111111111111"
EID="22222222-2222-4222-8222-222222222222"

class FakeBuyerAllocation:
    def latest_qualifications(self, prospect_id):
        return [{
            "id":"q1","prospect_id":PID,"entity_id":EID,
            "score":80,"tier":"hot","status":"scored",
            "scoring_version":"v2","evidence_confidence":0.8,
        }]
    def active_identity_links(self, prospect_id):
        return [{"prospect_id":PID,"entity_id":EID,"active":True}]

class FakeRepo:
    def __init__(self):
        self.buyer_allocation=FakeBuyerAllocation()
    def inventory_prospects(self, *, limit):
        return [{"id":PID,"business_name":"Roof Co","niche":"roofing","metro":"Austin, TX"}]
    def prospect_conversation_events(self, prospect_id):
        return []
    def prospect_commercial_outcomes(self, prospect_id):
        return []

def test_snapshot_classifies_canonical_prequalified_inventory():
    s=build_inventory_snapshot(repository=FakeRepo(),limit=10)
    assert s["counts"][PREQUALIFIED_LEAD]==1
    assert s["counts"][RAW_LEAD]==0
    assert s["actual_revenue"] is False

def test_diagnosis_prioritizes_raw_qualification():
    s={"counts":{RAW_LEAD:4,PREQUALIFIED_LEAD:2,QUALIFIED_CALL:0,BOOKED_APPOINTMENT:0,CPA_OUTCOME:0}}
    a=diagnose_next_revenue_action(s)
    assert a["action"]=="qualify_new_leads"
    assert a["authority"]=="internal_write"

def test_diagnosis_routes_prequalified_to_review_gate():
    s={"counts":{RAW_LEAD:0,PREQUALIFIED_LEAD:2,QUALIFIED_CALL:0,BOOKED_APPOINTMENT:0,CPA_OUTCOME:0}}
    a=diagnose_next_revenue_action(s)
    assert a["action"]=="match_prequalified_leads_to_verified_buyers"
    assert a["authority"]=="founder_gate"

def test_empty_inventory_requests_more_leads():
    s={"counts":{RAW_LEAD:0,PREQUALIFIED_LEAD:0,QUALIFIED_CALL:0,BOOKED_APPOINTMENT:0,CPA_OUTCOME:0}}
    a=diagnose_next_revenue_action(s)
    assert a["action"]=="generate_more_leads"


def test_review_queue_maps_inventory_to_correct_monetization_actions():
    from empire_os.autonomous_revenue_os import build_revenue_review_queue
    snapshot={"items":[
        {"prospect_id":"p1","stage":PREQUALIFIED_LEAD,"monetization_model":"PPL","evidence_refs":["e1"]},
        {"prospect_id":"p2","stage":QUALIFIED_CALL,"monetization_model":"PAY_PER_CALL","evidence_refs":["e2"]},
        {"prospect_id":"p3","stage":BOOKED_APPOINTMENT,"monetization_model":"BOOKED_APPOINTMENT","evidence_refs":["e3"]},
        {"prospect_id":"p4","stage":CPA_OUTCOME,"monetization_model":"CPA","evidence_refs":["e4"]},
    ]}
    q=build_revenue_review_queue(snapshot)
    assert [x["action"] for x in q]==[
        "ppl_buyer_match_review",
        "pay_per_call_or_appointment_conversion_review",
        "appointment_buyer_match_review",
        "cpa_outcome_learning_review",
    ]
    assert q[0]["founder_gate_required"] is True
    assert q[1]["founder_gate_required"] is True
    assert q[2]["founder_gate_required"] is True
    assert q[3]["founder_gate_required"] is False
    assert all(x["external_execution"] is False for x in q)


def test_diagnosis_prefers_missing_qualification_recovery():
    s={"counts":{RAW_LEAD:2,PREQUALIFIED_LEAD:1,QUALIFIED_CALL:0,BOOKED_APPOINTMENT:0,CPA_OUTCOME:0},
       "items":[
         {"stage":RAW_LEAD,"blockers":["missing_qualification","missing_active_identity_link"]},
         {"stage":RAW_LEAD,"blockers":["qualification_evidence_confidence_below_floor"]},
       ]}
    a=diagnose_next_revenue_action(s)
    assert a["action"]=="qualify_new_leads"
    assert a["candidate_count"]==1

def test_diagnosis_uses_evidence_recovery_when_no_missing_qualification():
    s={"counts":{RAW_LEAD:1,PREQUALIFIED_LEAD:1,QUALIFIED_CALL:0,BOOKED_APPOINTMENT:0,CPA_OUTCOME:0},
       "items":[
         {"stage":RAW_LEAD,"blockers":["qualification_evidence_confidence_below_floor","missing_active_identity_link"]},
       ]}
    a=diagnose_next_revenue_action(s)
    assert a["action"]=="recover_qualification_evidence"
    assert a["candidate_count"]==1

def test_diagnosis_uses_identity_recovery_when_only_identity_missing():
    s={"counts":{RAW_LEAD:1,PREQUALIFIED_LEAD:1,QUALIFIED_CALL:0,BOOKED_APPOINTMENT:0,CPA_OUTCOME:0},
       "items":[
         {"stage":RAW_LEAD,"blockers":["missing_active_identity_link"]},
       ]}
    a=diagnose_next_revenue_action(s)
    assert a["action"]=="resolve_identity_links"
    assert a["candidate_count"]==1


def test_recovery_breakdown_separates_raw_lanes():
    from empire_os.autonomous_revenue_os import _inventory_recovery_breakdown
    snapshot={"items":[
        {"stage":RAW_LEAD,"blockers":["missing_qualification","missing_active_identity_link"]},
        {"stage":RAW_LEAD,"blockers":["qualification_evidence_confidence_below_floor"]},
        {"stage":RAW_LEAD,"blockers":["missing_active_identity_link"]},
        {"stage":RAW_LEAD,"blockers":["qualification_tier_not_allocatable"]},
        {"stage":RAW_LEAD,"blockers":["something_else"]},
        {"stage":PREQUALIFIED_LEAD,"blockers":[]},
    ]}
    assert _inventory_recovery_breakdown(snapshot)=={
        "missing_qualification":1,
        "low_confidence":1,
        "missing_identity":1,
        "non_allocatable_tier":1,
        "other_raw":1,
    }


def test_lead_generation_uses_canonical_bounded_acquisition(monkeypatch):
    import empire_os.autonomous_revenue_os as revenue

    seen={}
    def fake_cycle(*, max_candidates, max_attempts):
        seen["max_candidates"]=max_candidates
        seen["max_attempts"]=max_attempts
        return {
            "ok":True,
            "canonical_acquisition_observed":True,
            "source":"overpass",
            "source_family":"broad_discovery",
            "metro":"Austin, TX",
            "country_code":"US",
            "attempt_count":1,
            "fallback_used":False,
        }

    monkeypatch.setattr(revenue,"run_acquisition_cycle",fake_cycle)
    monkeypatch.setattr(revenue,"LEAD_GENERATION_BATCH",25)

    result=revenue._run_lead_generation({
        "niche":"roofing",
        "metro":"Austin, TX",
        "opportunity_key":"opp:1",
    })

    assert seen=={"max_candidates":25,"max_attempts":2}
    assert result["ok"] is True
    assert result["canonical_acquisition_observed"] is True
    assert result["outreach_enabled"] is False
    assert result["payment_enabled"] is False
    assert result["opportunity_hint"]["niche"]=="roofing"


def test_qualification_cooldown_preserves_recent_idle_result():
    from datetime import datetime, timezone
    from empire_os.autonomous_revenue_os import _qualification_due
    previous={"qualification_result":{
        "attempted_at":datetime.now(timezone.utc).isoformat(),
        "material_actions":0,
    }}
    assert _qualification_due(previous) is False

def test_lead_generation_cooldown_preserves_last_attempt():
    from datetime import datetime, timezone
    from empire_os.autonomous_revenue_os import _lead_generation_due
    previous={"lead_generation":{
        "attempted_at":datetime.now(timezone.utc).isoformat(),
        "ok":True,
    }}
    assert _lead_generation_due(previous) is False
