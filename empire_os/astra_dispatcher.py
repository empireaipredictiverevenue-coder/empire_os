"""Bounded launch-critical Astra dispatcher.

This is deliberately narrower than full autonomous execution. Astra may run
internal data/revenue-preparation workers only. It cannot send mail directly,
accept commercial terms, move funds, verify/recognize revenue, alter authority,
or mutate infrastructure.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Any

ROOT = Path("/srv/empire_os")
LOOP = ROOT / "runtime/commercial_loop/latest.json"
SOURCE = ROOT / "runtime/source_health/latest.json"
BUYER_REVIEW = ROOT / "runtime/buyer_review_materializer/latest.json"
OUTPUT = ROOT / "runtime/astra/dispatch_latest.json"

SAFE_JOBS = {
    "buyer_deferred_enrichment": [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/run_buyer_deferred_enrichment.py"),
        "--limit",
        "5",
    ],
    "buyer_review_materializer": [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/run_buyer_review_materializer.py"),
        "--scan-limit",
        "40",
        "--proposal-limit",
        "10",
        "--max-offset",
        "500",
        "--probe-workers",
        "8",
    ],
    "gtm_pipeline": [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/run_gtm_pipeline_worker.py"),
        "--limit",
        "25",
    ],
    "closer_reply_handoff": [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/run_closer_reply_worker.py"),
        "--limit",
        "50",
    ],
    "commercial_terms_materializer": [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/run_commercial_terms_materializer.py"),
        "--scan-limit",
        "50",
        "--proposal-limit",
        "10",
    ],
    "source_health_refresh": [
        str(ROOT / "scripts/run_source_health_observer_cron.sh"),
    ],
    "conversion_intelligence_refresh": [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/run_conversion_intelligence.py"),
        "--min-sample-size",
        "20",
    ],
    "commercial_loop_refresh": [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/refresh_commercial_loop.py"),
    ],
    "revenue_pulse_refresh": [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/build_revenue_pulse_snapshot.py"),
    ],
}


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write(payload: dict[str, Any]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(OUTPUT)


def choose_jobs(
    loop: dict[str, Any],
    source: dict[str, Any],
    buyer_review: dict[str, Any] | None = None,
) -> list[str]:
    jobs: list[str] = []
    if source.get("end_to_end_healthy") is not True:
        jobs.append("source_health_refresh")

    if loop.get("loop_complete") is not True:
        review_state = buyer_review or {}
        if int(review_state.get("deferred_enrichment") or 0) > 0:
            jobs.append("buyer_deferred_enrichment")
        stages = {
            str(row.get("stage") or ""): row.get("observed")
            for row in (loop.get("stages") or [])
            if isinstance(row, dict)
        }
        if stages.get("recognized_revenue") is not True:
            jobs.append("buyer_review_materializer")
        if stages.get("buyer_conversation") is not True:
            jobs.append("gtm_pipeline")
        if stages.get("commercial_terms") is not True:
            jobs.append("closer_reply_handoff")
            jobs.append("commercial_terms_materializer")
        jobs.append("conversion_intelligence_refresh")
        jobs.append("commercial_loop_refresh")
        jobs.append("revenue_pulse_refresh")
    return list(dict.fromkeys(jobs))


def dispatch(
    *,
    mode: str | None = None,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    current_mode = (
        mode
        or os.getenv("EMPIRE_ASTRA_DISPATCH_MODE", "OBSERVE")
    ).strip().upper()
    loop = _read(LOOP)
    source = _read(SOURCE)
    buyer_review = _read(BUYER_REVIEW)
    selected = choose_jobs(loop, source, buyer_review)
    executed: list[dict[str, Any]] = []

    for job in selected:
        if current_mode != "GUARDED_EXECUTE":
            executed.append({
                "job": job,
                "decision": "WOULD_DISPATCH",
                "returncode": None,
            })
            continue

        command = SAFE_JOBS[job]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=max(10, min(int(timeout_seconds), 300)),
            env=os.environ.copy(),
        )
        executed.append({
            "job": job,
            "decision": "DISPATCHED",
            "returncode": completed.returncode,
            "stdout_tail": (completed.stdout or "")[-1200:],
            "stderr_tail": (completed.stderr or "")[-800:],
        })

    payload = {
        "schema_version": "astra_dispatch.v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "mode": current_mode,
        "scope": "internal_launch_pipeline_only",
        "selected_jobs": selected,
        "executions": executed,
        "prohibited": [
            "raw_provider_send_bypassing_outbound_governor",
            "commercial_terms_acceptance",
            "fund_movement",
            "payment_confirmation",
            "revenue_recognition",
            "authority_expansion",
            "destructive_infrastructure",
        ],
    }
    _write(payload)
    return payload
