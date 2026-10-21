"""Unpriced/conflicted founder SKU queues and single-product output."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path

import pytest

from empire_os.predictive_catalogue_price_comparison import (
    CataloguePricingHold, review_catalogue_price_comparison,
)
from empire_os.predictive_comparison_gap_report import build_comparison_gap_report
import scripts.review_predictive_comparison_20261021 as cli

SOURCE = Path("/srv/empire_os/runtime/commercial_catalog/latest.json")


def snapshot():
    return json.loads(SOURCE.read_text())


def test_four_price_source_custody_classes_match_original_86():
    report=review_catalogue_price_comparison(snapshot())
    assert report["price_source_custody_counts"] == {
        "founder_price_source_reported": 35,
        "legacy_consensus_unapproved": 26,
        "legacy_single_source_candidate": 20,
        "legacy_conflicted_candidate": 5,
    }
    assert report["legacy_consensus_price_review_required_count"] == 26
    assert report["legacy_price_review_required_count"] == 51
    assert report["source_approval_is_independent_customer_acceptance"] is False
    assert all(p["catalogue_source_approval_is_customer_contract"] is False
               for p in report["products"])
    assert all(p["evidence_backed_price_justified"] is False
               for p in report["products"])


def test_actionable_queues_reconcile_without_auto_price_resolution():
    report=review_catalogue_price_comparison(snapshot())
    gaps=build_comparison_gap_report(report)
    assert gaps["queue_counts"] == {
        "founder_price_resolution_required": 5,
        "unpriced_founder_economics_required": 20,
        "legacy_priced_founder_economics_required": 26,
        "source_approved_price_without_full_cost_policy": 9,
        "product_scope_or_comparator_research_needed": 25,
    }
    assert gaps["queues"]["founder_price_resolution_required"] == [
        "meetily_enterprise", "meetily_pro", "scraper_enterprise",
        "scraper_pro", "scraper_starter",
    ]
    assert gaps["astra_gpt6_independent_review"]=="NOT_EXECUTED"
    assert gaps["independent_customer_acceptance_or_revenue_verified"] is False
    assert gaps["price_changes_authorized"] is False
    assert gaps["execution_authority"] == "none"


def test_live_cli_gaps_small_and_original_source_custody_retained(capsys):
    assert cli.main(["--read-only","--gaps"]) == 0
    result=json.loads(capsys.readouterr().out)
    assert result["product_count"] == 86
    assert result["queue_counts"]["founder_price_resolution_required"] == 5
    assert result["source_root_owned_snapshot_custody_verified"] is True
    assert result["source_original_empiredb_issuer_authenticated"] is False
    assert "products" not in result


def test_live_cli_one_product_without_massive_catalogue_dump(capsys):
    assert cli.main(["--read-only","--product-code","meetily_pro"])==0
    result=json.loads(capsys.readouterr().out)
    assert result["selected_product_code"]=="meetily_pro"
    assert len(result["products"])==1
    assert result["products"][0]["catalogue_listed_price_minor_units"] is None
    assert result["products"][0]["catalogue_price_original_custody"]=="LEGACY_CONFLICT_NEEDS_FOUNDER_RESOLUTION"
    assert result["products"][0]["catalogue_source_approval_is_customer_contract"] is False


@pytest.mark.parametrize("code",["not_a_product","predictive_revenue_diagnostic;rm","../secrets","MEETILY_PRO"])
def test_unknown_or_unsafe_product_fails_closed(code,capsys):
    assert cli.main(["--read-only","--product-code",code])==2
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="COMPARISON_ORIGINAL_CATALOGUE_SOURCE_HELD"
    assert result["database_writes"] is False


def test_tampered_conflict_or_single_source_price_never_promoted():
    x=snapshot()
    z=next(p for p in x["products"] if p["product_code"]=="meetily_pro")
    z["price_basis"]["amount_cents"]=29900
    with pytest.raises(CataloguePricingHold):
        review_catalogue_price_comparison(x)
    x=snapshot()
    z=next(p for p in x["products"] if p["product_code"]=="closer_pro")
    z["price_basis"]["source_type"]="founder_approved"
    with pytest.raises(CataloguePricingHold):
        review_catalogue_price_comparison(x)


def test_reconciler_detects_omitted_review_item():
    r=review_catalogue_price_comparison(snapshot())
    r=deepcopy(r)
    r["products"].pop()
    with pytest.raises(ValueError):
        build_comparison_gap_report(r)
