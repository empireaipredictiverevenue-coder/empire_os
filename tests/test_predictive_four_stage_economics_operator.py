"""Opt-in original Finance/Commerce/Quant custody operator end-to-end."""
import json
from pathlib import Path

import pytest

from test_predictive_four_stage_economic_custody import packets, NOW
from test_predictive_profitability_playbooks import plan
import scripts.review_predictive_four_stage_economics_20261020 as operator


def clock(monkeypatch):
    class FakeClock:
        @staticmethod
        def now(tz):
            return NOW
    monkeypatch.setattr(operator,"datetime",FakeClock)


def test_missing_original_finance_owner_packets_remain_unknown(tmp_path,monkeypatch,capsys):
    clock(monkeypatch)
    monkeypatch.setattr("sys.argv",["read-only","--read-only",
                                   "--repo-root",str(tmp_path)])
    assert operator.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="FOUR_STAGE_SOURCE_PROOFS_AWAIT_ORIGINAL_OWNER_EVIDENCE"
    assert result["source_owner_bundle_supplied"] is False
    assert result["four_stage_cost_and_forecast_review"] is None
    assert result["original_profit_forecast_registration_preflight"] is None
    assert result["verified_supplier_invoice_coverage"] is None
    assert result["verified_local_labor_and_delivery_cost_coverage"] is None
    assert result["verified_accepted_price_and_settlement_coverage"] is None
    assert result["quant_prospectively_registered_forecast_coverage"] is None
    assert result["first_party_unit_level_gross_profit_accuracy"] is None
    assert result["independently_authenticated_financial_money_movement"] is False
    assert result["cloud_financial_optimization_eligible"] is False
    assert result["external_service_or_api_called"] is False
    assert result["database_writes"] is False


def test_four_stage_fictional_owner_contract_and_profit_intent_only(tmp_path,monkeypatch,capsys):
    clock(monkeypatch)
    p,m,o,s=packets()
    bundle={
        "pilot":p,"materials":m,"operations":o,"selling_price":s,
        "economic_plan":plan(p),
    }
    path=tmp_path/"fictional_only_owner_packet.json"
    path.write_text(json.dumps(bundle),encoding="utf-8")
    monkeypatch.setattr("sys.argv",["read-only","--read-only",
                                   "--repo-root",str(tmp_path),
                                   "--owner-evidence-bundle",str(path)])
    assert operator.main()==0
    out=json.loads(capsys.readouterr().out)
    assert out["status"]=="FOUR_STAGE_OWNER_CLAIM_RESEARCH_REVIEWED"
    review=out["four_stage_cost_and_forecast_review"]
    assert review["illustrative_unit_contribution_minor_excluding_cac_fees_tax_overhead"]==4250
    forecast=out["original_profit_forecast_registration_preflight"]
    assert forecast["status"]=="PROSPECTIVE_PROFIT_FORECAST_SOURCE_DECLARATION_UNREGISTERED"
    assert forecast["original_forecast_durably_registered"] is False
    assert forecast["original_profit_forecast_registry_target"]=="MISSING_DEDICATED_PROFIT_FORECAST_OWNER_REGISTRY"
    assert out["original_profit_forecast_durably_registered"] is False
    assert out["profit_registry_has_independent_readback"] is False
    assert out["cloud_financial_optimization_eligible"] is False
    assert out["database_writes"] is False
    assert m["tenant_ref_sha256"] not in json.dumps(out)
    assert m["product_ref_sha256"] not in json.dumps(out)


def test_owner_packet_requires_independent_pilot_and_currency_consistency(tmp_path,monkeypatch):
    clock(monkeypatch)
    p,m,o,s=packets()
    s["currency"]="GBP"
    path=tmp_path/"packet.json"
    path.write_text(json.dumps({
        "pilot":p,"materials":m,"operations":o,"selling_price":s,
    }))
    monkeypatch.setattr("sys.argv",["read-only","--read-only",
                                   "--repo-root",str(tmp_path),
                                   "--owner-evidence-bundle",str(path)])
    with pytest.raises(ValueError):
        operator.main()


def test_source_packet_symlink_is_not_accepted(tmp_path,monkeypatch):
    clock(monkeypatch)
    p,m,o,s=packets()
    target=tmp_path/"payload.json"
    target.write_text(json.dumps({
        "pilot":p,"materials":m,"operations":o,"selling_price":s,
    }))
    alias=tmp_path/"alias.json"
    alias.symlink_to(target)
    monkeypatch.setattr("sys.argv",["read-only","--read-only",
                                   "--repo-root",str(tmp_path),
                                   "--owner-evidence-bundle",str(alias)])
    with pytest.raises(ValueError):
        operator.main()


def test_owner_bundle_unknown_fields_cannot_request_payout(tmp_path):
    f=tmp_path/"packet.json"
    f.write_text(json.dumps({
        "pilot":{},"materials":{},"operations":{},"selling_price":{},
        "authorise_send_now":True,
    }))
    with pytest.raises(ValueError):
        operator._bundle(str(f))
