#!/usr/bin/env bash
# Existing EmpireOS CRM service, exactly two-file reviewed release.
# No args or --check is always read-only. The protected switch is explicit.
set -Eeuo pipefail

OLD=/opt/empire-ai/crm-pilot-releases/win-plans-solar-console-20261019v1
CAND=/home/ubuntu/empire_releases/agent_kanban_crm_pilot_candidate_20261022
NEW=/opt/empire-ai/crm-pilot-releases/agent-kanban-crm-20261022v1
DROP=/etc/systemd/system/empire-revenue-crm-pilot.service.d/90-agent-kanban-crm-20261022.conf
UNIT=empire-revenue-crm-pilot.service
EXPECTED_OLD=05fcd04cdd326cb4101d04de022abf0fde40e28fd4a238704c8b1cac25fb15ab
EXPECTED_NEW=34ecda4b2c2b86540daa9c4d74c420b8d67add94267308d721d2e405c6b21a15
STEP=preflight
DROP_CREATED=0

die() { echo "RELEASE_HOLD: $*" >&2; exit 1; }
code() {
  curl --silent --output /dev/null --write-out '%{http_code}' --max-time 2 \
    "http://127.0.0.1:8783$1" || true
}
ready() {
  local expected="$1" actual=000 index
  # Uvicorn can be active in systemd before its HTTP bind/startup completes.
  for ((index=0; index<40; index++)); do
    if [[ "$(systemctl show "$UNIT" --value -p ActiveState)" == active ]]; then
      actual="$(code /health)"
      if [[ "$actual" == 200 ]]; then
        actual="$(code /v1/revenue-crm/department-kanban)"
        if [[ "$actual" == "$expected" ]]; then return 0; fi
      fi
    fi
    sleep 0.5
  done
  echo "RELEASE_HTTP_NOT_READY expected=$expected last_status=$actual" >&2
  return 1
}
validate_release_inventory() {
  python3 -B - "$OLD" "$CAND" "$NEW" <<'PY'
import hashlib
import os
import pathlib
import stat
import sys

old, cand, staged = map(pathlib.Path, sys.argv[1:])
def files(path):
    inventory = {}
    for file in path.rglob("*"):
        if file.is_symlink():
            raise SystemExit("release_symlink_forbidden")
        if file.is_file():
            inventory[str(file.relative_to(path))] = hashlib.sha256(file.read_bytes()).digest()
    return inventory

baseline = files(old)
candidate = files(cand)
changed = {key for key in baseline.keys() & candidate if baseline[key] != candidate[key]}
added, removed = candidate.keys() - baseline.keys(), baseline.keys() - candidate.keys()
if (changed != {"empire_os/revenue_crm_api.py"}
        or added != {"empire_os/department_collaboration.py"} or removed):
    raise SystemExit("reviewed_two_file_delta_mismatch")
if staged.exists():
    if staged.is_symlink() or not staged.is_dir():
        raise SystemExit("invalid_existing_release_directory")
    if files(staged) != candidate:
        raise SystemExit("previously_staged_release_changed_or_incomplete")
    for target in (staged, staged / "empire_os/revenue_crm_api.py"):
        metadata = target.stat()
        if metadata.st_uid != 0 or metadata.st_mode & 0o022:
            raise SystemExit("staged_release_not_root_owned_immutable")
    print("EXISTING_PROTECTED_STAGE_VERIFIED")
else:
    print("NEW_PROTECTED_STAGE_REQUIRED")
print("PINNED_TWO_FILE_DELTA_VERIFIED")
PY
}
preflight() {
  [[ -d "$OLD" && -d "$CAND" ]] || die "source_release_missing"
  [[ ! -e "$DROP" && ! -L "$DROP" ]] || die "existing_release_override_needs_owner_review"
  [[ "$(systemctl show "$UNIT" --value -p WorkingDirectory)" == "$OLD" ]] \
    || die "current_service_no_longer_on_original_release"
  [[ "$(systemctl show "$UNIT" --value -p ActiveState)" == active ]] \
    || die "original_crm_service_not_active"
  printf '%s  %s\n' "$EXPECTED_OLD" "$OLD/empire_os/revenue_crm_api.py" \
    | sha256sum --check --status || die "original_file_hash_changed"
  printf '%s  %s\n' "$EXPECTED_NEW" "$CAND/empire_os/revenue_crm_api.py" \
    | sha256sum --check --status || die "candidate_file_hash_changed"
  validate_release_inventory || die "release_inventory_not_verified"
  [[ "$(code /health)" == 200 ]] || die "original_crm_unhealthy"
  [[ "$(code /v1/revenue-crm/department-kanban)" == 404 ]] \
    || die "unexpected_current_kanban_route"
  echo "DRY_RUN_PINNED_KANBAN_PREFLIGHT_PASS; original CRM unchanged"
}

# An ERR trap must exit after a failed deployment. The original handler
# returned, causing repeated rollback notices without identifying a stage.
rollback_on_error() {
  local original_rc="$1" line="$2" step="$3"
  trap - ERR
  set +e
  echo "DEPLOYMENT_FAILED step=$step line=$line exit_status=$original_rc" >&2
  if [[ "$DROP_CREATED" -eq 1 ]]; then
    local expected
    expected="$(printf '[Service]\nWorkingDirectory=%s\nEnvironment=PYTHONPATH=%s' "$NEW" "$NEW")"
    local existing
    existing="$(cat "$DROP" 2>/dev/null)"
    if [[ "$existing" == "$expected" ]]; then
      rm -f -- "$DROP"
      systemctl daemon-reload
      systemctl restart "$UNIT"
      if ready 404; then
        echo "ROLLED_BACK_TO_PRIOR_PINNED_RELEASE; health=200 kanban=404" >&2
      else
        echo "ROLLBACK_SERVICE_REQUIRES_MANUAL_INSPECTION" >&2
      fi
    else
      echo "OVERRIDE_CHANGED_EXTERNALLY; NO_UNSAFE_AUTOMATIC_RESTORE" >&2
    fi
  else
    echo "RELEASE_SWITCH_NOT_APPLIED; original service retained" >&2
  fi
  exit "$original_rc"
}

if [[ "${1:---check}" == "--check" && $# -le 1 ]]; then
  preflight
  exit 0
fi
[[ "${1:-}" == "--apply-founder-approved" && $# -eq 1 ]] \
  || die "explicit_approved_mode_required"
[[ "$EUID" -eq 0 ]] || die "approved_root_release_owner_required"
preflight
trap 'rollback_on_error "$?" "$LINENO" "$STEP"' ERR

STEP=stage
if [[ ! -d "$NEW" ]]; then
  cp -a -- "$CAND" "$NEW"
  chown -R root:root -- "$NEW"
  chmod -R go-w -- "$NEW"
fi
validate_release_inventory
printf '%s  %s\n' "$EXPECTED_NEW" "$NEW/empire_os/revenue_crm_api.py" \
  | sha256sum --check --status

STEP=override
[[ ! -e "$DROP" && ! -L "$DROP" ]] || die "another_override_appeared"
# Write the unique override, without editing other owners' existing files.
printf '[Service]\nWorkingDirectory=%s\nEnvironment=PYTHONPATH=%s\n' \
  "$NEW" "$NEW" > "$DROP"
DROP_CREATED=1
chmod 0644 "$DROP"

STEP=restart
systemctl daemon-reload
systemctl restart "$UNIT"
[[ "$(systemctl show "$UNIT" --value -p WorkingDirectory)" == "$NEW" ]]

STEP=http_readiness
ready 401
trap - ERR
echo "PINNED_KANBAN_BACKEND_ACTIVATED_AUTHENTICATED_READ_ONLY"
echo "REMAINING: founder-token 200 and real tenant-isolation canary"
