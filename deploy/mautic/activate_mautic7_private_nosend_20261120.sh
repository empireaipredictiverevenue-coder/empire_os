#!/usr/bin/env bash
# Founder-authorised isolated Mautic 7 no-send release. Never touches Smart CRM
# or EmpireDB; no cron, contacts, email, public reverse proxy or customer import.
set -Eeuo pipefail
umask 077
fail(){ printf 'MAUTIC_RELEASE=HOLD_%s\n' "$1" >&2; exit 3; }
[[ "${1:-}" == "--apply-founder-approved" && "$#" -eq 1 ]] || fail EXACT_ACTION_REQUIRED
[[ "$(id -u)" == 0 ]] || fail ROOT_OPERATOR_REQUIRED
P=/home/ubuntu/empire_worktrees/mautic_integrated_active_20261119
COMPOSE="$P/deploy/mautic/compose.mautic7.private-nosend.yaml"
PRIVATE=/home/ubuntu/.config/empireos/mautic_review/private.env
cd "$P"
[[ "$(git rev-parse --verify HEAD)" == "49ef8f76ecb5b48f0364672256023e123448b37f" ]] || fail BRANCH_DRIFT
[[ "$(stat -c %a "$PRIVATE")" == 600 ]] || fail SECRET_PERMISSIONS
[[ "$(stat -c %U "$PRIVATE")" == ubuntu ]] || fail SECRET_OWNER
[[ "$(systemctl is-active docker.service)" == active ]] || fail DOCKER_UNAVAILABLE
[[ "$(systemctl is-active empire-revenue-crm-pilot.service)" == active ]] || fail ORIGINAL_CRM_UNAVAILABLE
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]] || fail ORIGINAL_POSTGRES_UNAVAILABLE
[[ -f "$COMPOSE" && ! -L "$COMPOSE" ]] || fail COMPOSE_MISSING
[[ "$(sha256sum "$COMPOSE" | cut -d' ' -f1)" == "0cb41edc39a989125e0c1545c63481d7107595193f94b9cdf9576277f830c6b2" ]] || fail COMPOSE_CHANGED
[[ "$(ss -ltnH 'sport = :18784' | wc -l)" -eq 0 ]] || fail LOCAL_PORT_IN_USE
docker compose --env-file "$PRIVATE" -f "$COMPOSE" config --quiet || fail COMPOSE_INVALID
if [[ -n "$(docker ps -aq --filter label=com.docker.compose.project=empire-mautic-review)" ]]; then
  fail PROJECT_EXISTS_RECONCILE_WITHOUT_RECREATE
fi
if docker volume ls -q | grep -Eq '^empire-mautic-review_(mautic_db|mautic_config|mautic_logs|mautic_media_files|mautic_media_images)$'; then
  fail EXISTING_VOLUME_REQUIRES_RECONCILIATION
fi
if docker network ls --format '{{.Name}}' | grep -Fxq empire-mautic-review_private_review; then
  fail EXISTING_NETWORK_REQUIRES_RECONCILIATION
fi
printf 'MAUTIC_RELEASE=EXACT_CANDIDATE_ROOT_PREFLIGHT_PASS\n'
# Version-pinned pulls use the complete OCI digest in the guarded Compose.
docker compose --env-file "$PRIVATE" -f "$COMPOSE" pull db mautic_web || fail IMAGE_PULL_FAILED
printf 'MAUTIC_RELEASE=OFFICIAL_IMAGES_PULL_COMPLETE\n'
docker compose --env-file "$PRIVATE" -f "$COMPOSE" up -d --no-build db mautic_web || fail CONTAINER_BOOT_FAILED
printf 'MAUTIC_RELEASE=PRIVATE_CONTAINERS_CREATED\n'
docker compose --env-file "$PRIVATE" -f "$COMPOSE" ps --format json || :
[[ "$(systemctl is-active empire-revenue-crm-pilot.service)" == active ]] || fail CRM_STATE_CHANGED
[[ "$(systemctl is-active postgresql@18-main.service)" == active ]] || fail POSTGRES_STATE_CHANGED
printf 'MAUTIC_RELEASE=PRIVATE_CONTAINERS_STARTED_PENDING_MAUTIC_APP_INSTALL\n'
