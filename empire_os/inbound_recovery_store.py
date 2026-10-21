"""Offline durable evidence store, signed callback intake and scoped reports.

Not connected to production voice routes, Supabase, finance or CRM. Files contain
pseudonymous call/provider IDs only; keep in a private, access-controlled folder.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any

from empire_os.inbound_provider_contract import (
    InboundNumberRegistry,
    build_trusted_inbound_status,
)
from empire_os.inbound_revenue_recovery import RecoveryEvent, RecoveryLedger
from empire_os.inbound_reception_intake import CRMEnquiryDraft
from empire_os.inbound_signature_verification import (
    VerifiedVoiceCallback,
    verify_vonage_voice_callback,
)


class OfflineRecoveryStore:
    """Durable SQLite for local replay/testing only; not a production ledger."""

    def __init__(self, db_path: str | Path, *, read_only: bool = False):
        self.path = Path(db_path)
        self.read_only = read_only
        if read_only:
            if self.path == Path(":memory:") or not self.path.is_file():
                raise ValueError("existing_sqlite_database_required_for_read_only")
            self._conn = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
            self._conn.execute("PRAGMA query_only = ON")
            return
        if self.path == Path(":memory:"):
            self._conn = sqlite3.connect(":memory:")
        else:
            if not self.path.parent.exists():
                raise ValueError("recovery_store_parent_must_exist")
            self._conn = sqlite3.connect(str(self.path))
        self._conn.execute("PRAGMA busy_timeout = 3000")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS recovery_events (
                tenant_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                call_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                kind TEXT NOT NULL,
                origin TEXT NOT NULL,
                evidence_ref TEXT NOT NULL,
                amount_minor INTEGER,
                currency TEXT NOT NULL,
                verified INTEGER NOT NULL,
                synthetic INTEGER NOT NULL,
                PRIMARY KEY (tenant_id, event_id)
            );
            CREATE INDEX IF NOT EXISTS recovery_tenant_call_time_idx
                ON recovery_events(tenant_id, call_id, occurred_at);
            CREATE TABLE IF NOT EXISTS offline_reception_enquiry_drafts (
                tenant_id TEXT NOT NULL,
                enquiry_id TEXT NOT NULL,
                call_id TEXT NOT NULL,
                enquiry_type TEXT NOT NULL CHECK(enquiry_type IN ('appointment','callback')),
                requested_service TEXT NOT NULL,
                preferred_time_window TEXT NOT NULL CHECK(
                    preferred_time_window IN ('morning','afternoon','evening','anytime')),
                source TEXT NOT NULL CHECK(source = 'signed_inbound_reception_candidate'),
                status TEXT NOT NULL CHECK(status = 'PENDING_HUMAN_REVIEW_NOT_SUBMITTED'),
                caller_consented_to_review INTEGER NOT NULL CHECK(caller_consented_to_review = 1),
                PRIMARY KEY (tenant_id, enquiry_id),
                UNIQUE (tenant_id, call_id)
            );
            CREATE TABLE IF NOT EXISTS verified_voice_callbacks (
                api_key TEXT NOT NULL,
                jwt_id TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                PRIMARY KEY (api_key, jwt_id)
            );
            """
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "OfflineRecoveryStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @staticmethod
    def _fields(event: RecoveryEvent) -> tuple[Any, ...]:
        return (
            event.tenant_id, event.event_id, event.call_id, event.occurred_at,
            event.kind, event.origin, event.evidence_ref, event.amount_minor,
            event.currency, int(event.verified), int(event.synthetic),
        )

    def append_offline(self, event: RecoveryEvent) -> bool:
        """Trusted local test harness only: does not establish live authenticity."""
        if self.read_only:
            raise ValueError("offline_store_read_only")
        with self._conn:
            existing = self._conn.execute(
                "SELECT tenant_id,event_id,call_id,occurred_at,kind,origin,"
                "evidence_ref,amount_minor,currency,verified,synthetic "
                "FROM recovery_events WHERE tenant_id=? AND event_id=?",
                (event.tenant_id, event.event_id),
            ).fetchone()
            fields = self._fields(event)
            if existing is not None:
                if tuple(existing) != fields:
                    raise ValueError("conflicting_duplicate_event_id")
                return False
            self._conn.execute(
                "INSERT INTO recovery_events "
                "(tenant_id,event_id,call_id,occurred_at,kind,origin,"
                "evidence_ref,amount_minor,currency,verified,synthetic) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                fields,
            )
        return True

    def append_signed_status(
        self, event: RecoveryEvent, callback: VerifiedVoiceCallback
    ) -> bool:
        """Require signed JWT verification proof and track jti alongside event."""
        if self.read_only:
            raise ValueError("offline_store_read_only")
        if (callback.provider != "vonage" or event.origin != "provider"
            or event.synthetic or not event.verified
            or not event.evidence_ref or not callback.payload_sha256):
            raise ValueError("signed_non_synthetic_provider_evidence_required")
        key = (callback.api_key, callback.jwt_id)
        with self._conn:
            prior_callback = self._conn.execute(
                "SELECT payload_sha256, tenant_id, event_id "
                "FROM verified_voice_callbacks WHERE api_key=? AND jwt_id=?", key
            ).fetchone()
            if prior_callback:
                if prior_callback != (
                    callback.payload_sha256, event.tenant_id, event.event_id
                ):
                    raise ValueError("conflicting_callback_jwt_replay")
                return False
            existing = self._conn.execute(
                "SELECT tenant_id,event_id,call_id,occurred_at,kind,origin,"
                "evidence_ref,amount_minor,currency,verified,synthetic "
                "FROM recovery_events WHERE tenant_id=? AND event_id=?",
                (event.tenant_id, event.event_id),
            ).fetchone()
            if existing and tuple(existing) != self._fields(event):
                raise ValueError("conflicting_duplicate_event_id")
            self._conn.execute(
                "INSERT INTO verified_voice_callbacks "
                "(api_key,jwt_id,payload_sha256,tenant_id,event_id) VALUES (?,?,?,?,?)",
                (*key, callback.payload_sha256, event.tenant_id, event.event_id),
            )
            if existing:
                return False
            self._conn.execute(
                "INSERT INTO recovery_events "
                "(tenant_id,event_id,call_id,occurred_at,kind,origin,"
                "evidence_ref,amount_minor,currency,verified,synthetic) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)", self._fields(event)
            )
        return True

    def events_for_tenant(self, tenant_id: str) -> tuple[RecoveryEvent, ...]:
        """Tenant-scoped read of stored evidence; no cross-tenant joins."""
        if not tenant_id:
            raise ValueError("tenant_id_required")
        events: list[RecoveryEvent] = []
        rows = self._conn.execute(
            "SELECT tenant_id,event_id,call_id,occurred_at,kind,origin,"
            "evidence_ref,amount_minor,currency,verified,synthetic "
            "FROM recovery_events WHERE tenant_id=? ORDER BY occurred_at,event_id",
            (tenant_id,),
        ).fetchall()
        for r in rows:
            events.append(RecoveryEvent(
                tenant_id=r[0], event_id=r[1], call_id=r[2], occurred_at=r[3],
                kind=r[4], origin=r[5], evidence_ref=r[6],
                amount_minor=r[7], currency=r[8], verified=bool(r[9]),
                synthetic=bool(r[10]),
            ))
        return tuple(events)

    def report(self, tenant_id: str) -> dict[str, Any]:
        """Aggregated read of tenant-scoped offline provider evidence."""
        ledger = RecoveryLedger()
        for event in self.events_for_tenant(tenant_id):
            ledger.append(event)
        result = ledger.report(tenant_id)
        result["store"] = "offline_sqlite_persisted"
        result["database_writes"] = False
        return result

    @staticmethod
    def _reception_draft_fields(draft: CRMEnquiryDraft) -> tuple:
        """Privacy-minimal, synthetic/dark staging only. No actual CRM receipt."""
        from empire_os.inbound_reception_intake import draft_for_call
        if not isinstance(draft, CRMEnquiryDraft):
            raise ValueError("invalid_reception_draft")
        if (draft.status != "PENDING_HUMAN_REVIEW_NOT_SUBMITTED"
            or draft.source != "signed_inbound_reception_candidate"
            or draft.caller_consented_to_review is not True
            or draft.crm_write_performed or draft.outbound_authorized
            or draft.appointment_confirmed or draft.contact_identity_included):
            raise ValueError("unsafe_reception_draft")
        if (not isinstance(draft.tenant_id, str)
            or len(draft.tenant_id) > 160
            or not isinstance(draft.call_id, str)
            or not 8 <= len(draft.call_id) <= 96):
            raise ValueError("invalid_reception_scope")
        expected = draft_for_call(
            tenant_id=draft.tenant_id, call_id=draft.call_id,
            kind=draft.enquiry_type, service=draft.requested_service,
            window=draft.preferred_time_window,
        )
        if draft != expected:
            raise ValueError("conflicting_reception_draft")
        return (
            draft.tenant_id, draft.enquiry_id, draft.call_id,
            draft.enquiry_type, draft.requested_service,
            draft.preferred_time_window, draft.source, draft.status,
            int(draft.caller_consented_to_review),
        )

    def append_reception_draft_offline(self, draft: CRMEnquiryDraft) -> bool:
        """Atomic local staging receipt; NEVER a canonical EmpireDB CRM write.

        Repeated identical signed events return False; contradictory same-call
        consent payloads cannot silently overwrite evidence. Do not log PII.
        """
        if self.read_only:
            raise ValueError("offline_store_read_only")
        fields = self._reception_draft_fields(draft)
        with self._conn:
            existing = self._conn.execute(
                "SELECT tenant_id,enquiry_id,call_id,enquiry_type,"
                "requested_service,preferred_time_window,source,status,"
                "caller_consented_to_review FROM offline_reception_enquiry_drafts "
                "WHERE tenant_id=? AND (enquiry_id=? OR call_id=?)",
                (draft.tenant_id, draft.enquiry_id, draft.call_id),
            ).fetchone()
            if existing is not None:
                if tuple(existing) != fields:
                    raise ValueError("conflicting_reception_draft_replay")
                return False
            self._conn.execute(
                "INSERT INTO offline_reception_enquiry_drafts "
                "(tenant_id,enquiry_id,call_id,enquiry_type,requested_service,"
                "preferred_time_window,source,status,caller_consented_to_review) "
                "VALUES (?,?,?,?,?,?,?,?,?)", fields,
            )
        return True

    def reception_drafts_for_tenant(self, tenant_id: str) -> tuple[CRMEnquiryDraft, ...]:
        """Explicit tenant filter; caller must authenticate via CRM owner route."""
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("tenant_required")
        try:
            rows = self._conn.execute(
                "SELECT tenant_id,enquiry_id,call_id,enquiry_type,"
                "requested_service,preferred_time_window,source,status,"
                "caller_consented_to_review FROM offline_reception_enquiry_drafts "
                "WHERE tenant_id=? ORDER BY enquiry_id LIMIT 501",
                (tenant_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise ValueError("offline_reception_draft_storage_unavailable") from exc
        if len(rows) > 500:
            raise ValueError("offline_reception_draft_review_capacity_held")
        drafts: list[CRMEnquiryDraft] = []
        for r in rows:
            try:
                candidate = CRMEnquiryDraft(
                    tenant_id=r[0], enquiry_id=r[1], call_id=r[2],
                    enquiry_type=r[3], requested_service=r[4],
                    preferred_time_window=r[5], source=r[6],
                    status=r[7], caller_consented_to_review=bool(r[8]),
                )
                if self._reception_draft_fields(candidate) != tuple(r):
                    raise ValueError("offline_reception_draft_integrity_error")
            except (TypeError, ValueError) as exc:
                raise ValueError("offline_reception_draft_integrity_error") from exc
            drafts.append(candidate)
        return tuple(drafts)


def ingest_signed_vonage_status_offline(
    raw_body: bytes,
    authorization: str,
    *,
    store: OfflineRecoveryStore,
    registry: InboundNumberRegistry,
    signature_secret: str,
    expected_api_key: str,
    expected_application_id: str | None = None,
    now: int | None = None,
) -> bool:
    """Signed -> mapped tenant -> durable idempotent test record. Never route."""
    callback = verify_vonage_voice_callback(
        authorization,
        raw_body,
        signature_secret=signature_secret,
        expected_api_key=expected_api_key,
        expected_application_id=expected_application_id,
        now=now,
    )
    payload = json.loads(raw_body)
    # Stable status identity: provider retry could use a different JWT jti,
    # but same call/status/provider timestamp should not multiply events.
    identity_parts = (
        str(payload.get("uuid") or ""),
        str(payload.get("status") or "").strip().lower(),
        str(payload.get("timestamp") or ""),
    )
    digest = sha256(json.dumps(identity_parts).encode("utf-8")).hexdigest()
    payload["event_id"] = "vonage-" + digest
    event = build_trusted_inbound_status(
        payload, registry=registry, provider_signature_verified=True,
    )
    return store.append_signed_status(event, callback)
