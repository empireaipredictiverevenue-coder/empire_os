#!/usr/bin/env bash
# OBSERVE-only atomic release, independent from dirty /srv/empire_os.
set -euo pipefail

OWNER=/home/ubuntu/empire_agents/predictive_decision_control_20261018
RELEASE_ROOT=/home/ubuntu/empire_releases
COMMIT="$(git -C "$OWNER" rev-parse --verify HEAD)"
SHORT="${COMMIT:0:12}"
RELEASE="$RELEASE_ROOT/predictive_observe_${SHORT}"
TMP="$RELEASE_ROOT/.predictive_observe_${SHORT}.stage.$$"
if [[ "$(git -C "$OWNER" status --porcelain)" != "" ]]; then
  echo "REFUSE_DIRTY_FEATURE_COMMIT" >&2
  exit 4
fi
if [[ -e "$RELEASE" || -e "$TMP" ]]; then
  echo "RELEASE_ALREADY_PRESENT_OR_STAGE_COLLISION:$RELEASE" >&2
  exit 5
fi
umask 027
mkdir -p "$RELEASE_ROOT" "$TMP"
cleanup() {
  if [[ -d "$TMP" ]]; then rm -rf -- "$TMP"; fi
}
trap cleanup EXIT
git -C "$OWNER" archive --format=tar "$COMMIT" | tar -xf - -C "$TMP"
mkdir -p "$TMP/bin" "$TMP/metadata"
cat > "$TMP/bin/empire-predictive-observe" <<'LAUNCHER'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$#" -lt 1 || "$#" -gt 2 ]]; then
  printf 'Usage: %s {commercial|commercial-template|commercial-example|commercial-intake FILE|commercial-crm|sales-path|catalog|science|science-agent|source-gates|tenant-evidence|tenant-cohort|finance|gaps|cost|cost-sector|measurement|sources|owners|comparison|comparison-all}\n' "$0" >&2
  exit 2
fi
release="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
command="${1}"
if [[ "$command" == "commercial-intake" ]]; then
  if [[ "$#" -ne 2 ]]; then
    echo "COMMERCIAL_INTAKE_REQUIRES_ORIGINAL_SOURCE_FILE" >&2
    echo "Use: empire-predictive-observe commercial-template > /home/ubuntu/commercial_requirement.json" >&2
    exit 2
  fi
  if [[ ! -f "$2" || ! -r "$2" || -L "$2" ]]; then
    echo "COMMERCIAL_INTAKE_FILE_NOT_FOUND_OR_NOT_READABLE: Supply a real readable JSON file; /path/to/request.json is just an example, not a file." >&2
    echo "Create a blank draft: empire-predictive-observe commercial-template > /home/ubuntu/commercial_requirement.json" >&2
    exit 2
  fi
elif [[ "$#" -ne 1 ]]; then
  echo "UNEXPECTED_EXTRA_ARGS_HOLD" >&2; exit 2
fi
case "$command" in
  commercial) module=scripts.review_predictive_commercial_requirements_20261020 ;;
  commercial-template) module=scripts.print_predictive_commercial_intake_template_20261020 ;;
  commercial-example) module=scripts.review_predictive_commercial_requirements_20261020 ;;
  commercial-intake) module=scripts.review_predictive_commercial_requirements_20261020 ;;
  commercial-crm) module=scripts.review_predictive_founder_crm_visibility_20261020 ;;
  sales-path) module=scripts.review_predictive_sales_path_20261021 ;;
  catalog) module=scripts.review_predictive_catalog_readiness_20261020 ;;
  science) module=scripts.review_predictive_product_science_20261020 ;;
  science-agent) module=scripts.review_predictive_scientific_agent_20261020 ;;
  source-gates) module=scripts.review_predictive_source_owner_deployment_20261020 ;;
  tenant-evidence) module=scripts.review_predictive_tenant_outcome_reader_preflight_20261020 ;;
  tenant-cohort) module=scripts.review_predictive_tenant_terminal_cohort_20261020 ;;
  finance) module=scripts.review_predictive_four_stage_economics_20261020 ;;
  gaps) module=scripts.review_predictive_gap_intelligence_20261020 ;;
  cost) module=scripts.review_predictive_multi_index_cost_pressure_20261020 ;;
  cost-sector) module=scripts.review_predictive_multi_index_cost_pressure_20261020 ;;
  measurement) module=scripts.review_predictive_measurement_instruments_20261020 ;;
  sources) module=scripts.review_predictive_primary_economic_sources_20261020 ;;
  owners) module=scripts.review_empire_cross_agent_release_board_20261020 ;;
  comparison|comparison-all) module=scripts.review_predictive_comparison_20261021 ;;
  *) echo "UNSUPPORTED_COMMAND: $command" >&2; exit 2 ;;
esac
cd "$release"
if [[ "$command" == "commercial-example" ]]; then
  exec env -u PYTHONSTARTUP PYTHONPATH="$release" \
    /srv/empire_os/.venv/bin/python -B -m "$module" --read-only --example-tampa-roofing
fi
if [[ "$command" == "commercial-intake" ]]; then
  exec env -u PYTHONSTARTUP PYTHONPATH="$release" \
    /srv/empire_os/.venv/bin/python -B -m "$module" --read-only --requirement-intake "$2"
fi
if [[ "$command" == "cost-sector" ]]; then
  exec env -u PYTHONSTARTUP PYTHONPATH="$release" \
    /srv/empire_os/.venv/bin/python -B -m "$module" --read-only --probe-sector-bls-v1
fi
if [[ "$command" == "comparison-all" ]]; then
  exec env -u PYTHONSTARTUP PYTHONPATH="$release" \
    /srv/empire_os/.venv/bin/python -P -B -m "$module" --read-only --all-products
fi
exec env -u PYTHONSTARTUP PYTHONPATH="$release" \
  /srv/empire_os/.venv/bin/python -B -m "$module" --read-only
LAUNCHER
chmod 0750 "$TMP/bin/empire-predictive-observe"
cat > "$TMP/metadata/source.txt" <<EOF
SOURCE_COMMIT=$COMMIT
SOURCE_BRANCH=feature/predictive-decision-control-20261018
PRODUCTION_SOURCE_ROOT=/srv/empire_os
RELEASE_MODE=OBSERVE_ONLY_NO_SERVICE_INSTALL
RELEASE_DIR=$RELEASE
EOF
(
  cd "$TMP"
  sha256sum bin/empire-predictive-observe \
    empire_os/predictive_commercial_requirements.py \
    empire_os/predictive_commercial_intake_readiness.py \
    empire_os/predictive_commercial_evidence_chain.py \
    empire_os/predictive_existing_founder_crm_bridge.py \
    empire_os/predictive_existing_sales_path_review.py \
    scripts/review_predictive_sales_path_20261021.py \
    scripts/probe_first_party_sales_http_readonly.py \
    scripts/reconcile_founder_sales_handoff_aggregate_readonly.py \
    empire_os/predictive_catalog_intelligence_contracts.py \
    empire_os/predictive_catalog_readiness_bridge.py \
    empire_os/predictive_point_in_time_features.py \
    empire_os/predictive_competitive_product_comparison.py \
    empire_os/predictive_product_specific_competitors.py \
    empire_os/predictive_price_policy_evidence.py \
    empire_os/predictive_catalogue_price_comparison.py \
    scripts/review_predictive_comparison_20261021.py \
    empire_os/predictive_intelligence.py \
    empire_os/predictive_cloud_materializer.py \
    empire_os/predictive_cloud_status.py \
    empire_os/predictive_cloud_status_api.py \
    empire_os/optimization_status.py \
    empire_os/business_optimization_product.py \
    empire_os/intelligence_optimization_fabric.py \
    empire_os/solver_intelligence.py \
    empire_os/optimization_problem_factory.py \
    empire_os/optimization_runtime.py \
    empire_os/optimization_shards.py \
    empire_os/optimization_benchmark_ledger.py \
    empire_os/solver_adapters/greedy_binary.py \
    empire_os/solver_adapters/exact_binary.py \
    empire_os/predictive_cloud_formula.py \
    empire_os/predictive_cloud_v3.py \
    empire_os/future_trend_intelligence.py \
    empire_os/control_fabric.py \
    empire_os/departments.py \
    scripts/run_predictive_cloud_materializer.py \
    empire_os/sb.py \
    empire_os/canonical_data_gateway.py \
    empire_os/data_query.py \
    empire_os/data_values.py \
    empire_os/runtime_env.py \
    empire_os/quant_brain.py \
    scripts/build_predictive_intelligence.py \
    empire_os/predictive_source_owner_deployment_preflight.py \
    scripts/review_predictive_source_owner_deployment_20261020.py \
    empire_os/predictive_tenant_outcome_reader_preflight.py \
    scripts/review_predictive_tenant_outcome_reader_preflight_20261020.py \
    empire_os/predictive_tenant_terminal_cohort_reader.py \
    scripts/review_predictive_tenant_terminal_cohort_20261020.py \
    empire_os/outcome_feedback.py \
    scripts/review_predictive_catalog_readiness_20261020.py \
    empire_os/predictive_product_scientific_holdout.py \
    empire_os/predictive_product_prospective_baseline.py \
    empire_os/predictive_product_science_readiness.py \
    scripts/review_predictive_product_science_20261020.py \
    empire_os/predictive_product_scientific_agent_review.py \
    empire_os/predictive_existing_scientific_agent_skill_lock.py \
    empire_os/skills_library/skills/empire-evidence-verification/SKILL.md \
    empire_os/skills_library/skills/empire-engineering-verification/SKILL.md \
    empire_os/data/prompts/agent_world_model_architect.txt \
    empire_os/data/prompts/scientific_paper_replication_harness_architect.txt \
    empire_os/data/prompts/autonomous_ml_research_agent.txt \
    empire_os/experiment_registry.py \
    scripts/review_predictive_scientific_agent_20261020.py \
    scripts/review_predictive_founder_crm_visibility_20261020.py \
    scripts/review_predictive_commercial_requirements_20261020.py \
    scripts/print_predictive_commercial_intake_template_20261020.py \
    empire_os/predictive_commercial_supply_readiness.py \
    empire_os/predictive_commercial_lead_eligibility.py \
    empire_os/predictive_commercial_fulfilment.py \
    empire_os/predictive_existing_owner_pickup.py \
    empire_os/predictive_four_stage_economic_custody.py \
    empire_os/predictive_structural_revenue_gaps.py \
    scripts/review_empire_cross_agent_release_board_20261020.py \
    > metadata/critical_source_checksums.sha256
)
# Block publication if the newly generated allowlisted launcher is invalid.
for profile in commercial commercial-template commercial-example finance owners; do
  "$TMP/bin/empire-predictive-observe" "$profile" > /dev/null
done
# Verify the complete illustrative plan still refuses all commercial execution.
"$TMP/bin/empire-predictive-observe" commercial-example | \
  /srv/empire_os/.venv/bin/python -B -c '
import json,sys
value=json.load(sys.stdin)
chain=value["authenticated_original_commercial_evidence_chain"]
assert chain["status"]=="ORIGINAL_COMMERCIAL_EVIDENCE_NOT_YET_ADMITTED"
assert len(chain["stages"])==6
assert chain["original_intake_bytes_sha256_untrusted_file_identity"] is None
assert chain["commercial_execution_eligible"] is False
assert chain["cloud_learning_eligible"] is False
assert value["dispatch_performed"] is False
assert value["database_writes"] is False
'
# Existing owner CRM reader must stay a separate one-hit least-privilege review.
"$TMP/bin/empire-predictive-observe" commercial-crm | \
  /srv/empire_os/.venv/bin/python -B -c '
import json,sys
value=json.load(sys.stdin)
assert value["schema_version"]=="empire.predictive_revenue.existing_founder_sales_crm_bridge.v1"
assert value["mode"]=="OBSERVE" and value["execution_authority"]=="none"
assert value["canonical_original_acquisition_probe_checked"] is False
assert value["original_customer_order_authenticated"] is False
assert value["crm_write_performed"] is False
assert value["outbound_sent"] is False
'
# Live public-form + restricted CRM bridge never asserts first-party conversion.
"$TMP/bin/empire-predictive-observe" sales-path | \
  /srv/empire_os/.venv/bin/python -B -c '
import json,sys
x=json.load(sys.stdin)
assert x["schema_version"]=="empire.predictive_revenue.first_party_sales_path_observe.v1"
assert x["mode"]=="OBSERVE" and x["execution_authority"]=="none"
assert x["canonical_acquisition_count_checked"] is False
assert x["founder_crm_delivery_verified"] is False
assert x["individual_prospect_lineage_authenticated"] is False
assert x["customer_forecast_eligible"] is False
assert x["authenticated_customer_order_verified"] is False
assert x["database_writes"] is False and x["outbound_sent"] is False
assert x["payment_action"] is False and x["source_customer_contact_disclosed"] is False
'
# The pinned product catalogue bridge must reconcile real owner snapshot policy,
# but never mistake root-file custody for original DB/customer authentication.
"$TMP/bin/empire-predictive-observe" catalog | \
  /srv/empire_os/.venv/bin/python -B -c '
import json,sys
x=json.load(sys.stdin)
assert x["schema_version"]=="empire.predictive_revenue.catalog_original_readiness.v1"
assert x["status"]=="CANONICAL_CATALOGUE_POLICY_RECONCILED_SOURCE_DB_UNVERIFIED"
assert x["source_root_custody_verified"] is True
assert x["source_original_db_receipt_authenticated"] is False
assert x["catalogue_product_count"]>=5
assert len(x["flagship_deployments"])==5
assert x["catalogue_terms_ready_count"]<=x["catalogue_product_count"]
assert x["tenant_customer_forecast_verified"] is False
assert x["enterprise_delivery_verified"] is False
assert x["actual_revenue_verified"] is False
assert x["database_writes"] is False
assert x["execution_authority"]=="none"
'
# Competitive comparison is a READ-ONLY, exact-source category overlap. Never
# transform SaaS monthly seat fees into an enterprise project price or ROI.
"$TMP/bin/empire-predictive-observe" comparison | \
  /srv/empire_os/.venv/bin/python -B -c '
import json,sys
x=json.load(sys.stdin)
assert x["schema_version"]=="empire.predictive_revenue.catalogue_price_comparison.v1"
assert x["catalogue_product_count"]>=5
assert x["catalogue_prices_unknown"]+x["catalogue_prices_observed_not_authenticated"]==x["catalogue_product_count"]
assert x["founder_approved_flagship_prices_count"]==5
assert x["approved_cost_ceiling_scenarios_available"]>=0
assert x["approved_ceiling_scenarios_meeting_margin"]+x["approved_ceiling_scenarios_below_margin"]==x["approved_cost_ceiling_scenarios_available"]
assert x["approved_cost_ceiling_scenario_is_actual_margin"] is False
assert x["source_root_owned_snapshot_custody_verified"] is True
assert x["source_original_empiredb_issuer_authenticated"] is False
assert x["astra_gpt6_independent_review"]=="NOT_EXECUTED"
assert x["price_change_authority"]=="none"
assert x["database_writes"] is False and x["outbound_sent"] is False
assert "products" not in x
'
"$TMP/bin/empire-predictive-observe" comparison-all | \
  /srv/empire_os/.venv/bin/python -B -c '
import json,sys
x=json.load(sys.stdin)
assert len(x["products"])==x["catalogue_product_count"]
assert all(p["evidence_backed_price_justified"] is False for p in x["products"])
assert all(p["automatic_price_changes_authorized"] is False for p in x["products"])
assert all(p["foreign_currency_converted_to_usd"] is False for p in x["products"])
assert all(p["no_reliable_direct_comparator_yet"] is True for p in x["products"])
assert x["adjacent_reference_count"] == sum(len(p["competitor_categories"]) for p in x["products"])
assert x["products_without_adjacent_reference"] == sum(not p["competitor_categories"] for p in x["products"])
assert all(not c["feature_parity_verified"] and not c["price_justified_by_benchmark"] for p in x["products"] for c in p["competitor_categories"])
assert all(not p["founder_policy_cost_ceiling_scenario"]["realized_margin_verified"] for p in x["products"])
assert all(not p["founder_policy_cost_ceiling_scenario"]["price_justified_by_evidence"] for p in x["products"])
assert x["execution_authority"]=="none"
'
# The science adapter MUST preserve unknown forecasts when original product
# outcomes or forecast registry readback are absent.
"$TMP/bin/empire-predictive-observe" science | \
  /srv/empire_os/.venv/bin/python -B -c '
import json,sys
x=json.load(sys.stdin)
assert x["schema_version"]=="empire.predictive_revenue.product_science_readiness.v1"
assert x["mode"]=="OBSERVE" and x["execution_authority"]=="none"
assert x["catalogue_product_count"]>=5
assert x["original_source_issuer_authenticated"] is False
assert x["original_forecast_registry_readback_authenticated"] is False
assert x["forecast_eligible_for_customer"] is False
assert x["economic_memory_update_eligible"] is False
assert x["database_writes"] is False
'
# Existing Scientific Research Agent skill custody and governance must remain
# independent of revenue science; never convert synthetic world-model tests
# into commercial forecast authority.
"$TMP/bin/empire-predictive-observe" science-agent | \
  /srv/empire_os/.venv/bin/python -B -c '
import json,sys
x=json.load(sys.stdin)
assert x["schema_version"]=="empire.predictive_revenue.scientific_agent_product_protocol.v1"
assert x["status"] in (
  "SCIENTIFIC_AGENT_PROTOCOL_READY_WAITING_FOR_REAL_PRODUCT_COHORT",
  "SCIENTIFIC_AGENT_PROTOCOL_READY_ORIGINAL_SOURCE_AUTHENTICATION_HOLD",
  "SCIENTIFIC_AGENT_UNSCOPED_SOURCE_QUARANTINED",
)
assert x["existing_scientific_research_agent_skill_custody_verified"] is True
assert x["existing_experiment_registry_contract_reused"] is True
assert x["existing_scientific_agent_inference_invoked"] is False
assert x["original_forecast_experiment_registered"] is False
assert x["customer_model_validated"] is False
assert x["scientific_model_promotion_approved"] is False
assert x["economic_memory_update_eligible"] is False
assert x["database_writes"] is False
assert x["execution_authority"]=="none"
'
# Original production writer drift is inventoried, never silently repaired.
"$TMP/bin/empire-predictive-observe" source-gates | \
  /srv/empire_os/.venv/bin/python -B -c '
import json,sys
x=json.load(sys.stdin)
assert x["schema_version"]=="empire.predictive_revenue.original_source_owner_deployment.v1"
assert x["mode"]=="OBSERVE" and x["execution_authority"]=="none"
assert x["original_tenant_reader_role_verified"] is False
assert x["commercial_outcomes_rls_force_verified"] is False
assert x["customer_forecast_eligible"] is False
assert x["source_file_mutated"] is False
assert x["unit_modified"] is False
assert x["database_writes"] is False
'
# No credential injection or database connection during the release canary.
env -u EMPIREDB_TENANT_OUTCOME_READER_DSN \
  "$TMP/bin/empire-predictive-observe" tenant-evidence | \
  /srv/empire_os/.venv/bin/python -B -c '
import json,sys
x=json.load(sys.stdin)
assert x["schema_version"]=="empire.predictive_revenue.tenant_outcome_reader_policy_preflight.v1"
assert x["status"]=="HELD_DEDICATED_TENANT_OUTCOME_READER_CREDENTIAL_MISSING"
assert x["tenant_safe_data_reader_activated"] is False
assert x["customer_forecast_eligible"] is False
assert x["database_writes"] is False
assert x["execution_authority"]=="none"
'
# Canonical tenant cohort reader must hold with no dedicated login; no writes.
env -u EMPIREDB_TENANT_OUTCOME_READER_DSN \
  "$TMP/bin/empire-predictive-observe" tenant-cohort | \
  /srv/empire_os/.venv/bin/python -B -c '
import json,sys
x=json.load(sys.stdin)
assert x["schema_version"]=="empire.predictive_revenue.tenant_terminal_cohort_candidates.v1"
assert x["status"]=="HELD_DEDICATED_TENANT_OUTCOME_READER_CREDENTIAL_MISSING"
assert x["source_rows_exported_to_scientific_training"] is False
assert x["customer_forecast_eligible"] is False
assert x["database_writes"] is False and x["execution_authority"]=="none"
'
# The blank downloadable template must round-trip as a structured incomplete
# customer intake, never an unhandled ValueError or an inferred buyer order.
"$TMP/bin/empire-predictive-observe" commercial-template > "$TMP/metadata/blank_commercial_intake_template.json"
"$TMP/bin/empire-predictive-observe" commercial-intake \
  "$TMP/metadata/blank_commercial_intake_template.json" | \
  /srv/empire_os/.venv/bin/python -B -c '
import hashlib,json,sys
source=sys.argv[1]
value=json.load(sys.stdin)
assert value["status"]=="COMMERCIAL_INTAKE_MISSING_PLANNING_FIELDS"
assert value["original_intake_bytes_sha256_untrusted_file_identity"]==hashlib.sha256(open(source,"rb").read()).hexdigest()
assert value["owner_handoffs_dispatched"]==0
assert value["source_owner_reports_read"] is False
assert value["database_writes"] is False
' "$TMP/metadata/blank_commercial_intake_template.json"
if "$TMP/bin/empire-predictive-observe" commercial-intake /path/to/request.json \
    > /dev/null 2> "$TMP/metadata/missing_intake_error.txt"; then
  echo "RELEASE_VALIDATION_FAILED_ACCEPTED_NONEXISTENT_INTAKE" >&2
  exit 6
fi
grep -q "COMMERCIAL_INTAKE_FILE_NOT_FOUND_OR_NOT_READABLE" \
    "$TMP/metadata/missing_intake_error.txt"
if grep -q "Traceback" "$TMP/metadata/missing_intake_error.txt"; then
  echo "RELEASE_VALIDATION_FAILED_INTAKE_TRACEBACK" >&2
  exit 6
fi
rm -f "$TMP/metadata/missing_intake_error.txt"
# Cloud materializer must not promote forged local counts on a release build.
# Run only on an isolated temporary runtime; never write live Cloud caches.
(cd "$TMP" && PYTHONPATH="$TMP" /srv/empire_os/.venv/bin/python -B - <<'PY'
import json, tempfile
from pathlib import Path
from empire_os.predictive_cloud_materializer import refresh_predictive_cloud_materializers
with tempfile.TemporaryDirectory(prefix="empire-cloud-canary-") as d:
    root=Path(d)
    for rel, payload in (
        ("runtime/opportunity_factory/value_latest.json", {
            "candidate_count": 1,
            "items": [{
                "status": "AVAILABLE",
                "expected_revenue_cents": 100_000,
                "expected_gross_profit_cents": 80_000,
                "quant_input_evidence": {"evidence_refs": ["not-authenticated"]},
            }],
        }),
        ("runtime/predictive_intelligence/latest.json", {
            "probability_ready_product_count": 4,
            "timing_ready_product_count": 4,
            "matched_outcome_count": 200,
            "original_tenant_source_authenticated": True,
            "original_outcome_issuer_authenticated": True,
            "original_forecast_registered_before_outcome": True,
        }),
    ):
        path=root/rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))
    outcome=refresh_predictive_cloud_materializers(root)
    assert outcome["prediction_ready_component_count"] == 0
    for key in ("future_trend", "predictive_cloud_formula"):
        row=outcome[key]
        assert row["algorithm_available"] is True
        assert row["prediction_ready"] is False
        assert row["independent_source_admitted"] is False
        assert row["source_admission_state"] == "UNVERIFIED_LOCAL_SNAPSHOT_ONLY"
        assert row["normalized_economic_candidate_count"] == 0
PY
)
mv -T -- "$TMP" "$RELEASE"
trap - EXIT
echo "RELEASE_PATH=$RELEASE"
echo "RELEASE_COMMIT=$COMMIT"
echo "RELEASE_BIN=$RELEASE/bin/empire-predictive-observe"
echo "PRODUCTION_UNCHANGED=true"
