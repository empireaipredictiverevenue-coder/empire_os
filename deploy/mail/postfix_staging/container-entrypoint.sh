#!/usr/bin/env bash
# Entry point *inside disposable, network-none staging container only*.
# No production mail/DNS/credentials; no DATA, no external network.
set -euo pipefail

if [ "$(id -u)" != "0" ]; then
    echo "STAGING_HOLD=ISOLATED_CONTAINER_REQUIRES_OWN_SERVICE_IDENTITIES"
    exit 2
fi

ROOT="$(mktemp -d -p /tmp empire-postfix-stage-XXXXXXXX)"
STOP_POSTFIX=0
RSPAMD_PID=
cleanup() {
    if [ -n "$RSPAMD_PID" ]; then
        kill -TERM "$RSPAMD_PID" >/dev/null 2>&1 || true
        wait "$RSPAMD_PID" 2>/dev/null || true
    fi
    if [ "$STOP_POSTFIX" -eq 1 ]; then
        /usr/sbin/postfix stop >/dev/null 2>&1 || true
    fi
    case "$ROOT" in
        /tmp/empire-postfix-stage-*) rm -rf -- "$ROOT" ;;
    esac
}
trap cleanup EXIT

python3 - "$ROOT" <<'PY'
from pathlib import Path
from uuid import UUID
import sys
from empire_os.owned_postfix_staging_profile import (
    StageIdentity, generate_candidate_postfix_profile,
    validate_candidate_postfix_profile,
)
root=Path(sys.argv[1])
identity=StageIdentity(str(UUID(int=121)),uid=15000,gid=15000)
files=generate_candidate_postfix_profile(identity,root=root)
receipt=validate_candidate_postfix_profile(files,identity=identity,root=root)
assert receipt["external_relay_enabled"] is False
assert receipt["wildcard_or_catchall_admitted"] is False
assert receipt["smtp_submission_enabled"] is False
for name, body in files.items():
    target=root/name
    if target.exists() or target.is_symlink():
        raise ValueError("stage target already exists")
    target.write_text(body,encoding="utf8")
    target.chmod(0o600)
maildir=root/"maildir"
maildir.mkdir(mode=0o700)
maildir.chmod(0o700)
PY

# Virtual mailbox worker uses 15000:15000; strict but traversable stage parent.
chown 15000:15000 "$ROOT/maildir"
chmod 0700 "$ROOT/maildir"
install -o root -g root -m 0600 /dev/null "$ROOT/.empire-ci-mail-delivery-test"
printf "CI_CONTAINER_NETWORK_NONE\n" > "$ROOT/.empire-ci-mail-delivery-test"

# The real package-install stage creates the dedicated postfix/postdrop OS
# identities. Refuse to silently use ubuntu/nobody as a substitute.
getent passwd postfix >/dev/null
getent group postdrop >/dev/null

# Use the disposable container's already-initialised PRIMARY queue and
# data directories; an ad-hoc -c secondary configuration using primary
# spool paths would violate Postfix instance isolation.
# Never point at the host: docker runtime is --network none, no bind mounts.
if /usr/sbin/postfix status >/dev/null 2>&1; then
    echo "STAGING_HOLD=UNEXPECTED_ALREADY_RUNNING_POSTFIX"
    exit 2
fi
install -o root -g root -m 0644 "$ROOT/main.cf" /etc/postfix/main.cf
install -o root -g root -m 0644 "$ROOT/master.cf" /etc/postfix/master.cf

# Postfix's unprivileged smtpd must traverse the temporary map directory.
# No world-readable recipient map, no catch-all, and never change the
# generated static policy. Container lifetime owns these temporary paths.
/usr/sbin/postmap "hash:$ROOT/recipients"
test -r "$ROOT/recipients.db"
chown root:postfix "$ROOT" "$ROOT/recipients.db" "$ROOT/header_checks"
chmod 0751 "$ROOT"
chmod 0640 "$ROOT/recipients.db" "$ROOT/header_checks"

# Postfix regexp: map is used directly by cleanup; postmap -q confirms
# matching rule dispatch without compiling a regex database.
for FORGED_HEADER in \
    "Authentication-Results: mx-stage.mail.empire-ai.co.uk; dmarc=pass" \
    "ARC-Authentication-Results: i=1; mx-stage.mail.empire-ai.co.uk; dkim=pass" \
    "Received-SPF: pass (untrusted)"; do
    HEADER_ACTION="$(/usr/sbin/postmap -q "$FORGED_HEADER" "regexp:$ROOT/header_checks")"
    if [ "$HEADER_ACTION" != "IGNORE" ]; then
        echo "HOLD_FORGED_AUTHENTICATION_HEADER_SANITIZATION_MISSING"
        exit 2
    fi
done
echo "FORGED_AUTHENTICATION_HEADERS_IGNORED_BY_REAL_POSTFIX=TRUE"

# Validate the actual compiled map, not just source files. No open relay,
# bare reply@, unlisted alias or unrelated domain can match the allowlist.
EXPECTED="reply+00000000-0000-0000-0000-000000000079@mail.empire-ai.co.uk"
test -n "$(/usr/sbin/postmap -q "$EXPECTED" "hash:$ROOT/recipients")"
for REJECT in     "reply@mail.empire-ai.co.uk"     "reply+00000000-0000-0000-0000-00000000007a@mail.empire-ai.co.uk"     "unknown@mail.empire-ai.co.uk"     "anyone@external.invalid"; do
    if /usr/sbin/postmap -q "$REJECT" "hash:$ROOT/recipients" | grep -q .; then
        echo "STAGING_HOLD=UNEXPECTED_RECIPIENT_MAP_MATCH"
        exit 2
    fi
done

/usr/sbin/postconf -n >/dev/null
/usr/sbin/postconf -M >/dev/null
/usr/sbin/postfix check

# Only local RCPT admission; SMTP DATA and remote routes are never used.
STOP_POSTFIX=1
/usr/sbin/postfix start >/dev/null

python3 -m scripts.probe_postfix_staging_smtp_rcpt \
    --approved-isolated-loopback-rcpt-test

# Synthetic SMTP DATA is sent only to the private Maildir inside this
# disposable, no-network container. No real buyer or public route involved.
python3 -m scripts.probe_postfix_synthetic_delivery \
    --approved-isolated-synthetic-delivery --staging-root "$ROOT"

# Store evidence from the independently authored, no-follow Maildir reader.
# This validates original stored RFC bytes, exact one item, immutable inode,
# restricted owner/mode and stage-only synthetic Message-ID; not wire auth.
CUSTODY_BEFORE="$(python3 -m scripts.probe_postfix_maildir_custody \
    --approved-isolated-custody-check --staging-root "$ROOT")"
BEFORE="$(printf '%s' "$CUSTODY_BEFORE" | python3 -c '
import json,sys
s=json.load(sys.stdin)
assert s["status"]=="ORIGINAL_STORED_RFC_CUSTODY_VERIFIED"
assert s["sender_identity_verified"] is False
print(s["stored_rfc_bytes_sha256"])
')"

# Controlled same-container Postfix restart must not delete/mutate the
# single synthetic Maildir item. This is NOT power-loss durability.
# Validate stable digest and exact mailbox shape with a fresh no-follow
# read after the restart.
 /usr/sbin/postfix stop >/dev/null
STOP_POSTFIX=0
/usr/sbin/postfix start >/dev/null
STOP_POSTFIX=1
CUSTODY_AFTER="$(python3 -m scripts.probe_postfix_maildir_custody \
    --approved-isolated-custody-check --staging-root "$ROOT" \
    --previous-sha256 "$BEFORE")"
printf '%s' "$CUSTODY_AFTER" | python3 -c '
import json,sys
s=json.load(sys.stdin)
assert s["status"]=="ORIGINAL_STORED_RFC_CUSTODY_VERIFIED"
assert s["previous_digest_unchanged"] is True
assert s["sender_identity_verified"] is False
assert s["original_smtp_wire_digest_verified"] is False
'
echo "SYNTHETIC_MAILDIR_SURVIVED_SERVICE_RESTART=TRUE"
echo "STORED_RFC_CUSTODY_BEFORE_AND_AFTER_RESTART=VERIFIED"

echo "POSTFIX_ISOLATED_ACCEPTANCE=RCPT_PROBE_EXIT_ZERO"
echo "POSTFIX_ISOLATED_ACCEPTANCE_SYNTHETIC_DATA_ONLY=TRUE"
# A real inbound receiving verifier must be REQUIRED, not best-effort.
# Shut down the original test receiver first; no production ports exist.
/usr/sbin/postfix stop >/dev/null
STOP_POSTFIX=0

python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
from uuid import UUID
from empire_os.owned_postfix_rspamd_auth_stage import (
    StageIdentity, generate_postfix_rspamd_auth_stage,
)
root=Path(sys.argv[1])
candidate=generate_postfix_rspamd_auth_stage(
    StageIdentity(str(UUID(int=121)),15000,15000),root=root,
)
(root/"main.cf").write_text(candidate["main.cf"],encoding="utf8")
PY
install -o root -g root -m 0644 "$ROOT/main.cf" /etc/postfix/main.cf
/usr/sbin/postconf -n >/dev/null
/usr/sbin/postfix check

# The authentication verifier is deliberately NOT started. A down Milter
# MUST cause temporary failure, not acceptance or silent fallback.
python3 - <<'PY'
import socket
s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.settimeout(.5)
try:
    assert s.connect_ex(("127.0.0.1",11332)) != 0
finally:
    s.close()
print("REAL_MILTER_IS_DELIBERATELY_UNAVAILABLE=TRUE")
PY
/usr/sbin/postfix start >/dev/null
STOP_POSTFIX=1
python3 -m scripts.probe_postfix_milter_outage \
    --approved-offline-milter-outage
echo "REAL_POSTFIX_MILTER_DOWN_FAIL_CLOSED=TRUE"

# Only after the 451 outage proof, start the package-installed
# first-party Rspamd proxy worker. No DNS or network exists outside
# 127.0.0.1 due to the caller's --network none container flag.
getent passwd _rspamd >/dev/null
getent group _rspamd >/dev/null
/usr/bin/rspamadm configtest >/dev/null
/usr/bin/rspamd -f -u _rspamd -g _rspamd \
    >"$ROOT/rspamd-test.log" 2>&1 &
RSPAMD_PID=$!
python3 - <<'PY'
import socket,time
for _ in range(65):
    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock.settimeout(.4)
    try:
        if sock.connect_ex(("127.0.0.1",11332))==0:
            print("REAL_RSPAMD_PROXY_LISTENER_PRESENT=TRUE")
            break
    finally:
        sock.close()
    time.sleep(.2)
else:
    raise SystemExit("HOLD_RSPAMD_LOCAL_MILTER_LISTENER_UNAVAILABLE")
PY
python3 -m scripts.probe_postfix_milter_online \
    --approved-offline-local-milter
echo "REAL_POSTFIX_TO_RSPAMD_SYNTHETIC_DATA=ACCEPTED"
echo "SENDER_DKIM_SPF_DMARC_AUTHENTICATION_PROVEN=FALSE"
echo "POSTFIX_MX_CHANGED=FALSE"
