import pytest
from empire_os.acquisition_pool_qualification import qualify_pool

def row(ref="r1"):
    return dict(prospect_ref=ref,company="Example",offer="Approved scoped trial",
        trigger="Dated expansion",trigger_ref="evidence-1",offer_ref="offer-1",
        trigger_independently_verified=True,offer_approved=True,
        company_identity_verified=True,dated_commercial_trigger_verified=True,
        product_fit_verified=True)

def test_verified_candidate_is_review_only():
    r=qualify_pool(lane="vc_portfolio",records=[row()])
    assert r["qualified_for_review"] == 1
    assert r["contact_review_ready"] == 0
    assert r["outbound_authorized"] is False

def test_contact_gate_does_not_authorize_send():
    x=row();x.update(suppression_checked=True,contact_permission_cleared=True)
    r=qualify_pool(lane="contractor_quote",records=[x])
    assert r["contact_review_ready"] == 1
    assert not r["records"][0]["outbound_authorized"]

def test_unverified_trigger_stays_research():
    x=row();x["dated_commercial_trigger_verified"]=False
    assert qualify_pool(lane="vc_portfolio",records=[x])["qualified_for_review"] == 0

def test_duplicate_rejected():
    with pytest.raises(ValueError):qualify_pool(lane="vc_portfolio",records=[row(),row()])

def test_no_contacts_or_raw_claims_echoed():
    x=row();x["email"]="secret@example.org"
    assert "secret@example.org" not in str(qualify_pool(lane="vc_portfolio",records=[x]))
