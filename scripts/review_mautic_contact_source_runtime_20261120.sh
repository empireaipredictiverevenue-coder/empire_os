#!/usr/bin/env bash
# Read-only count-only Mautic contact and queue check. No customer data.
set -Eeuo pipefail
[[ "$(id -u)" == 0 ]] || exit 3
[[ "$(docker inspect -f '{{.State.Health.Status}}' empire-mautic-review-db-1)" == healthy ]] || exit 3
docker exec empire-mautic-review-db-1 sh -c 'MYSQL_PWD="$MARIADB_PASSWORD" mariadb -u"$MARIADB_USER" -D"$MARIADB_DATABASE" -N -e "SELECT (SELECT COUNT(*) FROM leads), (SELECT COUNT(*) FROM webhooks), (SELECT COUNT(*) FROM webhook_queue), (SELECT COUNT(*) FROM users)"'
