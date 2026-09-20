#!/usr/bin/env python3
"""
Empire OS — Autonomous Execution Bus v1.

Purpose
-------
Turns gtm_jobs into a governed autonomous execution loop.

Default mode is SAFE / OBSERVE:
    - may inspect the queue
    - does NOT execute real worker side effects
    - does NOT launch crawlers
    - does NOT send outreach
    - does NOT create invoices
    - does NOT trigger fulfilment

LIVE mode must be explicitly enabled:
    EMPIRE_EXECUTION_MODE=live

Architecture
------------
claim -> lease -> execute -> heartbeat -> commercial event -> complete
                                  |
                                  +-> failure -> retry -> quarantine

The bus is deliberately independent of the legacy supervisors.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from empire_os.buyer_allocation import (
    BuyerAllocationError,
    allocate_owned_prospect,
    buyer_activation_decision,
)
from empire_os.niche_taxonomy import (
    NICHE_FAMILIES,
    metro_key,
    niche_family,
    normalise,
)
from empire_os.runtime_env import load_runtime_env


ENV_PATH = os.environ.get(
    "EMPIRE_ENV_PATH",
    "/etc/empire_os.env",
)

RUNTIME_ROOT = Path(
    os.environ.get(
        "EMPIRE_RUNTIME_ROOT",
        "/srv/empire_os/runtime",
    )
)

LOG_DIR = RUNTIME_ROOT / "autonomous"
LOG_PATH = LOG_DIR / "execution_bus.jsonl"

DEFAULT_LEASE_SECONDS = int(
    os.environ.get("EMPIRE_JOB_LEASE_SECONDS", "300")
)

DEFAULT_HEARTBEAT_SECONDS = int(
    os.environ.get("EMPIRE_JOB_HEARTBEAT_SECONDS", "60")
)

IDLE_SLEEP_SECONDS = int(
    os.environ.get("EMPIRE_JOB_IDLE_SLEEP_SECONDS", "15")
)

MAX_JOBS_PER_CYCLE = int(
    os.environ.get("EMPIRE_MAX_JOBS_PER_CYCLE", "10")
)

# Hard production safety ceiling for one market-level
# qualification parent job.
MAX_QUALIFICATION_BATCH_SIZE = 5

# Hard ceiling for one market-level Phase 3D allocation materializer.
MAX_ALLOCATION_BATCH_SIZE = 5
ALLOCATION_SCAN_MULTIPLIER = 10

# Canonical buyer reads for capacity gating are paginated so the
# execution decision never silently truncates a growing buyer fleet.
CAPACITY_BUYER_PAGE_SIZE = 1000

EXECUTION_MODE = os.environ.get(
    "EMPIRE_EXECUTION_MODE",
    "observe",
).strip().lower()

WORKER_ID = os.environ.get(
    "EMPIRE_WORKER_ID",
    f"{socket.gethostname()}:{os.getpid()}",
)


@dataclass(frozen=True)
class ClaimedJob:
    id: str
    opportunity_id: str
    job_type: str
    worker_adapter: str
    priority: float
    payload: dict[str, Any]
    lease_token: str
    attempts: int
    max_attempts: int


class BusError(RuntimeError):
    pass


def load_env() -> dict[str, str]:
    return load_runtime_env(
        ENV_PATH,
        required=("SUPABASE_URL", "SUPABASE_SERVICE_KEY"),
    )


ENV = load_env()

SUPABASE_URL = ENV["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = ENV["SUPABASE_SERVICE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(level: str, event: str, **fields: Any) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    record = {
        "ts": utc_now(),
        "level": level,
        "event": event,
        "worker_id": WORKER_ID,
        "execution_mode": EXECUTION_MODE,
        **fields,
    }

    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")

    print(json.dumps(record, default=str), flush=True)


def rpc(
    function_name: str,
    payload: dict[str, Any],
) -> Any:
    query = urllib.parse.quote(
        f"/rest/v1/rpc/{function_name}",
        safe="/",
    )

    req = urllib.request.Request(
        f"{SUPABASE_URL}{query}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=HEADERS,
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise BusError(
            f"RPC {function_name} failed HTTP {exc.code}: "
            f"{body[:1000]}"
        ) from exc


def insert_event(
    *,
    event_type: str,
    job: ClaimedJob | None = None,
    payload: dict[str, Any] | None = None,
    actor: str = "autonomous_execution_bus",
    idempotency_key: str | None = None,
) -> None:
    if idempotency_key is None:
        if job is not None:
            idempotency_key = (
                f"job:{job.id}:{event_type}:"
                f"{job.attempts}"
            )
        else:
            idempotency_key = (
                f"event:{actor}:{event_type}:{utc_now()}"
            )

    body = {
        "event_type": event_type,
        "job_id": job.id if job else None,
        "channel": "autonomous_bus",
        "actor": actor,
        "payload": payload or {},
        "idempotency_key": idempotency_key,
        "occurred_at": utc_now(),
    }

    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/commercial_events",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            **HEADERS,
            "Prefer": (
                "resolution=ignore-duplicates,"
                "return=minimal"
            ),
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30):
            pass
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise BusError(
            f"commercial event insert failed HTTP {exc.code}: "
            f"{body_text[:1000]}"
        ) from exc


def claim_next_job() -> ClaimedJob | None:
    result = rpc(
        "claim_next_gtm_job",
        {
            "p_worker_id": WORKER_ID,
            "p_lease_seconds": DEFAULT_LEASE_SECONDS,
        },
    )

    if not result:
        return None

    row = (
        result[0]
        if isinstance(result, list)
        else result
    )

    if not isinstance(row, dict):
        raise BusError(
            f"unexpected claim response: {type(row).__name__}"
        )

    lease_token = str(row.get("lease_token") or "")

    if not lease_token:
        raise BusError(
            "claim returned job without lease_token"
        )

    opportunity_id = str(
        row.get("opportunity_id") or ""
    )

    if not opportunity_id:
        raise BusError(
            "claim returned job without opportunity_id"
        )

    opportunity_id = str(row.get("opportunity_id") or "")
    if not opportunity_id:
        raise BusError("claim returned job without opportunity_id")

    return ClaimedJob(
        id=str(row["id"]),
        opportunity_id=opportunity_id,
        job_type=str(row["job_type"]),
        worker_adapter=str(row["worker_adapter"]),
        priority=float(row.get("priority") or 0),
        payload=row.get("payload") or {},
        lease_token=lease_token,
        attempts=int(row.get("attempts") or 0),
        max_attempts=int(row.get("max_attempts") or 5),
    )


def heartbeat(job: ClaimedJob) -> bool:
    result = rpc(
        "heartbeat_gtm_job",
        {
            "p_job_id": job.id,
            "p_worker_id": WORKER_ID,
            "p_lease_token": job.lease_token,
            "p_lease_seconds": DEFAULT_LEASE_SECONDS,
        },
    )

    return bool(result)


def complete(
    job: ClaimedJob,
    result: dict[str, Any],
) -> bool:
    completed = rpc(
        "complete_gtm_job",
        {
            "p_job_id": job.id,
            "p_worker_id": WORKER_ID,
            "p_lease_token": job.lease_token,
            "p_result": result,
        },
    )

    return bool(completed)


def fail(
    job: ClaimedJob,
    error: str,
    *,
    retry_delay_seconds: int = 60,
    result: dict[str, Any] | None = None,
) -> str:
    return str(
        rpc(
            "fail_gtm_job",
            {
                "p_job_id": job.id,
                "p_worker_id": WORKER_ID,
                "p_lease_token": job.lease_token,
                "p_error": error[:4000],
                "p_retry_delay_seconds": max(
                    retry_delay_seconds,
                    5,
                ),
                "p_result": result or {},
            },
        )
    )


# ---------------------------------------------------------------------------
# Worker adapters
# ---------------------------------------------------------------------------

Adapter = Callable[[ClaimedJob], dict[str, Any]]


def execute_observe(job: ClaimedJob) -> dict[str, Any]:
    """
    Safe mode.

    Records what WOULD happen without invoking a side-effecting worker.
    """

    return {
        "ok": True,
        "mode": "observe",
        "executed": False,
        "job_type": job.job_type,
        "worker_adapter": job.worker_adapter,
        "message": (
            "Job observed only. Live worker execution is disabled."
        ),
    }


def execute_subprocess(
    job: ClaimedJob,
    command: list[str],
    timeout: int,
) -> dict[str, Any]:
    """
    Controlled subprocess adapter for live mode.

    Commands must be explicitly registered in ADAPTERS.
    No shell=True.
    """

    log(
        "INFO",
        "worker_start",
        job_id=job.id,
        adapter=job.worker_adapter,
        command=command,
    )

    completed_process = subprocess.run(
        command,
        cwd="/srv/empire_os",
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    result = {
        "ok": completed_process.returncode == 0,
        "executed": True,
        "returncode": completed_process.returncode,
        "stdout_tail": (
            completed_process.stdout or ""
        )[-4000:],
        "stderr_tail": (
            completed_process.stderr or ""
        )[-4000:],
    }

    if not result["ok"]:
        diagnostic = (
            str(result["stderr_tail"]).strip()
            or str(result["stdout_tail"]).strip()
            or (
                "worker exited with return code "
                f"{completed_process.returncode}"
            )
        )
        result["error"] = diagnostic[-4000:]

    log(
        "INFO" if result["ok"] else "ERROR",
        "worker_finish",
        job_id=job.id,
        adapter=job.worker_adapter,
        returncode=completed_process.returncode,
        error=result.get("error"),
    )

    return result


def execute_lead_generation(job: ClaimedJob) -> dict[str, Any]:
    """
    Live-capable lead generation adapter.

    Still requires explicit LIVE mode.
    Market/metro are passed as arguments to the hardened crawler.
    """

    niche = str(job.payload.get("niche") or "")
    metro = str(job.payload.get("metro") or "")

    command = [
        sys.executable,
        "-m",
        "empire_os.crawler_runner",
    ]

    if metro:
        command.extend(
            [
                "--metro",
                metro,
            ]
        )

    return execute_subprocess(
        job,
        command,
        timeout=1800,
    )


def _rest_json(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
    prefer: str | None = None,
) -> Any:
    query = ""
    if params:
        query = "?" + urllib.parse.urlencode(params)

    body = (
        json.dumps(payload).encode("utf-8")
        if payload is not None
        else None
    )

    headers = dict(HEADERS)
    if prefer:
        headers["Prefer"] = prefer

    req = urllib.request.Request(
        f"{SUPABASE_URL}{path}{query}",
        data=body,
        method=method,
        headers=headers,
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise BusError(
            f"REST {method} {path} failed HTTP {exc.code}: "
            f"{body_text[:1000]}"
        ) from exc




def _write_canonical_prospect(
    payload: dict[str, Any],
) -> dict[str, Any]:
    prospect = payload.get("prospect")
    evidence = payload.get("evidence")
    ingest_key = payload.get("ingest_key")
    identity_keys = payload.get("identity_keys")

    if not isinstance(prospect, dict):
        raise BusError("canonical prospect writer missing prospect")

    if not isinstance(evidence, dict):
        raise BusError("canonical prospect writer missing evidence")

    if not isinstance(ingest_key, str) or not ingest_key:
        raise BusError("canonical prospect writer missing ingest_key")

    if (
        not isinstance(identity_keys, list)
        or not identity_keys
        or not all(isinstance(key, str) and key for key in identity_keys)
    ):
        raise BusError("canonical prospect writer missing identity_keys")

    result = _rest_json(
        "POST",
        "/rest/v1/rpc/ingest_prospect_atomic",
        payload={
            "p_prospect": prospect,
            "p_evidence": evidence,
            "p_ingest_key": ingest_key,
            "p_identity_keys": identity_keys,
        },
    )

    if not isinstance(result, dict):
        raise BusError(
            "canonical prospect ingest returned invalid response"
        )

    return result

def _qualification_candidates(
    *,
    family: str,
    metro: str,
    limit: int = MAX_QUALIFICATION_BATCH_SIZE,
) -> list[dict[str, Any]]:
    aliases = sorted(
        {
            normalise(alias)
            for alias in NICHE_FAMILIES.get(
                family,
                {family},
            )
            if normalise(alias)
        }
    )

    if not aliases:
        aliases = [normalise(family)]

    rows = _rest_json(
        "GET",
        "/rest/v1/prospects",
        params={
            "select": (
                "id,business_name,niche,metro,status,"
                "buy_signal_score,phone,website,address,"
                "rating,review_count,contact_name,"
                "contact_title,contact_source,contacted_status"
            ),
            "niche": "in.(" + ",".join(aliases) + ")",
            "metro": "ilike." + metro,
            "status": "not.eq.archived",
            "order": "buy_signal_score.desc.nullslast,created_at.asc",
            "limit": str(limit),
        },
    )

    return rows if isinstance(rows, list) else []


def _materialize_qualification_jobs(
    job: ClaimedJob,
) -> dict[str, Any]:
    target = job.payload.get("target")
    if not isinstance(target, dict):
        target = {}

    family = normalise(
        target.get("niche_family")
        or job.payload.get("niche_family")
        or job.payload.get("niche")
        or ""
    )

    metro = normalise(
        target.get("metro")
        or job.payload.get("metro")
        or ""
    )

    if not family or not metro:
        raise BusError(
            "qualification job missing niche_family or metro"
        )

    raw_batch_size = job.payload.get(
        "qualification_batch_size"
    )

    if raw_batch_size is None:
        raise BusError(
            "qualification job missing qualification_batch_size"
        )

    try:
        batch_size = int(raw_batch_size)
    except (TypeError, ValueError) as exc:
        raise BusError(
            "qualification_batch_size must be an integer"
        ) from exc

    if not (
        1
        <= batch_size
        <= MAX_QUALIFICATION_BATCH_SIZE
    ):
        raise BusError(
            "qualification_batch_size must be between "
            f"1 and {MAX_QUALIFICATION_BATCH_SIZE}"
        )

    candidates = _qualification_candidates(
        family=family,
        metro=metro,
        limit=batch_size,
    )

    if not candidates:
        return {
            "ok": True,
            "executed": True,
            "mode": "materialize",
            "niche_family": family,
            "metro": metro,
            "candidates": 0,
            "already_qualified": 0,
            "jobs_created": 0,
        }

    prospect_ids = [
        str(row["id"])
        for row in candidates
        if row.get("id")
    ]

    existing: set[str] = set()

    if prospect_ids:
        rows = _rest_json(
            "GET",
            "/rest/v1/prospect_qualifications",
            params={
                "select": "prospect_id",
                "prospect_id": (
                    "in.(" + ",".join(prospect_ids) + ")"
                ),
                "scoring_engine": (
                    "eq.empire_os.lead_scoring"
                ),
                "scoring_version": "eq.v1",
            },
        )

        if isinstance(rows, list):
            existing = {
                str(row["prospect_id"])
                for row in rows
                if row.get("prospect_id")
            }

    jobs_created = 0
    jobs_existing = 0
    jobs_considered = 0

    for prospect in candidates:
        prospect_id = str(prospect.get("id") or "")

        if not prospect_id or prospect_id in existing:
            continue

        jobs_considered += 1

        idempotency_key = (
            f"qualification:{prospect_id}:v1"
        )

        row = {
            "opportunity_id": job.opportunity_id,
            "job_type": "prospect_qualification",
            "worker_adapter": (
                "autonomous_qualification_adapter"
            ),
            "priority": float(job.priority or 0.0),
            "status": "queued",
            "requires_approval": False,
            "approved_at": utc_now(),
            "payload": {
                "opportunity_id": job.opportunity_id,
                "parent_job_id": job.id,
                "prospect_id": prospect_id,
                "niche_family": family,
                "metro": metro,
                "prospect": {
                    "business_name": prospect.get(
                        "business_name"
                    ),
                    "niche": prospect.get("niche"),
                    "metro": prospect.get("metro"),
                    "buy_signal_score": prospect.get(
                        "buy_signal_score"
                    ),
                },
                "created_by": (
                    "autonomous_execution_bus"
                ),
            },
            "attempts": 0,
            "max_attempts": 5,
            "created_by": "autonomous_execution_bus",
            "idempotency_key": idempotency_key,
        }

        existing_jobs = _rest_json(
            "GET",
            "/rest/v1/gtm_jobs",
            params={
                "select": "id",
                "idempotency_key": (
                    f"eq.{idempotency_key}"
                ),
                "limit": "1",
            },
        )

        if (
            isinstance(existing_jobs, list)
            and existing_jobs
        ):
            jobs_existing += 1
            continue

        try:
            created_rows = _rest_json(
                "POST",
                "/rest/v1/gtm_jobs",
                payload=row,
                prefer="return=representation",
            )
        except BusError as exc:
            message = str(exc)

            duplicate_child = (
                "HTTP 409" in message
                and '"code":"23505"' in message
                and "idempotency_key" in message
            )

            if not duplicate_child:
                raise

            jobs_existing += 1
            continue

        if not (
            isinstance(created_rows, list)
            and created_rows
        ):
            raise BusError(
                "qualification child job insert "
                "returned no row"
            )

        jobs_created += 1

    return {
        "ok": True,
        "executed": True,
        "mode": "materialize",
        "niche_family": family,
        "metro": metro,
        "candidates": len(candidates),
        "already_qualified": len(existing),
        "jobs_considered": jobs_considered,
        "jobs_existing": jobs_existing,
        "jobs_created": jobs_created,
        "batch_size": batch_size,
    }


def execute_qualification(job: ClaimedJob) -> dict[str, Any]:
    """
    Convert one bounded market-level qualification job into
    deterministic lead-level qualification jobs.

    Actual scoring is performed by the lead-level adapter.
    """

    return _materialize_qualification_jobs(job)


def execute_autonomous_qualification(
    job: ClaimedJob,
) -> dict[str, Any]:
    prospect_id = str(
        job.payload.get("prospect_id") or ""
    )

    if not prospect_id:
        raise BusError(
            "prospect qualification job missing prospect_id"
        )

    command = [
        sys.executable,
        "-m",
        "empire_os.autonomous_qualification_worker",
        "--prospect-id",
        prospect_id,
    ]

    return execute_subprocess(
        job,
        command,
        timeout=300,
    )



def _allocation_candidates(
    *,
    family: str,
    metro: str,
    limit: int = MAX_ALLOCATION_BATCH_SIZE,
) -> list[dict[str, Any]]:
    aliases = sorted(
        {
            normalise(alias)
            for alias in NICHE_FAMILIES.get(family, {family})
            if normalise(alias)
        }
    )

    if not aliases:
        aliases = [normalise(family)]

    scan_limit = max(
        limit * ALLOCATION_SCAN_MULTIPLIER,
        limit,
    )

    prospects = _rest_json(
        "GET",
        "/rest/v1/prospects",
        params={
            "select": (
                "id,business_name,niche,metro,status,"
                "buy_signal_score,phone,website,address,"
                "contact_source,contacted_status"
            ),
            "niche": "in.(" + ",".join(aliases) + ")",
            "metro": "ilike." + metro,
            "status": "not.eq.archived",
            "order": "buy_signal_score.desc.nullslast,created_at.asc",
            "limit": str(scan_limit),
        },
    )

    if not isinstance(prospects, list) or not prospects:
        return []

    prospect_ids = [
        str(row.get("id") or "")
        for row in prospects
        if isinstance(row, dict) and row.get("id")
    ]

    if not prospect_ids:
        return []

    qualifications = _rest_json(
        "GET",
        "/rest/v1/prospect_qualifications",
        params={
            "select": "prospect_id,score,tier,status,scored_at",
            "prospect_id": "in.(" + ",".join(prospect_ids) + ")",
            "status": "eq.scored",
            "tier": "in.(hot,warm)",
            "score": "gte.50",
            "scoring_engine": "eq.empire_os.lead_scoring",
            "scoring_version": "eq.v1",
            "order": "score.desc,scored_at.asc",
        },
    )

    if not isinstance(qualifications, list):
        raise BusError(
            "allocation qualification query returned invalid payload"
        )

    qual_by_id = {
        str(row.get("prospect_id")): row
        for row in qualifications
        if isinstance(row, dict) and row.get("prospect_id")
    }

    qualified = [
        {
            **row,
            "_qualification": qual_by_id[str(row["id"])],
        }
        for row in prospects
        if (
            isinstance(row, dict)
            and row.get("id")
            and str(row["id"]) in qual_by_id
        )
    ]

    if not qualified:
        return []

    qualified_ids = [str(row["id"]) for row in qualified]

    existing_orders = _rest_json(
        "GET",
        "/rest/v1/fulfilment_orders",
        params={
            "select": "prospect_id",
            "prospect_id": "in.(" + ",".join(qualified_ids) + ")",
            "state": "not.in.(rejected,cancelled)",
        },
    )

    if not isinstance(existing_orders, list):
        raise BusError(
            "allocation fulfilment query returned invalid payload"
        )

    allocated = {
        str(row.get("prospect_id"))
        for row in existing_orders
        if isinstance(row, dict) and row.get("prospect_id")
    }

    available = [
        row for row in qualified
        if str(row["id"]) not in allocated
    ]

    available.sort(
        key=lambda row: (
            -float(row["_qualification"].get("score") or 0),
            -float(row.get("buy_signal_score") or 0),
            str(row["id"]),
        )
    )

    return available[:limit]


def _materialize_allocation_jobs(
    job: ClaimedJob,
) -> dict[str, Any]:
    target = job.payload.get("target")
    if not isinstance(target, dict):
        target = {}

    family = normalise(
        target.get("niche_family")
        or job.payload.get("niche_family")
        or job.payload.get("niche")
        or ""
    )
    metro = normalise(
        target.get("metro")
        or job.payload.get("metro")
        or ""
    )

    if not family or not metro:
        raise BusError(
            "allocation materializer missing niche_family or metro"
        )

    raw_batch_size = job.payload.get("allocation_batch_size")
    if raw_batch_size is None:
        raise BusError(
            "allocation materializer missing allocation_batch_size"
        )

    try:
        batch_size = int(raw_batch_size)
    except (TypeError, ValueError) as exc:
        raise BusError(
            "allocation_batch_size must be an integer"
        ) from exc

    if not (1 <= batch_size <= MAX_ALLOCATION_BATCH_SIZE):
        raise BusError(
            "allocation_batch_size must be between "
            f"1 and {MAX_ALLOCATION_BATCH_SIZE}"
        )

    candidates = _allocation_candidates(
        family=family,
        metro=metro,
        limit=batch_size,
    )

    jobs_created = 0
    jobs_existing = 0

    for prospect in candidates:
        prospect_id = str(prospect.get("id") or "")
        qualification = prospect.get("_qualification") or {}
        idempotency_key = f"allocation:{prospect_id}:v1"

        existing_jobs = _rest_json(
            "GET",
            "/rest/v1/gtm_jobs",
            params={
                "select": "id",
                "idempotency_key": f"eq.{idempotency_key}",
                "limit": "1",
            },
        )

        if isinstance(existing_jobs, list) and existing_jobs:
            jobs_existing += 1
            continue

        row = {
            "opportunity_id": job.opportunity_id,
            "job_type": "prospect_buyer_allocation",
            "worker_adapter": "buyer_allocation_adapter",
            "priority": float(job.priority or 0.0),
            "status": "planned",
            "requires_approval": True,
            "approved_at": None,
            "payload": {
                "opportunity_id": job.opportunity_id,
                "parent_job_id": job.id,
                "prospect_id": prospect_id,
                "niche_family": family,
                "metro": metro,
                "qualification_score": qualification.get("score"),
                "qualification_tier": qualification.get("tier"),
                "created_by": "autonomous_execution_bus",
            },
            "attempts": 0,
            "max_attempts": 5,
            "created_by": "autonomous_execution_bus",
            "idempotency_key": idempotency_key,
        }

        try:
            created = _rest_json(
                "POST",
                "/rest/v1/gtm_jobs",
                payload=row,
                prefer="return=representation",
            )
        except BusError as exc:
            message = str(exc)
            duplicate = (
                "HTTP 409" in message
                and '"code":"23505"' in message
                and "idempotency_key" in message
            )
            if not duplicate:
                raise
            jobs_existing += 1
            continue

        if not isinstance(created, list) or not created:
            raise BusError(
                "allocation child job insert returned no row"
            )

        jobs_created += 1

    return {
        "ok": True,
        "executed": True,
        "mode": "allocation_materialize",
        "niche_family": family,
        "metro": metro,
        "candidates": len(candidates),
        "jobs_created": jobs_created,
        "jobs_existing": jobs_existing,
        "batch_size": batch_size,
    }


def execute_allocation_materializer(
    job: ClaimedJob,
) -> dict[str, Any]:
    return _materialize_allocation_jobs(job)


def execute_buyer_allocation(
    job: ClaimedJob,
) -> dict[str, Any]:
    prospect_id = str(job.payload.get("prospect_id") or "").strip()
    if not prospect_id:
        raise BusError("buyer allocation job missing prospect_id")

    rows = _rest_json(
        "GET",
        "/rest/v1/prospects",
        params={
            "select": (
                "id,business_name,niche,metro,status,buy_signal_score,"
                "phone,website,address,contact_source,contacted_status"
            ),
            "id": f"eq.{prospect_id}",
            "limit": "1",
        },
    )

    if not isinstance(rows, list) or len(rows) != 1:
        raise BusError("buyer allocation prospect not found")

    prospect = rows[0]
    if normalise(prospect.get("status")) in {"archived", "rejected"}:
        raise BusError("buyer allocation prospect is not active")

    def reader(path: str, params: dict[str, str]) -> Any:
        return _rest_json("GET", path, params=params)

    def allocator(payload: dict[str, Any]) -> Any:
        return rpc("allocate_prospect_atomic", payload)

    try:
        result = allocate_owned_prospect(
            prospect,
            reader,
            allocator,
        )
    except BuyerAllocationError as exc:
        raise BusError(f"buyer allocation failed: {exc}") from exc

    decision = str(result.get("decision") or "")
    return {
        "ok": True,
        "executed": decision in {
            "allocated",
            "existing_allocation",
        },
        "mode": "buyer_allocation",
        **result,
    }


def execute_visibility(job: ClaimedJob) -> dict[str, Any]:
    """
    Visibility adapter remains coordination-only until SEO/AEO/GEO
    asset generation is connected to the governed job/event model.
    """

    return {
        "ok": True,
        "executed": False,
        "mode": "coordination_only",
        "channel": job.payload.get("channel"),
    }


def execute_buyer_acquisition(job: ClaimedJob) -> dict[str, Any]:
    return {
        "ok": True,
        "executed": False,
        "mode": "coordination_only",
        "reason": (
            "buyer acquisition requires a governed outbound "
            "candidate/action queue"
        ),
    }


def execute_product_offer(job: ClaimedJob) -> dict[str, Any]:
    return {
        "ok": True,
        "executed": False,
        "mode": "coordination_only",
        "reason": (
            "product offer generation requires commercial "
            "product definition and approval policy"
        ),
    }


def _nonnegative_int(value: Any) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _capacity_buyer_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0

    while True:
        batch = _rest_json(
            "GET",
            "/rest/v1/buyers",
            params={
                "select": (
                    "id,buyer_name,niche,metro,is_active,status,"
                    "daily_cap,calls_today,destination_phone,webhook_url,"
                    "reviewed_at,commercial_activation_state,"
                    "commercial_activated_at,commercial_terms_source,"
                    "commercial_terms_reference,commercial_terms_verified_at,"
                    "capacity_verified_at,delivery_verified_at"
                ),
                "limit": str(CAPACITY_BUYER_PAGE_SIZE),
                "offset": str(offset),
            },
        )

        if not isinstance(batch, list):
            raise BusError(
                "capacity check buyers query returned invalid payload"
            )

        rows.extend(batch)

        if len(batch) < CAPACITY_BUYER_PAGE_SIZE:
            break

        offset += CAPACITY_BUYER_PAGE_SIZE

    return rows


def execute_capacity_check(job: ClaimedJob) -> dict[str, Any]:
    """
    Recompute fulfilment capacity from canonical buyer state.

    This is a read-only execution gate. Planner payload capacity is
    retained only for audit/comparison and is never trusted as the
    live gate decision.
    """

    target = job.payload.get("target")
    if not isinstance(target, dict):
        target = {}

    target_niche = str(
        target.get("niche")
        or target.get("niche_family")
        or job.payload.get("niche")
        or job.payload.get("niche_family")
        or ""
    )

    target_metro = str(
        target.get("metro")
        or job.payload.get("metro")
        or ""
    )

    family = niche_family(target_niche)
    metro = metro_key(target_metro)

    if not family or not metro:
        raise BusError(
            "capacity check missing niche_family or metro"
        )

    rows = _capacity_buyer_rows()

    matched_buyers = 0
    available_buyers = 0
    daily_cap = 0
    calls_today = 0
    remaining_capacity = 0

    for row in rows:
        activation_allowed, _ = buyer_activation_decision(row)
        if not activation_allowed:
            continue

        buyer_niche = normalise(
            row.get("niche")
        )

        buyer_family = (
            niche_family(buyer_niche)
            if buyer_niche
            else ""
        )

        buyer_metro = metro_key(
            row.get("metro")
        )

        niche_match = buyer_family == family
        metro_match = buyer_metro == metro

        if not (
            niche_match
            and metro_match
        ):
            continue

        buyer_daily_cap = _nonnegative_int(
            row.get("daily_cap")
        )

        buyer_calls_today = _nonnegative_int(
            row.get("calls_today")
        )

        buyer_remaining = max(
            buyer_daily_cap
            - buyer_calls_today,
            0,
        )

        matched_buyers += 1
        daily_cap += buyer_daily_cap
        calls_today += buyer_calls_today
        remaining_capacity += buyer_remaining

        if buyer_remaining > 0:
            available_buyers += 1

    planned_capacity = _nonnegative_int(
        job.payload.get("buyer_capacity")
    )

    gate_open = (
        available_buyers > 0
        and remaining_capacity > 0
    )

    return {
        "ok": True,
        "executed": True,
        "mode": "capacity_check",
        "source": "buyers",
        "niche_family": family,
        "metro": metro,
        "matched_buyers": matched_buyers,
        "available_buyers": available_buyers,
        "daily_cap": daily_cap,
        "calls_today": calls_today,
        "remaining_capacity": remaining_capacity,
        # Preserve the legacy result key, but make it live capacity.
        "buyer_capacity": remaining_capacity,
        "planned_buyer_capacity": planned_capacity,
        "capacity_changed": (
            planned_capacity
            != remaining_capacity
        ),
        "gate_open": gate_open,
        "gate_reason": (
            "live_buyer_capacity_available"
            if gate_open
            else "no_live_buyer_capacity"
        ),
        "market_balance": job.payload.get(
            "market_balance"
        ),
    }


def execute_experiment(job: ClaimedJob) -> dict[str, Any]:
    return {
        "ok": True,
        "executed": False,
        "mode": "coordination_only",
        "reason": (
            "experiment execution requires a concrete "
            "allocation/test subject"
        ),
    }


ADAPTERS: dict[str, Adapter] = {
    "market_sweep_adapter": execute_lead_generation,
    "omega_qualification_adapter": execute_qualification,
    "autonomous_qualification_adapter": (
        execute_autonomous_qualification
    ),
    "buyer_allocation_materializer_adapter": (
        execute_allocation_materializer
    ),
    "buyer_allocation_adapter": execute_buyer_allocation,
    "seo_adapter": execute_visibility,
    "aeo_adapter": execute_visibility,
    "geo_adapter": execute_visibility,
    "buyer_gtm_adapter": execute_buyer_acquisition,
    "mrr_product_adapter": execute_product_offer,
    "fulfilment_capacity_adapter": execute_capacity_check,
    "experiment_adapter": execute_experiment,
}


def run_adapter(job: ClaimedJob) -> dict[str, Any]:
    adapter = ADAPTERS.get(job.worker_adapter)

    if adapter is None:
        raise BusError(
            f"unregistered worker adapter: "
            f"{job.worker_adapter}"
        )

    if EXECUTION_MODE != "live":
        return execute_observe(job)

    return adapter(job)


# ---------------------------------------------------------------------------
# Heartbeat supervision
# ---------------------------------------------------------------------------

def heartbeat_loop(
    job: ClaimedJob,
    stop_event: threading.Event,
) -> None:
    while not stop_event.wait(
        max(DEFAULT_HEARTBEAT_SECONDS, 10)
    ):
        try:
            ok = heartbeat(job)

            log(
                "INFO" if ok else "WARN",
                "heartbeat",
                job_id=job.id,
                success=ok,
            )

            if not ok:
                log(
                    "ERROR",
                    "heartbeat_rejected",
                    job_id=job.id,
                )
                return

        except Exception as exc:
            log(
                "ERROR",
                "heartbeat_error",
                job_id=job.id,
                error=str(exc)[:500],
            )


def run_one_job() -> bool:
    job = claim_next_job()

    if job is None:
        return False

    log(
        "INFO",
        "job_claimed",
        job_id=job.id,
        job_type=job.job_type,
        adapter=job.worker_adapter,
        priority=job.priority,
        attempt=job.attempts,
    )

    insert_event(
        event_type="gtm_job_claimed",
        job=job,
        payload={
            "job_type": job.job_type,
            "worker_adapter": job.worker_adapter,
            "attempt": job.attempts,
        },
        idempotency_key=f"job:{job.id}:claimed:{job.attempts}",
    )

    insert_event(
        event_type="gtm_job_started",
        job=job,
        payload={
            "job_type": job.job_type,
            "worker_adapter": job.worker_adapter,
            "attempt": job.attempts,
        },
        idempotency_key=f"job:{job.id}:started:{job.attempts}",
    )

    stop_event = threading.Event()

    heartbeat_thread = threading.Thread(
        target=heartbeat_loop,
        args=(job, stop_event),
        daemon=True,
    )

    heartbeat_thread.start()

    started = time.monotonic()

    try:
        result = run_adapter(job)

        elapsed_ms = int(
            (time.monotonic() - started) * 1000
        )

        result["duration_ms"] = elapsed_ms

        if not result.get("ok"):
            raise BusError(
                str(result.get("error") or "worker failed")
            )

        if not complete(job, result):
            raise BusError(
                "complete_gtm_job rejected the lease"
            )

        # The database state transition is authoritative. Once the job
        # is completed, a telemetry/audit write must never push the same
        # job through the failure path and attempt to re-lease/retry it.
        try:
            insert_event(
                event_type="gtm_job_completed",
                job=job,
                payload=result,
                idempotency_key=(
                    f"job:{job.id}:completed:{job.attempts}"
                ),
            )
            completion_event_recorded = True
        except Exception as event_exc:
            completion_event_recorded = False
            log(
                "ERROR",
                "completion_event_deferred",
                job_id=job.id,
                error=str(event_exc)[:1000],
                idempotency_key=(
                    f"job:{job.id}:completed:{job.attempts}"
                ),
            )

        log(
            "INFO",
            "job_completed",
            job_id=job.id,
            duration_ms=elapsed_ms,
            completion_event_recorded=completion_event_recorded,
        )

        return True

    except Exception as exc:
        error = str(exc)[:4000]

        log(
            "ERROR",
            "job_failed",
            job_id=job.id,
            error=error,
        )

        try:
            state = fail(
                job,
                error,
                retry_delay_seconds=min(
                    300,
                    30 * max(job.attempts, 1),
                ),
                result={
                    "worker": WORKER_ID,
                    "failed_at": utc_now(),
                },
            )

            insert_event(
                event_type="gtm_job_failed",
                job=job,
                payload={
                    "error": error,
                    "next_state": state,
                },
                idempotency_key=(
                    f"job:{job.id}:failed:{job.attempts}"
                ),
            )

            log(
                "WARN",
                "job_failure_recorded",
                job_id=job.id,
                next_state=state,
            )

        except Exception as fail_exc:
            log(
                "CRITICAL",
                "failure_recording_failed",
                job_id=job.id,
                error=str(fail_exc)[:1000],
            )

        return True

    finally:
        stop_event.set()


def run_once() -> int:
    # Observe mode must never claim or complete real queue work.
    # It is a configuration/health mode only.
    if EXECUTION_MODE != "live":
        log(
            "INFO",
            "observe_cycle",
            processed=0,
            reason="live_execution_disabled",
        )
        return 0

    processed = 0

    for _ in range(MAX_JOBS_PER_CYCLE):
        if not run_one_job():
            break

        processed += 1

    return processed


def print_status() -> None:
    print(
        json.dumps(
            {
                "worker_id": WORKER_ID,
                "execution_mode": EXECUTION_MODE,
                "supabase": SUPABASE_URL,
                "lease_seconds": DEFAULT_LEASE_SECONDS,
                "heartbeat_seconds": DEFAULT_HEARTBEAT_SECONDS,
                "max_jobs_per_cycle": MAX_JOBS_PER_CYCLE,
                "registered_adapters": sorted(
                    ADAPTERS,
                ),
                "timestamp": utc_now(),
            },
            indent=2,
        )
    )


def main() -> None:
    shutdown_event = threading.Event()

    def request_shutdown(signum: int, _frame: Any) -> None:
        log(
            "INFO",
            "shutdown_requested",
            signal=signum,
        )
        shutdown_event.set()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)

    parser = argparse.ArgumentParser(
        description="Empire OS Autonomous Execution Bus",
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Process available jobs once.",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Print bus configuration and exit.",
    )

    args = parser.parse_args()

    if args.status:
        print_status()
        return

    log(
        "INFO",
        "bus_start",
        registered_adapters=sorted(
            ADAPTERS,
        ),
    )

    if args.once:
        processed = run_once()

        log(
            "INFO",
            "bus_cycle_complete",
            processed=processed,
        )

        return

    while not shutdown_event.is_set():
        try:
            processed = run_once()

            log(
                "INFO",
                "bus_cycle_complete",
                processed=processed,
            )

        except Exception as exc:
            log(
                "ERROR",
                "bus_cycle_failed",
                error=str(exc)[:1000],
            )

        shutdown_event.wait(
            max(IDLE_SLEEP_SECONDS, 5)
        )

    log(
        "INFO",
        "bus_stop",
        reason="shutdown_requested",
    )


if __name__ == "__main__":
    main()
