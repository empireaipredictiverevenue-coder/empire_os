from empire_os.revenue_inventory import (
    RAW_LEAD,
    PREQUALIFIED_LEAD,
    QUALIFIED_CALL,
    BOOKED_APPOINTMENT,
    CPA_OUTCOME,
    classify_revenue_inventory,
)

PROSPECT_ID="11111111-1111-4111-8111-111111111111"
ENTITY_ID="22222222-2222-4222-8222-222222222222"

def prospect():
    return {"id":PROSPECT_ID,"business_name":"Roof Co","niche":"roofing","metro":"Austin, TX"}

def qualification(**overrides):
    row={"id":"q1","prospect_id":PROSPECT_ID,"entity_id":ENTITY_ID,"score":82,"tier":"hot","status":"scored","scoring_version":"v2","evidence_confidence":0.7}
    row.update(overrides); return row

def identity():
    return {"prospect_id":PROSPECT_ID,"entity_id":ENTITY_ID,"active":True}

def voice_event():
    return {
        "channel":"voice","direction":"inbound",
        "evidence":{"transcript_ref":"transcript:1","evidence_ref":"provider:1","qualification_signals":["interest","commercial_need"]}
    }

def outcome(value):
    return {"conversion_outcome":value,"evidence_reference":f"crm:{value}:1"}

def test_raw_when_not_qualified():
    r=classify_revenue_inventory(prospect=prospect())
    assert r.stage==RAW_LEAD and r.price_cents is None

def test_prequalified_requires_qualification_and_identity():
    r=classify_revenue_inventory(prospect=prospect(),qualification=qualification(),identity_link=identity())
    assert r.stage==PREQUALIFIED_LEAD
    assert r.monetization_model=="PPL"
    assert r.price_cents is None

def test_qualified_call_requires_voice_inbound_transcript_signal():
    r=classify_revenue_inventory(prospect=prospect(),qualification=qualification(),identity_link=identity(),conversation_events=[voice_event()])
    assert r.stage==QUALIFIED_CALL
    assert r.monetization_model=="PAY_PER_CALL"

def test_email_signal_does_not_become_call():
    e=voice_event(); e["channel"]="email"
    r=classify_revenue_inventory(prospect=prospect(),qualification=qualification(),identity_link=identity(),conversation_events=[e])
    assert r.stage==PREQUALIFIED_LEAD

def test_booked_requires_explicit_outcome_evidence():
    r=classify_revenue_inventory(prospect=prospect(),qualification=qualification(),identity_link=identity(),commercial_outcomes=[outcome("booked")])
    assert r.stage==BOOKED_APPOINTMENT
    assert r.product_family=="appointment"

def test_won_promotes_to_cpa_outcome():
    r=classify_revenue_inventory(prospect=prospect(),qualification=qualification(),identity_link=identity(),commercial_outcomes=[outcome("booked"),outcome("won")])
    assert r.stage==CPA_OUTCOME
    assert r.monetization_model=="CPA"
    assert r.price_cents is None
