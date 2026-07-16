"""
Empire OS — Homeowner Job Intake & Matching Module (Blueprint v5 #2).

Manages homeowner job submissions and matches them to carrier-approved
contractors in the area. Tables:
  - carrier_rosters: carrier-approved contractors by ZIP
  - homeowner_jobs: job intake records
  - job_matches: match results between jobs and contractors

Flow:
  submit_job() → status=discovered
  find_matches() → status=matched_to_contractor + job_matches rows
  update_job_status() → bid_sent → bid_accepted → work_scheduled → work_completed → settled
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("homeowner_matching")

FB = Path("/root/feedback")
LOG = Path("/tmp/homeowner_matching.jsonl")

VALID_JOB_STATUSES = frozenset({
    "discovered", "matched_to_contractor", "bid_sent", "bid_accepted",
    "work_scheduled", "work_completed", "settled",
})
VALID_MATCH_STATUSES = frozenset({"pending", "bid_sent", "bid_accepted", "rejected"})


def log(level, msg, **fields):
    """JSONL log matching contractor_scraper_agent pattern."""
    e = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
        **fields,
    }
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "EVENT"):
        print(json.dumps(e), flush=True)


# ── Schema ──────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS carrier_rosters (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    contractor_name     TEXT    NOT NULL,
    license_no          TEXT    DEFAULT '',
    carrier             TEXT    NOT NULL,
    zip                 TEXT    NOT NULL,
    service_area_radius INTEGER DEFAULT 50,
    specialties         TEXT    DEFAULT '',
    rating              REAL    DEFAULT 0.0,
    phone               TEXT    DEFAULT '',
    email               TEXT    DEFAULT '',
    created_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_carrier_rosters_zip
    ON carrier_rosters(zip);

CREATE INDEX IF NOT EXISTS idx_carrier_rosters_carrier
    ON carrier_rosters(carrier);

CREATE TABLE IF NOT EXISTS homeowner_jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    phone       TEXT    DEFAULT '',
    email       TEXT    DEFAULT '',
    zip         TEXT    NOT NULL,
    job_type    TEXT    NOT NULL,
    description TEXT    DEFAULT '',
    status      TEXT    NOT NULL DEFAULT 'discovered'
                        CHECK(status IN ('discovered','matched_to_contractor','bid_sent','bid_accepted','work_scheduled','work_completed','settled')),
    opt_in      INTEGER DEFAULT 0,
    opt_in_at   TEXT,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_homeowner_jobs_status
    ON homeowner_jobs(status);

CREATE INDEX IF NOT EXISTS idx_homeowner_jobs_zip
    ON homeowner_jobs(zip);

CREATE TABLE IF NOT EXISTS job_matches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL REFERENCES homeowner_jobs(id),
    contractor_id   TEXT    NOT NULL,
    contractor_name TEXT    NOT NULL,
    carrier         TEXT    NOT NULL,
    distance        REAL    DEFAULT 0.0,
    status          TEXT    NOT NULL DEFAULT 'pending'
                            CHECK(status IN ('pending','bid_sent','bid_accepted','rejected')),
    match_score     REAL    DEFAULT 0.0,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_job_matches_job
    ON job_matches(job_id);

CREATE INDEX IF NOT EXISTS idx_job_matches_status
    ON job_matches(status);
"""


# ── DTOs ────────────────────────────────────────────────────────────


@dataclass
class HomeownerJob:
    id: int
    name: str
    phone: str
    email: str
    zip: str
    job_type: str
    description: str
    status: str
    opt_in: int
    opt_in_at: Optional[str]
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class JobMatch:
    id: int
    job_id: int
    contractor_id: str
    contractor_name: str
    carrier: str
    distance: float
    status: str
    match_score: float
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return asdict(self)


# ── Errors ──────────────────────────────────────────────────────────


class HomeownerMatchError(Exception):
    """Base error for homeowner matching operations."""


class JobNotFoundError(HomeownerMatchError):
    """Raised when a job id does not exist."""


class InvalidJobStatusError(HomeownerMatchError):
    """Raised when an invalid job status is supplied."""


class InvalidMatchStatusError(HomeownerMatchError):
    """Raised when an invalid match status is supplied."""


# ── Operations ──────────────────────────────────────────────────────


def _validate_job_status(status: str) -> str:
    if status not in VALID_JOB_STATUSES:
        raise InvalidJobStatusError(
            f"Invalid job status '{status}'. Valid: {sorted(VALID_JOB_STATUSES)}"
        )
    return status


def _validate_match_status(status: str) -> str:
    if status not in VALID_MATCH_STATUSES:
        raise InvalidMatchStatusError(
            f"Invalid match status '{status}'. Valid: {sorted(VALID_MATCH_STATUSES)}"
        )
    return status


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")


def ensure_schema(backend) -> None:
    """Create carrier_rosters, homeowner_jobs, job_matches tables if missing."""
    backend.executescript(SCHEMA_SQL)
    backend.commit()
    logger.info("homeowner_matching schema ensured")


def submit_job(
    backend,
    name: str,
    phone: str,
    email: str,
    zip: str,
    job_type: str,
    description: str,
) -> HomeownerJob:
    """Create a new homeowner job record (status = 'discovered')."""
    now = _now()
    cursor = backend.execute(
        """INSERT INTO homeowner_jobs
           (name, phone, email, zip, job_type, description,
            status, opt_in, opt_in_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?,
                   'discovered', ?, ?, ?, ?)""",
        (
            name.strip(),
            phone.strip(),
            email.strip(),
            zip.strip(),
            job_type.strip(),
            description.strip(),
            1 if email.strip() else 0,
            now if email.strip() else None,
            now,
            now,
        ),
    )
    backend.commit()
    job_id = cursor.lastrowid
    log("EVENT", "job_submitted",
        job_id=job_id, name=name, zip=zip, job_type=job_type)
    return get_job(backend, job_id)


def find_matches(backend, job_id: int) -> list[JobMatch]:
    """Find carrier-roster contractors in or near the job's ZIP, score them,
    and create job_matches rows.

    Scoring:
      - Exact ZIP match:       +50
      - Same ZIP prefix (3):   +30
      - Specialization match:  +30
      - Rating bonus:          rating × 10 (max +50)

    After matching the job status is advanced to 'matched_to_contractor'.
    """
    job = get_job(backend, job_id)

    zip_code = job.zip.strip()
    zip_prefix = zip_code[:3] if len(zip_code) >= 3 else zip_code
    job_type_lower = job.job_type.lower().replace(" ", "_")

    cursor = backend.execute(
        """SELECT id, company_name, license_no, carrier, zip,
                  service_areas, specializations, phone, scraped_at
           FROM carrier_rosters
           WHERE zip = ? OR zip LIKE ?
           ORDER BY zip = ? DESC""",
        (zip_code, f"{zip_prefix}%", zip_code),
    )
    rows = cursor.fetchall()

    if not rows:
        log("INFO", "no_carrier_rosters_found", job_id=job_id, zip=zip_code)
        return []

    matches: list[JobMatch] = []
    now = _now()

    for row in rows:
        score = 0.0

        # ZIP distance scoring
        if row["zip"] == zip_code:
            score += 50.0
        else:
            score += 30.0

        # Specialization match
        specializations = (row["specializations"] or "").lower()
        if job_type_lower in specializations:
            score += 30.0

        # Scraped data bonus (recent = more likely active)
        score += 10.0

        distance = 0.0 if row["zip"] == zip_code else 30.0

        cursor2 = backend.execute(
            """INSERT INTO job_matches
               (job_id, contractor_id, contractor_name, carrier, distance,
                status, match_score, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?,
                       'pending', ?, ?, ?)""",
            (
                job_id,
                str(row["id"]),
                row["company_name"],
                row["carrier"],
                distance,
                score,
                now,
                now,
            ),
        )
        match_id = cursor2.lastrowid
        matches.append(get_match(backend, match_id))

        log("INFO", "match_created",
            job_id=job_id, match_id=match_id,
            contractor=row["company_name"],
            score=round(score, 2))

    backend.commit()

    # Advance job status to matched_to_contractor if matches were created
    if matches and job.status == "discovered":
        backend.execute(
            "UPDATE homeowner_jobs SET status = ?, updated_at = ? WHERE id = ?",
            ("matched_to_contractor", now, job_id),
        )
        backend.commit()
        # Also record pipeline event
        try:
            from empire_os.homeowner_pipeline import transition_job
            transition_job(backend, str(job_id), "homeowner_job",
                           "matched_to_contractor", actor="matching_engine")
        except ImportError:
            pass

    matches.sort(key=lambda m: m.match_score, reverse=True)
    return matches


def get_job(backend, job_id: int) -> HomeownerJob:
    """Fetch a single job by id. Raises JobNotFoundError if missing."""
    cursor = backend.execute(
        "SELECT * FROM homeowner_jobs WHERE id = ?", (job_id,)
    )
    row = cursor.fetchone()
    if row is None:
        raise JobNotFoundError(f"Job id={job_id} not found")
    return HomeownerJob(**dict(row))


def get_job_with_matches(backend, job_id: int) -> dict:
    """Return a job dict together with its match list (scored desc)."""
    job = get_job(backend, job_id)
    cursor = backend.execute(
        "SELECT * FROM job_matches WHERE job_id = ? ORDER BY match_score DESC",
        (job_id,),
    )
    matches = [JobMatch(**dict(r)) for r in cursor.fetchall()]
    return {
        "job": job.to_dict(),
        "matches": [m.to_dict() for m in matches],
    }


def get_match(backend, match_id: int) -> JobMatch:
    """Fetch a single match by id. Raises HomeownerMatchError if missing."""
    cursor = backend.execute(
        "SELECT * FROM job_matches WHERE id = ?", (match_id,)
    )
    row = cursor.fetchone()
    if row is None:
        raise HomeownerMatchError(f"Match id={match_id} not found")
    return JobMatch(**dict(row))


def list_jobs(
    backend,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """List jobs with optional status filter. Each entry includes match_count."""
    if status is not None:
        _validate_job_status(status)

    parts = ["SELECT * FROM homeowner_jobs WHERE 1=1"]
    params: list = []

    if status:
        parts.append("AND status = ?")
        params.append(status)

    parts.append("ORDER BY created_at DESC LIMIT ?")
    params.append(limit)

    cursor = backend.execute(" ".join(parts), tuple(params))
    rows = cursor.fetchall()

    results: list[dict] = []
    for row in rows:
        job = HomeownerJob(**dict(row)).to_dict()
        c = backend.execute(
            "SELECT COUNT(*) AS cnt FROM job_matches WHERE job_id = ?",
            (job["id"],),
        ).fetchone()
        job["match_count"] = c["cnt"] if c else 0
        results.append(job)

    return results


def update_job_status(
    backend,
    job_id: int,
    status: str,
    opt_in: Optional[bool] = None,
) -> HomeownerJob:
    """Update a job's status (and optionally opt-in flag)."""
    _validate_job_status(status)
    job = get_job(backend, job_id)  # raises if not found

    now = _now()
    updates = ["status = ?", "updated_at = ?"]
    params: list = [status, now]

    if opt_in is not None:
        updates.append("opt_in = ?")
        params.append(1 if opt_in else 0)
        if opt_in:
            updates.append("opt_in_at = ?")
            params.append(now)

    params.append(job_id)
    backend.execute(
        f"UPDATE homeowner_jobs SET {', '.join(updates)} WHERE id = ?",
        tuple(params),
    )
    backend.commit()

    updated = get_job(backend, job_id)
    log("EVENT", "job_status_updated",
        job_id=job_id, status=status, previous=job.status)
    return updated


def update_match_status(
    backend,
    match_id: int,
    status: str,
) -> JobMatch:
    """Update a single match's status."""
    _validate_match_status(status)
    match = get_match(backend, match_id)  # raises if not found

    now = _now()
    backend.execute(
        "UPDATE job_matches SET status = ?, updated_at = ? WHERE id = ?",
        (status, now, match_id),
    )
    backend.commit()

    updated = get_match(backend, match_id)
    log("EVENT", "match_status_updated",
        match_id=match_id, job_id=updated.job_id, status=status)
    return updated
