from empire_os.commercial_trial_conversion_review import review_trial, STAGES
import pytest

def test_empty_holds():
    r=review_trial({})
    assert r["owner_asserted_stage"]=="DISCOVERY"
    assert r["next_review"]=="prospect_qualified"

def test_skipped_proof_does_not_promote():
    r=review_trial({"prospect_qualified": True, "trial_result_verified": True})
    assert r["owner_asserted_stage"]=="PROSPECT_QUALIFIED"
    assert "terms_accepted" in r["unmet_evidence"]

def test_complete_still_not_verified_revenue():
    r=review_trial(dict.fromkeys(STAGES,True))
    assert r["owner_asserted_stage"]=="SETTLEMENT_VERIFIED"
    assert r["realised_revenue"] is None
    assert not r["payment_execution"] and not r["trial_activated"]

def test_no_contact_leak():
    r=review_trial({"email":"person@private.example"})
    assert "person@private.example" not in str(r)

def test_type_rejected():
    with pytest.raises(ValueError): review_trial(None)
