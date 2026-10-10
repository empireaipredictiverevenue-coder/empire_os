"""Restricted EmpireDB suppression-hit transport for the existing CRM.

This uses a dedicated CRM reader login and a separately approved, tenant-bound
boolean/enum database function. It never reads the global suppression table,
contact addresses, or consent rows. No SQL function or database grant is created
here; until provisioned it fails closed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

from empire_os.revenue_crm_channel_evidence import TrustedChannelEvidence
from empire_os.revenue_crm_transport import ROLE

# Self-contained: do not depend on another agent's uncommitted changes to
# revenue_crm_transport.py. Verify the dedicated LOGIN before SET LOCAL ROLE.
CRM_LOGIN_AUTHORITY_SQL = (
    "SELECT "
    "pg_catalog.pg_has_role(session_user,"
    "'empire_revenue_crm_reader'::pg_catalog.regrole,'MEMBER'),"
    "EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE "
    "r.rolname <> 'empire_revenue_crm_reader' "
    "AND r.rolname <> session_user "
    "AND pg_catalog.pg_has_role(session_user,r.oid,'MEMBER')),"
    "EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE r.rolname=session_user "
    "AND (NOT r.rolcanlogin OR r.rolinherit OR r.rolsuper OR "
    "r.rolcreatedb OR r.rolcreaterole OR r.rolbypassrls OR r.rolreplication)),"
    "pg_catalog.pg_has_role(session_user,"
    "'empire_revenue_crm_reader'::pg_catalog.regrole,'USAGE')"
)

SUPPRESSION_FUNCTION = "public.empire_crm_prospect_suppression_hit(uuid,text)"
SUPPRESSION_SQL = "SELECT public.empire_crm_prospect_suppression_hit(%s::uuid,%s::text)"


class ChannelEvidenceSourceUnavailable(RuntimeError):
    """No privileged, independently authenticated suppression source."""


class PostgresCrmSuppressionEvidenceReader:
    """Use only the dedicated CRM login already bound to one tenant.

    This adapter is intentionally suppression-hit only, not an allow-list.
    An UNKNOWN result cannot be turned into not_found/clear/eligible.
    """

    def __init__(
        self, dsn: str, *, tenant_id: str,
        connect_factory: Callable | None = None,
    ) -> None:
        self._dsn = str(dsn or "").strip()
        try:
            self.tenant_id = str(UUID(str(tenant_id)))
        except (ValueError, TypeError, AttributeError):
            raise ChannelEvidenceSourceUnavailable("tenant authority invalid") from None
        if not self._dsn:
            raise ChannelEvidenceSourceUnavailable("dedicated reader DSN missing")
        if connect_factory is None:
            import psycopg
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def suppression_proof(
        self, *, prospect_id: str, channel: str,
    ) -> TrustedChannelEvidence:
        try:
            target = str(UUID(str(prospect_id)))
        except (ValueError, TypeError, AttributeError):
            raise ChannelEvidenceSourceUnavailable("canonical prospect UUID required") from None
        if channel not in ("email", "sms", "web_push"):
            raise ChannelEvidenceSourceUnavailable("unsupported CRM channel")
        # The canonical contact source currently supports *only* phone hits.
        # These other channels remain unknown WITHOUT contacting any DB.
        if channel != "sms":
            return self._evidence(target, channel, "unknown", None)
        try:
            with self._connect(self._dsn) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute("SET LOCAL statement_timeout = '4000ms'")
                    cursor.execute(CRM_LOGIN_AUTHORITY_SQL)
                    authority = cursor.fetchone()
                    if not isinstance(authority, (tuple, list)) or tuple(authority) != (
                        True, False, False, False,
                    ):
                        raise ChannelEvidenceSourceUnavailable("reader login unsafe")
                    cursor.execute("SET LOCAL ROLE " + ROLE)
                    cursor.execute("SELECT public.empire_current_tenant_id()")
                    bound = cursor.fetchone()
                    if (
                        not isinstance(bound, (tuple, list))
                        or len(bound) != 1 or str(bound[0]) != self.tenant_id
                    ):
                        raise ChannelEvidenceSourceUnavailable("tenant mismatch")
                    cursor.execute(
                        "SELECT pg_catalog.to_regprocedure(%s)",
                        (SUPPRESSION_FUNCTION,),
                    )
                    registered = cursor.fetchone()
                    if (
                        not isinstance(registered, (tuple, list))
                        or len(registered) != 1 or registered[0] is None
                    ):
                        raise ChannelEvidenceSourceUnavailable(
                            "canonical suppression function not provisioned"
                        )
                    # The installed function must be a stable, narrowly owned
                    # tenant-bound helper, not an unreviewed public replacement.
                    cursor.execute(
                        "SELECT p.prosecdef,p.provolatile,r.rolname "
                        "FROM pg_catalog.pg_proc p "
                        "JOIN pg_catalog.pg_roles r ON r.oid=p.proowner "
                        "WHERE p.oid=pg_catalog.to_regprocedure(%s)",
                        (SUPPRESSION_FUNCTION,),
                    )
                    owner = cursor.fetchone()
                    if not isinstance(owner, (tuple, list)) or tuple(owner) != (
                        True, "s", "empiredb_migrator",
                    ):
                        raise ChannelEvidenceSourceUnavailable(
                            "suppression function ownership unverified"
                        )
                    cursor.execute(SUPPRESSION_SQL, (target, channel))
                    result = cursor.fetchone()
                    if (
                        not isinstance(result, (tuple, list))
                        or len(result) != 1
                        or result[0] not in ("SUPPRESSED", "UNKNOWN")
                    ):
                        raise ChannelEvidenceSourceUnavailable(
                            "invalid suppression source result"
                        )
                    state = result[0]
        except ChannelEvidenceSourceUnavailable:
            raise
        except Exception:
            # Never expose DSN, database errors, contact or role diagnostics.
            raise ChannelEvidenceSourceUnavailable(
                "canonical suppression read unavailable"
            ) from None
        return self._evidence(
            target, channel, "suppressed" if state == "SUPPRESSED" else "unknown",
            "canonical-suppression-hit" if state == "SUPPRESSED" else None,
        )

    def _evidence(
        self, target: str, channel: str, suppression: str,
        reference: str | None,
    ) -> TrustedChannelEvidence:
        return TrustedChannelEvidence(
            tenant_id=self.tenant_id,
            prospect_id=target,
            channel=channel,
            identity_bound=False,  # no separately verified person binding
            consent_state="unknown",  # no marketing consent proof source
            suppression_state=suppression,
            consent_evidence_ref=None,
            suppression_evidence_ref=reference,
            observed_at=datetime.now(timezone.utc),
        )
