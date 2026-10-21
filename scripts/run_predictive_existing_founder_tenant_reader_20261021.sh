#!/usr/bin/env bash
# Existing founder tenant only. Operator-run, OBSERVE-only. Never print/relax
# the original root-owned PostgreSQL SCRAM password file.
set -euo pipefail

RELEASE='/home/ubuntu/empire_releases/predictive_observe_261d07fe9b00'
MANIFEST="$RELEASE/metadata/critical_source_checksums.sha256"
PYTHON='/srv/empire_os/.venv/bin/python'
PASSFILE='/etc/empire/verified-order-reader/reader.pgpass'
DSN='host=127.0.0.1 port=5432 dbname=empiredb user=empire_verified_order_tenant_login'

mode="${1:-both}"
case "$mode" in
  both|tenant-evidence|tenant-cohort|--check) ;;
  *) printf '%s\n' 'Usage: empire-predictive-founder-reader [both|tenant-evidence|tenant-cohort|--check]' >&2; exit 2 ;;
esac
# Privileged Python must not load the writable shared /srv source. Insist on
# the exact pinned tested release. No sudo required for verification.
if [[ ! -f "$MANIFEST" || ! -x "$PYTHON" ]]; then
  printf '%s\n' 'PREDICTIVE_PINNED_RELEASE_NOT_AVAILABLE' >&2
  exit 3
fi
if ! (cd "$RELEASE" && sha256sum --status -c "$MANIFEST"); then
  printf '%s\n' 'PREDICTIVE_RELEASE_CHECKSUM_HOLD' >&2
  exit 3
fi
if [[ "$mode" == --check ]]; then
  printf '%s\n' 'PINNED_PREDICTIVE_RELEASE_VERIFIED'
  printf '%s\n' 'ROOT_OWNED_CREDENTIAL_NOT_TESTED_IN_CHECK_MODE'
  exit 0
fi

case "$mode" in
  both) checks=(tenant-evidence tenant-cohort) ;;
  tenant-evidence) checks=(tenant-evidence) ;;
  tenant-cohort) checks=(tenant-cohort) ;;
esac
for check in "${checks[@]}"; do
  case "$check" in
    tenant-evidence) module='scripts.review_predictive_tenant_outcome_reader_preflight_20261020' ;;
    tenant-cohort) module='scripts.review_predictive_tenant_terminal_cohort_20261020' ;;
  esac
  # Requires existing founder sudo permission. Intentionally no fallback:
  # never use postgres, app credentials or chmod/copy the protected passfile.
  if ! sudo -n /usr/bin/env -i \
      PATH='/usr/bin:/bin' HOME='/root' \
      PGPASSFILE="$PASSFILE" \
      EMPIREDB_TENANT_OUTCOME_READER_DSN="$DSN" \
      PYTHONPATH="$RELEASE" \
      "$PYTHON" -B -m "$module" --read-only; then
    printf 'PREDICTIVE_%s_OPERATOR_EXECUTION_HOLD\n' "$check" >&2
    exit 4
  fi
done
