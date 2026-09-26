#!/usr/bin/env bash
set -euo pipefail

cd /srv/empire_os
exec bash scripts/deploy_continuous_buyer_lanes.sh
