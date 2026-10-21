"""Full 86-SKU price review remains a bounded, read-only research surface."""
from __future__ import annotations

import json
import pytest

import scripts.review_predictive_comparison_20261021 as cli


def test_cli_summary_verified_local_file_not_original_db(capsys):
    assert cli.main(["--read-only"]) == 0
    result=json.loads(capsys.readouterr().out)
    assert result["catalogue_product_count"] == 86
    assert result["approved_cost_ceiling_scenarios_available"] == 26
    assert result["approved_ceiling_scenarios_meeting_margin"] == 26
    assert result["approved_ceiling_scenarios_below_margin"] == 0
    assert result["approved_cost_ceiling_scenario_is_actual_margin"] is False
    assert "products" not in result
    assert result["source_root_owned_snapshot_custody_verified"] is True
    assert result["source_original_empiredb_issuer_authenticated"] is False
    assert result["astra_gpt6_independent_review"] == "NOT_EXECUTED"
    assert result["price_change_authority"] == "none"
    assert result["database_writes"] is False
    assert result["execution_authority"] == "none"


def test_cli_full_review_retains_all_sku_currency_and_no_repricing(capsys):
    assert cli.main(["--read-only", "--all-products"]) == 0
    result=json.loads(capsys.readouterr().out)
    assert len(result["products"]) == 86
    assert set(p["catalogue_currency"] for p in result["products"]) == {
        "USD", "GBP", "EUR", "CAD", "AUD", "NZD"
    }
    assert all(p["automatic_price_changes_authorized"] is False
               for p in result["products"])
    assert all(
        p["founder_policy_cost_ceiling_scenario"]["realized_margin_verified"] is False
        for p in result["products"]
    )
    assert result["adjacent_reference_count"] == sum(
        len(p["competitor_categories"]) for p in result["products"]
    )
    assert result["products_without_adjacent_reference"] == sum(
        not p["competitor_categories"] for p in result["products"]
    )


def test_cli_source_hold_is_redacted_and_fails_closed(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise cli.ProductContractHold("sensitive-original-source-details")
    monkeypatch.setattr(cli, "_read_bounded_file", fail)
    assert cli.main(["--read-only"]) == 2
    raw=capsys.readouterr().out
    assert "sensitive-original-source-details" not in raw
    x=json.loads(raw)
    assert x["catalogue_product_count"] is None
    assert x["source_root_owned_snapshot_custody_verified"] is False
    assert x["database_writes"] is False
    assert x["execution_authority"] == "none"


def test_release_launcher_has_comparison_without_repricing_service():
    from pathlib import Path
    content=(Path(__file__).resolve().parents[1] /
             "scripts/prepare_predictive_readonly_release_20261020.sh").read_text()
    assert 'comparison|comparison-all|comparison-gaps|comparison-product|comparison-astra|comparison-astra-all) module=scripts.review_predictive_comparison_20261021' in content
    assert 'if [[ "$command" == "comparison-gaps" ]]' in content
    assert 'if [[ "$command" == "comparison-product" ]]' in content
    assert 'empire_os/predictive_comparison_gap_report.py' in content
    assert '"$TMP/bin/empire-predictive-observe" comparison-all' in content
    assert '"$TMP/bin/empire-predictive-observe" comparison |' in content
    assert "empire_os/predictive_point_in_time_features.py" in content
    assert "empire_os/predictive_competitive_product_comparison.py" in content
    assert "empire_os/predictive_product_specific_competitors.py" in content
    assert "empire_os/predictive_catalogue_price_comparison.py" in content
    assert "empire_os/predictive_price_policy_evidence.py" in content
    assert "scripts/review_predictive_comparison_20261021.py" in content
    assert "automatic_price_changes_authorized" in content
    assert 'price_change_authority' in content
