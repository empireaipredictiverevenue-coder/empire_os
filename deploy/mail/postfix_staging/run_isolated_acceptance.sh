#!/usr/bin/env bash
# Explicit isolated SMTP acceptance test. No production receiving services.
# Docker is only invoked after a separate operator approval and availability.
set -euo pipefail

if [ "${1:-}" != "--approved-isolated-container-only" ]; then
    echo "HOLD_ISOLATED_CONTAINER_OPERATOR_APPROVAL_REQUIRED"
    exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "HOLD_DOCKER_RUNTIME_NOT_PRESENT"
    exit 2
fi

# This does not bypass denied Docker daemon access or adjust memberships.
if ! docker info >/dev/null 2>&1; then
    echo "HOLD_DOCKER_DAEMON_ACCESS_DENIED"
    exit 2
fi

HERE="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(CDPATH= cd -- "$HERE/../../.." && pwd -P)"
STAGE="$(mktemp -d -p /tmp empire-postfix-stage-build-XXXXXXXX)"
TAG="empire-postfix-rcpt-fixture-${USER:-operator}-$$"
cleanup() {
    case "$STAGE" in
        /tmp/empire-postfix-stage-build-*) rm -rf -- "$STAGE" ;;
    esac
    docker image rm -- "$TAG" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Strict three-file build context: no .env, Git history, credentials, logs
# or unrelated source trees are sent to the Docker daemon.
install -m 0600 "$ROOT/empire_os/owned_postfix_staging_profile.py" \
    "$STAGE/owned_postfix_staging_profile.py"
install -m 0600 "$ROOT/scripts/probe_postfix_staging_smtp_rcpt.py" \
    "$STAGE/probe_postfix_staging_smtp_rcpt.py"
install -m 0600 "$HERE/container-entrypoint.sh" \
    "$STAGE/container-entrypoint.sh"
install -m 0600 "$HERE/Dockerfile" "$STAGE/Dockerfile"

docker build --tag "$TAG" "$STAGE"

# Absolutely NO public network or port publishing at runtime.
# The container starts a local-only Postfix and executes RCPT-only probes.
docker run --rm --pull never --network none --pids-limit 80 \
    --memory 384m --hostname mx-stage.mail.empire-ai.co.uk "$TAG"

echo "ISOLATED_RUNTIME_PROBE_COMPLETE"
echo "PRODUCTION_MAIL_ROUTE_NOT_CHANGED"
