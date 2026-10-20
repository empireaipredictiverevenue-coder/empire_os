"""Public operator consumes existing source-owner aggregates without side effects."""
from datetime import datetime,timezone
from pathlib import Path
import json
import pytest
import scripts.review_predictive_commercial_requirements_20261020 as cli
from test_predictive_commercial_requirements_fulfilment import (
    source_packets, NOW, quote, roof_scope, assumptions,
)
from empire_os.predictive_commercial_requirements import tampa_roofing_founder_example


def fake_clock(monkeypatch):
    class Fixed:
        @staticmethod
        def now(zone):
            return NOW
    monkeypatch.setattr(cli,"datetime",Fixed)


def fixture_root(tmp_path):
    supply,buyer,scout=source_packets()
    for relative,source in (
        ("runtime/lead_supply/private_leadgen/research_queue_latest.json",supply),
        ("runtime/buyer_capacity_readiness/latest.json",buyer),
        ("runtime/buyer_acquisition/scout_latest.json",scout),
    ):
        p=tmp_path/relative
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(source),encoding="utf-8")


def test_end_to_end_tampa_operator_from_original_owner_packets(monkeypatch,tmp_path,capsys):
    fixture_root(tmp_path);fake_clock(monkeypatch)
    monkeypatch.setattr("sys.argv",["operator","--read-only","--example-tampa-roofing",
                                   "--repo-root",str(tmp_path)])
    assert cli.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="ILLUSTRATIVE_REQUIREMENT_READINESS_REVIEWED"
    req=result["commercial_requirement"]
    supply=result["original_lead_supply_and_buyer_owner_readiness"]
    plan=result["governed_fulfilment_and_sourcing_plan"]
    assert req["requested_qualified_leads_target_not_inventory"]==20
    assert supply["global_immediately_sellable_inventory"]==0
    assert supply["original_source_roofing_research_records_not_leads"]==56
    assert supply["verified_tampa_eligible_leads"] is None
    assert supply["verified_global_buyer_capacity_count"]==0
    assert plan["prepared_owner_ticket_count"]==8
    assert plan["owner_handoff_delivery_receipts"]==0
    assert plan["verified_fulfilment_gap_units"] is None
    assert plan["supplier_sourcing_preflight"]["source_owner_quote_count"]==0
    assert plan["cloud_scenario_capacity_review"]["scenario_ir"] is None
    assert result["supplier_contacted"] is False
    assert result["customer_committed"] is False
    assert result["production_services_modified"] is False
    assert result["database_writes"] is False


def test_read_only_operator_does_not_write_files(tmp_path,monkeypatch,capsys):
    fixture_root(tmp_path);fake_clock(monkeypatch)
    paths={p.relative_to(tmp_path):p.read_bytes()
           for p in tmp_path.rglob("*") if p.is_file()}
    monkeypatch.setattr("sys.argv",["operator","--read-only","--example-tampa-roofing",
                                   "--repo-root",str(tmp_path)])
    cli.main()
    capsys.readouterr()
    assert paths=={p.relative_to(tmp_path):p.read_bytes()
                   for p in tmp_path.rglob("*") if p.is_file()}


def test_missing_owner_source_comes_back_unknown_not_zero(tmp_path,monkeypatch,capsys):
    fake_clock(monkeypatch)
    monkeypatch.setattr("sys.argv",["operator","--read-only","--example-tampa-roofing",
                                   "--repo-root",str(tmp_path)])
    cli.main()
    out=json.loads(capsys.readouterr().out)
    assert out["original_lead_supply_and_buyer_owner_readiness"][
        "global_immediately_sellable_inventory"] is None
    assert out["governed_fulfilment_and_sourcing_plan"][
        "verified_market_and_customer_eligible_leads"] is None


def test_example_intake_and_unapproved_quotes_do_not_unlock_procurement(tmp_path,monkeypatch,capsys):
    fixture_root(tmp_path);fake_clock(monkeypatch)
    survey=tmp_path/"survey.json";survey.write_text(json.dumps(roof_scope()))
    owner_quotes=tmp_path/"quotes.json"
    owner_quotes.write_text(json.dumps({"source_owner_quote_claims":[quote()]}))
    monkeypatch.setattr("sys.argv",["operator","--read-only","--example-tampa-roofing",
                                   "--repo-root",str(tmp_path),
                                   "--original-roof-survey",str(survey),
                                   "--supplier-owner-quotes",str(owner_quotes)])
    cli.main()
    out=json.loads(capsys.readouterr().out)
    rfq=out["governed_fulfilment_and_sourcing_plan"]["supplier_sourcing_preflight"]
    assert rfq["source_owner_quote_count"]==1
    assert rfq["confirmed_comparable_landed_quote_minor"] is None
    assert rfq["purchase_orders_issued"] is False
    assert out["database_writes"] is False


def test_hypothetical_cloud_scenario_not_deliverable_lead_allocation(tmp_path,monkeypatch,capsys):
    fixture_root(tmp_path);fake_clock(monkeypatch)
    src=tmp_path/"what_if.json"
    src.write_text(json.dumps(assumptions()))
    monkeypatch.setattr("sys.argv",["operator","--read-only","--example-tampa-roofing",
                                   "--repo-root",str(tmp_path),
                                   "--cloud-what-if",str(src)])
    cli.main()
    out=json.loads(capsys.readouterr().out)
    cloud=out["governed_fulfilment_and_sourcing_plan"]["cloud_scenario_capacity_review"]
    assert cloud["status"]=="HYPOTHETICAL_RESEARCH_CLOUD_IR_NOT_ALLOCATION"
    assert cloud["scenario_ir"]["execution_authority"]=="none"
    assert cloud["optimizer_executed"] is False


def test_external_source_file_symlinks_fail_closed(tmp_path):
    content=tmp_path/"content.json"
    content.write_text(json.dumps(tampa_roofing_founder_example()))
    link=tmp_path/"link.json"
    link.symlink_to(content)
    with pytest.raises(ValueError):
        cli._read(str(link))


def test_founder_intake_cannot_self_authorise_money_or_outbound(tmp_path,monkeypatch):
    fixture_root(tmp_path);fake_clock(monkeypatch)
    intake=tampa_roofing_founder_example()
    intake["permission_proof_owner_receipt"]={"founder_ok":True}
    p=tmp_path/"intake.json";p.write_text(json.dumps(intake))
    monkeypatch.setattr("sys.argv",["operator","--read-only",
                                   "--repo-root",str(tmp_path),
                                   "--requirement-intake",str(p)])
    with pytest.raises(ValueError):
        cli.main()


def test_read_only_operator_accepts_owner_per_lead_preview_without_delivering(tmp_path,monkeypatch,capsys):
    from test_predictive_commercial_lead_eligibility import preview,req
    fixture_root(tmp_path);fake_clock(monkeypatch)
    intake=tampa_roofing_founder_example()
    intake["zip_codes"]=["33602","33606"]
    request=tmp_path/"intake.json"
    request.write_text(json.dumps(intake))
    audit=tmp_path/"audit.json"
    audit.write_text(json.dumps(preview(req())))
    monkeypatch.setattr("sys.argv",["operator","--read-only",
                                   "--repo-root",str(tmp_path),
                                   "--requirement-intake",str(request),
                                   "--lead-owner-eligibility-preview",str(audit)])
    cli.main()
    result=json.loads(capsys.readouterr().out)
    p=result["governed_fulfilment_and_sourcing_plan"]
    a=p["per_lead_duplicate_consent_and_eligibility_preflight"]
    assert a["status"]=="SOURCE_OWNER_LEAD_PREVIEW_DEDUPED_NOT_AUTHENTICATED"
    assert a["source_owner_claimed_billable_not_verified"]==1
    assert a["eligible_and_independently_authenticated_customer_leads"] is None
    assert p["verified_inventory_reserved_for_customer"] is None
    assert p["lead_duplicates_and_rejections_checked_against_canonical_owner"] is False
    assert result["database_writes"] is False


def test_no_request_defaults_to_no_customer_and_no_geography(monkeypatch,tmp_path,capsys):
    fixture_root(tmp_path);fake_clock(monkeypatch)
    monkeypatch.setattr("sys.argv",["operator","--read-only",
                                   "--repo-root",str(tmp_path)])
    assert cli.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="COMMERCIAL_REQUIREMENT_INPUT_REQUIRED"
    assert result["current_customer_order"] is None
    assert result["default_industry"] is None
    assert result["default_market"] is None
    assert result["example_tampa_roofing_used"] is False
    assert result["database_writes"] is False
    assert result["outbound_sent"] is False


def test_user_supplied_non_tampa_intake_is_selected_not_example(tmp_path,monkeypatch,capsys):
    fixture_root(tmp_path);fake_clock(monkeypatch)
    intake=tampa_roofing_founder_example()
    intake.update(country="US",state="AZ",city="Phoenix",industry="hvac",
                  requested_qualified_leads=30,service_types=["hvac_replacement"],
                  zip_codes=["85001"])
    p=tmp_path/"customer_intake.json";p.write_text(json.dumps(intake))
    monkeypatch.setattr("sys.argv",["operator","--read-only",
                                   "--repo-root",str(tmp_path),
                                   "--requirement-intake",str(p)])
    assert cli.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="MULTI_INDUSTRY_COMMERCIAL_REQUIREMENT_READINESS_REVIEWED"
    assert result["example_tampa_roofing_used"] is False
    req=result["commercial_requirement"]
    supply=result["original_lead_supply_and_buyer_owner_readiness"]
    plan=result["governed_fulfilment_and_sourcing_plan"]
    assert req["source_instruction_kind"]=="FOUNDER_OR_CUSTOMER_UNVERIFIED_REQUIREMENT_DRAFT"
    assert req["city"]=="Phoenix" and req["industry"]=="hvac"
    assert supply["research_target_market_city"]=="Phoenix"
    assert supply["source_target_industry_research_records_not_leads"]==34
    assert plan["customer_requested_qualified_leads"]==30
    assert "equipment_system" in plan["supplier_sourcing_preflight"][
        "materials_to_scope_not_purchase_quantities"]
    assert plan["verified_target_market_inventory_units"] is None
    assert result["database_writes"] is False


def test_no_original_customer_request_refuses_material_and_cloud_evidence(
    tmp_path,monkeypatch,
):
    fake_clock(monkeypatch)
    p=tmp_path/"research.json";p.write_text(json.dumps({}))
    monkeypatch.setattr("sys.argv",["operator","--read-only",
                                   "--repo-root",str(tmp_path),
                                   "--cloud-what-if",str(p)])
    with pytest.raises(SystemExit):
        cli.main()


def test_original_request_and_explicit_illustration_cannot_be_combined(
    tmp_path,monkeypatch,
):
    fake_clock(monkeypatch)
    p=tmp_path/"req.json";p.write_text(json.dumps(tampa_roofing_founder_example()))
    monkeypatch.setattr("sys.argv",["operator","--read-only",
                                   "--requirement-intake",str(p),
                                   "--example-tampa-roofing"])
    with pytest.raises(SystemExit):
        cli.main()


def test_existing_a2a_lead_and_finance_original_source_contracts_join_read_only(
    tmp_path,monkeypatch,capsys,
):
    from test_predictive_existing_owner_pickup import report,receipts
    fixture_root(tmp_path);fake_clock(monkeypatch)
    folder=tmp_path/"runtime/a2a_commercial_signal_mining"
    folder.mkdir(parents=True)
    (folder/"buyer_owner_research_handoffs_v1.json").write_text(json.dumps(report()))
    (folder/"owner_signed_receipts_review_v1.json").write_text(json.dumps(receipts()))
    monkeypatch.setattr("sys.argv",[
        "operator","--read-only","--example-tampa-roofing",
        "--repo-root",str(tmp_path),"--a2a-owner-root",str(tmp_path),
    ])
    assert cli.main()==0
    result=json.loads(capsys.readouterr().out)
    a2a=result["original_a2a_owner_research_overlap"]
    assert a2a["source_matching_exact_sector_city_region_tickets_count"]==2
    assert a2a["original_owner_authenticated_reply_count"]==0
    assert a2a["owner_source_reported_match_is_our_requirement_acknowledgement"] is False
    finance=result["existing_finance_proof_gate_status"]
    assert finance["independent_finance_proof_gaps_remaining"]==7
    assert finance["actual_customer_profit_authenticated"] is False
    owners=result["department_owner_acceptance_and_next_actions"]
    assert owners["handoff_draft_count"]==8
    assert owners["owner_handoffs_dispatched"]==0
    assert owners["existing_a2a_matching_research_tickets_not_customer_acks"]==2
    assert all(x["live_service_execution_eligible"] is False
               for x in owners["owner_required_action_queue"])
    assert result["dispatch_performed"] is False
    assert result["database_writes"] is False


def test_cross_owner_synthetic_hvac_market_mismatch_reports_no_matching_a2a(
    tmp_path,monkeypatch,capsys,
):
    from test_predictive_existing_owner_pickup import report,receipts
    fixture_root(tmp_path);fake_clock(monkeypatch)
    folder=tmp_path/"runtime/a2a_commercial_signal_mining"
    folder.mkdir(parents=True)
    (folder/"buyer_owner_research_handoffs_v1.json").write_text(json.dumps(report()))
    (folder/"owner_signed_receipts_review_v1.json").write_text(json.dumps(receipts()))
    data=tampa_roofing_founder_example()
    data.update(country="US",state="TX",city="Houston",industry="solar",
                requested_qualified_leads=25)
    intake=tmp_path/"solar_intake.json"
    intake.write_text(json.dumps(data))
    monkeypatch.setattr("sys.argv",[
        "operator","--read-only",
        "--repo-root",str(tmp_path),"--a2a-owner-root",str(tmp_path),
        "--requirement-intake",str(intake),
    ])
    assert cli.main()==0
    out=json.loads(capsys.readouterr().out)
    assert out["commercial_requirement"]["industry"]=="solar"
    assert out["original_a2a_owner_research_overlap"]["status"]==(
        "NO_EXACT_PREEXISTING_A2A_SECTOR_CITY_REGION_PROFILE")
    assert out["department_owner_acceptance_and_next_actions"][
        "existing_a2a_matching_research_tickets_not_customer_acks"]==0
    assert out["governed_fulfilment_and_sourcing_plan"]["verified_market_and_customer_eligible_leads"] is None
    assert out["database_writes"] is False
