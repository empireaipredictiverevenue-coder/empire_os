#!/usr/bin/env bash
# Founder-approved ONE-RECORD CRM membership activation.
# NEVER authorises SQL LOGIN, credentials, HTTP/API, mail, payments or outbound.
# Requires fresh DNS challenge on BOTH Cloudflare authoritative nameservers.
set -euo pipefail
umask 077
die() { printf 'CRM_FOUNDER_ACTIVE=BLOCKED reason=%s\n' "$1" >&2; exit 3; }
[[ "$#" -eq 2 && "$1" == "--apply" && "$2" == "--approved-single-active-owner" ]] ||
  die 'EXPLICIT_FOUNDER_APPROVAL_REQUIRED'
[[ "$(id -u)" -eq 0 ]] || die 'ROOT_OPERATOR_REQUIRED'
cd /srv/empire_os

sql=scripts/activate_crm_founder_owner_membership.sql
sql_sha=5c441a736ac9a28d3da031b256ede90ff00904c2e37b83155d3b406e131373bf
dns_script=scripts/crm_founder_domain_challenge.py
dns_sha=9b3af3212c22fb0a69621955488d1a10be693865310ba0e7df5316abd1681a7b
[[ -f "$sql" && -f "$dns_script" ]] || die 'RELEASE_SOURCE_MISSING'
[[ "$(sha256sum "$sql" | cut -d' ' -f1)" == "$sql_sha" ]] ||
  die 'ACTIVATION_SQL_HASH_DRIFT'
[[ "$(sha256sum "$dns_script" | cut -d' ' -f1)" == "$dns_sha" ]] ||
  die 'DNS_VERIFICATION_CODE_DRIFT'
for file in "$sql" "$dns_script"; do
  git ls-files --error-unmatch "$file" >/dev/null 2>&1 ||
    die 'RELEASE_SOURCE_NOT_TRACKED'
  [[ "$(git rev-parse "HEAD:$file")" == "$(git hash-object "$file")" ]] ||
    die 'RELEASE_SOURCE_NOT_COMMITTED'
done
for executable in pg_dump pg_dumpall pg_restore runuser psql pg_isready flock df sha256sum; do
  command -v "$executable" >/dev/null || die 'DEPENDENCY_MISSING'
done
[[ -f /etc/empiredb.env ]] || die 'DB_ENV_MISSING'
set -a
# shellcheck disable=SC1091
source /etc/empiredb.env
set +a
[[ -n "${EMPIREDB_DSN:-}" ]] || die 'APP_DSN_MISSING'
unset PGUSER PGPASSWORD PGDATABASE PGSERVICE PGHOSTADDR
export PGHOST=/var/run/postgresql PGPORT=5432
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]] ||
  die 'CANONICAL_POSTGRES18_UNAVAILABLE'
pg_isready -q -d empiredb || die 'CANONICAL_DB_NOT_READY'
exec 9>/run/lock/empiredb-crm-founder-active-only.lock
flock -n -x 9 || die 'SAME_RELEASE_ALREADY_RUNNING'
pg() {
  runuser -u postgres -- psql -X -w -q -At -v ON_ERROR_STOP=1 \
    -h /var/run/postgresql -p 5432 -U postgres -d empiredb -c "$1"
}
[[ "$(pg 'SELECT current_database()')" == empiredb ]] || die 'WRONG_DATABASE'
[[ "$(pg "SELECT current_setting('data_directory')")" == /var/lib/postgresql/18/main ]] ||
  die 'WRONG_CLUSTER'
[[ "$(pg 'SELECT pg_is_in_recovery()')" == f ]] || die 'READ_ONLY_REPLICA'

operator_instance="$(pg "SELECT current_database()||'|'||
  extract(epoch from pg_postmaster_start_time())::bigint")"
app_instance="$(/srv/empire_os/.venv/bin/python - <<'PY'
import os
try:
    import psycopg
    with psycopg.connect(os.environ['EMPIREDB_DSN'], connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute('SET TRANSACTION READ ONLY')
            cur.execute("SET LOCAL statement_timeout='3000ms'")
            cur.execute("SELECT current_database()||'|'||"
                        "extract(epoch from pg_postmaster_start_time())::bigint")
            record=cur.fetchone()
            print(record[0] if record else 'UNVERIFIED')
except Exception:
    print('UNVERIFIED')
PY
)"
[[ "$operator_instance" == "$app_instance" ]] ||
  die 'APP_AND_OPERATOR_DATABASE_DIFFER'

# Read DNS challenge state as its owning ubuntu account (0600 / 0700).
# The verifier itself makes no database or DNS changes. The JSON is strict:
# no success can be inferred from a mere HTTP response or one nameserver.
verify_dns() {
  local result
  result="$(runuser -u ubuntu -- env -i \
    PATH=/usr/bin:/bin HOME=/home/ubuntu USER=ubuntu \
    /srv/empire_os/.venv/bin/python \
    /srv/empire_os/scripts/crm_founder_domain_challenge.py --verify)" ||
    die 'DNS_CHALLENGE_CHECK_UNAVAILABLE'
  printf '%s\n' "$result" | /srv/empire_os/.venv/bin/python -c '
import json,sys
try:
    v=json.load(sys.stdin)
    verified = (
        v.get("schema")=="empire.crm.founder_domain_txt_challenge.v1"
        and v.get("status")=="DOMAIN_DNS_TXT_MATCH_REVIEW_ONLY"
        and v.get("mode")=="OBSERVE"
        and v.get("verification_tenant_id")=="708efd4b-53b2-43d7-961d-1cecab67f17a"
        and v.get("dns_control_challenge_verified") is True
        and v.get("authoritative_nameserver_matches")=={
            "gracie.ns.cloudflare.com":True, "nash.ns.cloudflare.com":True}
        and v.get("founder_human_identity_verified") is False
        and v.get("legal_company_ownership_verified") is False
        and v.get("crm_membership_activated") is False
        and v.get("login_or_credentials_created") is False
    )
except (ValueError,TypeError,AttributeError):
    verified=False
sys.exit(0 if verified else 3)
' || die 'AUTHORITATIVE_DNS_CHALLENGE_MISSING_OR_EXPIRED'
}
verify_dns
printf 'CRM_FOUNDER_ACTIVE_DOMAIN_PROOF=TWO_AUTHORITATIVE_NAMESERVERS_MATCH\n'

before="$(pg "
SELECT
  (to_regclass('public.empire_crm_tenant_memberships') IS NOT NULL)::int
  ||'|'||(to_regclass('public.empire_crm_login_credentials') IS NOT NULL)::int
  ||'|'||(to_regprocedure('public.empire_crm_read_member(text,uuid)') IS NOT NULL)::int
  ||'|'||(SELECT count(*) FROM public.empire_crm_login_credentials)
  ||'|'||(SELECT count(*) FROM pg_authid
    WHERE rolname IN ('empire_crm_auth_login','empire_crm_membership_login')
      AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
      AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
      AND NOT rolreplication AND rolpassword IS NULL)
  ||'|'||(SELECT count(*) FROM public.empire_crm_tenant_memberships)
  ||'|'||(SELECT count(*) FROM public.empire_crm_tenant_memberships
    WHERE tenant_id='708efd4b-53b2-43d7-961d-1cecab67f17a'
      AND subject='founder:phil_livesley' AND role='owner'
      AND status='pending' AND revoked_at IS NULL AND valid_until IS NULL
      AND evidence_ref=
        'founder:chat-approved-single-owner-20261010'
        ||'|identity:connected-gmail-profile-reviewed-ownership-pending'
        ||'|tenant:operator-evidence-only-not-legal-proof')
  ||'|'||(SELECT count(*) FROM public.empire_crm_tenant_memberships
    WHERE status='active')
  ||'|'||(SELECT count(*) FROM public.empire_tenant_role_bindings
    WHERE tenant_id='708efd4b-53b2-43d7-961d-1cecab67f17a')
  ||'|'||(SELECT count(*) FROM public.empire_tenant_role_bindings b
    JOIN pg_roles r ON r.rolname=b.role_name
    WHERE b.tenant_id='708efd4b-53b2-43d7-961d-1cecab67f17a'
      AND b.role_name='empire_intelligence_materializer_login'
      AND b.active AND nullif(btrim(b.evidence_ref),'') IS NOT NULL
      AND r.rolcanlogin AND NOT r.rolsuper AND NOT r.rolbypassrls)
")" || die 'PREFLIGHT_QUERY_FAILED'
[[ "$before" == '1|1|1|0|2|1|1|0|1|1' ]] ||
  die 'EXISTING_MEMBERSHIP_OR_AUTHORITY_DRIFT_RECONCILE_FIRST'
printf 'CRM_FOUNDER_ACTIVE_PREFLIGHT=EXACT_PENDING_OWNER_ONLY\n'

size="$(pg "SELECT pg_database_size('empiredb')")" ||
  die 'DATABASE_SIZE_UNAVAILABLE'
[[ "$size" =~ ^[0-9]+$ ]] || die 'DATABASE_SIZE_NOT_NUMERIC'
backup_root=/var/backups/empiredb/crm-founder-active-owner
install -d -m 0700 -o root -g root "$backup_root"
available="$(df -PB1 "$backup_root" | awk 'NR==2{print $4}')"
[[ "$available" =~ ^[0-9]+$ ]] || die 'BACKUP_SPACE_UNVERIFIED'
(( available >= size * 2 + 536870912 )) || die 'BACKUP_SPACE_INSUFFICIENT'
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="$backup_root/$stamp"
[[ ! -e "$backup_dir" ]] || die 'BACKUP_PATH_ALREADY_EXISTS'
install -d -m 0700 -o root -g root "$backup_dir"
archive="$backup_dir/empiredb-before-founder-active-owner.dump"
globals="$backup_dir/pg-globals-before-founder-active-owner.sql"
manifest="$backup_dir/restore-list.txt"
printf 'CRM_FOUNDER_ACTIVE_BACKUP_START=YES\n'
runuser -u postgres -- pg_dump -w -Fc -d empiredb >"$archive" ||
  die 'CANONICAL_BACKUP_FAILED'
runuser -u postgres -- pg_dumpall -w --globals-only >"$globals" ||
  die 'GLOBAL_BACKUP_FAILED'
[[ -s "$archive" && -s "$globals" ]] || die 'BACKUP_EMPTY'
pg_restore --list "$archive" >"$manifest" ||
  die 'BACKUP_ARCHIVE_INVALID'
grep -q 'TABLE.*public.*empire_crm_tenant_memberships' "$manifest" ||
  die 'MEMBERSHIP_TABLE_ABSENT_IN_BACKUP'
grep -q 'TABLE.*public.*empire_crm_login_credentials' "$manifest" ||
  die 'CREDENTIAL_TABLE_ABSENT_IN_BACKUP'
(cd "$backup_dir" && sha256sum \
  empiredb-before-founder-active-owner.dump \
  pg-globals-before-founder-active-owner.sql \
  restore-list.txt > SHA256SUMS && sha256sum -c SHA256SUMS >/dev/null) ||
  die 'BACKUP_INTEGRITY_FAILED'
chmod 0600 "$archive" "$globals" "$manifest" "$backup_dir/SHA256SUMS"
printf 'CRM_FOUNDER_ACTIVE_BACKUP=VERIFIED_SHA256_FORMAT\n'
printf 'CRM_FOUNDER_ACTIVE_BACKUP_LOCATION=%s\n' "$backup_dir"
printf 'CRM_FOUNDER_ACTIVE_FULL_RESTORE_REHEARSAL=NOT_PERFORMED\n'

# Verify authorization evidence again after backup and before any write.
verify_dns
printf 'CRM_FOUNDER_ACTIVE_DOMAIN_RECHECK=PASS\n'
if ! runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 \
  -h /var/run/postgresql -p 5432 -U postgres -d empiredb \
  -f "$sql" >"$backup_dir/operation-stdout.log" \
  2>"$backup_dir/operation-stderr.log"; then
  printf 'CRM_FOUNDER_ACTIVE_TRANSACTION=ROLLED_BACK_OR_UNCONFIRMED\n' >&2
  printf 'CRM_FOUNDER_ACTIVE_PRIVATE_ERROR_LOG=%s\n' \
    "$backup_dir/operation-stderr.log" >&2
  exit 4
fi
printf 'CRM_FOUNDER_ACTIVE_TRANSACTION=COMMITTED\n'

after="$(pg "
SELECT
 (SELECT count(*) FROM public.empire_crm_tenant_memberships)
 ||'|'||(SELECT count(*) FROM public.empire_crm_tenant_memberships
   WHERE tenant_id='708efd4b-53b2-43d7-961d-1cecab67f17a'
     AND subject='founder:phil_livesley' AND role='owner' AND status='active'
     AND revoked_at IS NULL AND valid_until IS NULL
     AND evidence_ref=
        'founder:chat-approved-single-owner-20261010'
        ||'|identity:connected-gmail-profile-reviewed-ownership-pending'
        ||'|tenant:operator-evidence-only-not-legal-proof'
        ||'|founder:chat-approved-pending-to-active-20261010'
        ||'|mailbox:challenge-confirmed-20261010'
        ||'|dns:two-authoritative-nameservers-confirmed-20261010')
 ||'|'||(SELECT count(*) FROM public.empire_crm_tenant_memberships WHERE status='active')
 ||'|'||(SELECT count(*) FROM public.empire_crm_login_credentials)
 ||'|'||(SELECT count(*) FROM pg_authid
   WHERE rolname IN ('empire_crm_auth_login','empire_crm_membership_login')
    AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
    AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
    AND NOT rolreplication AND rolpassword IS NULL)
")" || {
 echo 'CRM_FOUNDER_ACTIVE_POSTCOMMIT=CATALOG_UNAVAILABLE_DO_NOT_RETRY' >&2
 exit 5
}
[[ "$after" == '1|1|1|0|2' ]] || {
  echo 'CRM_FOUNDER_ACTIVE_POSTCOMMIT=UNEXPECTED_STATE_DO_NOT_RETRY' >&2
  exit 5
}
printf 'CRM_FOUNDER_ACTIVE_POST_DEPLOYMENT=CATALOG_VERIFIED\n'
printf 'CRM_FOUNDER_ACTIVE_MEMBERSHIP_ROWS=1\n'
printf 'CRM_FOUNDER_ACTIVE_MEMBERSHIP_STATUS=active\n'
printf 'CRM_FOUNDER_ACTIVE_CREDENTIAL_ROWS=0\n'
printf 'CRM_FOUNDER_ACTIVE_LOGIN_ROLES=NOLOGIN_UNCHANGED\n'
printf 'CRM_FOUNDER_ACTIVE_HTTP_CONFIG_CHANGED=NO\n'
printf 'CRM_FOUNDER_ACTIVE_EMAIL_OR_INVITE_SENT=NO\n'
printf 'CRM_FOUNDER_ACTIVE_RESULT=ONE_ACTIVE_MEMBERSHIP_ONLY_LOGIN_AND_API_HELD\n'
