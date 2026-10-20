#!/usr/bin/env bash
set -euo pipefail
W=/home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020
test -f "$W/scripts/probe_consumer_optin_ephemeral_db_20261020.py"
command -v pg_virtualenv >/dev/null
exec pg_virtualenv -v 18 /bin/bash "$W/scripts/consumer_optin_ephemeral_db_fixture_20261020.sh"
