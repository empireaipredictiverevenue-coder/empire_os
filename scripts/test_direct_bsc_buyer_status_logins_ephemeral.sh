#!/usr/bin/env bash
# Isolated PG18 proof only: 047–050 baseline + two NOINHERIT logins.
set -euo pipefail
cd "$(dirname "$(dirname "$(readlink -f "$0")")")"
if [[ "$#" -eq 0 ]]; then exec pg_virtualenv -v 18 bash "$0" --isolated-inner; fi
[[ "$1" == --isolated-inner && -n "${PGPORT:-}" && "$PGPORT" != 5432 ]] || exit 70
pgdir="$(psql -X -w -At -d postgres -c 'SHOW data_directory')"
[[ "$pgdir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 71

# Reuse only existing source fixtures; never run any external service.
source <(sed '/^# Deliberately make a login/,$d' \
  scripts/test_direct_bsc_private_reader_049_ephemeral.sh)
pg -f migrations/empiredb/049_direct_bsc_buyer_status_private_reader.sql >/dev/null
pg -f migrations/empiredb/050_direct_bsc_buyer_status_private_issuer.sql >/dev/null
echo 'EPHEMERAL_047_TO_050_BASELINE=PASS'
for entry in "049|12|scripts/inspect_direct_bsc_reader_049_after_050.sql" \
             "050|10|scripts/inspect_direct_bsc_private_issuer_050_postcommit.sql"; do
 IFS='|' read -r ver expected proof <<< "$entry"
 report="$(pg -f "$proof")"
 total="$(printf '%s\n' "$report" | grep -Ec '^(0[1-9]|1[0-2])_[a-z0-9_]+\|PASS$' || true)"
 [[ "$total" == "$expected" ]] || {
  echo "EPHEMERAL_EXISTING_049_050_READBACK_UNSAFE"; exit 72;
 }
 echo "EPHEMERAL_${ver}_AFTER_050_SECURITY_READBACK=PASS"
done
# The role provisioner grants CONNECT on canonical database name. Reproduce
# that name only in this disposable cluster; fixture finance rows stay separate.
psql -X -w -v ON_ERROR_STOP=1 -d postgres -c 'CREATE DATABASE empiredb' >/dev/null

./.venv/bin/python - <<'PY' | pg >/dev/null
from scripts.provision_direct_bsc_buyer_status_logins import (
    provision_sql, READ_LOGIN, ISSUE_LOGIN
)
print(provision_sql({READ_LOGIN:"a"*54, ISSUE_LOGIN:"b"*54}))
PY
echo 'EPHEMERAL_EXACT_DEDICATED_LOGIN_DDL=PASS'
./.venv/bin/python - <<'PY'
import os
from scripts.provision_direct_bsc_buyer_status_logins import (
    verify_login, READ_LOGIN, ISSUE_LOGIN, READ_ROLE, ISSUE_ROLE, FUNCTIONS,
)
base="dbname=direct_bsc_capability_fixture host=127.0.0.1 port="+os.environ["PGPORT"]
verify_login(base+" user="+READ_LOGIN+" password="+("a"*54), READ_ROLE,
             FUNCTIONS[READ_LOGIN], FUNCTIONS[ISSUE_LOGIN])
verify_login(base+" user="+ISSUE_LOGIN+" password="+("b"*54), ISSUE_ROLE,
             FUNCTIONS[ISSUE_LOGIN], FUNCTIONS[READ_LOGIN])
print('EPHEMERAL_BOTH_NO_INHERIT_CONNECTIONS_VERIFIED=PASS')
PY

# Exact membership plus cannot connect into other role.
details="$(pg -At -c "
SELECT member.rolname||'|'||granted.rolname||'|'||
       m.inherit_option::int||'|'||m.set_option::int||'|'||
       m.admin_option::int
FROM pg_catalog.pg_auth_members m
JOIN pg_catalog.pg_roles member ON member.oid=m.member
JOIN pg_catalog.pg_roles granted ON granted.oid=m.roleid
WHERE member.rolname IN (
 'empire_direct_checkout_status_reader_login',
 'empire_direct_checkout_status_issuer_login')
ORDER BY member.rolname")"
printf '%s\n' "$details" |
 grep -qx 'empire_direct_checkout_status_reader_login|empire_direct_checkout_status_reader|0|1|0' ||
 { echo 'EPHEMERAL_READER_LOGIN_MEMBERSHIP_DRIFT'; exit 73; }
printf '%s\n' "$details" |
 grep -qx 'empire_direct_checkout_status_issuer_login|empire_direct_checkout_status_issuer|0|1|0' ||
 { echo 'EPHEMERAL_ISSUER_LOGIN_MEMBERSHIP_DRIFT'; exit 74; }
[[ "$(printf '%s\n' "$details" | wc -l)" == 2 ]] ||
 { echo 'EPHEMERAL_EXTRA_LOGIN_MEMBERSHIPS'; exit 75; }
echo 'EPHEMERAL_EXACT_TWO_LOGIN_MEMBERSHIPS=PASS'

if pg -c "SET SESSION AUTHORIZATION empire_direct_checkout_status_reader_login;
 SET ROLE empire_direct_checkout_status_issuer" >/dev/null 2>&1; then
 echo 'EPHEMERAL_CROSS_ROLE_SWITCH_UNSAFE';exit 76
fi
echo 'EPHEMERAL_CROSS_ROLE_SWITCH_DENIED=PASS'

# A second attempt must stop at the first preexisting LOGIN before writes.
if ./.venv/bin/python - <<'PY' | pg >/dev/null 2>&1
from scripts.provision_direct_bsc_buyer_status_logins import (
    provision_sql, READ_LOGIN, ISSUE_LOGIN
)
print(provision_sql({READ_LOGIN:"c"*54, ISSUE_LOGIN:"d"*54}))
PY
then
 echo 'EPHEMERAL_REPEAT_LOGIN_PROVISIONING_UNSAFE';exit 77
fi
echo 'EPHEMERAL_SECOND_PROVISIONING_DENIED=PASS'
echo 'PRODUCTION_POSTGRES_PORT_ACCESSED=NO'
echo 'PRODUCTION_LOGIN_OR_PAYMENT_ACTIVATION=NO'
