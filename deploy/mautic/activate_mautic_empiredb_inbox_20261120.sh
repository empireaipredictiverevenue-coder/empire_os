#!/usr/bin/env bash
# Founder-authorised one-time EmpireDB Mautic inbox. No tenant login,
# customer mutation, service restart, sender, marketing consent or outreach.
set -Eeuo pipefail
umask 077
hold(){ printf 'MAUTIC_DB_RELEASE=HOLD_%s\n' "$1" >&2; exit 3; }
[[ "${1:-}" == "--apply-founder-approved" && "$#" -eq 1 ]] || hold EXACT_ACTION_REQUIRED
[[ "$(id -u)" == 0 ]] || hold AUTHORIZED_ROOT_REQUIRED
SQL=/home/ubuntu/.config/empireos/mautic_review/mautic_atomic_release_v3.sql
EXPECTED=0efa236d8deb18c98cd99609d20ab669d5b142cd2e8de4d612ca98b2feb9445d
[[ -f "$SQL" && ! -L "$SQL" && "$(stat -c %U "$SQL")" == ubuntu && "$(stat -c %a "$SQL")" == 600 ]] || hold PREPARED_SOURCE_INVALID
[[ "$(sha256sum "$SQL" | cut -d' ' -f1)" == "$EXPECTED" ]] || hold ATOMIC_SOURCE_HASH_MISMATCH
for c in runuser psql pg_dump pg_dumpall pg_restore pg_isready flock df sha256sum; do
 command -v "$c" >/dev/null || hold DEPENDENCY_MISSING
done
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]] || hold POSTGRES_NOT_ACTIVE
[[ "$(systemctl is-active empire-revenue-crm-pilot.service)" == active ]] || hold CRM_NOT_ACTIVE
pg_isready -q -d empiredb || hold DB_NOT_READY
mkdir -p /run/lock
exec 9>/run/lock/empiredb-mautic-20261120.lock
flock -n -x 9 || hold RELEASE_LOCK_BUSY
pg(){ runuser -u postgres -- psql -X -w -q -At -v ON_ERROR_STOP=1 -d empiredb -c "$1"; }
[[ "$(pg "SELECT current_database()")" == empiredb ]] || hold WRONG_DATABASE
[[ "$(pg "SELECT current_setting('data_directory')")" == /var/lib/postgresql/18/main ]] || hold WRONG_POSTGRESQL_INSTANCE
[[ "$(pg "SELECT pg_is_in_recovery()")" == f ]] || hold DATABASE_IN_RECOVERY
preflight="$(pg "
SELECT CASE WHEN
    pg_catalog.to_regclass('public.empire_crm_mautic_event_inbox') IS NULL
    AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empire_mautic_crm_inbox_writer')
    AND pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NOT NULL
    AND EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator' AND NOT rolcanlogin)
    AND EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empire_revenue_crm_reader' AND NOT rolcanlogin)
    AND EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empiredb_app')
    AND EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empiredb_readonly')
    AND EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empiredb_tenant_reader')
THEN 'PASS' ELSE 'HOLD' END;
")"
[[ "$preflight" == PASS ]] || hold CANONICAL_ROLE_SCHEMA_COLLISION
printf 'MAUTIC_DB_RELEASE=CANONICAL_INSTANCE_AND_ROLE_PRECHECK_PASS\n'
size="$(pg "SELECT pg_catalog.pg_database_size('empiredb')")"
[[ "$size" =~ ^[0-9]+$ ]] || hold DATABASE_SIZE_UNKNOWN
BACKUP=/var/backups/empiredb/mautic-inbox-20261120
install -d -o root -g root -m 0700 "$BACKUP"
available="$(df -PB1 "$BACKUP" | awk 'NR==2{print $4}')"
[[ "$available" =~ ^[0-9]+$ && "$available" -gt "$((size*2+536870912))" ]] || hold INSUFFICIENT_BACKUP_SPACE
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REC="$BACKUP/$STAMP"
[[ ! -e "$REC" ]] || hold BACKUP_COLLISION
install -d -o root -g root -m 0700 "$REC"
DUMP="$REC/empiredb-before-mautic-inbox.dump"
GLOBALS="$REC/empiredb-globals-before-mautic.sql"
LIST="$REC/restore-list.txt"
runuser -u postgres -- pg_dump -w -Fc -d empiredb > "$DUMP" || hold DATABASE_BACKUP_FAILED
runuser -u postgres -- pg_dumpall -w --globals-only > "$GLOBALS" || hold ROLE_BACKUP_FAILED
pg_restore --list "$DUMP" > "$LIST" || hold BACKUP_INVALID
[[ -s "$DUMP" && -s "$GLOBALS" && -s "$LIST" ]] || hold BACKUP_EMPTY
grep -Eq 'TABLE.*public.*prospects' "$LIST" || hold CANONICAL_PROSPECT_TABLE_NOT_BACKED_UP
(
 cd "$REC"
 sha256sum "$(basename "$DUMP")" "$(basename "$GLOBALS")" "$(basename "$LIST")" > SHA256SUMS
 sha256sum --check SHA256SUMS >/dev/null
) || hold BACKUP_HASH_MISMATCH
chmod 0600 "$DUMP" "$GLOBALS" "$LIST" "$REC/SHA256SUMS"
printf 'MAUTIC_DB_RELEASE=FULL_LOGICAL_DATABASE_AND_GLOBAL_ROLE_BACKUP_SHA_VERIFIED\n'
printf 'MAUTIC_DB_BACKUP_RECEIPT=%s\n' "$REC"
install -m 0600 -o root -g root "$SQL" "$REC/pinned-atomic-inbox.sql"
[[ "$(sha256sum "$REC/pinned-atomic-inbox.sql" | cut -d' ' -f1)" == "$EXPECTED" ]] || hold STAGED_SQL_HASH_CHANGED
cat "$REC/pinned-atomic-inbox.sql" | runuser -u postgres -- psql -X -w -q -v ON_ERROR_STOP=1 -d empiredb > "$REC/atomic-apply-output.log" 2>&1 || hold ATOMIC_TRANSACTION_FAILED
chmod 0600 "$REC/atomic-apply-output.log"
printf 'MAUTIC_DB_RELEASE=ATOMIC_ROLE_AND_INBOX_TRANSACTION_APPLIED\n'
post="$(pg "
SELECT CASE WHEN
 EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empire_mautic_crm_inbox_writer'
     AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper AND NOT rolbypassrls)
 AND EXISTS(SELECT 1 FROM pg_catalog.pg_class WHERE oid='public.empire_crm_mautic_event_inbox'::regclass
     AND relrowsecurity AND relforcerowsecurity)
 AND pg_catalog.has_schema_privilege('empire_mautic_crm_inbox_writer','public','USAGE')
 AND pg_catalog.has_table_privilege('empire_mautic_crm_inbox_writer',
     'public.empire_crm_mautic_event_inbox','SELECT,INSERT')
 AND pg_catalog.has_table_privilege('empire_revenue_crm_reader',
     'public.empire_crm_mautic_event_inbox','SELECT')
 AND NOT pg_catalog.has_table_privilege('empire_revenue_crm_reader',
     'public.empire_crm_mautic_event_inbox','INSERT')
 AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members m JOIN pg_catalog.pg_roles r ON r.oid=m.roleid
     WHERE r.rolname='empire_mautic_crm_inbox_writer')
 AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname LIKE 'empire_mautic_tenant_%')
 AND (SELECT count(*) FROM public.empire_crm_mautic_event_inbox)=0
THEN 'PASS' ELSE 'HOLD' END;")" || hold POSTCOMMIT_READBACK_FAILED
[[ "$post" == PASS ]] || hold POSTCOMMIT_SECURITY_OR_EVIDENCE_STATE_MISMATCH
[[ "$(systemctl is-active empire-revenue-crm-pilot.service)" == active ]] || hold EXISTING_CRM_STATE_CHANGED
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]] || hold EXISTING_DB_STATE_CHANGED
printf 'MAUTIC_DB_RELEASE=POSTCOMMIT_TENANT_RLS_AND_PRIVILEGES_VERIFIED\n'
printf 'MAUTIC_DB_RELEASE=PROVISIONED_INERT_NO_TENANT_LOGIN_NO_EVENT_NO_SEND\n'
