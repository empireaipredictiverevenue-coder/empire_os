#!/usr/bin/env bash
# First real Mautic application backup: isolated MariaDB + private config.
# READS live app, writes only a root-owned backup; no stopping/restarting.
set -Eeuo pipefail
umask 077
hold(){ printf 'MAUTIC_APP_BACKUP=HOLD_%s\n' "$1" >&2; exit 3; }
[[ "$(id -u)" == 0 && "${1:-}" == "--apply-founder-approved" ]] || hold ROOT_AND_APPROVAL_REQUIRED
WEB=empire-mautic-review-mautic_web-1
DB=empire-mautic-review-db-1
BASE=/home/ubuntu/.config/empireos/mautic_review
[[ "$(docker inspect -f '{{.State.Health.Status}}' "$WEB")" == healthy ]] || hold WEB_HEALTH
[[ "$(docker inspect -f '{{.State.Health.Status}}' "$DB")" == healthy ]] || hold DB_HEALTH
[[ "$(docker network inspect empire-mautic-review_private_review --format '{{.Internal}}')" == true ]] || hold NO_SEND_NETWORK_MISMATCH
[[ "$(systemctl is-active empire-revenue-crm-pilot.service)" == active ]] || hold CRM_UNAVAILABLE
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]] || hold POSTGRES_UNAVAILABLE
ROOT=/var/backups/empiredb/mautic-app-20261120
install -d -o root -g root -m 0700 "$ROOT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$ROOT/$STAMP"
[[ ! -e "$DEST" ]] || hold RECEIPT_COLLISION
install -d -o root -g root -m 0700 "$DEST"
docker exec "$DB" sh -c 'MYSQL_PWD="$MARIADB_PASSWORD" exec mariadb-dump --single-transaction --routines --triggers --events -u"$MARIADB_USER" "$MARIADB_DATABASE"' > "$DEST/mautic_review.sql" || hold MARIADB_DUMP_FAILED
docker cp "$WEB":/var/www/html/config/local.php "$DEST/mautic-local.php" >/dev/null || hold LOCAL_PHP_BACKUP_FAILED
install -m 0600 -o root -g root "$BASE/private.admin.env" "$DEST/admin-recovery.env" || hold ADMIN_RECOVERY_FAILED
chmod 0600 "$DEST/mautic_review.sql" "$DEST/mautic-local.php"
[[ -s "$DEST/mautic_review.sql" && -s "$DEST/mautic-local.php" && -s "$DEST/admin-recovery.env" ]] || hold BACKUP_EMPTY
tables="$(grep -c 'CREATE TABLE' "$DEST/mautic_review.sql" || :)"
[[ "$tables" =~ ^[0-9]+$ && "$tables" -ge 50 ]] || hold SQL_STRUCTURE_INCOMPLETE
(
 cd "$DEST"
 sha256sum mautic_review.sql mautic-local.php admin-recovery.env > SHA256SUMS
 sha256sum --check SHA256SUMS >/dev/null
)
chmod 0600 "$DEST/SHA256SUMS"
printf 'MAUTIC_APP_BACKUP=VERIFIED_SQL_CONFIG_AND_ADMIN_RECOVERY_SHA256\n'
printf 'MAUTIC_APP_BACKUP_SQL_TABLES=%s\n' "$tables"
printf 'MAUTIC_APP_BACKUP_RECEIPT=%s\n' "$DEST"
