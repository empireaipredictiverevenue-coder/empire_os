#!/usr/bin/env bash
# Prepare an immutable-content, non-secret operator bundle readable by
# PostgreSQL's OS account. NO database SQL is executed by this command.
set -euo pipefail
W=/home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020
PY=/srv/empire_os/.venv/bin/python
EXPECTED=2fa878eb0d93d011dc55b1cba0e9c37b58603944b9c99abb4959a1238b80de0c
test -f "$W/scripts/guarded_install_consumer_schema_20261021.py"
out=$(mktemp -d /var/tmp/empire-consumer-db-20261021.XXXXXXXX)
trap '[[ -z "${out:-}" ]] || rm -rf -- "$out"' ERR
chmod 0755 "$out"
mkdir -p "$out/scripts" "$out/migrations/empiredb"
chmod 0755 "$out/scripts" "$out/migrations" "$out/migrations/empiredb"
install -m 0644 "$W/scripts/guarded_install_consumer_schema_20261021.py" "$out/scripts/"
install -m 0644 "$W/migrations/empiredb/057_consumer_roofing_optin_staged_20261020.sql" "$out/migrations/empiredb/"
install -m 0644 "$W/migrations/empiredb/058_consumer_optin_private_role_staged_20261020.sql" "$out/migrations/empiredb/"
digest=$("$PY" -B - "$out/scripts/guarded_install_consumer_schema_20261021.py" <<'PY'
import runpy,sys
module=runpy.run_path(sys.argv[1],run_name="stage_verify")
print(module["fingerprint"]())
PY
)
if [[ "$digest" != "$EXPECTED" ]];then
  echo "STAGED_RELEASE_DIGEST_CHANGED_HOLD"
  exit 3
fi
printf 'BUNDLE_PATH=%s\n' "$out"
printf 'EXACT_RELEASE_SHA256=%s\n' "$digest"
printf 'POSTGRES_READ_ONLY_PREFLIGHT=sudo -n -u postgres /srv/empire_os/.venv/bin/python -B %s/scripts/guarded_install_consumer_schema_20261021.py --read-only\n' "$out"
printf 'DATABASE_MUTATIONS=0\n'
printf 'SUBSCRIBER_COLLECTION_ENABLED=false\n'
out=""
