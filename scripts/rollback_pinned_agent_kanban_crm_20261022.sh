#!/usr/bin/env bash
# Explicit controlled rollback: removes only this release's override.
set -Eeuo pipefail
OLD=/opt/empire-ai/crm-pilot-releases/win-plans-solar-console-20261019v1
NEW=/opt/empire-ai/crm-pilot-releases/agent-kanban-crm-20261022v1
DROP=/etc/systemd/system/empire-revenue-crm-pilot.service.d/90-agent-kanban-crm-20261022.conf
UNIT=empire-revenue-crm-pilot.service
EXPECTED_OLD=05fcd04cdd326cb4101d04de022abf0fde40e28fd4a238704c8b1cac25fb15ab

preflight() {
  test -f "$DROP" && test -d "$OLD"
  test "$(systemctl show "$UNIT" --value -p WorkingDirectory)" = "$NEW"
  printf '%s  %s\n' "$EXPECTED_OLD" "$OLD/empire_os/revenue_crm_api.py" | sha256sum --check --status
  python3 -B - "$DROP" "$NEW" <<'PY'
from pathlib import Path
import sys
drop, path = Path(sys.argv[1]), sys.argv[2]
expected = f"[Service]\nWorkingDirectory={path}\nEnvironment=PYTHONPATH={path}\n"
if drop.is_symlink() or drop.read_text(encoding="utf-8") != expected:
    raise SystemExit("override_no_longer_matches_original_release")
PY
  echo ROLLBACK_PREFLIGHT_PASS
}

if [[ "${1:---check}" == "--check" && $# -le 1 ]]; then
  preflight
  exit 0
fi
if [[ "${1:-}" != "--apply-founder-approved" || $# -ne 1 || "$EUID" -ne 0 ]]; then
  echo APPROVED_ROOT_RELEASE_OWNER_REQUIRED >&2
  exit 2
fi
preflight
rm -- "$DROP"
systemctl daemon-reload
systemctl restart "$UNIT"
test "$(systemctl show "$UNIT" --value -p WorkingDirectory)" = "$OLD"
test "$(systemctl show "$UNIT" --value -p ActiveState)" = active
test "$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 5 http://127.0.0.1:8783/health)" = 200
test "$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 5 http://127.0.0.1:8783/v1/revenue-crm/department-kanban)" = 404
echo ORIGINAL_PINNED_CRM_RELEASE_RESTORED
