#!/usr/bin/env python3
"""Summarize the bounded EmpireOS 72-hour canonical crawler trial."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

ROOT = Path("/srv/empire_os/runtime/crawler_72h")
LOG = ROOT / "crawler_runs.jsonl"


def main() -> int:
    counters = Counter()
    sources = Counter()
    errors = Counter()
    created_ids: set[str] = set()
    matched_ids: set[str] = set()
    signal_ids: set[str] = set()

    if not LOG.exists():
        print(json.dumps({
            "ok": False,
            "reason": "crawler_72h_log_missing",
            "path": str(LOG),
        }, indent=2))
        return 1

    rows = 0
    for raw in LOG.read_text(errors="ignore").splitlines():
        try:
            event = json.loads(raw)
        except Exception:
            counters["invalid_json_lines"] += 1
            continue

        rows += 1
        msg = str(event.get("msg") or "")
        source = str(event.get("source") or "")
        if source:
            sources[source] += 1

        if msg == "crawler_run_start":
            counters["runs_started"] += 1
        elif msg == "crawler_run_done":
            counters["runs_completed"] += 1
        elif msg == "source_run_done":
            counters["source_runs_completed"] += 1
            counters["candidates"] += int(event.get("candidates") or 0)
            counters["accepted"] += int(event.get("accepted") or 0)
            source_errors = int(event.get("errors") or 0)
            counters["errors"] += source_errors
            if source_errors:
                counters["sources_err"] += 1
            else:
                counters["sources_ok"] += 1
        elif msg == "prospect_acquired":
            counters["prospects_created_events"] += 1
            pid = str(event.get("prospect_id") or "")
            if pid:
                created_ids.add(pid)
        elif msg == "prospect_matched":
            counters["prospects_matched_events"] += 1
            pid = str(event.get("prospect_id") or "")
            if pid:
                matched_ids.add(pid)
        elif msg == "signal_queued":
            counters["signals_queued_events"] += 1
            sid = str(event.get("signal_id") or "")
            if sid:
                signal_ids.add(sid)
        elif msg == "candidate_quality_rejected":
            counters["quality_rejections"] += 1
        elif msg == "canonical_identity_ambiguous":
            counters["identity_ambiguous"] += 1
        elif msg == "canonical_ingest_failed":
            counters["canonical_ingest_failed"] += 1
            errors[str(event.get("error") or "unknown")[:120]] += 1
        elif msg == "source_crashed":
            counters["source_crashed"] += 1
            errors[
                f"{source}:{str(event.get('error') or 'unknown')[:100]}"
            ] += 1
        elif msg == "missing_required_env":
            counters["source_missing_env"] += 1
        elif msg == "source_not_real":
            counters["non_real_source_skipped"] += 1

    payload = {
        "schema_version": "empire.crawler_72h_report.v1",
        "ok": True,
        "log_lines": rows,
        "runs_started": counters["runs_started"],
        "runs_completed": counters["runs_completed"],
        "source_runs_completed": counters["source_runs_completed"],
        "candidates_seen": counters["candidates"],
        "accepted_total": counters["accepted"],
        "unique_prospects_created": len(created_ids),
        "unique_prospects_matched": len(matched_ids),
        "unique_signals_queued": len(signal_ids),
        "quality_rejections": counters["quality_rejections"],
        "identity_ambiguous": counters["identity_ambiguous"],
        "canonical_ingest_failed": counters["canonical_ingest_failed"],
        "source_crashed": counters["source_crashed"],
        "sources_ok_total": counters["sources_ok"],
        "sources_err_total": counters["sources_err"],
        "source_event_counts": dict(sources.most_common()),
        "top_errors": dict(errors.most_common(10)),
        "outreach_sent": False,
        "live_calls_placed": False,
        "payment_actions": False,
        "production_mock_data_enabled": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
