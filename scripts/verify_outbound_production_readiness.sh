#!/usr/bin/env bash
set -euo pipefail

cd /srv/empire_os

echo "========================================================"
echo " EMPIRE OUTBOUND — READ-ONLY PRODUCTION READINESS DOCTOR"
echo " NO MIGRATION / NO ROLE CHANGE / NO SERVICE CHANGE / NO SEND"
echo "========================================================"
echo

# Canonical readiness logic lives in the Python doctor. This wrapper performs
# no mutation and deliberately does not start/enable services, apply migrations,
# change roles, touch DNS, provision infrastructure, approve, claim or send.
exec ./.venv/bin/python -m empire_os.outbound_production_doctor
