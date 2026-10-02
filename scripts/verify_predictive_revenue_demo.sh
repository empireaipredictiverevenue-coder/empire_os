#!/usr/bin/env bash
set -euo pipefail
cd /srv/empire_os

echo "=== PREDICTIVE REVENUE LIVE DEMO GAUNTLET ==="

PYTHONPATH=/srv/empire_os ./.venv/bin/python -m pytest -q   tests/test_predictive_revenue_demo.py   tests/test_founder_dashboard_service_routes.py   --tb=short

./.venv/bin/python -m py_compile   empire_os/predictive_revenue_demo.py   empire_os/predictive_revenue_demo_api.py   empire_os/founder_dashboard_service.py

git diff --check

grep -q '"/demo"' empire_os/predictive_revenue_demo_api.py
grep -q '"/demo/live"' empire_os/predictive_revenue_demo_api.py
grep -q '"LIVE_READ_ONLY"' empire_os/predictive_revenue_demo.py
grep -q '"predicted_is_not_actual_revenue": True' empire_os/predictive_revenue_demo.py
grep -q '"execution_authority": "none"' empire_os/predictive_revenue_demo.py
grep -q 'D\*Q\*E\*OMEGA\*B\*O\*C\*T\*P\*F\*LTV' empire_os/predictive_revenue_demo.py
grep -q 'private_deployment_economics' empire_os/predictive_revenue_demo.py

echo "GAUNTLET_VERIFY=READY_FOR_LIVE_DEMO"
