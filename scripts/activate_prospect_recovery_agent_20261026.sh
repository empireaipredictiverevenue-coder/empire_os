#!/usr/bin/env bash
# Install the single source-pinned, root-owned EmpireOS Prospect Recovery Agent.
# Invoked explicitly by the authorised server owner. No DB migration/outbound.
set -euo pipefail
ROOT=/srv/empire_os
SRC=$ROOT/empire_os/prospect_recovery_agent.py
ROOT_COPY=/usr/local/libexec/empire-prospect-recovery-agent.py
SERVICE_NAME=empire-prospect-recovery-agent.service
TIMER_NAME=empire-prospect-recovery-agent.timer
SERVICE=/etc/systemd/system/$SERVICE_NAME
TIMER=/etc/systemd/system/$TIMER_NAME

if [[ "${EUID}" -ne 0 ]]; then
    echo 'HOLD: owner-authorised sudo installation required' >&2
    exit 3
fi
cd "$ROOT"

# Refuse a changed source tree rather than silently installing a different agent.
printf '%s\n' \
  'ac252ee0bce4161dafcf35ebdaa189352b3422a1c5081415e0708ca90b908d92  empire_os/prospect_recovery_agent.py' \
  'a649b5e7961fc9aca96d6c346a8a15a07c0338c4fcadc98c59485b4bb8ac091e  deploy/systemd/empire-prospect-recovery-agent.service' \
  '89ae356b7b4cd51803c451f19a789e794dbc1414e77980ddc37e0244d234f79d  deploy/systemd/empire-prospect-recovery-agent.timer' |
  sha256sum --check --status || {
    echo 'HOLD: agent source or unit changed since review' >&2
    exit 4
  }

if [[ -L /usr/local/libexec || -L "$ROOT_COPY" || -L "$SERVICE" || -L "$TIMER" ]]; then
    echo 'HOLD: unsafe symlink in installation target' >&2
    exit 5
fi
for pair in \
    "$SRC:$ROOT_COPY" \
    "$ROOT/deploy/systemd/$SERVICE_NAME:$SERVICE" \
    "$ROOT/deploy/systemd/$TIMER_NAME:$TIMER"
do
    source_file="${pair%%:*}"
    target_file="${pair#*:}"
    if [[ -e "$target_file" ]] && ! cmp -s "$source_file" "$target_file"; then
        echo "HOLD: existing deployment differs: $target_file" >&2
        exit 6
    fi
done

if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo 'HOLD: agent already executing' >&2
    exit 7
fi

created_copy=0
created_service=0
created_timer=0
timer_previously_enabled=0
systemctl is-enabled --quiet "$TIMER_NAME" && timer_previously_enabled=1 || true

install -d -m 0755 -o root -g root /usr/local/libexec
if [[ ! -e "$ROOT_COPY" ]]; then
    install -m 0555 -o root -g root "$SRC" "$ROOT_COPY"
    created_copy=1
fi
if [[ ! -e "$SERVICE" ]]; then
    install -m 0644 -o root -g root "$ROOT/deploy/systemd/$SERVICE_NAME" "$SERVICE"
    created_service=1
fi
if [[ ! -e "$TIMER" ]]; then
    install -m 0644 -o root -g root "$ROOT/deploy/systemd/$TIMER_NAME" "$TIMER"
    created_timer=1
fi

revert_on_failure() {
    code=$?
    if [[ "$code" -eq 0 ]]; then return; fi
    echo 'HOLD: agent activation did not verify; reverting new unit install' >&2
    if [[ "$timer_previously_enabled" -eq 0 ]]; then
        systemctl disable --now "$TIMER_NAME" >/dev/null 2>&1 || true
    fi
    [[ "$created_timer" -eq 0 ]] || rm -f "$TIMER"
    [[ "$created_service" -eq 0 ]] || rm -f "$SERVICE"
    [[ "$created_copy" -eq 0 ]] || rm -f "$ROOT_COPY"
    systemctl daemon-reload || true
}
trap revert_on_failure EXIT

# Unit names are fixed; systemd owns job locking/restart serialisation.
systemctl daemon-reload
systemctl enable --now "$TIMER_NAME" >/dev/null
systemctl start "$SERVICE_NAME"
systemctl is-active --quiet "$TIMER_NAME"
systemctl show "$SERVICE_NAME" -p Result --value | grep -qx success
test -f /var/lib/empire-prospect-recovery-agent/latest.json

/usr/bin/python3 -I -B -c '
import json
from pathlib import Path
path = Path("/var/lib/empire-prospect-recovery-agent/latest.json")
payload = json.loads(path.read_text())
assert payload["schema_version"] == "empire.prospect_recovery_agent.v1"
assert payload["execution_mode"] == "OWNER_INSTALLED_SUPERVISOR"
assert payload["outbound_sent"] is False
assert payload["payments_changed"] is False
print("PROSPECT_RECOVERY_AGENT_ACTIVE")
print("CANONICAL_PROSPECTS=" + str(payload["metrics"]["canonical_prospects"]))
print("V2_BACKLOG=" + str(payload["metrics"]["without_v2_record"]))
print("BUYER_RECRUITMENT_MARKETS=" + str(payload["worklist_count"]))
print("REPAIRS_REQUESTED=" + str(len(payload["unit_requests"])))
print("TIMER=15_MINUTES EXISTING_WORKERS_ONLY=true")
'
