#!/usr/bin/env bash
# A real public-source match preview; no acquisition writes or outreach.
set -euo pipefail
set +x
umask 077
[[ "$(id -u)" == "0" ]] || {
  echo 'SOURCE_MATCH_RESULT=BLOCKED reason=AUTHORISED_ROOT_REQUIRED' >&2
  exit 3
}
cd /srv/empire_os
exec /srv/empire_os/.venv/bin/python \
  -m scripts.run_tam_source_acquisition_connector "$@"
