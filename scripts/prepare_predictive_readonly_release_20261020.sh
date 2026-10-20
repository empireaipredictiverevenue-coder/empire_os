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
if [[ "$#" -ne 1 ]]; then
  printf 'Usage: %s {commercial|finance|gaps|cost|cost-sector|measurement|sources|owners}\n' "$0" >&2
  exit 2
fi
release="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
command="${1}"
case "$command" in
  commercial) module=scripts.review_predictive_commercial_requirements_20261020 ;;
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
    empire_os/predictive_commercial_supply_readiness.py \
    empire_os/predictive_commercial_lead_eligibility.py \
    empire_os/predictive_commercial_fulfilment.py \
    empire_os/predictive_four_stage_economic_custody.py \
    empire_os/predictive_structural_revenue_gaps.py \
    scripts/review_empire_cross_agent_release_board_20261020.py \
    > metadata/critical_source_checksums.sha256
)
mv -T -- "$TMP" "$RELEASE"
trap - EXIT
echo "RELEASE_PATH=$RELEASE"
echo "RELEASE_COMMIT=$COMMIT"
echo "RELEASE_BIN=$RELEASE/bin/empire-predictive-observe"
echo "PRODUCTION_UNCHANGED=true"
