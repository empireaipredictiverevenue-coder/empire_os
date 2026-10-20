"""Offline append-only-at-API-level booking/consent evidence repository.

No provider API and no send/booking methods. Input must already be trustworthy;
ordinary verified flags alone do not authenticate external sources.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from empire_os.inbound_booking_workflow import (
    InboundWorkflowEvent, WorkflowPolicy, summarise_inbound_workflow,
)
from datetime import datetime


class OfflineBookingWorkflowStore:
    def __init__(self, path: str | Path, *, read_only: bool = False):
        self.path = Path(path)
        self.read_only = read_only
        if read_only:
            if self.path == Path(":memory:") or not self.path.is_file() or self.path.is_symlink():
                raise ValueError("existing_workflow_database_required")
            self.db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
            self.db.execute("PRAGMA query_only=ON")
        else:
            if self.path != Path(":memory:") and (
                not self.path.parent.is_dir() or self.path.is_symlink()
            ):
                raise ValueError("invalid_workflow_database_path")
            self.db = sqlite3.connect(str(self.path), timeout=3)
            self.db.execute("PRAGMA busy_timeout=3000")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS inbound_workflow_evidence (
                    tenant_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, event_id)
                );
                CREATE INDEX IF NOT EXISTS inbound_workflow_by_tenant_time
                    ON inbound_workflow_evidence(tenant_id, occurred_at);
            """)

    def __enter__(self) -> "OfflineBookingWorkflowStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.db.close()

    @staticmethod
    def _encode(e: InboundWorkflowEvent) -> tuple[str, str]:
        body = json.dumps(asdict(e), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return body, sha256(body.encode("utf-8")).hexdigest()

    def append_offline(self, event: InboundWorkflowEvent) -> bool:
        if self.read_only:
            raise ValueError("workflow_store_read_only")
        body, digest = self._encode(event)
        with self.db:
            previous = self.db.execute(
                "SELECT payload_json,payload_sha256 FROM inbound_workflow_evidence "
                "WHERE tenant_id=? AND event_id=?",
                (event.tenant_id, event.event_id),
            ).fetchone()
            if previous:
                if previous != (body, digest):
                    raise ValueError("conflicting_workflow_event_id")
                return False
            self.db.execute(
                "INSERT INTO inbound_workflow_evidence "
                "(tenant_id,event_id,occurred_at,call_id,payload_json,payload_sha256) "
                "VALUES (?,?,?,?,?,?)",
                (event.tenant_id, event.event_id, event.occurred_at,
                 event.call_id, body, digest),
            )
            return True

    def events_for_tenant(self, tenant_id: str) -> tuple[InboundWorkflowEvent, ...]:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("tenant_id_required")
        rows = self.db.execute(
            "SELECT payload_json,payload_sha256 FROM inbound_workflow_evidence "
            "WHERE tenant_id=? ORDER BY occurred_at,event_id",
            (tenant_id,),
        ).fetchall()
        result = []
        for body, digest in rows:
            if sha256(body.encode("utf-8")).hexdigest() != digest:
                raise ValueError("workflow_event_integrity_failure")
            payload = json.loads(body)
            if not isinstance(payload, dict) or payload.get("tenant_id") != tenant_id:
                raise ValueError("workflow_tenant_payload_mismatch")
            result.append(InboundWorkflowEvent(**payload))
        return tuple(result)

    def summary(self, policy: WorkflowPolicy, *, as_of: datetime) -> dict:
        report = summarise_inbound_workflow(
            self.events_for_tenant(policy.tenant_id), policy=policy, as_of=as_of,
        )
        report["store"] = "offline_sqlite"
        return report
