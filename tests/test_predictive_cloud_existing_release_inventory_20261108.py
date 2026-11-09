"""Static release-ledger guard: cannot promote staged/historical code to live."""
import json
from pathlib import Path

FILE = (
    Path(__file__).resolve().parents[1]
    / "docs/PREDICTIVE_CLOUD_EXISTING_RELEASE_INVENTORY_20261108.json"
)


def get():
    return json.loads(FILE.read_text())


def test_current_live_schedulers_are_not_misreported_as_dead_services():
    d=get()
    assert d["schema_version"]=="empire.predictive_cloud.existing_release_inventory.v1"
    assert len(d["enabled_scheduled_jobs"])==4
    assert all(row["unit_file"]=="enabled" and row["active"]=="active"
               for row in d["enabled_scheduled_jobs"])
    assert {r["unit"] for r in d["enabled_scheduled_jobs"]} >= {
        "empire-predictive-cloud-materializer.timer",
        "empire-predictive-intelligence.timer",
        "empire-opportunity-loop.timer",
    }


def test_predicted_revenue_and_customer_entitlements_not_inferred():
    d=get()
    a=d["original_model_readiness"]
    assert a["prediction_ready"] is False
    assert a["independent_source_admitted"] is False
    assert a["verified_terminal_outcomes"]==0
    assert a["matched_outcome_count"]==0
    assert a["probability_ready_product_count"]==0
    assert a["forecast_claim_authorized"] is False
    s=d["source_tenant_evidence"]
    assert s["state"]=="PENDING_HELD"
    assert s["external_redistribution_or_forecasting_authorized"] is False
    assert s["authenticated_http200_server_receipt_extracted"] is False


def test_original_genuine_auth_and_private_usage_still_protected():
    d=get()
    surfaces={row["surface"]:row for row in d["live_protected_http"]}
    assert surfaces["Original Predictive Cloud status"]["status"]==200
    assert surfaces["Original Predictive V4 HELD admission review"]["status"]==200
    assert surfaces["Founder CRM health"]["status"]==200
    assert surfaces["Original source-rights verify requires CRM bearer"]["status"]==401
    assert surfaces["Data Cloud usage requires auth"]["status"]==401


def test_shared_production_checkout_never_mass_committed():
    d=get()
    shared=d["production_shared_checkout"]
    assert shared["dirty_paths"]>0
    assert shared["bulk_commit_safe"] is False
    assert shared["other_agent_changes_must_be_preserved"] is True
    assert d["production_changes"] is False
    assert d["commits_performed_by_inventory"] is False
    assert d["billing_or_provider_calls"] is False


def test_separate_agentos_and_historical_branch_not_mislabelled_deployed():
    d=get()
    assert d["historical_branch_count"]==len(d["historical_predictive_branches"])
    assert d["historical_branch_count"]>40
    names={x["branch"] for x in d["historical_predictive_branches"]}
    assert "feature/predictive-cloud-seven-lens-20261107" in names
    assert "release/predictive-cloud-source-admission-20261025" in names
    decisions={x["component"]:x for x in d["priority_release_decisions"]}
    assert decisions["Seven Lens 20261107 cross-owner Agent OS"]["state"]=="STAGED_SEPARATE_OWNER"
    assert decisions["Legacy source-admission branch 20261025"]["state"]=="HISTORIC_UNMERGED_UNRECONCILED"
    assert decisions["Commercial source admission + customer forecast"]["state"]=="HELD_REQUIRED_EVIDENCE"


def test_component_health_is_not_real_model_readiness():
    d=get()
    assert d["original_status_component_health"]["schema_version"]=="empire.predictive_cloud.status.v2"
    assert d["original_status_component_health"]["not_forecast_readiness"] is True
    assert d["original_status_component_health"]["component_count"]>=27
