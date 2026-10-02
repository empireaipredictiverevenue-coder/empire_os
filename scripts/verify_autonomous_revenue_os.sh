#!/usr/bin/env bash
set -euo pipefail
cd /srv/empire_os

echo "=== AUTONOMOUS REVENUE OS GAUNTLET VERIFY ==="

PYTHONPATH=/srv/empire_os ./.venv/bin/python -m pytest -q   tests/test_engineering_gauntlet.py   tests/test_revenue_architecture_critic.py   tests/test_revenue_inventory.py   tests/test_autonomous_revenue_loop.py   tests/test_autonomous_revenue_os.py   tests/test_conversation_qualification.py   tests/test_buyer_allocation.py   tests/test_qualification_worker_v2.py   --tb=short

./.venv/bin/python -m py_compile   empire_os/engineering_gauntlet.py   empire_os/revenue_architecture_critic.py   empire_os/revenue_inventory.py   empire_os/autonomous_revenue_os.py   empire_os/execution_bus_data_repository.py

git diff --check
systemd-analyze verify deploy/systemd/empire-autonomous-revenue-os.service >/tmp/empire_revenue_systemd_verify.txt 2>&1 || {
  cat /tmp/empire_revenue_systemd_verify.txt
  exit 1
}

test ! -e deploy/systemd/empire-autonomous-revenue-os.timer

grep -q 'Senior Architect' docs/AUTONOMOUS_SYSTEM_STITCHING_ARCHITECTURE.md
grep -q 'Empire Agent Harness' docs/AUTONOMOUS_SYSTEM_STITCHING_ARCHITECTURE.md
grep -q 'Gauntlet' docs/AUTONOMOUS_SYSTEM_STITCHING_ARCHITECTURE.md
grep -q 'EMPIRE_REVENUE_RELEASE_ID=autonomous-revenue-os-v1' deploy/systemd/empire-autonomous-revenue-os.service
grep -q 'EMPIRE_REVENUE_CONTINUOUS_LEAD_GENERATION=1' deploy/systemd/empire-autonomous-revenue-os.service
grep -q 'EMPIRE_REVENUE_LOOP_INTERNAL_WRITE=1' deploy/systemd/empire-autonomous-revenue-os.service

! grep -q '"communications_execution": True' empire_os/autonomous_revenue_os.py
! grep -q '"booking_execution": True' empire_os/autonomous_revenue_os.py
! grep -q '"actual_revenue": True' empire_os/autonomous_revenue_os.py

echo "GAUNTLET_VERIFY=READY_FOR_ACTIVATION"
