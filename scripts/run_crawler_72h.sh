#!/usr/bin/env bash
set -uo pipefail

ROOT="/srv/empire_os"
RUNTIME="$ROOT/runtime/crawler_72h"
mkdir -p "$RUNTIME"

START_FILE="$RUNTIME/started_epoch"
END_FILE="$RUNTIME/end_epoch"
RUN_LOG="$RUNTIME/runner.log"
CRAWLER_LOG="$RUNTIME/crawler_runs.jsonl"

# Fresh bounded trial: never mix prior run evidence into this report.
: > "$RUN_LOG"
: > "$CRAWLER_LOG"

START="$(date +%s)"
END="$((START + 72*60*60))"
echo "$START" > "$START_FILE"
echo "$END" > "$END_FILE"

export PYTHONPATH="$ROOT"
export PYTHONUNBUFFERED=1
export CRAWLER_LOG_PATH="$CRAWLER_LOG"

# Each source gets its own fail-closed runtime and evidence budget. A noisy
# source such as NYC permits must never starve the rest of the sensor mesh.
SOURCE_TIMEOUT="${CRAWLER_SOURCE_TIMEOUT:-300}"
SOURCE_CAP="${CRAWLER_SOURCE_MAX_CANDIDATES:-250}"
INTERVAL="${CRAWLER_INTERVAL_SECONDS:-21600}"

SOURCES=(
  permits
  chicago_311
  courtlistener
  reddit
  nyc_hpd
  nws_alerts
  overpass
  biz_search
)

echo "[crawler-72h] started_at=$(date -Is) start_epoch=$START end_epoch=$END interval=${INTERVAL}s source_timeout=${SOURCE_TIMEOUT}s source_cap=$SOURCE_CAP" | tee -a "$RUN_LOG"

CYCLE=0
while true; do
  NOW="$(date +%s)"
  if (( NOW >= END )); then
    break
  fi

  CYCLE=$((CYCLE + 1))
  echo "[crawler-72h] cycle=$CYCLE started_at=$(date -Is)" | tee -a "$RUN_LOG"

  for SOURCE in "${SOURCES[@]}"; do
    NOW="$(date +%s)"
    if (( NOW >= END )); then
      break 2
    fi

    echo "[crawler-72h] cycle=$CYCLE source=$SOURCE started_at=$(date -Is)" | tee -a "$RUN_LOG"

    set +e
    timeout --signal=TERM --kill-after=15s "${SOURCE_TIMEOUT}s" \
      "$ROOT/.venv/bin/python" -m empire_os.crawler_runner \
      --source "$SOURCE" \
      --max-candidates "$SOURCE_CAP" \
      >> "$RUN_LOG" 2>&1
    RC=$?
    set -e

    echo "[crawler-72h] cycle=$CYCLE source=$SOURCE finished_at=$(date -Is) rc=$RC" | tee -a "$RUN_LOG"
  done

  echo "[crawler-72h] cycle=$CYCLE complete_at=$(date -Is)" | tee -a "$RUN_LOG"

  NOW="$(date +%s)"
  REMAINING="$((END - NOW))"
  if (( REMAINING <= 0 )); then
    break
  fi

  SLEEP="$INTERVAL"
  if (( REMAINING < SLEEP )); then
    SLEEP="$REMAINING"
  fi
  echo "[crawler-72h] sleeping=$SLEEP seconds" | tee -a "$RUN_LOG"
  sleep "$SLEEP"
done

echo "[crawler-72h] complete_at=$(date -Is) cycles=$CYCLE" | tee -a "$RUN_LOG"
