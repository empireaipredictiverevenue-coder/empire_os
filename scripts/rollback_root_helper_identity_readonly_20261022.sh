#!/usr/bin/env bash
# Revert only the exact owned identity-readonly helper override.
set -Eeuo pipefail
OLD=/opt/empire-ai/privileged-helper/releases/20261015-custody-audit-v5
NEW=/opt/empire-ai/privileged-helper/releases/agent-identity-readonly-20261022v1
DROP=/etc/systemd/system/empire-ops-privileged-helper.service.d/95-agent-identity-readonly-20261022.conf
UNIT=empire-ops-privileged-helper.service
LEGACY=/run/empire-ops/privileged.sock
IDENTITY=/run/empire-ops/agent-identity-readonly.sock
ORIGINAL_SHA=3d2d66c17c09900864eef3ca6776af0456269c655479c8d615c6762c566ec239
fail() { echo "ROOT_HELPER_IDENTITY_ROLLBACK_HOLD: $*" >&2; exit 1; }
expected() {
  printf '[Service]\nWorkingDirectory=%s\nEnvironment=PYTHONPATH=%s\nEnvironment=PYTHONNOUSERSITE=1\nEnvironment=PYTHONDONTWRITEBYTECODE=1\nExecStart=\nExecStart=/usr/bin/python3 -B -P -m empire_os.ops_privileged_helper --socket /run/empire-ops/privileged.sock --allowed-user ubuntu\n' "$NEW" "$NEW"
}
[[ "${1:-}" == --apply-founder-approved && $# == 1 ]] || fail "exact founder approval flag required"
[[ "$EUID" == 0 ]] || fail "root release owner required"
[[ "$(systemctl show "$UNIT" -p WorkingDirectory --value)" == "$NEW" ]] || fail "not_on_our_pinned_release"
[[ -f "$DROP" && ! -L "$DROP" ]] || fail "reviewed_override_missing"
cmp -s "$DROP" <(expected) || fail "override_changed_externally"
printf '%s  %s\n' "$ORIGINAL_SHA" "$OLD/empire_os/ops_privileged_helper.py" | sha256sum --check --status || fail "original_release_changed"
rm -f -- "$DROP"
systemctl daemon-reload
systemctl restart "$UNIT"
[[ "$(systemctl show "$UNIT" -p WorkingDirectory --value)" == "$OLD" ]] || fail "original_release_not_restored"
[[ "$(systemctl show "$UNIT" -p ActiveState --value)" == active ]] || fail "original_root_helper_not_active"
[[ -S "$LEGACY" ]] || fail "original_management_socket_not_restored"
# Only remove our own stale socket once the old pinned helper is proven active.
if [[ -S "$IDENTITY" && ! -L "$IDENTITY" ]]; then
  rm -f -- "$IDENTITY"
fi
echo "ROOT_HELPER_IDENTITY_READONLY_ROLLBACK_VERIFIED; original root helper active"
