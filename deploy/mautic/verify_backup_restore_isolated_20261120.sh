#!/usr/bin/env bash
# Disposable isolated MariaDB recovery rehearsal. No live database writes,
# external network, ports, persistent storage, mail or customer imports.
set -Eeuo pipefail
umask 077
[[ "$(id -u)" == 0 && "${1:-}" == "--verify-founder-approved" ]] || exit 3
BACKUP=/var/backups/empiredb/mautic-app-20261120/20261120T103507Z
IMAGE='mariadb:11.4.13@sha256:5e73baf8179b29f115101bb102763a47a017361f3e9792daccba6646c3ab1532'
NAME="empire-mautic-restore-verify-20261120-$$"
[[ -f "$BACKUP/mautic_review.sql" && -f "$BACKUP/SHA256SUMS" ]] || exit 3
(cd "$BACKUP" && sha256sum --check SHA256SUMS >/dev/null) || exit 3
cleanup(){ docker rm -f "$NAME" >/dev/null 2>&1 || :; }
trap cleanup EXIT
docker run -d --name "$NAME" --network none --tmpfs /var/lib/mysql:rw,size=768m   -e MARIADB_ALLOW_EMPTY_ROOT_PASSWORD=yes -e MARIADB_DATABASE=mautic_restore   "$IMAGE" > /dev/null
ready=0
for i in $(seq 1 40); do
 if docker exec "$NAME" mariadb-admin ping -uroot --silent >/dev/null 2>&1; then ready=1; break; fi
 sleep 2
done
[[ "$ready" -eq 1 ]] || { echo MAUTIC_RESTORE=HOLD_DB_STARTUP >&2; exit 3; }
docker exec -i "$NAME" mariadb -uroot mautic_restore < "$BACKUP/mautic_review.sql"
tables="$(docker exec "$NAME" mariadb -uroot -D mautic_restore -N -e 'SHOW TABLES' | sed '/^$/d' | wc -l)"
[[ "$tables" =~ ^[0-9]+$ && "$tables" -eq 126 ]] || { echo MAUTIC_RESTORE=HOLD_TABLES_MISMATCH >&2; exit 3; }
admins="$(docker exec "$NAME" mariadb -uroot -D mautic_restore -N -e 'SELECT COUNT(*) FROM users')"
[[ "$admins" -eq 1 ]] || { echo MAUTIC_RESTORE=HOLD_ADMIN_COUNT_MISMATCH >&2; exit 3; }
printf 'MAUTIC_RESTORE=DISPOSABLE_NETWORK_NONE_NO_PORT_PERSISTENT_DATA_UNTOUCHED\n'
printf 'MAUTIC_RESTORE=VERIFIED_TABLES_%s_ADMIN_USERS_%s\n' "$tables" "$admins"
