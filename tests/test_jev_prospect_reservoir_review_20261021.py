"""Canonical ~33k prospects are a historical reservoir, not bulk marketable leads."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import pytest
from empire_os.jev_prospect_reservoir_review import audit_jev_prospect_reservoir

ROOT=Path("/srv/empire_os")
NOW=datetime(2026,10,21,22,34,tzinfo=timezone.utc)
SNAP={
    "historic_verified":"runtime/data_cloud/shadow_independent_verify_latest.json",
    "historic_dual_read":"runtime/data_cloud/dual_read_compare_latest.json",
    "leads_runtime":"runtime/leads_control/leads_runtime_observer_latest.json",
    "legacy_permit":"runtime/recovery/legacy_permit_inventory_summary.json",
    "current_markets":"runtime/market_sweeps/revenue_gps_latest.json",
}


def params():
    # Synthetic temporal fixture: other agents continuously refresh the
    # production snapshots while this pinned test clock remains unchanged.
    # Never turn a genuinely stale *live* source into current evidence.
    data={k:json.loads((ROOT/v).read_text()) for k,v in SNAP.items()}
    data["leads_runtime"]["generated_at"]=(NOW-timedelta(minutes=3)).isoformat()
    data["current_markets"]["generated_at"]=(NOW-timedelta(minutes=3)).isoformat()
    return data


def audit(**changes):
    return audit_jev_prospect_reservoir(**{**params(),**changes,"as_of":NOW})


def test_32899_is_verified_historical_id_reservoir_not_current_qualified_leads():
    d=audit()
    assert d["historical_empiredb_prospect_count"]==32899
    assert d["historical_distinct_id_set_matched_between_snapshots"] is True
    assert d["current_empiredb_prospect_count"] is None
    assert d["current_empiredb_reservoir_refresh_verified"] is False
    assert d["full_reservoir_commercial_rights_verified"] is False
    assert d["bulk_qualified_or_contactable_lead_total_proven"] is False
    assert d["qualified_records_for_mass_jev_inference"]==0
    assert d["automatic_outreach_authorized"] is False
    assert d["execution_authority"]=="none"


def test_leads_and_legacy_project_populations_cannot_be_summed():
    d=audit()
    assert d["existing_leads_control_rows"]==6828
    assert d["existing_leads_unique_ids"]==6828
    assert d["lead_duplicate_email_row_observations"]==1611
    assert d["lead_duplicate_phone_row_observations"]==53
    assert d["lead_status_converted_unverified_count"]==6636
    assert d["lead_outcome_linked_count_not_paid_revenue"]==2008
    assert d["permit_recovery_local_rows"]==6500
    assert d["permit_current_verified_project_only"]==1939
    assert d["permit_current_verified_owner_identified"]==3405
    assert d["permit_scan_complete"] is False
    assert d["recent_market_window_days"]==7
    assert d["recent_market_observed_acquisition_total"]==62
    assert d["counting_populations_additive"] is False
    assert d["overlap_between_sources_proven"] is False


@pytest.mark.parametrize("modify",[
    lambda x:x["historic_verified"].update(verified=False),
    lambda x:x["historic_verified"].update(production_cutover_authority=True),
    lambda x:x["historic_dual_read"].update(all_equal=False),
    lambda x:x["historic_dual_read"].update(dual_write_enabled=True),
    lambda x:x["historic_verified"]["tables"][0].update(target_rows=32898),
    lambda x:x["historic_verified"]["tables"][0].update(source_pk_sha256="f"*64),
    lambda x:x["historic_dual_read"]["tables"][0].update(target_pk_sha256="f"*64),
    lambda x:x["historic_verified"].update(read_only=False),
])
def test_forged_historical_count_or_source_authority_fails_closed(modify):
    data=params()
    modify(data)
    with pytest.raises(ValueError):
        audit_jev_prospect_reservoir(**data,as_of=NOW)


def test_stale_lead_observer_is_not_current(tmp_path):
    data=params()
    data["leads_runtime"]["generated_at"]=(NOW-timedelta(hours=8)).isoformat()
    r=audit_jev_prospect_reservoir(**data,as_of=NOW)
    assert r["existing_leads_control_status"]=="MISSING_OR_UNTRUSTED"
    assert r["existing_leads_control_rows"] is None
    assert r["historical_empiredb_prospect_count"]==32899


def test_fake_lead_promotion_is_ignored_and_does_not_set_outreach():
    data=params()
    data["leads_runtime"]["governance"]["outbound"]=True
    r=audit_jev_prospect_reservoir(**data,as_of=NOW)
    assert r["existing_leads_control_rows"] is None
    assert r["automatic_outreach_authorized"] is False


def test_forged_market_revenue_flag_disables_recent_window():
    data=params()
    data["current_markets"]["revenue_inferred"]=True
    r=audit_jev_prospect_reservoir(**data,as_of=NOW)
    assert r["recent_market_aggregate_status"]=="MISSING_OR_UNTRUSTED"
    assert r["recent_market_observed_acquisition_total"] is None


def test_missing_local_permits_does_not_change_historical_count():
    r=audit(legacy_permit=None)
    assert r["permit_recovery_status"]=="MISSING_OR_UNTRUSTED"
    assert r["historical_empiredb_prospect_count"]==32899
    assert r["counting_populations_additive"] is False


def test_naive_clock_rejected():
    with pytest.raises(ValueError):
        audit_jev_prospect_reservoir(**params(),as_of=datetime(2026,10,21))


def test_public_receipt_contains_aggregate_only_and_no_approval():
    file=Path(__file__).resolve().parents[1]/"docs/commercial/JEV_PROSPECT_32899_RESERVOIR_TRUTH_20261021.json"
    report=json.loads(file.read_text())
    assert report["schema_version"]=="empire.jev.prospect_reservoir_review.v1"
    assert report["historical_empiredb_prospect_count"]==32899
    assert report["current_empiredb_prospect_count"] is None
    assert report["qualified_records_for_mass_jev_inference"]==0
    assert report["individual_consent_and_suppression_cleared"] is False
    assert len(report["priority_review_tasks"])==5
    assert report["automatic_outreach_authorized"] is False
    assert report["database_writes"] is False
    assert report["execution_authority"]=="none"
    text=file.read_text()
    assert "@" not in text
    assert "contact_email" not in text
    assert "prospect_id" not in text
    assert "phone_number" not in text


def test_32899_audit_can_join_executive_portfolio_without_contact_authority():
    from empire_os.jev_commercial_action_readiness import review_portfolio_commercial_readiness
    from test_jev_commercial_action_readiness_20261021 import (
        portfolio,capacity,registry,
    )
    source=audit()
    combined=review_portfolio_commercial_readiness(
        portfolio(),buyer_capacity=capacity(),relationships=registry(),
        prospect_reservoir=source,as_of=NOW,
    )
    x=combined["prospect_reservoir_review"]
    assert x["historical_canonical_prospect_count"]==32899
    assert x["status"]=="HISTORIC_SOURCE_COUNT_ONLY_COMMERCIAL_REVALIDATION_REQUIRED"
    assert x["contactable_qualified_leads_verified"] is False
    assert x["counting_across_populations_authorized"] is False
    assert x["local_lead_control_rows"]==6828
    assert x["legacy_permit_project_rows"]==6500
    assert x["recent_market_window_acquisitions"]==62
    assert combined["bulk_prospect_email_or_contact_authorized"] is False
    assert combined["mass_jev_person_inference_authorized"] is False
    assert combined["review_steps"][0]["task"]=="CANONICAL_PROSPECT_RESERVOIR_RIGHTS_AND_LINEAGE_AUDIT"
    assert all(task["action_authorized"] is False for task in combined["review_steps"])
    assert combined["outreach_sent"]==0
    assert combined["commercial_offers_ready"]==0


@pytest.mark.parametrize("mutation",[
    lambda p:p.update(current_empiredb_prospect_count=32899),
    lambda p:p.update(full_reservoir_commercial_rights_verified=True),
    lambda p:p.update(bulk_qualified_or_contactable_lead_total_proven=True),
    lambda p:p.update(counting_populations_additive=True),
    lambda p:p.update(qualified_records_for_mass_jev_inference=32899),
    lambda p:p.update(automatic_outreach_authorized=True),
    lambda p:p.update(individual_consent_and_suppression_cleared=True),
    lambda p:p.update(execution_authority="execute"),
])
def test_bulk_reservoir_promotion_forgery_rejected_in_commercial_pipeline(mutation):
    from empire_os.jev_commercial_action_readiness import review_portfolio_commercial_readiness
    from test_jev_commercial_action_readiness_20261021 import portfolio
    forged=audit()
    mutation(forged)
    with pytest.raises(ValueError):
        review_portfolio_commercial_readiness(
            portfolio(),buyer_capacity=None,relationships=None,
            prospect_reservoir=forged,as_of=NOW)


def test_private_safe_combined_32899_executive_packet_has_only_aggregates():
    path=(Path(__file__).resolve().parents[1]/
          "docs/commercial/JEV_EXECUTIVE_32899_PROSPECT_COMMERCIAL_ALIGNMENT_20261021.json")
    report=json.loads(path.read_text())
    assert report["source_signal_review_count"]==35
    assert report["prospect_reservoir_review"]["historical_canonical_prospect_count"]==32899
    assert report["prospect_reservoir_review"]["current_canonical_count_verified"] is False
    assert report["prospect_reservoir_review"]["contactable_qualified_leads_verified"] is False
    assert len(report["review_steps"])==4
    assert report["outreach_sent"]==0
    assert report["mass_jev_person_inference_authorized"] is False
    assert report["bulk_prospect_email_or_contact_authorized"] is False
    assert report["database_writes"] is False
    assert report["execution_authority"]=="none"
    body=path.read_text()
    assert "@" not in body
    assert "entity_key" not in body
    assert "source_reference_sha256" not in body
    assert "reddit.com" not in body
