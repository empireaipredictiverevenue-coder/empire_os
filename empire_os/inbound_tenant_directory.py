"""Offline tenant directory and explicit reporting eligibility.

This local SQLite module is a transition contract, NOT customer provisioning in
production. No public API issues tenant credentials or enables telecom routing.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class RecoveryTenant:
    tenant_id: str
    business_name: str
    timezone_name: str
    vertical: str = "general"
    state: str = "draft"
    reporting_approved: bool = False

    def __post_init__(self) -> None:
        for field in ("tenant_id", "business_name"):
            if not isinstance(getattr(self, field), str) or not getattr(self, field).strip():
                raise ValueError(f"{field}_required")
        if self.vertical not in {
            "general", "home_services", "hospitality", "professional_services"
        }:
            raise ValueError("unsupported_vertical")
        if self.state not in {"draft", "testing", "approved", "suspended"}:
            raise ValueError("unsupported_tenant_state")
        if not isinstance(self.reporting_approved, bool):
            raise ValueError("invalid_reporting_approval")
        try:
            ZoneInfo(self.timezone_name)
        except (ZoneInfoNotFoundError, TypeError, ValueError) as exc:
            raise ValueError("invalid_tenant_timezone") from exc

    @property
    def may_review(self) -> bool:
        return self.state == "approved" and self.reporting_approved


class OfflineTenantDirectory:
    """Persistent local config, fail-closed read path; no API for mutations."""

    def __init__(self, path: str | Path, *, read_only: bool = False):
        self.path = Path(path)
        self.read_only = read_only
        if read_only:
            if not self.path.is_file() or self.path.is_symlink():
                raise ValueError("approved_tenant_directory_required")
            self.db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
            self.db.execute("PRAGMA query_only = ON")
        else:
            if self.path != Path(":memory:") and (not self.path.parent.exists() or self.path.is_symlink()):
                raise ValueError("tenant_directory_path_invalid")
            self.db = sqlite3.connect(str(self.path))
            self.db.execute("PRAGMA foreign_keys = ON")
            self.db.execute("""
            CREATE TABLE IF NOT EXISTS tenant_directory (
                tenant_id TEXT PRIMARY KEY,
                business_name TEXT NOT NULL,
                timezone_name TEXT NOT NULL,
                vertical TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'draft',
                reporting_approved INTEGER NOT NULL DEFAULT 0
            )""")

    def __enter__(self) -> "OfflineTenantDirectory":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.db.close()

    def register_offline(self, tenant: RecoveryTenant) -> None:
        """Explicit local test/config operator action, not a live API endpoint."""
        if self.read_only:
            raise ValueError("tenant_directory_read_only")
        with self.db:
            self.db.execute(
                "INSERT INTO tenant_directory VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(tenant_id) DO UPDATE SET "
                "business_name=excluded.business_name, "
                "timezone_name=excluded.timezone_name, "
                "vertical=excluded.vertical, state=excluded.state, "
                "reporting_approved=excluded.reporting_approved",
                (tenant.tenant_id, tenant.business_name, tenant.timezone_name,
                 tenant.vertical, tenant.state, int(tenant.reporting_approved)),
            )

    def get(self, tenant_id: str) -> RecoveryTenant | None:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("tenant_id_required")
        record = self.db.execute(
            "SELECT tenant_id,business_name,timezone_name,vertical,state,"
            "reporting_approved FROM tenant_directory WHERE tenant_id=?",
            (tenant_id,),
        ).fetchone()
        if record is None:
            return None
        return RecoveryTenant(
            tenant_id=record[0], business_name=record[1],
            timezone_name=record[2], vertical=record[3],
            state=record[4], reporting_approved=bool(record[5]),
        )
