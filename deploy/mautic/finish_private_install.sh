#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
project=/home/ubuntu/empire_worktrees/mautic_integrated_active_20261119/deploy/mautic
secrets=/home/ubuntu/.config/empireos/mautic_review
dc(){ docker compose --env-file "$secrets/private.env" -f "$project/compose.mautic7.private-nosend.yaml" "$@"; }
[[ "$(id -u)" == 0 && "${1:-}" == "--apply-founder-approved" ]] || exit 3
[[ "$(docker network inspect empire-mautic-review_private_review --format '{{.Internal}}')" == true ]] || exit 3
[[ "$(docker inspect -f '{{.State.Health.Status}}' empire-mautic-review-db-1)" == healthy ]] || exit 3
# The official Docker entrypoint creates a local.php bootstrap file even
# before the database installer runs. Prove an empty Mautic DB instead.
tables="$(dc exec -T db sh -c 'MYSQL_PWD="$MARIADB_PASSWORD" mariadb -u"$MARIADB_USER" -D"$MARIADB_DATABASE" -N -e "SHOW TABLES"' | sed '/^$/d' | wc -l)"
[[ "$tables" -eq 0 ]] || { echo MAUTIC_INSTALL=HOLD_ALREADY_PROVISIONED >&2; exit 3; }
dc exec -T mautic_web curl -s -I --max-time 5 http://127.0.0.1/ | grep -q /installer
printf 'MAUTIC_PRIVATE_INSTALL_PREFLIGHT=PASS\n'

[[ "$(stat -c %a "$secrets/private.admin.env")" == 600 ]] || exit 3
admin="$(sed -n 's/^EMPIRE_MAUTIC_ADMIN_PASSWORD=//p' "$secrets/private.admin.env")"
[[ "$admin" =~ ^[A-Za-z0-9_-]{40,}$ ]] || exit 3
printf '%s\n' "$admin" | dc exec -T -u www-data -w /var/www/html mautic_web sh -c 'IFS= read -r pass; php bin/console mautic:install "http://127.0.0.1:18784" --db_host=db --db_port=3306 --db_name=mautic_review --db_user=mautic_review --db_password="$MAUTIC_DB_PASSWORD" --admin_email=mautic-review-admin@example.invalid --admin_password="$pass" --force --no-interaction'
unset admin
printf 'MAUTIC_PRIVATE_INSTALL_CLI=PASS\n'

tables_after="$(dc exec -T db sh -c 'MYSQL_PWD="$MARIADB_PASSWORD" mariadb -u"$MARIADB_USER" -D"$MARIADB_DATABASE" -N -e "SHOW TABLES"' | sed '/^$/d' | wc -l)"
[[ "$tables_after" -ge 50 ]] || { echo MAUTIC_INSTALL=HOLD_SCHEMA_INCOMPLETE >&2; exit 3; }
echo "MAUTIC_PRIVATE_SCHEMA_VERIFIED_TABLES=$tables_after"
dc exec -T mautic_web php /var/www/html/bin/console --version
[[ "$(systemctl is-active empire-revenue-crm-pilot.service)" == active ]] || exit 3
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]] || exit 3
echo MAUTIC_PRIVATE_NO_SEND_INSTALL_VERIFIED
