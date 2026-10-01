from empire_os.predictive_revenue_enterprise_pool import build_rolling_enterprise_pool

def proposal(name, domain, *, pools=None, products=None, emails=None, buyer_type="qualified_end_buyer"):
    return {
        "candidate_id": domain,
        "domain": domain,
        "buyer_type": buyer_type,
        "target_buyer_pools": pools or ["enterprise_and_data_buyers"],
        "target_product_codes": products or [],
        "first_party_emails_preserved_for_identity_resolution": emails or ["person@" + domain],
        "proposed_prospect_payload": {
            "business_name": name,
            "website": "https://" + domain + "/",
        },
    }

def test_pool_adds_beyond_seed_nine_and_stays_no_send():
    plan = {"proposals": [proposal(f"Enterprise {i}", f"enterprise{i}.com") for i in range(40)]}
    out = build_rolling_enterprise_pool(plan, limit=25)
    assert out["seed_target_count"] == 9
    assert out["rolling_addition_count"] == 25
    assert out["total_enterprise_candidate_count"] == 34
    assert out["outreach_authorized"] is False
    assert out["payment_action"] is False

def test_pool_rejects_search_and_press_release_noise():
    plan = {"proposals": [
        proposal("Google Search - A new kind of help", "search.google"),
        proposal("Best Press Release Distribution", "abnewswire.com"),
        proposal("Acme Revenue Platform", "acme.com"),
    ]}
    out = build_rolling_enterprise_pool(plan, limit=25)
    domains = {r["domain"] for r in out["rolling_candidates"]}
    assert "search.google" not in domains
    assert "abnewswire.com" not in domains
    assert "acme.com" in domains
