#!/usr/bin/env bash
# Guarded existing-service release switch. Never run from an agent chat.
# Invoking with no arguments performs read-only preflight only.
set -Eeuo pipefail
OLD=/opt/empire-ai/crm-pilot-releases/win-plans-solar-console-20261019v1
CAND=/home/ubuntu/empire_releases/agent_kanban_crm_pilot_candidate_20261022
NEW=/opt/empire-ai/crm-pilot-releases/agent-kanban-crm-20261022v1
DROP=/etc/systemd/system/empire-revenue-crm-pilot.service.d/90-agent-kanban-crm-20261022.conf
UNIT=empire-revenue-crm-pilot.service
EXPECTED_OLD=05fcd04cdd326cb4101d04de022abf0fde40e28fd4a238704c8b1cac25fb15ab
EXPECTED_NEW=34ecda4b2c2b86540daa9c4d74c420b8d67add94267308d721d2e405c6b21a15

preflight() {
  test -d "$OLD" && test -d "$CAND"
  test ! -e "$NEW" && test ! -e "$DROP"
  test "$(systemctl show "$UNIT" --value -p WorkingDirectory)" = "$OLD"
  test "$(systemctl show "$UNIT" --value -p ActiveState)" = active
  printf '%s  %s\n' "$EXPECTED_OLD" "$OLD/empire_os/revenue_crm_api.py" | sha256sum --check --status
  printf '%s  %s\n' "$EXPECTED_NEW" "$CAND/empire_os/revenue_crm_api.py" | sha256sum --check --status
  python3 -B - "$OLD" "$CAND" <<'PY'
import hashlib
import pathlib
import sys
old, new = map(pathlib.Path, sys.argv[1:])
def files(directory):
    found = {}
    for file in directory.rglob("*"):
        if file.is_symlink():
            raise SystemExit("release_symlink_forbidden")
        if file.is_file():
            found[str(file.relative_to(directory))] = hashlib.sha256(file.read_bytes()).digest()
    return found
before, after = files(old), files(new)
changed = {name for name in before.keys() & after.keys() if before[name] != after[name]}
added = after.keys() - before.keys()
removed = before.keys() - after.keys()
if (changed != {"empire_os/revenue_crm_api.py"}
        or added != {"empire_os/department_collaboration.py"}
        or removed):
    raise SystemExit("release_delta_not_exactly_reviewed_two_files")
print("PINNED_TWO_FILE_DELTA_VERIFIED")
PY
  test "$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 4 http://127.0.0.1:8783/health)" = 200
  test "$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 4 http://127.0.0.1:8783/v1/revenue-crm/department-kanban)" = 404
  echo "DRY_RUN_PINNED_KANBAN_PREFLIGHT_PASS; service unchanged"
}

if [[ "${1:-}" == "--check" || $# -eq 0 ]]; then
  preflight
  exit 0
fi
if [[ "$1" != "--apply-founder-approved" || $# -ne 1 ]]; then
  echo "UNRECOGNISED_DEPLOYMENT_AUTHORITY" >&2
  exit 2
fi
if [[ "${EUID}" -ne 0 ]]; then
  echo "APPROVED_RELEASE_REQUIRES_EXISTING_ROOT_RELEASE_OWNER" >&2
  exit 3
fi
preflight
rollback() {
  trap - ERR
  if [[ -e "$DROP" ]]; then
    rm -f -- "$DROP"
    systemctl daemon-reload
    systemctl restart "$UNIT"
  fi
  echo "ROLLED_BACK_TO_PRIOR_PINNED_RELEASE" >&2
}
trap rollback ERR

cp -a -- "$CAND" "$NEW"
chown -R root:root "$NEW"
chmod -R go-w "$NEW"
test -f "$NEW/empire_os/department_collaboration.py"
printf '%s  %s\n' "$EXPECTED_NEW" "$NEW/empire_os/revenue_crm_api.py" | sha256sum --check --status
# A later override must not silently redirect this application.
cat >"$DROP" <<EOF
[Service]
WorkingDirectory=$NEW
Environment=PYTHONPATH=$NEW
EOF
chmod 0644 "$DROP"
systemctl daemon-reload
systemctl restart "$UNIT"
test "$(systemctl show "$UNIT" --value -p WorkingDirectory)" = "$NEW"
test "$(systemctl show "$UNIT" --value -p ActiveState)" = active
test "$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 5 http://127.0.0.1:8783/health)" = 200
test "$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 5 http://127.0.0.1:8783/v1/revenue-crm/department-kanban)" = 401
trap - ERR
echo "PINNED_KANBAN_BACKEND_ACTIVATED_AUTHENTICATED_READ_ONLY"
echo "STILL_REQUIRED: real existing founder-token 200 and tenant-isolation canary"
