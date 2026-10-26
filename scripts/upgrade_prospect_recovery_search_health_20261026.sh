#!/usr/bin/env bash
# Reviewed owner-only upgrade of the existing stand-alone agent.
# Does not create/disable new agents, change allowlisted units, touch EmpireDB,
# send outbound, spend API credits, or expand restart authority.
set -euo pipefail

ROOT=/srv/empire_os
SOURCE=$ROOT/empire_os/prospect_recovery_agent.py
DEST=/usr/local/libexec/empire-prospect-recovery-agent.py
SERVICE=empire-prospect-recovery-agent.service
TIMER=empire-prospect-recovery-agent.timer
PREVIOUS=ac252ee0bce4161dafcf35ebdaa189352b3422a1c5081415e0708ca90b908d92
UPGRADED=1730335714608cc83eb1fe1607185e1f95935065fdbdd17a6fa8c3ddb9476567

if [[ "${EUID}" -ne 0 ]]; then
  echo "HOLD: authorised root operator required" >&2
  exit 3
fi
if [[ -L "$SOURCE" || -L "$DEST" || ! -f "$DEST" ]]; then
  echo "HOLD: unsafe or absent installed agent" >&2
  exit 4
fi
printf '%s\n' "$UPGRADED  $SOURCE" | sha256sum --check --status || {
  echo "HOLD: staged source differs from reviewed code" >&2
  exit 5
}
old_hash="$(sha256sum "$DEST" | cut -d' ' -f1)"
if [[ "$old_hash" == "$UPGRADED" ]]; then
  echo "PROSPECT_RECOVERY_SEARCH_HEALTH_ALREADY_INSTALLED"
  exit 0
fi
if [[ "$old_hash" != "$PREVIOUS" ]]; then
  echo "HOLD: installed agent differs from prior reviewed version" >&2
  exit 6
fi
if [[ "$(stat -c '%U:%G:%a' "$DEST")" != "root:root:555" ]]; then
  echo "HOLD: installed agent ownership/mode unexpected" >&2
  exit 7
fi
if ! systemctl is-enabled --quiet "$TIMER" ||
   ! systemctl is-active --quiet "$TIMER"; then
  echo "HOLD: existing timer must be active before upgrade" >&2
  exit 8
fi
if systemctl is-active --quiet "$SERVICE"; then
  echo "HOLD: existing agent currently running" >&2
  exit 9
fi

backup="$(mktemp /usr/local/libexec/.empire-prospect-recovery-old.XXXXXXXX)"
candidate="$(mktemp /usr/local/libexec/.empire-prospect-recovery-new.XXXXXXXX)"
chmod 0600 "$backup" "$candidate"
cp "$DEST" "$backup"
timer_was_stopped=false
success=false
on_exit() {
  if [[ "$success" != true ]]; then
    echo "HOLD: upgrade failed, restoring previously verified agent" >&2
    if [[ -f "$backup" ]]; then
      install -m 0555 -o root -g root "$backup" "$DEST"
    fi
  fi
  if [[ "$timer_was_stopped" == true ]]; then
    systemctl start "$TIMER" || true
  fi
  rm -f "$backup" "$candidate"
}
trap on_exit EXIT

# Pausing only this timer prevents a racing job while swapping the root file.
systemctl stop "$TIMER"
timer_was_stopped=true
if systemctl is-active --quiet "$SERVICE"; then
  echo "HOLD: service raced with timer shutdown" >&2
  exit 10
fi
install -m 0555 -o root -g root "$SOURCE" "$candidate"
printf '%s\n' "$UPGRADED  $candidate" | sha256sum --check --status || {
  echo "HOLD: staged copy modified during installation" >&2
  exit 11
}
mv -f "$candidate" "$DEST"
/usr/bin/python3 -I -B "$DEST" --repo-root "$ROOT" >/dev/null
systemctl start "$SERVICE"
if [[ "$(systemctl show "$SERVICE" -p Result --value)" != success ]]; then
  echo "HOLD: controlled service verification failed" >&2
  exit 12
fi
/usr/bin/python3 -I -B -c '
import json
from pathlib import Path
p = json.loads(Path("/var/lib/empire-prospect-recovery-agent/latest.json").read_text())
assert p["schema_version"] == "empire.prospect_recovery_agent.v1"
health = p["buyer_research_source_health"]
assert health["automatic_additional_search_requests"] == 0
assert health["automated_search_restart_authorized_by_degradation"] is False
assert p["outbound_sent"] is False
assert p["payments_changed"] is False
print("PROSPECT_RECOVERY_SEARCH_HEALTH_ACTIVE")
print("SEARCH_HEALTH=" + health["state"])
print("SCOUT_QUERIES_WITH_DOMAINS=" + str(health["queries_with_eligible_domains"]))
print("SUPERVISOR=EXISTING_SERVICE TIMER=EXISTING_15_MINUTE")
'
success=true
