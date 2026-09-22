#!/usr/bin/env bash
set -uo pipefail

ROOT="/srv/empire_os"
RUNTIME="$ROOT/runtime/crawler_72h"
mkdir -p "$RUNTIME"

START_FILE="$RUNTIME/started_epoch"
END_FILE="$RUNTIME/end_epoch"
RUN_LOG="$RUNTIME/runner.log"
CRAWLER_LOG="$RUNTIME/crawler_runs.jsonl"

START="$(date +%s)"
END="$((START + 72*60*60))"
echo "$START" > "$START_FILE"
echo "$END" > "$END_FILE"

export PYTHONPATH="$ROOT"
export PYTHONUNBUFFERED=1
export CRAWLER_LOG_PATH="$CRAWLER_LOG"
if [[ -z "${CRAWLER_TIMEOUT:-}" ]]; then
  export CRAWLER_TIMEOUT="1800"
fi

echo "[crawler-72h] started_at=$(date -Is) start_epoch=$START end_epoch=$END interval=6h timeout=$CRAWLER_TIMEOUT" | tee -a "$RUN_LOG"

RUN=0
while true; do
  NOW="$(date +%s)"
  if (( NOW >= END )); then
    break
  fi

  RUN=$((RUN + 1))
  echo "[crawler-72h] run=$RUN started_at=$(date -Is)" | tee -a "$RUN_LOG"

  set +e
  "$ROOT/.venv/bin/python" -m empire_os.crawler_runner >> "$RUN_LOG" 2>&1
  RC=$?
  set -e

  echo "[crawler-72h] run=$RUN finished_at=$(date -Is) rc=$RC" | tee -a "$RUN_LOG"

  NOW="$(date +%s)"
  REMAINING="$((END - NOW))"
  if (( REMAINING <= 0 )); then
    break
  fi

  SLEEP=21600
  if (( REMAINING < SLEEP )); then
    SLEEP="$REMAINING"
  fi
  echo "[crawler-72h] sleeping=$SLEEP seconds" | tee -a "$RUN_LOG"
  sleep "$SLEEP"
done

echo "[crawler-72h] complete_at=$(date -Is) runs=$RUN" | tee -a "$RUN_LOG"
