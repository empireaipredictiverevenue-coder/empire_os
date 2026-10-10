"""Opt-in, dedicated-login EmpireDB transport for versioned CRM journey drafts.

Not wired to a production HTTP write route. All writes are append-only DESIGN
metadata with one tenant per dedicated LOGIN and mandatory server-side validation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from empire_os.revenue_crm_designs import (
    UnsafeJourneyDesign, canonical_tenant, prepare_design_revision,
)

ROLE = "empire_revenue_crm_journey_writer"
TABLE = "public.empire_crm_journey_design_versions"


class JourneyStorageUnavailable(RuntimeError):
    """Dedicated tenant-bound version store unavailable or authorization failed."""


@dataclass(frozen=True)
class JourneyStorageResult:
    tenant_id: str
    design_id: str
    revision: int
    sha256: str
    result: str
    execution_authority: str = "none"
    send_authorized: bool = False


class PostgresCrmJourneyDesignStore:
    """A distinct per-tenant NOINHERIT LOGIN, never the CRM reader/app role."""

    def __init__(self, dsn: str, *, authenticated_tenant_id: str,
                 connect_factory: Callable | None = None):
        self._tenant = canonical_tenant(authenticated_tenant_id)
        self._dsn = str(dsn or "").strip()
        if not self._dsn:
            raise JourneyStorageUnavailable("dedicated CRM journey DB login required")
        if connect_factory is None:
            import psycopg
            connect_factory = psycopg.connect
        self._connect = connect_factory

    @property
    def tenant_id(self) -> str:
        return self._tenant

    def _authority(self, cur: Any) -> None:
        cur.execute("SET LOCAL statement_timeout = '5000ms'")
        cur.execute("SET LOCAL lock_timeout = '3000ms'")
        cur.execute(
            "SELECT "
            "pg_catalog.pg_has_role(session_user,"
            "'empire_revenue_crm_journey_writer'::pg_catalog.regrole,'MEMBER'),"
            "EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE "
            "r.rolname <> 'empire_revenue_crm_journey_writer' "
            "AND r.rolname <> session_user "
            "AND pg_catalog.pg_has_role(session_user,r.oid,'MEMBER')),"
            "EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE r.rolname=session_user "
            "AND (NOT r.rolcanlogin OR r.rolinherit OR r.rolsuper OR "
            "r.rolcreatedb OR r.rolcreaterole OR r.rolbypassrls OR r.rolreplication)),"
            "pg_catalog.pg_has_role(session_user,"
            "'empire_revenue_crm_journey_writer'::pg_catalog.regrole,'USAGE')"
        )
        privileges = cur.fetchone()
        if privileges != (True, False, False, False):
            raise JourneyStorageUnavailable("journey writer login privileges unsafe")
        cur.execute("SET LOCAL ROLE " + ROLE)
        cur.execute("SELECT public.empire_current_tenant_id()")
        observed = cur.fetchone()
        if not observed or str(observed[0]) != self._tenant:
            raise JourneyStorageUnavailable("database-bound journey tenant mismatch")

    def save(self, draft: dict[str, Any], *, design_id: str | None = None,
             expected_prior_revision: int | None = None) -> JourneyStorageResult:
        if design_id is None and expected_prior_revision is not None:
            raise UnsafeJourneyDesign("expected prior revision needs a design id")
        if design_id is not None and expected_prior_revision is None:
            raise UnsafeJourneyDesign("existing design needs expected revision")
        prepared = prepare_design_revision(
            draft, authenticated_tenant_id=self._tenant,
            design_id=design_id, prior_revision=expected_prior_revision
        )
        try:
            with self._connect(self._dsn) as connection:
                with connection.cursor() as cur:
                    self._authority(cur)
                    # A transaction-scoped serialisation key prevents two local
                    # writers racing to append the same design version.
                    cur.execute(
                        "SELECT pg_catalog.pg_advisory_xact_lock("
                        "pg_catalog.hashtext(%s),pg_catalog.hashtext(%s))",
                        (self._tenant, prepared.design_id),
                    )
                    cur.execute(
                        "SELECT revision,design_sha256 FROM " + TABLE
                        + " WHERE tenant_id=%s AND design_id=%s "
                          "ORDER BY revision DESC LIMIT 1 FOR UPDATE",
                        (self._tenant, prepared.design_id),
                    )
                    latest = cur.fetchone()
                    if latest:
                        latest_revision = int(latest[0])
                        if (
                            latest_revision == prepared.revision
                            and str(latest[1]) == prepared.sha256
                            and expected_prior_revision is not None
                            and latest_revision == expected_prior_revision + 1
                        ):
                            state = "ALREADY_SAVED_SAME_CONTENT"
                        elif latest_revision != expected_prior_revision or (
                            prepared.revision != latest_revision + 1
                        ):
                            raise UnsafeJourneyDesign("concurrent journey revision conflict")
                        else:
                            state = "INSERTED"
                    elif expected_prior_revision is not None:
                        raise UnsafeJourneyDesign("journey does not exist at expected revision")
                    else:
                        state = "INSERTED"
                    if state == "INSERTED":
                        cur.execute(
                            "INSERT INTO " + TABLE
                            + " (tenant_id,design_id,revision,design_json,design_sha256)"
                              " VALUES (%s,%s,%s,%s::jsonb,%s)"
                              " RETURNING revision,design_sha256",
                            (self._tenant, prepared.design_id, prepared.revision,
                             json.dumps(prepared.payload,sort_keys=True,allow_nan=False),
                             prepared.sha256),
                        )
                        if cur.fetchone() != (prepared.revision, prepared.sha256):
                            raise JourneyStorageUnavailable("journal insert readback mismatch")
            # Separate committed readback: refuse to claim persisted until verified.
            with self._connect(self._dsn) as connection:
                with connection.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
                    self._authority(cur)
                    cur.execute(
                        "SELECT revision,design_sha256 FROM " + TABLE
                        + " WHERE tenant_id=%s AND design_id=%s "
                          "AND revision=%s LIMIT 1",
                        (self._tenant, prepared.design_id, prepared.revision),
                    )
                    if cur.fetchone() != (prepared.revision, prepared.sha256):
                        raise JourneyStorageUnavailable("postcommit journey readback failed")
            return JourneyStorageResult(
                self._tenant, prepared.design_id, prepared.revision,
                prepared.sha256, state
            )
        except UnsafeJourneyDesign:
            raise
        except Exception:
            raise JourneyStorageUnavailable(
                "tenant-bound journey design write unavailable"
            ) from None
