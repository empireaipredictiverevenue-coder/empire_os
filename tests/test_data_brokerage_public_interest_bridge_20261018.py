"""First sale: original 199 public intake is distinct from internal premium drafts."""
from __future__ import annotations
import copy
import json

from empire_os.data_brokerage_public_interest_bridge import review_visibility
from scripts.review_data_brokerage_sales_activation_20261018 import review
from scripts import review_data_brokerage_public_interest_20261018 as operator


def current_private():
    value=review(show_packages=True)
    assert value["status"]=="THREE_BROKERAGE_DRAFT_PACKAGES_READY_REVENUE_HELD"
    return value

def public_catalog():
    return {
        "schema_version":"empire.first-party-commercial-interest.v1",
        "status":"FOUNDER_LED_ENQUIRY_AVAILABLE","scope":"BUYER_INITIATED_CONTACT_ONLY",
        "outbound_authority":"none","payment_authority":"none",
        "commercial_terms_binding":False,"checkout_authorized":False,"actual_revenue":False,
        "count":1,
        "offers":[{
            "product_code":"competitor_search_gap","offer_family":"intelligence_product",
            "approved_price_cents":19900,"currency":"USD","price_interval":"one_time",
            "sale_mode":"FOUNDER_LED_PROPOSAL_ONLY",
            "checkout_enabled":False,"binding_terms_ready":False,
            "fulfilment_automated":False,
        }]
    }

def test_public_entry_and_private_agency_enterprise_truth():
    r=review_visibility(current_private(),public_catalog())
    assert r["status"]=="ONE_PUBLIC_ENTRY_TWO_PRIVATE_RECURRING_DRAFTS"
    assert r["public_entry_match_count"]==1
    assert r["internal_brokerage_packages"]==3
    assert r["private_recurring_package_count"]==2
    assert r["end_to_end_website_to_crm_proved"] is False
    assert r["website_mutation"] is False
    assert r["database_writes"] is False
    assert [r["packages"][i]["founder_enquiry_catalog_match"] for i in range(3)]==[
        True,False,False
    ]
    assert all(x["payment_or_contract_executed"] is False for x in r["packages"])

def test_missing_199_public_offer_is_hold_not_claim_of_buyer_data():
    p=public_catalog()
    p["offers"]=[dict(p["offers"][0],product_code="other_valid_product")]
    r=review_visibility(current_private(),p)
    assert r["status"]=="BROKERAGE_NO_PUBLIC_ENTRY_ON_CURRENT_CATALOG"
    assert r["public_entry_match_count"]==0

def test_forgeries_cannot_infer_authority():
    for field,value in (
        ("approved_price_cents",400000),
        ("currency","GBP"),
        ("price_interval","month"),
        ("checkout_enabled",True),
        ("binding_terms_ready",True),
        ("sale_mode","LIVE_PAID_SUBSCRIPTION"),
    ):
        p=public_catalog()
        p["offers"][0][field]=value
        try:review_visibility(current_private(),p)
        except ValueError:pass
        else:raise AssertionError(f"unsafe public claim allowed: {field}")

def test_publicly_spoofed_internal_offer_is_blocked():
    for code in ("agency_white_label_search","portfolio_geography_intelligence"):
        p=public_catalog()
        p["offers"].append(dict(p["offers"][0],product_code=code))
        p["count"]+=1
        try:review_visibility(current_private(),p)
        except ValueError:pass
        else:raise AssertionError("an unapproved public SKU was accepted")

def test_private_pack_forged_buyer_acceptance_is_denied():
    p=current_private()
    p["packages"][1]["buyer_scope_accepted"]=True
    try:review_visibility(p,public_catalog())
    except ValueError:pass
    else:raise AssertionError("buyer intent invented")

def test_fail_closed_catalog_and_error_redaction():
    for change in (
        {"outbound_authority":"approved"},
        {"payment_authority":"on"},
        {"count":4},
        {"scope":"SELL_TO_ALL"},
        {"actual_revenue":True},
        {"commercial_terms_binding":True},
    ):
        p=public_catalog();p.update(change)
        try:review_visibility(current_private(),p)
        except ValueError:pass
        else:raise AssertionError(f"catalog drift accepted {change}")

def test_operator_never_posts_and_returns_redacted_hold():
    result=operator.inspect(public_fetch=public_catalog,private_fetch=lambda **_:current_private())
    assert result["status"]=="ONE_PUBLIC_ENTRY_TWO_PRIVATE_RECURRING_DRAFTS"
    invalid=operator.inspect(
        public_fetch=lambda:(_ for _ in ()).throw(ValueError("personal-contact-private-secret")),
        private_fetch=lambda **_:current_private(),
    )
    assert invalid["status"]=="HOLD_PUBLIC_ENQUIRY_SOURCE_OR_PRIVATE_AUTHORITY_UNVERIFIED"
    assert "private-secret" not in json.dumps(invalid)

def test_cli_needs_explicit_read_only(monkeypatch,capsys):
    monkeypatch.setattr(operator,"inspect",lambda **_:(_ for _ in ()).throw(
        RuntimeError("unexpected network access")))
    assert operator.main([])==2
    assert "HOLD_EXPLICIT_GET_ONLY_APPROVAL_REQUIRED" in capsys.readouterr().out
