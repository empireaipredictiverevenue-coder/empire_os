import pytest
from empire_os.quote_acquisition_v4 import analyze_acquisition_evidence

def row(ref, token=None, **fields):
    return {"enquiry_ref": ref, "vertical": "roofing", "evidence": {},
            "duplicate_token": token, **fields}

def review(rows):
    return analyze_acquisition_evidence(enquiries=rows, buyer_candidates={})

def test_attribution_and_rejections():
    r = review([row("1", attribution={"channel":"organic_search", "verified_acquisition_cost":"4.25", "cost_verified":True}, rejection_reason="out_of_area")])
    assert r["channel_summary"]["organic_search"]["owner_asserted_known_cost"] == "4.25"
    assert r["rejections"] == {"out_of_area":1}
    assert r["channel_summary"]["organic_search"]["roi"] is None

def test_duplicate_collisions_not_automatic_suppression():
    token = "dedupe:v1:abcdef123456"
    r = review([row("1", token),row("2", token)])
    assert r["duplicate_token_collisions"] == 1
    assert r["funnel"]["enquiries_reviewed"] == 2

def test_invalid_dedupe_token_rejected():
    with pytest.raises(ValueError):
        review([row("1", "someone@example.com")])

def test_no_pii_or_financial_claims():
    r = review([row("1", attribution={"channel":"direct", "campaign":"private@example.com"})])
    assert "private@example.com" not in str(r)
    assert r["realised_revenue"] is None
    assert r["canonical_empiredb_connected"] is False
    assert r["outbound_authorized"] is False

def test_unverified_cost_is_not_counted():
    r = review([row("1", attribution={"channel":"direct","verified_acquisition_cost":"999"})])
    assert r["channel_summary"]["direct"]["cost_records"] == 0
