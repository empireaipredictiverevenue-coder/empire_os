import pytest
from empire_os.acquisition_copy_bridge import prepare_acquisition_copy

def valid():
    return dict(company="Sample Co", offer="a bounded acquisition assessment",
        trigger="a publicly announced expansion", trigger_ref="research:123",
        offer_ref="offer:42", trigger_independently_verified=True, offer_approved=True)

def test_vc_lane_handoff():
    r=prepare_acquisition_copy(lane="vc_portfolio", evidence=valid())
    assert r["status"]=="READY_FOR_CANONICAL_COPY_REVIEW"
    assert r["brief"]["channel"]=="cold_email"
    assert r["brief"]["evidence"]["why_now_evidence_ref"]=="research:123"
    assert not r["send_allowed"] and not r["crm_writes"]

def test_contractor_stays_separate():
    r=prepare_acquisition_copy(lane="contractor_quote", evidence=valid())
    assert r["brief"]["product_code"]=="acquisition_contractor_quote"

def test_unverified_holds():
    e=valid();e["trigger_independently_verified"]=False
    assert prepare_acquisition_copy(lane="vc_portfolio", evidence=e)["status"]=="HOLD"

def test_missing_claim_holds():
    e=valid();e["trigger_ref"]=""
    assert "trigger_ref" in prepare_acquisition_copy(lane="contractor_quote",evidence=e)["missing_evidence"]

def test_invalid_lane():
    with pytest.raises(ValueError): prepare_acquisition_copy(lane="other",evidence=valid())
