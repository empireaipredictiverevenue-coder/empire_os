"""OpenManus-compatible read-only review outbox for this one project.

There is NO verified OpenManus runtime on EmpireOS today. This module stages
machine-readable, non-secret assignments. Only an independently authenticated,
allowlisted future agent may receive jobs; staging NEVER dispatches tasks.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

_ALLOWED_TASK = "oauth_calendar_readonly_browser_review"
_ALLOWED_SOURCE = "docs/commercial/INBOUND_OPENMANUS_CALENDAR_REVIEW_HANDOFF_20261020.md"
_SHA = re.compile(r"^[a-f0-9]{40}$")


@dataclass(frozen=True)
class ManusReviewJob:
    job_id: str
    task_type: str
    source_doc: str
    code_commit: str
    owner: str
    state: str
    execution_authority: str = "none"
    provider_access: bool = False
    browser_actions: bool = False
    credentials_allowed: bool = False
    customer_data_allowed: bool = False


class OfflineManusReviewOutbox:
    """Local-only, no network or background worker, idempotent staging."""

    def __init__(self, path: str | Path, *, read_only: bool = False):
        self.path = Path(path)
        self.read_only = read_only
        if self.path != Path(":memory:") and (
            not self.path.is_absolute() or self.path.is_symlink()
            or not self.path.parent.is_dir() or (read_only and not self.path.is_file())
        ):
            raise ValueError("private_manus_outbox_path_required")
        if read_only:
            self.db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)
            self.db.execute("PRAGMA query_only=ON")
        else:
            self.db = sqlite3.connect(str(self.path))
            self.db.execute("PRAGMA busy_timeout=3000")
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS manus_review_jobs (
                    job_id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    source_doc TEXT NOT NULL,
                    code_commit TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('pending','reviewed')),
                    created_at TEXT NOT NULL
                )
            """)
            self.db.commit()

    def __enter__(self) -> "OfflineManusReviewOutbox":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.db.close()

    def stage(self, *, code_commit: str, source_doc: str = _ALLOWED_SOURCE,
              at: datetime) -> tuple[ManusReviewJob, bool]:
        if self.read_only:
            raise ValueError("manus_review_outbox_readonly")
        if not isinstance(code_commit, str) or not _SHA.fullmatch(code_commit):
            raise ValueError("verified_full_git_commit_required")
        if source_doc != _ALLOWED_SOURCE:
            raise ValueError("manus_review_source_not_allowlisted")
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("time_zone_required")
        job_id = "manus-review-" + sha256(
            (code_commit + "\x00" + _ALLOWED_TASK + "\x00" + source_doc).encode()
        ).hexdigest()
        with self.db:
            prior = self.db.execute(
                "SELECT task_type,source_doc,code_commit,owner,state "
                "FROM manus_review_jobs WHERE job_id=?", (job_id,),
            ).fetchone()
            if prior:
                if prior[:4] != (_ALLOWED_TASK, source_doc, code_commit, "existing_openmanus_owner"):
                    raise ValueError("manus_review_id_conflict")
                return self._job((job_id, *prior)), False
            self.db.execute(
                "INSERT INTO manus_review_jobs VALUES(?,?,?,?,?,?,?)",
                (job_id, _ALLOWED_TASK, source_doc, code_commit,
                 "existing_openmanus_owner", "pending", at.isoformat()),
            )
        return self._job((job_id, _ALLOWED_TASK, source_doc, code_commit,
                          "existing_openmanus_owner", "pending")), True

    @staticmethod
    def _job(row) -> ManusReviewJob:
        return ManusReviewJob(*row)

    def listing(self) -> tuple[ManusReviewJob, ...]:
        records = self.db.execute(
            "SELECT job_id,task_type,source_doc,code_commit,owner,state "
            "FROM manus_review_jobs ORDER BY created_at,job_id"
        ).fetchall()
        return tuple(self._job(row) for row in records)

    def summary(self) -> dict:
        jobs = self.listing()
        return {
            "mode": "isolated_read_only_review_handoff",
            "queued_for_existing_owner": sum(j.state == "pending" for j in jobs),
            "reviewed": sum(j.state == "reviewed" for j in jobs),
            "worker_connected": False,
            "jobs_dispatched": 0,
            "live_execution_authorized": False,
            "items": [asdict(job) for job in jobs],
        }
