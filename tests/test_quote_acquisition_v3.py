import pytest
from empire_os.quote_acquisition_review import GATES
from empire_os.quote_acquisition_v3 import review_quote_funnel

def request(**kw):
    value = dict.fromkeys(GATES, True)
    value.update(kw)
    return {"enquiry_ref": "opaque-1", "vertical": "roofing", "evidence": value,
            "email": "private@example.com"}

def buyer():
    return {"buyer_ref": "contractor-1", "contracted": True,
            "service_match": True, "territory_match": True,
            "capacity_verified": True, "terms_accepted": True,
            "delivery_permission": True, "remaining_capacity": 3}

def run(req, buyers=None):
    return review_quote_funnel(enquiries=[req],
                               buyer_candidates={"opaque-1": [buyer()] if buyers is None else buyers})

def test_ready_quote_is_only_matched_without_acceptance_proof():
    r = run(request())
    assert r["queue"][0]["stage"] == "matched"
    assert r["stage_counts_owner_asserted"]["settled"] == 0
    assert r["realised_revenue"] is None

def test_no_skipping_stages():
    r = run(request(contact_permission=False, canonical_settlement_verified=True))
    assert r["queue"][0]["stage"] == "captured"

def test_successive_owner_evidence_still_is_not_verified_revenue():
    q = request(canonical_buyer_acceptance_verified=True,
                canonical_appointment_verified=True,
                canonical_completion_verified=True,
                canonical_settlement_verified=True)
    r = run(q)
    assert r["queue"][0]["stage"] == "settled"
    assert r["source_verification"] == "UNVERIFIED_OWNER_INPUT"
    assert r["realised_revenue"] is None

def test_private_fields_are_never_echoed():
    assert "private@example.com" not in str(run(request()))

def test_duplicate_and_unbounded_rejected():
    with pytest.raises(ValueError):
        review_quote_funnel(enquiries=[request(), request()],
                            buyer_candidates={})
    with pytest.raises(ValueError):
        review_quote_funnel(enquiries=[request()] * 101, buyer_candidates={})
