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
    "commercial_product_catalog_refresh": [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/refresh_commercial_product_catalog.py"),
        "--limit",
        "100",
    ],
    "commercial_evidence_auto_verifier": [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/run_commercial_evidence_auto_verifier.py"),
        "--limit",
        "25",
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
    "opportunity_loop_refresh": [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/run_opportunity_loop.py"),
    ],
    "astra_executive_refresh": [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/build_astra_executive.py"),
    ],
    "astra_department_dispatch": [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/dispatch_astra_departments.py"),
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
    """Choose only work Astra uniquely owns.

    Recurring production workers with dedicated systemd timers must not also be
    relaunched by Astra. Duplicating them here multiplies canonical REST reads,
    burns Supabase egress and can create retry storms without adding commercial
    value.
    """
    jobs: list[str] = []

    # Dedicated timers own source health, buyer review materialization, GTM,
    # closer replies, catalog refresh, commercial evidence verification,
    # revenue pulse and opportunity loop. Astra observes their artifacts rather
    # than scheduling a second copy of those workers.
    if loop.get("loop_complete") is not True:
        stages = {
            str(row.get("stage") or ""): row.get("observed")
            for row in (loop.get("stages") or [])
            if isinstance(row, dict)
        }
        if stages.get("commercial_terms") is not True:
            jobs.append("commercial_terms_materializer")
        jobs.append("conversion_intelligence_refresh")
        jobs.append("commercial_loop_refresh")

    # Executive synthesis and department dispatch remain Astra-owned.
    jobs.append("astra_executive_refresh")
    jobs.append("astra_department_dispatch")
    return list(dict.fromkeys(jobs))

def dispatch(
    *,
    mode: str | None = None,
    timeout_seconds: int | None = None,
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
        job_timeout = (
            int(timeout_seconds)
            if timeout_seconds is not None
            else 120
        )
        try:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(10, min(job_timeout, 300)),
                env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired as exc:
            executed.append({
                "job": job,
                "decision": "TIMED_OUT",
                "returncode": 124,
                "stdout_tail": (
                    (exc.stdout.decode(errors="ignore") if isinstance(exc.stdout, bytes) else exc.stdout)
                    or ""
                )[-1200:],
                "stderr_tail": (
                    (exc.stderr.decode(errors="ignore") if isinstance(exc.stderr, bytes) else exc.stderr)
                    or ""
                )[-800:],
            })
            continue
        except OSError as exc:
            executed.append({
                "job": job,
                "decision": "EXECUTION_ERROR",
                "returncode": 127,
                "stdout_tail": "",
                "stderr_tail": str(exc)[:800],
            })
            continue
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
