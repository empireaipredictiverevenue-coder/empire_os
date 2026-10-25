"""Predictive Cloud V4.10 restricted source-rights inventory reader.

Reads prepared EmpireDB 066 owner evidence ONLY via dedicated constrained
login. A candidate review is not a licence, consent, source admission or
financial authority. Never accepts caller credentials, trusted keys or arbitrary
SQL from the evidence envelope. Fail closed on any database ambiguity/error.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable
from uuid import UUID

PURPOSE = "PRIVATE_PREDICTIVE_RESEARCH_ONLY"
DIGEST = re.compile(r"^[a-f0-9]{64}$")
DECISIONS = frozenset({
    "NO_SOURCE_RIGHTS_HELD", "PENDING_HELD",
    "CANDIDATE_REVIEW_HELD", "EXPIRED_HELD", "FUTURE_EVIDENCE_HELD",
    "REVOKED_HELD",
})


@dataclass(frozen=True)
class HeldRightsObservation:
    tenant_id: str
    source_evidence_digest: str
    decision: str
    revoked: bool
    real_rights_independently_verified: bool = False
    source_admission_authorized: bool = False
    execution_authority: str = "none"


class EmpireDbHeldSourceRightsReader:
    """Bounded read with exact original EmpireDB session_user authority."""
    DATABASE_LOGIN = "empire_predictive_rights_login"
    SQL = (
        "SELECT decision,tenant_id,source_evidence_digest,permitted_purpose,"
        "revocation_present,real_rights_independently_verified,"
        "source_admission_authorized,execution_authority "
        "FROM public.read_empire_predictive_source_rights_held("
        "%s::uuid,%s::text,%s::text)"
    )

    def __init__(self, dsn: str, *, connect_factory: Callable | None = None):
        if not isinstance(dsn, str) or not dsn.strip():
            raise ValueError("owner-provided dedicated EmpireDB connection required")
        if connect_factory is None:
            import psycopg
            connect_factory = psycopg.connect
        self._dsn = dsn
        self._connect = connect_factory

    def __call__(self, tenant_id: str, source_digest: str) -> HeldRightsObservation | None:
        if not isinstance(tenant_id, str):
            return None
        try:
            tenant = str(UUID(tenant_id))
        except (ValueError, TypeError, AttributeError):
            return None
        if tenant != tenant_id or UUID(tenant_id).int == 0:
            return None
        if not isinstance(source_digest, str) or not DIGEST.fullmatch(source_digest):
            return None
        try:
            with self._connect(self._dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute("SET LOCAL statement_timeout = '3000ms'")
                    cursor.execute("SELECT session_user")
                    identity = cursor.fetchone()
                    if not isinstance(identity, (tuple, list)) or identity != (self.DATABASE_LOGIN,):
                        return None
                    cursor.execute(self.SQL, (tenant, source_digest, PURPOSE))
                    data = cursor.fetchone()
                    if not isinstance(data, (tuple, list)) or len(data) != 8:
                        return None
                    if cursor.fetchone() is not None:
                        return None
                    (
                        decision, observed_tenant, observed_digest,
                        purpose, revoked, verified, admitted, authority,
                    ) = data
                    if (
                        decision not in DECISIONS
                        or str(observed_tenant) != tenant
                        or observed_digest != source_digest
                        or purpose != PURPOSE
                        or type(revoked) is not bool
                        or verified is not False or admitted is not False
                        or authority != "none"
                        or (decision == "REVOKED_HELD") != revoked
                    ):
                        return None
                    return HeldRightsObservation(
                        tenant_id=tenant, source_evidence_digest=source_digest,
                        decision=decision, revoked=revoked,
                    )
        except Exception:
            # Never expose database diagnostic strings; may contain credentials.
            return None
