"""Offline owner-approved calendar registry and readback history.

Stores NO OAuth credentials and exposes NO self-service calendar registration.
All owner approvals / tracked appointment mapping are supplied by an authorized
internal operator, not by public API clients. No live provider calls on import.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from datetime import datetime
from typing import Any

from empire_os.inbound_google_calendar_adapter import (
    ApprovedCalendarBinding, TrackedCalendarAppointment, CalendarStatusProof,
    CalendarReadTransport, CalendarVerificationError,
    verify_google_booking_readback,
)


class OfflineCalendarRegistry:
    def __init__(self, path: str | Path, *, read_only: bool = False):
        self.path = Path(path)
        self.read_only = read_only
        if read_only:
            if self.path == Path(":memory:") or self.path.is_symlink() or not self.path.is_file():
                raise ValueError("existing_calendar_registry_required")
            self.db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
            self.db.execute("PRAGMA query_only=ON")
        else:
            if self.path != Path(":memory:") and (
                not self.path.parent.is_dir() or self.path.is_symlink()
            ):
                raise ValueError("invalid_calendar_registry_path")
            self.db = sqlite3.connect(str(self.path), timeout=3)
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.execute("PRAGMA busy_timeout=3000")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS owned_calendars (
                    calendar_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    provider_account_ref TEXT NOT NULL,
                    owner_approved INTEGER NOT NULL,
                    account_access_verified INTEGER NOT NULL,
                    approval_ref TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tracked_appointments (
                    calendar_id TEXT NOT NULL REFERENCES owned_calendars(calendar_id),
                    event_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    contact_key TEXT NOT NULL,
                    tracked_ref TEXT NOT NULL,
                    PRIMARY KEY(calendar_id, event_id)
                );
                CREATE TABLE IF NOT EXISTS calendar_status_reads (
                    calendar_id TEXT NOT NULL REFERENCES owned_calendars(calendar_id),
                    appointment_id TEXT NOT NULL,
                    proof_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    proof_json TEXT NOT NULL,
                    proof_sha256 TEXT NOT NULL,
                    PRIMARY KEY(calendar_id, appointment_id, proof_id),
                    FOREIGN KEY(calendar_id, appointment_id)
                       REFERENCES tracked_appointments(calendar_id, event_id)
                );
                CREATE INDEX IF NOT EXISTS inbound_calendar_recent_readbacks
                    ON calendar_status_reads(calendar_id,appointment_id,observed_at);
                CREATE TABLE IF NOT EXISTS calendar_projections (
                    calendar_id TEXT NOT NULL,
                    appointment_id TEXT NOT NULL,
                    proof_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending','complete')),
                    projected_at TEXT,
                    PRIMARY KEY(calendar_id,appointment_id,proof_id),
                    FOREIGN KEY(calendar_id,appointment_id,proof_id)
                        REFERENCES calendar_status_reads(calendar_id,appointment_id,proof_id)
                );
                CREATE INDEX IF NOT EXISTS calendar_projection_tenant_status_idx
                    ON calendar_projections(tenant_id,status);
                INSERT OR IGNORE INTO calendar_projections
                    (calendar_id,appointment_id,proof_id,tenant_id)
                SELECT r.calendar_id,r.appointment_id,r.proof_id,a.tenant_id
                FROM calendar_status_reads r
                JOIN tracked_appointments a
                  ON a.calendar_id=r.calendar_id AND a.event_id=r.appointment_id;
            """)

    def __enter__(self) -> "OfflineCalendarRegistry":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.db.close()

    def register_binding_offline(
        self, binding: ApprovedCalendarBinding, *, approval_ref: str
    ) -> bool:
        if self.read_only:
            raise ValueError("calendar_registry_read_only")
        if not isinstance(approval_ref, str) or not approval_ref.strip():
            raise ValueError("calendar_owner_approval_evidence_required")
        record = (
            binding.calendar_id, binding.tenant_id, binding.provider_account_ref,
            int(binding.owner_approved), int(binding.account_access_verified),
            approval_ref,
        )
        with self.db:
            previous = self.db.execute(
                "SELECT calendar_id,tenant_id,provider_account_ref,"
                "owner_approved,account_access_verified,approval_ref "
                "FROM owned_calendars WHERE calendar_id=?",
                (binding.calendar_id,),
            ).fetchone()
            if previous:
                if previous != record:
                    raise ValueError("calendar_cannot_be_reassigned_or_reapproved_silently")
                return False
            self.db.execute(
                "INSERT INTO owned_calendars VALUES(?,?,?,?,?,?)", record
            )
        return True

    def register_appointment_offline(self, link: TrackedCalendarAppointment) -> bool:
        if self.read_only:
            raise ValueError("calendar_registry_read_only")
        binding = self.get_binding(link.calendar_id)
        if binding is None:
            raise ValueError("calendar_binding_required")
        binding.check()
        if binding.tenant_id != link.tenant_id:
            raise ValueError("cross_tenant_calendar_link")
        row = (
            link.calendar_id, link.event_id, link.tenant_id,
            link.call_id, link.contact_key, link.tracked_ref,
        )
        with self.db:
            previous = self.db.execute(
                "SELECT calendar_id,event_id,tenant_id,call_id,contact_key,tracked_ref "
                "FROM tracked_appointments WHERE calendar_id=? AND event_id=?",
                (link.calendar_id, link.event_id),
            ).fetchone()
            if previous:
                if previous != row:
                    raise ValueError("conflicting_calendar_appointment_owner")
                return False
            self.db.execute(
                "INSERT INTO tracked_appointments VALUES(?,?,?,?,?,?)", row
            )
        return True

    def get_binding(self, calendar_id: str) -> ApprovedCalendarBinding | None:
        row = self.db.execute(
            "SELECT tenant_id,calendar_id,provider_account_ref,"
            "owner_approved,account_access_verified FROM owned_calendars "
            "WHERE calendar_id=?", (calendar_id,),
        ).fetchone()
        return ApprovedCalendarBinding(
            tenant_id=row[0], calendar_id=row[1], provider_account_ref=row[2],
            owner_approved=bool(row[3]), account_access_verified=bool(row[4]),
        ) if row else None

    def get_link(self, *, calendar_id: str, event_id: str) -> TrackedCalendarAppointment | None:
        row = self.db.execute(
            "SELECT tenant_id,calendar_id,event_id,call_id,contact_key,tracked_ref "
            "FROM tracked_appointments WHERE calendar_id=? AND event_id=?",
            (calendar_id, event_id),
        ).fetchone()
        return TrackedCalendarAppointment(
            tenant_id=row[0], calendar_id=row[1], event_id=row[2],
            call_id=row[3], contact_key=row[4], tracked_ref=row[5],
        ) if row else None

    def _history(self, calendar_id: str, event_id: str) -> tuple[CalendarStatusProof, ...]:
        rows = self.db.execute(
            "SELECT proof_json,proof_sha256 FROM calendar_status_reads "
            "WHERE calendar_id=? AND appointment_id=? ORDER BY observed_at,proof_id",
            (calendar_id, event_id),
        ).fetchall()
        results: list[CalendarStatusProof] = []
        for body, digest in rows:
            if sha256(body.encode()).hexdigest() != digest:
                raise ValueError("calendar_readback_integrity_failure")
            obj = json.loads(body)
            if not isinstance(obj, dict) or obj.get("calendar_id") != calendar_id or obj.get("appointment_id") != event_id:
                raise ValueError("calendar_readback_identity_corrupt")
            results.append(CalendarStatusProof(**obj))
        results.sort(key=lambda proof: (
            datetime.fromisoformat(proof.observed_at.replace("Z", "+00:00")),
            self.proof_version_id(proof),
        ))
        return tuple(results)

    def current_proof(self, *, calendar_id: str, event_id: str) -> CalendarStatusProof | None:
        history = self._history(calendar_id, event_id)
        return history[-1] if history else None

    def verified_readback_offline(
        self, *, tenant_id: str, calendar_id: str, event_id: str,
        token: str, transport: CalendarReadTransport, observed_at: datetime,
    ) -> tuple[CalendarStatusProof, bool]:
        """Fetch provider event then retain evidence; never writes to provider.

        Replays of an unchanged provider event are idempotent by status+provider
        revision. Cancellation without a revision is uniquely observed each
        time, but does not multiply current booking counts.
        """
        if self.read_only:
            raise ValueError("calendar_registry_read_only")
        binding = self.get_binding(calendar_id)
        link = self.get_link(calendar_id=calendar_id, event_id=event_id)
        if binding is None or link is None or tenant_id != binding.tenant_id or tenant_id != link.tenant_id:
            raise CalendarVerificationError("unregistered_tenant_calendar_or_appointment")
        prior = self.current_proof(calendar_id=calendar_id, event_id=event_id)
        proof = verify_google_booking_readback(
            binding=binding, link=link,
            token=token, transport=transport, observed_at=observed_at,
            previously_verified=prior,
        )
        version_id = self.proof_version_id(proof)
        canonical = asdict(proof)
        data = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        digest = sha256(data.encode()).hexdigest()
        with self.db:
            previous = self.db.execute(
                "SELECT proof_json FROM calendar_status_reads "
                "WHERE calendar_id=? AND appointment_id=? AND proof_id=?",
                (calendar_id, event_id, version_id),
            ).fetchone()
            if previous:
                # The provider revision is unchanged; read-observed timestamp
                # is not part of the canonical source version.
                return proof, False
            self.db.execute(
                "INSERT INTO calendar_status_reads "
                "(calendar_id,appointment_id,proof_id,observed_at,proof_json,proof_sha256) "
                "VALUES(?,?,?,?,?,?)",
                (calendar_id, event_id, version_id, proof.observed_at, data, digest),
            )
            self.db.execute(
                "INSERT INTO calendar_projections "
                "(calendar_id,appointment_id,proof_id,tenant_id) VALUES(?,?,?,?)",
                (calendar_id,event_id,version_id,tenant_id),
            )
        return proof, True

    @staticmethod
    def proof_version_id(proof: CalendarStatusProof) -> str:
        """Stable ID for a provider status + revision. Never uses OAuth tokens."""
        return sha256((
            proof.canonical_ref + "\x00" + proof.status + "\x00" +
            (proof.provider_updated_at or proof.observed_at)
        ).encode()).hexdigest()

    def pending_projection_proofs(
        self, tenant_id: str, *, limit: int = 200,
    ) -> tuple[CalendarStatusProof, ...]:
        """Read only tenant-scoped, unprojected verified calendar state changes."""
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("tenant_id_required")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 2000:
            raise ValueError("invalid_projection_limit")
        rows = self.db.execute(
            "SELECT r.calendar_id,r.appointment_id,r.proof_id,"
            "r.proof_json,r.proof_sha256 FROM calendar_projections p "
            "JOIN calendar_status_reads r ON r.calendar_id=p.calendar_id "
            "AND r.appointment_id=p.appointment_id AND r.proof_id=p.proof_id "
            "JOIN tracked_appointments a ON a.calendar_id=r.calendar_id "
            "AND a.event_id=r.appointment_id "
            "WHERE p.tenant_id=? AND a.tenant_id=? AND p.status='pending' "
            "ORDER BY r.observed_at,r.proof_id",
            (tenant_id, tenant_id),
        ).fetchall()
        proofs: list[CalendarStatusProof] = []
        for calendar_id, appointment_id, proof_id, body, digest in rows:
            if sha256(body.encode("utf-8")).hexdigest() != digest:
                raise ValueError("calendar_projection_evidence_integrity_failure")
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("invalid_calendar_projection_payload")
            proof = CalendarStatusProof(**payload)
            link = self.get_link(calendar_id=calendar_id, event_id=appointment_id)
            if (proof.tenant_id != tenant_id or proof.calendar_id != calendar_id
                or proof.appointment_id != appointment_id or link is None
                or proof.call_id != link.call_id or
                self.proof_version_id(proof) != proof_id):
                raise ValueError("calendar_projection_owner_or_version_mismatch")
            proofs.append(proof)
        # Sort by actual offset-aware instants; string ISO sorting is not
        # chronologically safe across different time-zone offsets.
        proofs.sort(key=lambda p: (
            datetime.fromisoformat(p.observed_at.replace("Z", "+00:00")),
            p.canonical_ref, self.proof_version_id(p),
        ))
        return tuple(proofs[:limit])

    def acknowledge_projection_offline(
        self, proof: CalendarStatusProof, *, projected_at: datetime,
    ) -> bool:
        """Ack only *after* both target stores accept the same proof."""
        if self.read_only:
            raise ValueError("calendar_registry_read_only")
        if projected_at.tzinfo is None or projected_at.utcoffset() is None:
            raise ValueError("projection_ack_time_must_be_aware")
        binding = self.get_binding(proof.calendar_id)
        link = self.get_link(calendar_id=proof.calendar_id, event_id=proof.appointment_id)
        if (binding is None or link is None
            or binding.tenant_id != proof.tenant_id
            or link.tenant_id != proof.tenant_id
            or link.call_id != proof.call_id):
            raise ValueError("calendar_projection_tenant_or_call_mismatch")
        proof_id = self.proof_version_id(proof)
        with self.db:
            cursor = self.db.execute(
                "UPDATE calendar_projections SET status='complete', projected_at=? "
                "WHERE calendar_id=? AND appointment_id=? AND proof_id=? "
                "AND tenant_id=? AND status='pending'",
                (projected_at.isoformat(), proof.calendar_id,
                 proof.appointment_id, proof_id, proof.tenant_id),
            )
            if cursor.rowcount:
                return True
            prior = self.db.execute(
                "SELECT status FROM calendar_projections WHERE calendar_id=? "
                "AND appointment_id=? AND proof_id=? AND tenant_id=?",
                (proof.calendar_id, proof.appointment_id, proof_id, proof.tenant_id),
            ).fetchone()
            if prior == ("complete",):
                return False
            raise ValueError("calendar_projection_receipt_missing")

    def projection_counts(self, tenant_id: str) -> dict[str, int]:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("tenant_id_required")
        rows = self.db.execute(
            "SELECT status,COUNT(*) FROM calendar_projections WHERE tenant_id=? "
            "GROUP BY status", (tenant_id,),
        ).fetchall()
        counts = dict(rows)
        return {"pending": counts.get("pending", 0),
                "complete": counts.get("complete", 0)}

    def tenant_summary(self, tenant_id: str) -> dict[str, Any]:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("tenant_id_required")
        rows = self.db.execute(
            "SELECT c.calendar_id, a.event_id "
            "FROM tracked_appointments a "
            "JOIN owned_calendars c ON c.calendar_id=a.calendar_id "
            "WHERE a.tenant_id=? AND c.tenant_id=? ORDER BY c.calendar_id,a.event_id",
            (tenant_id, tenant_id),
        ).fetchall()
        counts = {"confirmed": 0, "cancelled": 0, "not_verified": 0}
        for calendar_id, event_id in rows:
            p = self.current_proof(calendar_id=calendar_id, event_id=event_id)
            counts[p.status if p is not None else "not_verified"] += 1
        return {
            "tenant_id": tenant_id,
            "mode": "local_calendar_readback_history_only",
            "tracked_appointments": len(rows),
            "current_confirmed": counts["confirmed"],
            "current_cancelled": counts["cancelled"],
            "not_verified": counts["not_verified"],
            "projection_pending": self.projection_counts(tenant_id)["pending"],
            "projection_complete": self.projection_counts(tenant_id)["complete"],
            "customer_contact_authorized": False,
            "calendar_write_authorized": False,
            "bookings_created": False,
            "revenue_inferred": False,
        }
