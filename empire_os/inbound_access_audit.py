"""Local HMAC-linked management access audit log (no call text or PII).

Append-only at API level and independently verifiable. The log is tamper-
evident, not immutable against an administrator controlling both DB and key.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
from pathlib import Path
import sqlite3

from empire_os.inbound_management_auth import RecoveryActor


def _canonical(record: dict) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


class RecoveryAccessAudit:
    def __init__(self, path: str | Path, *, audit_key: str):
        if not isinstance(audit_key, str) or len(audit_key.encode()) < 32:
            raise ValueError("management_audit_key_not_configured")
        self.key = audit_key.encode()
        self.path = Path(path)
        if self.path != Path(":memory:") and (
            not self.path.parent.is_dir() or self.path.is_symlink()
        ):
            raise ValueError("invalid_management_audit_path")
        self.db = sqlite3.connect(str(self.path), timeout=3)
        self.db.execute("PRAGMA busy_timeout = 3000")
        self.db.execute("PRAGMA synchronous = FULL")
        self.db.execute("""
        CREATE TABLE IF NOT EXISTS access_audit (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            occurred_at TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            actor_fingerprint TEXT NOT NULL,
            operation TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            record_hash TEXT NOT NULL
        )""")
        self.db.commit()

    def __enter__(self) -> "RecoveryAccessAudit":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.db.close()

    def _digest(self, record: dict) -> str:
        return hmac.new(self.key, _canonical(record), "sha256").hexdigest()

    def append(
        self, actor: RecoveryActor, operation: str, *, timestamp: datetime | None = None
    ) -> str:
        if operation not in {"profile_read", "scorecard_read", "queue_read", "patterns_read"}:
            raise ValueError("unsupported_audit_operation")
        when = timestamp or datetime.now(timezone.utc)
        if when.tzinfo is None or when.utcoffset() is None:
            raise ValueError("audit_timestamp_must_be_aware")
        actor_fingerprint = hmac.new(
            self.key, (actor.subject + "|" + actor.token_id).encode(), "sha256"
        ).hexdigest()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if not self.verify_chain():
                raise ValueError("management_audit_chain_integrity_failure")
            previous = self.db.execute(
                "SELECT seq, record_hash FROM access_audit ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            seq = (previous[0] + 1) if previous else 1
            prev_hash = previous[1] if previous else "GENESIS"
            details = {
                "seq": seq, "occurred_at": when.isoformat(),
                "tenant_id": actor.tenant_id,
                "actor_fingerprint": actor_fingerprint,
                "operation": operation, "previous_hash": prev_hash,
            }
            digest = self._digest(details)
            self.db.execute(
                "INSERT INTO access_audit "
                "(seq,occurred_at,tenant_id,actor_fingerprint,operation,previous_hash,record_hash) "
                "VALUES (?,?,?,?,?,?,?)",
                (seq, details["occurred_at"], actor.tenant_id, actor_fingerprint,
                 operation, prev_hash, digest),
            )
            self.db.commit()
            return digest
        except Exception:
            self.db.rollback()
            raise

    def verify_chain(self) -> bool:
        rows = self.db.execute(
            "SELECT seq,occurred_at,tenant_id,actor_fingerprint,operation,"
            "previous_hash,record_hash FROM access_audit ORDER BY seq"
        ).fetchall()
        previous = "GENESIS"
        for expected_seq, row in enumerate(rows, 1):
            record = {
                "seq": row[0], "occurred_at": row[1],
                "tenant_id": row[2], "actor_fingerprint": row[3],
                "operation": row[4], "previous_hash": row[5],
            }
            if row[0] != expected_seq or row[5] != previous:
                return False
            if not hmac.compare_digest(self._digest(record), row[6]):
                return False
            previous = row[6]
        return True

    def row_count(self) -> int:
        return int(self.db.execute("SELECT count(*) FROM access_audit").fetchone()[0])
