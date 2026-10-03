#!/usr/bin/env bash
set -euo pipefail

cd /srv/empire_os

if [[ "${EMPIRE_OUTBOUND_ROLE_PROVISION_APPROVED:-}" != "YES" ]]; then
  echo "BLOCKED: set EMPIRE_OUTBOUND_ROLE_PROVISION_APPROVED=YES only after explicit founder authority-expansion approval." >&2
  exit 2
fi

: "${EMPIREDB_MIGRATOR_DSN:?EMPIREDB_MIGRATOR_DSN is required}"

psql "$EMPIREDB_MIGRATOR_DSN" \
  -X -v ON_ERROR_STOP=1 -1 \
  -f deploy/empiredb/outbound_deliverability_roles.sql
