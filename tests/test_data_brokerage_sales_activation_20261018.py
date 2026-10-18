"""Existing portfolio → actual evidence → Sales review, without elevated authority."""
from __future__ import annotations
import copy
from datetime import datetime,timezone

import pytest
from empire_os.data_brokerage_sales_activation import (
    SAFE_OFFERS, PLAYBOOK, build_sales_activation_review,
    validate_sales_activation_review,
)
from empire_os.data_brokerage_monetization_portfolio import (
    build_monetization_portfolio,
)
from scripts.preview_data_brokerage_monetization import source_catalog
from scripts.review_data_brokerage_first_sale_closeout_20261018 import inspect
from scripts import review_data_brokerage_sales_activation_20261018 as operator

def real_inputs():
    assert inspect()["status"]=="BROKERAGE_PRIVATE_SAMPLE_VERIFIED_FIRST_SALE_HELD"
    return build_monetization_portfolio(source_catalog()), inspect()

def test_existing_four_products_to_three_distinct_sales_proposals():
    portfolio,receipt=real_inputs()
    report=build_sales_activation_review(portfolio,receipt,
        now=datetime(2026,10,18,20,36,tzinfo=timezone.utc))
    assert validate_sales_activation_review(report)
    assert report["draft_package_count"]==3
    assert report["catalog_offer_hypotheses"]==14
    assert [p["offer_code"] for p in report["packages"]]==list(SAFE_OFFERS)
    assert [p["price_hypothesis"]["amount"] for p in report["packages"]]==[199,1250,4000]
    assert report["revenue_amount_recognised"]==0
    assert report["forecast_from_unaccepted_offers_enabled"] is False
    assert report["outbound_sent"] is False
    assert report["database_writes"] is False
    assert report["external_marketplace_registered"] is False

def test_each_proposal_is_always_subject_to_real_world_contract_and_delivery():
    portfolio,receipt=real_inputs()
    report=build_sales_activation_review(portfolio,receipt)
    for package in report["packages"]:
        assert package["pilot_capacity_promise_authorized"] is False
        assert package["buyer_scope_accepted"] is False
        assert package["customer_contract_verified"] is False
        assert package["payment_verified"] is False
        assert package["fulfilment_verified"] is False
        assert package["source_rights_and_licence_signed_off"] is False
        assert package["commercial_stage"]=="DRAFT_INTERNAL_NOT_SENT_OR_COMMITTED"
        assert "report" in package["proposed_delivery"].lower() or "brief" in package["proposed_delivery"].lower() or "market" in package["proposed_delivery"].lower()
        assert len(package["proof_needed_before_binding_offer"])>=4
        assert package["offer_code"] in PLAYBOOK

def test_forged_production_accepted_revenue_receipt_is_rejected():
    portfolio,receipt=real_inputs()
    for key,value in (
        ("status","FIRST_SALE_COMPLETE"),("first_sale_ready",True),
        ("revenue_or_payment_verified",True),
        ("buyer_accepted_scope_verified",True),
        ("outbound_sent",True),("database_mutation",True),
        ("payment_executed",True),
        ("report_sha256","b"*64),
    ):
        forged=copy.deepcopy(receipt)
        forged[key]=value
        with pytest.raises(ValueError):
            build_sales_activation_review(portfolio,forged)

def test_forged_existing_source_commercial_authority_rejected():
    portfolio,receipt=real_inputs()
    portfolio=copy.deepcopy(portfolio)
    portfolio["customer_data_delivery_enabled"]=True
    with pytest.raises(ValueError):
        build_sales_activation_review(portfolio,receipt)

def test_readiness_validator_cannot_be_elevated_by_mutating_output():
    portfolio,receipt=real_inputs()
    base=build_sales_activation_review(portfolio,receipt)
    scenarios=(
        (("revenue_amount_recognised",),19900),
        (("outbound_sent",),True),
        (("database_writes",),True),
        (("forecast_from_unaccepted_offers_enabled",),True),
        (("packages",1,"pilot_capacity_promise_authorized"),True),
        (("packages",1,"buyer_scope_accepted"),True),
        (("packages",1,"customer_contract_verified"),True),
        (("packages",1,"payment_verified"),True),
        (("packages",1,"live_public_listing"),True),
        (("packages",1,"commercial_stage"),"APPROVED"),
        (("packages",1,"proposed_delivery"),"Unlimited reports guaranteed"),
        (("packages",2,"proof_needed_before_binding_offer"),[]),
        (("packages",2,"price_hypothesis"),{"amount":4000,"currency":"USD","unit":"month","buyer_accepted":True,"market_price_verified":True}),
        (("packages",2,"price_hypothesis"),{"amount":4000,"currency":"USD","unit":"month","buyer_accepted":False,"market_price_verified":True}),
        (("packages",2,"price_hypothesis"),{"amount":90000,"currency":"USD","unit":"month","buyer_accepted":False,"market_price_verified":False}),
    )
    for path,value in scenarios:
        modified=copy.deepcopy(base)
        cursor=modified
        for part in path[:-1]:
            cursor=cursor[part]
        cursor[path[-1]]=value
        assert not validate_sales_activation_review(modified),path

def test_timezone_naive_rejected():
    portfolio,receipt=real_inputs()
    with pytest.raises(ValueError):
        build_sales_activation_review(portfolio,receipt,
            now=datetime(2026,10,18,20,0))

def test_readonly_operator_uses_actual_source_without_adding_records():
    summary=operator.review()
    assert summary["status"]=="THREE_BROKERAGE_DRAFT_PACKAGES_READY_REVENUE_HELD"
    assert summary["draft_offer_codes"]==list(SAFE_OFFERS)
    assert summary["registered_hypotheses"]==14
    assert summary["payment_or_revenue_verified"] is False
    assert summary["commercial_outbound_authorized"] is False
    assert summary["crm_mutation"] is False
    detailed=operator.review(show_packages=True)
    assert validate_sales_activation_review(detailed)

def test_bad_source_is_safe_redacted_hold(monkeypatch):
    monkeypatch.setattr(operator,"source_catalog",
        lambda:(_ for _ in ()).throw(ValueError("PRIVATE_SECRET_EMAIL")))
    response=operator.review(show_packages=True)
    assert response["status"]=="HOLD_SOURCE_EVIDENCE_OR_COMMERCIAL_AUTHORITY"
    assert "PRIVATE_SECRET" not in repr(response)

def test_cli_requires_exact_readonly_flag(monkeypatch,capsys):
    monkeypatch.setattr(operator,"review",lambda **_:
        (_ for _ in ()).throw(AssertionError("must not read source")))
    assert operator.main([])==2
    assert "HOLD_EXPLICIT_READ_ONLY_FLAG_REQUIRED" in capsys.readouterr().out
