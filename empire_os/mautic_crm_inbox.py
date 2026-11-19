"""Prepared-only EmpireDB event inbox for verified Mautic -> Smart CRM signals.

No connection or DB change occurs on import or construction. Only the
independently authenticated Mautic ingress may call reserve_new. The isolated
tenant-bound INSERT + independent committed readback never sends or executes
journeys and never stores raw webhook bodies/contact PII.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from uuid import UUID

ROLE = "empire_mautic_crm_inbox_writer"
TABLE = "public.empire_crm_mautic_event_inbox"
SOURCE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$", re.ASCII)
DIGEST = re.compile(r"^[a-f0-9]{64}$", re.ASCII)
ALLOWED_EVENTS = frozenset({
    "mautic.form_on_submit",
    "mautic.email_on_open",
    "mautic.lead_channel_subscription_changed",
})
ALLOWED_SIGNALS = frozenset({
    "SUPPRESSION_REVIEW_REQUIRED",
    "CONTACTABILITY_REVIEW_NOT_CONSENT",
    "FORM_SUBMISSION_REVIEW_NOT_CONSENT",
    "LOW_CONFIDENCE_EMAIL_OPEN_REVIEW",
    "STALE_OR_UNVERIFIED_EVENT_REVIEW",
})
ALLOWED_STAGES = frozenset({
    "contact_hold", "fulfilment_review", "awaiting_payment_review",
    "proposal_review", "engaged_conversation_review",
    "unqualified_evidence_review",
})
ALLOWED_TIMESTAMP_STATES = frozenset({
    "RECENT_OBSERVED", "UNVERIFIED",
    "FUTURE_UNVERIFIED", "STALE_OVER_30_DAYS",
})


class MauticInboxUnavailable(RuntimeError):
    """Unprovisioned writer, unsafe authority, or transaction/readback failure."""


def canonical_uuid(value: Any) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise MauticInboxUnavailable("canonical tenant/prospect UUID required") from None


def validate_review(record: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    if not isinstance(record, Mapping):
        raise MauticInboxUnavailable("canonical projection required")
    keys = (
        "prospect_id", "source_event", "signal", "timestamp_state",
        "canonical_journey_segment",
    )
    prospect_id, event, signal, timestamp, segment = [record.get(k) for k in keys]
    prospect_id = canonical_uuid(prospect_id)
    if (
        not all(isinstance(item, str) for item in (event,signal,timestamp,segment))
        or event not in ALLOWED_EVENTS or signal not in ALLOWED_SIGNALS
        or timestamp not in ALLOWED_TIMESTAMP_STATES
        or segment not in ALLOWED_STAGES
    ):
        raise MauticInboxUnavailable("unrecognized or unbound CRM review evidence")
    # No arbitrary JSON or user text is ever persisted.
    return prospect_id, event, signal, timestamp, segment


class PostgresMauticEventInbox:
    """Dedicated NOINHERIT tenant login, append-only source-of-truth inbox.

    The DBA-owned prepared SQL schema is deliberately NOT auto-installed.
    Separate registration, provisioning and migration approvals are needed.
    """

    def __init__(
        self, dsn: str, *, authenticated_tenant_id: str,
        connect_factory: Callable | None = None,
    ):
        self.tenant_id = canonical_uuid(authenticated_tenant_id)
        if not isinstance(dsn, str) or not dsn.strip():
            raise MauticInboxUnavailable("dedicated EmpireDB writer connection required")
        self._dsn = dsn.strip()
        if connect_factory is None:
            import psycopg
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def _authority(self, cursor: Any) -> None:
        cursor.execute("SET LOCAL statement_timeout='5000ms'")
        cursor.execute("SET LOCAL lock_timeout='2000ms'")
        cursor.execute(
            "SELECT current_database(),"
            "pg_catalog.pg_has_role(session_user,"
            "'empire_mautic_crm_inbox_writer'::pg_catalog.regrole,'MEMBER'),"
            "EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE"
            " r.rolname<>session_user AND"
            " r.rolname<>'empire_mautic_crm_inbox_writer' AND"
            " pg_catalog.pg_has_role(session_user,r.oid,'MEMBER')),"
            "EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE"
            " r.rolname=session_user AND"
            " (NOT r.rolcanlogin OR r.rolinherit OR r.rolsuper OR"
            " r.rolcreatedb OR r.rolcreaterole OR"
            " r.rolbypassrls OR r.rolreplication)),"
            "pg_catalog.pg_has_role(session_user,"
            "'empire_mautic_crm_inbox_writer'::pg_catalog.regrole,'USAGE')"
        )
        privileges = cursor.fetchone()
        if privileges not in (
            ("empiredb", True, False, False, False),
            ("mautic_crm_inbox_fixture", True, False, False, False),
        ):
            raise MauticInboxUnavailable("dedicated writer login privileges unsafe")
        cursor.execute("SET LOCAL ROLE " + ROLE)
        cursor.execute("SELECT public.empire_current_tenant_id()")
        observed = cursor.fetchone()
        if not observed or str(observed[0]) != self.tenant_id:
            raise MauticInboxUnavailable("database tenant is not authenticated tenant")

    def reserve_new(
        self, *, tenant_id: str, source_id: str,
        evidence_hmacs: list[str], now: datetime,
        reviews: list[Mapping[str, Any]] | None = None,
    ) -> set[str]:
        """Atomically enqueue sanitized events then verify committed readback.

        A duplicate event is not delivered again. A failed write/readback is
        explicitly unavailable so Mautic can retry. No direct CRM mutation.
        """
        if canonical_uuid(tenant_id) != self.tenant_id:
            raise MauticInboxUnavailable("cross-tenant inbox receipt attempted")
        if not isinstance(source_id, str) or not SOURCE.fullmatch(source_id):
            raise MauticInboxUnavailable("invalid configured source")
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise MauticInboxUnavailable("authenticated receipt clock required")
        if (not isinstance(evidence_hmacs, list) or not isinstance(reviews, list)
                or len(evidence_hmacs) != len(reviews)
                or len(evidence_hmacs) > 40):
            raise MauticInboxUnavailable("missing bounded normalized event reviews")
        items: list[tuple[Any, ...]] = []
        for fingerprint, record in zip(evidence_hmacs, reviews, strict=True):
            if not isinstance(fingerprint, str) or not DIGEST.fullmatch(fingerprint):
                raise MauticInboxUnavailable("invalid keyed event fingerprint")
            if record.get("event_evidence_hmac") != fingerprint:
                raise MauticInboxUnavailable("mismatched event review fingerprint")
            items.append((self.tenant_id, source_id, fingerprint,
                          *validate_review(record)))
        inserted: set[str] = set()
        try:
            with self._connect(self._dsn) as conn:
                with conn.cursor() as cur:
                    self._authority(cur)
                    for (tenant, source, fingerprint, prospect,
                         event, signal, timestamp, segment) in items:
                        cur.execute(
                            "INSERT INTO " + TABLE + " "
                            "(tenant_id,source_id,event_evidence_hmac,"
                            " prospect_id,source_event,review_signal,"
                            " timestamp_state,journey_segment)"
                            " VALUES (%s::uuid,%s,%s,%s::uuid,%s,%s,%s,%s)"
                            " ON CONFLICT DO NOTHING RETURNING event_evidence_hmac",
                            (tenant,source,fingerprint,prospect,
                             event,signal,timestamp,segment),
                        )
                        received = cur.fetchone()
                        if received is not None:
                            if received != (fingerprint,):
                                raise MauticInboxUnavailable("writer receipt mismatch")
                            inserted.add(fingerprint)
            # Postcommit verification on a separate read-only transaction.
            # This verifies every event (including duplicate receipts) exists.
            with self._connect(self._dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
                    self._authority(cur)
                    for (tenant, source, fingerprint, prospect,
                         event, signal, timestamp, segment) in items:
                        cur.execute(
                            "SELECT prospect_id::text,source_event,review_signal,"
                            " timestamp_state,journey_segment FROM " + TABLE +
                            " WHERE tenant_id=%s::uuid AND source_id=%s"
                            " AND event_evidence_hmac=%s LIMIT 1",
                            (tenant, source, fingerprint),
                        )
                        if cur.fetchone() != (prospect, event, signal, timestamp, segment):
                            raise MauticInboxUnavailable("committed inbox readback mismatch")
        except Exception:
            raise MauticInboxUnavailable(
                "canonical Mautic inbox unavailable or unverified"
            ) from None
        return inserted
