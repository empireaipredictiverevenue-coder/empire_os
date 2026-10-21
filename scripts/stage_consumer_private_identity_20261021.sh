#!/usr/bin/env bash
# Stages only code, no DB connection, login, key, mail or service activation.
set -euo pipefail
W=/home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020
SRC="$W/scripts/provision_consumer_private_identity_20261021.py"
EXPECTED=477671838ef673880d1ecda409c0118824d7d4e2e243aa04a8749cc85b8c87c4
test -f "$SRC"
[[ "$(sha256sum "$SRC" | cut -d' ' -f1)" == "$EXPECTED" ]] || {
 echo "IDENTITY_SOURCE_DIGEST_HOLD";exit 3;
}
out=$(mktemp -d /var/tmp/empire-consumer-private-identity-20261021.XXXXXXXX)
chmod 0755 "$out"
install -m 0644 "$SRC" "$out/provision_consumer_private_identity_20261021.py"
[[ "$(sha256sum "$out/provision_consumer_private_identity_20261021.py" |cut -d' ' -f1)" == "$EXPECTED" ]] || {
 echo "STAGED_IDENTITY_SOURCE_MISMATCH";exit 3;
}
printf 'IDENTITY_RELEASE_STAGED_ONLY=true\n'
printf 'IDENTITY_RELEASE_SHA256=%s\n' "$EXPECTED"
printf 'STAGED_FILE=%s\n' "$out/provision_consumer_private_identity_20261021.py"
printf 'DB_ROLE_CREATED=false\n'
printf 'SECRETS_CREATED=false\n'
printf 'USER_ACTIVATION_ENABLED=false\n'
