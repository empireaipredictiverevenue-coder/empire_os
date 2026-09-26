"""Evidence-only summary for the temporary 24-hour acquisition benchmark."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            result = datetime.strptime(text, "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def build_soak_summary(
    *,
    crawler_log: Path,
    signal_inbox: Path,
    expiry_epoch: int,
) -> dict[str, Any]:
    expiry = datetime.fromtimestamp(int(expiry_epoch), tz=timezone.utc)
    start = datetime.fromtimestamp(int(expiry_epoch) - 86400, tz=timezone.utc)

    runs = 0
    candidates = 0
    accepted = 0
    errors = 0
    canonical_events: list[dict[str, Any]] = []
    signal_events: list[dict[str, Any]] = []
    source_runs: Counter[str] = Counter()
    source_accepted: Counter[str] = Counter()
    metro_runs: Counter[str] = Counter()
    current_start: dict[str, Any] | None = None

    try:
        lines = crawler_log.read_text(
            encoding="utf-8",
            errors="ignore",
        ).splitlines()
    except OSError:
        lines = []

    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        observed = _parse_time(item.get("ts"))
        if observed is None or observed < start or observed > expiry:
            continue

        msg = str(item.get("msg") or "")
        if msg == "crawler_run_start":
            current_start = item
        elif msg == "crawler_run_done":
            runs += 1
            run_candidates = int(item.get("candidates") or 0)
            run_accepted = int(item.get("accepted") or 0)
            candidates += run_candidates
            accepted += run_accepted
            errors += int(item.get("errors") or 0)
            if current_start:
                source = str(
                    current_start.get("source") or "unknown"
                )
                metro = str(
                    current_start.get("metro") or "unscoped"
                )
                source_runs[source] += 1
                source_accepted[source] += run_accepted
                metro_runs[metro] += 1
            current_start = None
        elif msg == "prospect_acquired":
            canonical_events.append(item)
        elif msg == "signal_queued":
            signal_events.append(item)

    unique_prospect_ids = {
        str(item.get("prospect_id"))
        for item in canonical_events
        if item.get("prospect_id")
    }
    unique_signal_ids = {
        str(item.get("signal_id"))
        for item in signal_events
        if item.get("signal_id")
    }

    signal_statuses: Counter[str] = Counter()
    signal_sources: Counter[str] = Counter()
    try:
        inbox = json.loads(signal_inbox.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        inbox = {}
    if isinstance(inbox, dict):
        for row in inbox.values():
            if not isinstance(row, dict):
                continue
            created = _parse_time(row.get("created_at"))
            if created is None or created < start or created > expiry:
                continue
            signal_statuses[
                str(row.get("status") or "unknown")
            ] += 1
            signal_sources[
                str(row.get("source") or "unknown")
            ] += 1

    return {
        "schema_version": "empire.acquisition-soak-summary.v1",
        "window_start": start.isoformat(),
        "window_end": expiry.isoformat(),
        "country_scope": ["US"],
        "real_data_only": True,
        "canonical_store": "supabase",
        "crawler_runs_completed": runs,
        "crawler_candidates_seen": candidates,
        "accepted_event_total": accepted,
        "crawler_errors": errors,
        "unique_canonical_prospects_observed": len(
            unique_prospect_ids
        ),
        "canonical_prospect_events": len(canonical_events),
        "unique_signals_observed": len(unique_signal_ids),
        "signal_events": len(signal_events),
        "source_runs": dict(source_runs),
        "source_accepted": dict(source_accepted),
        "metro_runs": dict(metro_runs),
        "signal_statuses_at_summary": dict(signal_statuses),
        "signal_sources_at_summary": dict(signal_sources),
        "actual_revenue": False,
        "outreach_execution": False,
        "payment_execution": False,
    }


def write_soak_summary(
    output: Path,
    *,
    crawler_log: Path,
    signal_inbox: Path,
    expiry_epoch: int,
) -> dict[str, Any]:
    payload = build_soak_summary(
        crawler_log=crawler_log,
        signal_inbox=signal_inbox,
        expiry_epoch=expiry_epoch,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(output)
    return payload
