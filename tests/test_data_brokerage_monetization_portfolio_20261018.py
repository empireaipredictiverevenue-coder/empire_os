"""No new customer authority from potential Data Brokerage pricing channels."""
import copy
from datetime import datetime, timezone
from pathlib import Path
import json

import pytest

from empire_os.data_brokerage_monetization_portfolio import (
    _MODELS,_CHANNELS,SCHEMA,
    build_monetization_portfolio,validate_portfolio,
)
from scripts.preview_data_brokerage_monetization import (
    PRIVATE_CATALOG,ROOT,source_catalog,preview,main
)

def trusted_catalog():
    return source_catalog(ROOT)

def test_real_private_catalog_yields_four_sources_fourteen_pricing_options():
    report=build_monetization_portfolio(
        trusted_catalog(),assessed_at=datetime(2026,10,18,18,tzinfo=timezone.utc)
    )
    assert report["schema_version"]==SCHEMA
    assert report["existing_product_count"]==4
    assert report["option_count"]==14
    assert report["route_count"]==6
    assert validate_portfolio(report)
    assert {p["existing_product_id"] for p in report["options"]} == {
        "uk_brownfield_site_change_intelligence",
        "nyc_permit_project_verification",
        "historical_competitor_domain_graph_research",
        "founder_original_intelligence_reports",
    } - {"historical_competitor_domain_graph_research"}
    assert report["realised_revenue_verified"] is False
    assert report["raw_third_party_data_resale_authorized"] is False
    assert report["payment_processed"] is False
    assert report["outbound_sent"] is False
    assert report["customer_data_delivery_enabled"] is False
    assert report["execution_authority"]=="NONE"

def test_199_price_does_not_cascade_into_high_ticket_buyer_claims():
    report=build_monetization_portfolio(trusted_catalog())
    sample=next(o for o in report["options"] if o["offer_code"]=="roofing_competitor_report")
    assert sample["price_hypothesis"]=={
        "currency":"USD","amount":199,"unit":"one_time_report",
        "market_price_verified":False,"buyer_accepted":False
    }
    assert all(o["signed_agreement_verified"] is False for o in report["options"])
    assert all(o["subscription_active"] is False for o in report["options"])
    assert all(o["payment_verified"] is False for o in report["options"])
    assert all(o["source_specific_delivery_rights_verified"] is False
               for o in report["options"])
    assert all(o["derived_analysis_only"] is True for o in report["options"])

def test_free_first_external_channel_does_not_pretend_marketplace_signup():
    report=build_monetization_portfolio(trusted_catalog())
    routes={r["channel_code"]:r for r in report["routes"]}
    assert routes["direct_enterprise"]["priority"]==0
    assert routes["agency_partners"]["priority"]==0
    assert routes["datarade"]["priority"]==1
    assert routes["aws_data_exchange"]["priority"]==2
    assert routes["snowflake_marketplace"]["priority"]==2
    assert routes["databricks_marketplace"]["priority"]==2
    assert all(route["listing_published"] is False for route in report["routes"])
    assert all(route["account_registered_or_approved"] is False
               for route in report["routes"])

def test_cannot_elevate_published_outbound_raw_resale_or_source_status():
    baseline=build_monetization_portfolio(trusted_catalog())
    for path,value in (
        (("raw_third_party_data_resale_authorized",),True),
        (("customer_data_delivery_enabled",),True),
        (("outbound_authorized",),True),
        (("realised_revenue_verified",),True),
        (("options",0,"published"),True),
        (("options",0,"source_specific_delivery_rights_verified"),True),
        (("options",0,"buyer_verified"),True),
        (("options",0,"offer_status"),"PUBLISHED"),
        (("options",0,"payment_verified"),True),
        (("options",0,"existing_product_id"),"uk_brownfield_site_change_intelligence"),
        (("options",0,"price_hypothesis"),{"currency":"USD","amount":90000,"unit":"year","market_price_verified":False,"buyer_accepted":False}),
        (("options",0,"signed_agreement_verified"),True),
        (("routes",2,"customer_entitlements_issued"),True),
        (("routes",2,"listing_published"),True),
    ):
        copy_=copy.deepcopy(baseline)
        parent=copy_
        for key in path[:-1]:
            parent=parent[key]
        parent[path[-1]]=value
        assert validate_portfolio(copy_) is False,path

def test_old_catalog_drift_or_forged_rights_fail_closed():
    base=trusted_catalog()
    for modify in ("rights","buyer","payment","missing"):
        payload=copy.deepcopy(base)
        if modify=="rights":
            payload["products"][0]["raw_third_party_resale_cleared"]=True
        elif modify=="buyer":
            payload["independently_verified_buyer_count"]=1
        elif modify=="payment":
            payload["billing_activation_enabled"]=True
        else:
            payload.pop("products")
        with pytest.raises(ValueError):
            build_monetization_portfolio(payload)

def test_timezone_naive_rejected():
    with pytest.raises(ValueError):
        build_monetization_portfolio(
            trusted_catalog(),assessed_at=datetime(2026,10,18)
        )

def test_operator_summarizes_without_raw_data_export():
    result=preview()
    assert result["status"]=="DATA_BROKERAGE_MULTICHANNEL_PRICING_HYPOTHESES_PREPARED"
    assert result["monetization_options"]==14
    assert result["distribution_channels"]==6
    assert result["database_writes"] is False
    assert result["raw_data_exported"] is False
    assert "options" not in result
    verbose=preview(show_options=True)
    assert validate_portfolio(verbose)

def test_private_catalog_permission_gate(tmp_path):
    folder=tmp_path/"runtime"/"data_brokerage"
    folder.mkdir(parents=True)
    artifact=folder/"internal_product_catalog_latest.json"
    artifact.write_text(json.dumps(trusted_catalog()))
    artifact.chmod(0o644)
    assert preview(root=tmp_path)["status"].startswith("HOLD_")
    artifact.chmod(0o600)
    assert preview(root=tmp_path)["status"]=="DATA_BROKERAGE_MULTICHANNEL_PRICING_HYPOTHESES_PREPARED"
    artifact.unlink()
    artifact.symlink_to(ROOT/PRIVATE_CATALOG)
    assert preview(root=tmp_path)["status"].startswith("HOLD_")

def test_explicit_readonly_flag_required(monkeypatch,capsys):
    monkeypatch.setattr(
        "scripts.preview_data_brokerage_monetization.preview",
        lambda **_:(_ for _ in ()).throw(AssertionError("no file reads")),
    )
    assert main([])==2
    assert "HOLD_EXPLICIT_READ_ONLY_REQUIRED" in capsys.readouterr().out
