"""Private, durable SQLite pilot security and cost-ceiling ledger.

Not a replacement for EmpireDB or an authorisation to deploy. Operates on one
single-host private filesystem; credential provisioning is offline/admin-only.
Provider charges are not inferred from reserved cost ceilings.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import stat
from typing import Any


class AdmissionError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class ActiveTenant:
    tenant_id: str
    monthly_cap: int
    monthly_cost_cap_usd_micros: int
    search_ceiling_usd_micros: int
    audit_ceiling_usd_micros: int
    permitted_operations: frozenset[str]
    approved_site_hosts: frozenset[str]


class DurablePilotStore:
    """Atomic per-tenant/month reservations, revocable credentials, no billing.

    SQLite BEGIN IMMEDIATE serialises reservation writes across independent
    Python processes on the same host and persistent local filesystem.
    Never host this file on NFS or share it across a service fleet.
    """
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        if not self.path.parent.is_dir():
            raise ValueError("existing private state directory required")
        dmode = stat.S_IMODE(self.path.parent.stat().st_mode)
        if dmode & 0o077:
            raise ValueError("private state directory must not be group/world-accessible")
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        if self.path.is_symlink() or not stat.S_ISREG(self.path.stat().st_mode) or stat.S_IMODE(self.path.stat().st_mode) & 0o077:
            raise ValueError("unsafe usage database file permissions")
        with self._db() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS tenants (
                    tenant_id TEXT PRIMARY KEY,
                    active INTEGER NOT NULL CHECK(active IN (0,1)),
                    hold INTEGER NOT NULL DEFAULT 0 CHECK(hold IN (0,1)),
                    monthly_cap INTEGER NOT NULL CHECK(monthly_cap >= 0),
                    cost_cap_micros INTEGER NOT NULL CHECK(cost_cap_micros >= 0),
                    search_ceiling_micros INTEGER NOT NULL CHECK(search_ceiling_micros > 0),
                    audit_ceiling_micros INTEGER NOT NULL CHECK(audit_ceiling_micros > 0),
                    operations TEXT NOT NULL, approved_hosts TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS api_keys (
                    token_hash TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
                    active INTEGER NOT NULL CHECK(active IN (0,1)),
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
                );
                CREATE TABLE IF NOT EXISTS usage_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    window TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    reserved_usd_micros INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    verified_actual_usd_micros INTEGER,
                    cost_source_ref TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(tenant_id, idempotency_key),
                    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
                );
                CREATE INDEX IF NOT EXISTS idx_usage_month
                    ON usage_requests (tenant_id, window);
            """)

    @contextmanager
    def _db(self):
        con = sqlite3.connect(self.path, timeout=8, isolation_level=None)
        try:
            con.execute("PRAGMA busy_timeout=8000")
            con.execute("PRAGMA foreign_keys=ON")
            con.execute("PRAGMA journal_mode=WAL")
            yield con
        finally:
            con.close()

    @staticmethod
    def _window() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def admin_upsert_tenant(self, policy: ActiveTenant) -> None:
        """Offline operator action. Not reachable through any customer endpoint."""
        if (not policy.tenant_id or len(policy.tenant_id) > 100 or
                any(n < 0 for n in (policy.monthly_cap, policy.monthly_cost_cap_usd_micros)) or
                policy.search_ceiling_usd_micros <= 0 or policy.audit_ceiling_usd_micros <= 0 or
                not policy.permitted_operations.issubset({"search", "site_audit"})):
            raise ValueError("invalid pilot tenant policy")
        with self._db() as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                con.execute("""INSERT INTO tenants
                    (tenant_id,active,monthly_cap,cost_cap_micros,
                     search_ceiling_micros,audit_ceiling_micros,operations,approved_hosts)
                    VALUES (?,?,?,?,?,?,?,?)
                    ON CONFLICT(tenant_id) DO UPDATE SET
                      monthly_cap=excluded.monthly_cap,
                      cost_cap_micros=excluded.cost_cap_micros,
                      search_ceiling_micros=excluded.search_ceiling_micros,
                      audit_ceiling_micros=excluded.audit_ceiling_micros,
                      operations=excluded.operations,approved_hosts=excluded.approved_hosts
                """, (policy.tenant_id, 1, policy.monthly_cap,
                         policy.monthly_cost_cap_usd_micros, policy.search_ceiling_usd_micros,
                         policy.audit_ceiling_usd_micros,
                         json.dumps(sorted(policy.permitted_operations)),
                         json.dumps(sorted(policy.approved_site_hosts))))
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise

    def admin_issue_key(self, tenant_id: str) -> str:
        """Returns plaintext once. Caller must store securely; never log it."""
        token = secrets.token_urlsafe(48)
        hashed = hashlib.sha256(token.encode()).hexdigest()
        with self._db() as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                row = con.execute("SELECT active,hold FROM tenants WHERE tenant_id=?", (tenant_id,)).fetchone()
                if row != (1, 0):
                    raise AdmissionError(403, "tenant_not_active")
                con.execute("INSERT INTO api_keys(token_hash,tenant_id,active,created_at) VALUES(?,?,1,?)",
                            (hashed, tenant_id, self._now()))
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
        return token

    def admin_revoke_key(self, raw_token: str) -> None:
        with self._db() as con:
            con.execute("UPDATE api_keys SET active=0 WHERE token_hash=?",
                        (hashlib.sha256(raw_token.encode()).hexdigest(),))

    def authenticate(self, raw_token: str) -> ActiveTenant:
        if len(raw_token) < 24 or len(raw_token) > 512:
            raise AdmissionError(401, "valid_bearer_token_required")
        digest = hashlib.sha256(raw_token.encode()).hexdigest()
        with self._db() as con:
            row = con.execute("""SELECT t.tenant_id,t.active,t.hold,t.monthly_cap,
                t.cost_cap_micros,t.search_ceiling_micros,t.audit_ceiling_micros,
                t.operations,t.approved_hosts FROM api_keys AS k
                JOIN tenants AS t ON t.tenant_id=k.tenant_id
                WHERE k.token_hash=? AND k.active=1""", (digest,)).fetchone()
        if row is None:
            raise AdmissionError(401, "valid_bearer_token_required")
        if row[1] != 1 or row[2] != 0:
            raise AdmissionError(403, "tenant_held_or_inactive")
        return ActiveTenant(row[0], row[3], row[4], row[5], row[6],
                            frozenset(json.loads(row[7])), frozenset(json.loads(row[8])))

    def reserve(self, policy: ActiveTenant, operation: str, idempotency_key: str,
                request_hash: str, token_hash: str, target_host: str | None = None) -> int:
        if operation not in policy.permitted_operations:
            raise AdmissionError(403, "operation_not_entitled")
        ceiling = (policy.search_ceiling_usd_micros if operation == "search"
                   else policy.audit_ceiling_usd_micros if operation == "site_audit" else None)
        if ceiling is None:
            raise AdmissionError(400, "operation_unsupported")
        window = self._window()
        now = self._now()
        with self._db() as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                # Recheck the actual key and live tenant policy inside the write lock.
                key = con.execute("SELECT tenant_id,active FROM api_keys WHERE token_hash=?", (token_hash,)).fetchone()
                if key != (policy.tenant_id, 1):
                    raise AdmissionError(401, "valid_bearer_token_required")
                row = con.execute("""SELECT active,hold,monthly_cap,cost_cap_micros,
                    search_ceiling_micros,audit_ceiling_micros,operations,approved_hosts
                    FROM tenants WHERE tenant_id=?""", (policy.tenant_id,)).fetchone()
                if row is None or row[0] != 1 or row[1] != 0:
                    raise AdmissionError(403, "tenant_held_or_inactive")
                if operation not in json.loads(row[6]):
                    raise AdmissionError(403, "operation_not_entitled")
                if target_host is not None and target_host not in json.loads(row[7]):
                    raise AdmissionError(403, "site_not_approved_for_tenant")
                ceiling = row[4] if operation == "search" else row[5]
                dup = con.execute("""SELECT request_hash FROM usage_requests
                    WHERE tenant_id=? AND idempotency_key=?""",
                    (policy.tenant_id, idempotency_key)).fetchone()
                if dup is not None:
                    raise AdmissionError(409, "idempotency_key_reused" if dup[0] == request_hash else "idempotency_key_payload_mismatch")
                count, reserved = con.execute("""SELECT COUNT(*), COALESCE(SUM(reserved_usd_micros),0)
                    FROM usage_requests WHERE tenant_id=? AND window=?""",
                    (policy.tenant_id, window)).fetchone()
                if count >= row[2]:
                    raise AdmissionError(429, "monthly_request_cap_reached")
                if reserved + ceiling > row[3]:
                    raise AdmissionError(429, "monthly_cost_ceiling_reached")
                cur = con.execute("""INSERT INTO usage_requests
                    (tenant_id,window,operation,idempotency_key,request_hash,
                     reserved_usd_micros,state,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?)""", (policy.tenant_id, window,
                        operation, idempotency_key, request_hash, ceiling,
                        "reserved", now, now))
                reservation_id = cur.lastrowid
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
        return int(reservation_id)

    def settle(self, policy: ActiveTenant, reservation_id: int, state: str,
               *, actual_usd_micros: int | None = None,
               cost_source_ref: str | None = None, token_hash: str | None = None) -> None:
        if state not in {"completed", "provider_error", "invalid_response", "cost_integrity_hold"}:
            raise ValueError("invalid reservation state")
        valid_receipt = (type(actual_usd_micros) is int and actual_usd_micros >= 0
                         and bool(cost_source_ref and cost_source_ref.strip()))
        if (actual_usd_micros is not None or cost_source_ref is not None) and not valid_receipt:
            raise ValueError("verified actual cost requires nonnegative integer and source reference")
        with self._db() as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                if token_hash is not None:
                    key = con.execute("SELECT tenant_id,active FROM api_keys WHERE token_hash=?", (token_hash,)).fetchone()
                    if key != (policy.tenant_id, 1):
                        raise AdmissionError(401, "valid_bearer_token_required")
                row = con.execute("""SELECT state,reserved_usd_micros FROM usage_requests
                    WHERE id=? AND tenant_id=?""", (reservation_id, policy.tenant_id)).fetchone()
                if row is None or row[0] != "reserved":
                    raise ValueError("unknown or already settled reservation")
                if valid_receipt and actual_usd_micros > row[1]:
                    state = "cost_integrity_hold"
                    con.execute("UPDATE tenants SET hold=1 WHERE tenant_id=?", (policy.tenant_id,))
                con.execute("""UPDATE usage_requests SET state=?,verified_actual_usd_micros=?,
                    cost_source_ref=?,updated_at=? WHERE id=? AND tenant_id=?""",
                    (state, actual_usd_micros, cost_source_ref, self._now(),
                     reservation_id, policy.tenant_id))
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
        if state == "cost_integrity_hold":
            raise AdmissionError(503, "provider_cost_exceeded_approved_ceiling_tenant_held")

    def snapshot(self, policy: ActiveTenant, *, token_hash: str | None = None) -> dict[str, Any]:
        with self._db() as con:
            if token_hash is not None:
                key = con.execute("SELECT tenant_id,active FROM api_keys WHERE token_hash=?", (token_hash,)).fetchone()
                if key != (policy.tenant_id, 1):
                    raise AdmissionError(401, "valid_bearer_token_required")
            row = con.execute("""SELECT COUNT(*),COALESCE(SUM(reserved_usd_micros),0),
                    COALESCE(SUM(verified_actual_usd_micros),0),
                    SUM(CASE WHEN verified_actual_usd_micros IS NULL THEN 1 ELSE 0 END)
                    FROM usage_requests WHERE tenant_id=? AND window=?""",
                    (policy.tenant_id, self._window())).fetchone()
            tenant = con.execute("""SELECT monthly_cap,cost_cap_micros,hold
                    FROM tenants WHERE tenant_id=?""", (policy.tenant_id,)).fetchone()
        if tenant is None:
            raise AdmissionError(403, "tenant_not_active")
        return {"window": self._window(), "request_count": row[0], "cap": tenant[0],
                "cost_ceiling_usd_micros": tenant[1], "cost_reserved_usd_micros": row[1],
                "verified_actual_cost_usd_micros": row[2],
                "unverified_cost_requests": row[3] or 0,
                "tenant_cost_hold": bool(tenant[2]), "billing_enabled": False}
