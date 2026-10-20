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
  printf 'Usage: %s {commercial|commercial-template|commercial-example|commercial-intake FILE|commercial-crm|catalog|science|science-agent|source-gates|finance|gaps|cost|cost-sector|measurement|sources|owners}\n' "$0" >&2
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
  catalog) module=scripts.review_predictive_catalog_readiness_20261020 ;;
  science) module=scripts.review_predictive_product_science_20261020 ;;
  science-agent) module=scripts.review_predictive_scientific_agent_20261020 ;;
  source-gates) module=scripts.review_predictive_source_owner_deployment_20261020 ;;
  finance) module=scripts.review_predictive_four_stage_economics_20261020 ;;
  gaps) module=scripts.review_predictive_gap_intelligence_20261020 ;;
  cost) module=scripts.review_predictive_multi_index_cost_pressure_20261020 ;;
  cost-sector) module=scripts.review_predictive_multi_index_cost_pressure_20261020 ;;
  measurement) module=scripts.review_predictive_measurement_instruments_20261020 ;;
  sources) module=scripts.review_predictive_primary_economic_sources_20261020 ;;
  owners) module=scripts.review_empire_cross_agent_release_board_20261020 ;;
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
    empire_os/predictive_catalog_intelligence_contracts.py \
    empire_os/predictive_catalog_readiness_bridge.py \
    empire_os/predictive_intelligence.py \
    empire_os/predictive_source_owner_deployment_preflight.py \
    scripts/review_predictive_source_owner_deployment_20261020.py \
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
mv -T -- "$TMP" "$RELEASE"
trap - EXIT
echo "RELEASE_PATH=$RELEASE"
echo "RELEASE_COMMIT=$COMMIT"
echo "RELEASE_BIN=$RELEASE/bin/empire-predictive-observe"
echo "PRODUCTION_UNCHANGED=true"
