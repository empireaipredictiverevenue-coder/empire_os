"""Read-only production truth requires real HTTP GET, not app route introspection."""
from __future__ import annotations
from scripts import review_brokerage_premium_live_release_20261019 as s

def private():
    return 200,{"status":s.STATUS_PRIVATE,"offers":[
        {"product_code":code,"approved_price_cents":None,
         "checkout_enabled":False,"enquiry_enabled_in_production":False}
        for code in sorted(s.PREMIUM_CODES)
    ]}

def public():
    return 200,{"status":s.STATUS_PUBLIC,"count":2,
        "offers":[
            {"product_code":code,"price_state":"DISCUSS_CUSTOM_SCOPE",
             "checkout_enabled":False,"public_approved_price_available":False}
            for code in sorted(s.PREMIUM_CODES)],
        "payment_authorized":False,"binding_terms_ready":False,
    }

def test_current_404_routes_are_release_holds_not_crm_failures():
    r=s.evaluate((404,None),(404,None),static_exists=True,
                 static_identical=False,concurrent_shared_edits=True)
    assert r["status"]=="BROKERAGE_PREMIUM_API_RELEASE_INCOMPLETE"
    assert r["private_get_http_status"]==404
    assert r["public_get_http_status"]==404
    assert r["actual_buyer_enquiry_verified"] is False
    assert r["database_writes"] is False
    assert r["end_to_end_founder_crm_delivery_verified"] is False
    assert "STAGED_SITE_BUILD_DIFFERS_FROM_CURRENT_LIVE_HTML" in r["blockers"]

def test_both_exact_gets_live_is_not_proof_of_real_buyer():
    r=s.evaluate(private(),public(),static_exists=True,
                 static_identical=True,concurrent_shared_edits=False)
    assert r["status"]=="BROKERAGE_PREMIUM_TWO_API_GET_ROUTES_LIVE_FRONTEND_UNVERIFIED"
    assert r["private_route_responds_with_two_unpriced_choices"] is True
    assert r["public_route_responds_with_two_unpriced_choices"] is True
    assert r["actual_buyer_enquiry_verified"] is False
    assert r["end_to_end_founder_crm_delivery_verified"] is False
    assert r["payment_settlement_verified"] is False

def test_no_price_or_paid_claim_may_pass_live_read_only():
    changes=(
        ("private","offer_price",True),
        ("public","offer_price",True),
        ("public","payment_authorized",True),
        ("private","offer_code",True),
        ("public","offer_code",True),
    )
    for target,key,_ in changes:
        p=private();g=public()
        v=p[1] if target=="private" else g[1]
        if key=="offer_price":
            v["offers"][0]["approved_price_cents"]=125000
            if target=="public":
                v["offers"][0]["public_approved_price_available"]=True
        elif key=="payment_authorized":
            v["payment_authorized"]=True
        elif key=="offer_code":
            v["offers"][0]["product_code"]="fake_new_product"
        r=s.evaluate(p,g,static_exists=True,
                     static_identical=True,concurrent_shared_edits=False)
        assert r["status"]=="BROKERAGE_PREMIUM_API_RELEASE_INCOMPLETE"

def test_source_failure_fail_closed_and_does_not_echo_secrets():
    def boom(url):
        raise RuntimeError("SENSITIVE_FULL_CUSTOMER_EMAIL")
    result=s.inspect(getter=boom)
    assert result["status"]=="HOLD_PREMIUM_RELEASE_EVIDENCE_UNAVAILABLE"
    assert "SENSITIVE" not in str(result)

def test_same_hash_check_has_no_file_writes(tmp_path):
    left=tmp_path/"live.html";right=tmp_path/"new.html"
    left.write_bytes(b"existing ASTRA page")
    right.write_bytes(b"new website")
    assert s.same_site_build(left,right)==(True,False)
    right.write_bytes(b"existing ASTRA page")
    assert s.same_site_build(left,right)==(True,True)
    assert s.same_site_build(left,tmp_path/"missing")==(False,False)

def test_readonly_exact_two_url_allowlist():
    try:
        s.get_json("https://evil.invalid/data")
    except ValueError:
        pass
    else:
        raise AssertionError("external arbitrary fetch allowed")

def test_no_flag_rejects_before_network(monkeypatch,capsys):
    monkeypatch.setattr(s,"inspect",lambda:(_ for _ in ()).throw(
        RuntimeError("SHOULD_NOT_RUN_NETWORK")))
    assert s.main([])==2
    assert "HOLD_EXPLICIT_READ_ONLY_REQUIRED" in capsys.readouterr().out

def test_inject_readonly_http_and_site_evidence():
    got=[]
    def getter(url):
        got.append(url)
        return private() if url==s.PRIVATE_URL else public()
    r=s.inspect(getter=getter,files=lambda:(True,False),edits=lambda:True)
    assert got==[s.PRIVATE_URL,s.PUBLIC_URL]
    assert r["shared_gateway_checkout_edits_pending"] is True
    assert "STAGED_SITE_BUILD_DIFFERS_FROM_CURRENT_LIVE_HTML" in r["blockers"]
    assert r["realised_revenue_verified"] is False
