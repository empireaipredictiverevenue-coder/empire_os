"""Opt-in Mautic -> canonical Smart CRM journey preview, never an outbound route.

This router is NOT included in any production application by default.
Mautic authenticates with its raw-body HMAC; server-side source configuration
binds the tenant. Canonical CRM reads must use existing tenant-bound transport.
Only opaque keyed event fingerprints are kept in the isolated receipt journal.
"""
from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from empire_os.mautic_webhook_review import (
    MAX_BODY_BYTES, MauticWebhookReviewError, preview_signed_mautic_webhook,
)
from empire_os.revenue_crm_journeys import preview_crm_journey
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository, RevenueCrmTransportError

SOURCE_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{2,63}\Z", re.ASCII)
DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


class MauticIntegrationError(RuntimeError):
    """Failure of the trusted source, receipt journal or CRM read."""


@dataclass(frozen=True)
class MauticSource:
    """Configured server-side only; no input comes from Mautic's JSON body."""
    source_id: str
    tenant_id: str
    webhook_secret: bytes
    contact_bindings: Mapping[int, Mapping[str, Any]]


class MauticJourneyRepository(Protocol):
    tenant_id: str
    def prospect(self, prospect_id: str) -> Mapping[str, Any] | None: ...


class SqliteMauticReceiptJournal:
    """Isolated staging-only durable dedup receipts, not a CRM or marketing DB.

    An EmpireDB owner-approved writer must replace this staging journal before
    production activation. The exclusive sqlite transaction is atomic across
    an entire webhook batch; duplicates are skipped, never re-promoted.
    """

    def __init__(self, path: Path):
        if not isinstance(path, Path) or str(path) == ":memory:":
            raise MauticIntegrationError("persistent absolute journal path required")
        if not path.is_absolute() or path.exists() and path.is_symlink():
            raise MauticIntegrationError("unsafe receipt journal path")
        if not path.parent.is_dir():
            raise MauticIntegrationError("pre-existing private receipt directory required")
        if path.parent.stat().st_mode & 0o077:
            raise MauticIntegrationError("receipt directory must be private to owner")
        # Create as 0600 even if the process default umask is permissive.
        # Never follow a pre-existing file symlink or accept a public journal.
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR
                         | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        if path.is_symlink() or path.stat().st_mode & 0o077:
            raise MauticIntegrationError("receipt file must be private to owner")
        self._path = path
        con = self._connection()
        try:
            con.execute(
                "CREATE TABLE IF NOT EXISTS mautic_review_receipts ("
                " tenant_id TEXT NOT NULL,"
                " source_id TEXT NOT NULL,"
                " evidence_hmac TEXT NOT NULL,"
                " observed_at TEXT NOT NULL,"
                " PRIMARY KEY (tenant_id,source_id,evidence_hmac))"
            )
        finally:
            con.close()

    def _connection(self):
        con = sqlite3.connect(str(self._path), timeout=3.0, isolation_level=None)
        con.execute("PRAGMA busy_timeout=3000")
        return con

    def reserve_new(self, *, tenant_id: str, source_id: str,
                    evidence_hmacs: list[str], now: datetime) -> set[str]:
        """Atomically record new event digests. Any DB failure is fail-closed."""
        if not SOURCE_PATTERN.fullmatch(source_id):
            raise MauticIntegrationError("invalid configured Mautic source")
        try:
            canonical = str(UUID(tenant_id))
        except (ValueError, TypeError, AttributeError):
            raise MauticIntegrationError("invalid authenticated tenant") from None
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise MauticIntegrationError("timezone-aware clock required")
        if len(evidence_hmacs) > 40 or any(
            not isinstance(item, str) or not DIGEST_PATTERN.fullmatch(item)
            for item in evidence_hmacs
        ):
            raise MauticIntegrationError("invalid bounded receipt set")
        inserted: set[str] = set()
        con = self._connection()
        try:
            con.execute("BEGIN IMMEDIATE")
            for fingerprint in evidence_hmacs:
                cursor = con.execute(
                    "INSERT OR IGNORE INTO mautic_review_receipts "
                    "(tenant_id,source_id,evidence_hmac,observed_at) VALUES (?,?,?,?)",
                    (canonical, source_id, fingerprint, now.astimezone(timezone.utc).isoformat()),
                )
                if cursor.rowcount == 1:
                    inserted.add(fingerprint)
            con.execute("COMMIT")
        except Exception as exc:
            try:
                con.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise MauticIntegrationError("receipt journal unavailable") from exc
        finally:
            con.close()
        return inserted


def create_mautic_crm_preview_router(
    *,
    resolve_source: Callable[[str], MauticSource | None],
    resolve_tenant_reader: Callable[[str], MauticJourneyRepository | None],
    receipt_journal: SqliteMauticReceiptJournal,
    allow_synthetic_test_reader: bool = False,
    now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> APIRouter:
    """Opt-in webhook preview on the existing CRM URL namespace.

    Must not be registered until the canonical owner has approved the source,
    authenticated tenant reader and receipt location. Never use client-supplied
    tenant, source bindings, or contact identity.
    """
    if (not callable(resolve_source) or not callable(resolve_tenant_reader)
            or not isinstance(receipt_journal, SqliteMauticReceiptJournal)):
        raise MauticIntegrationError("explicit trusted server integration required")
    router = APIRouter(prefix="/v1/revenue-crm/integrations/mautic")

    @router.post("/{source_id}/events/preview")
    async def preview_webhook(source_id: str, request: Request) -> dict[str, Any]:
        if not SOURCE_PATTERN.fullmatch(source_id):
            raise HTTPException(status_code=404, detail="mautic_source_unknown")
        try:
            source = resolve_source(source_id)
        except Exception:
            raise HTTPException(status_code=503, detail="mautic_source_unavailable") from None
        if source is None:
            raise HTTPException(status_code=404, detail="mautic_source_unknown")
        if not isinstance(source, MauticSource) or source.source_id != source_id:
            raise HTTPException(status_code=503, detail="mautic_source_unavailable")

        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            raise HTTPException(status_code=415, detail="application_json_required")
        signatures = request.headers.getlist("webhook-signature")
        if len(signatures) != 1:
            raise HTTPException(status_code=401, detail="mautic_webhook_signature_required")
        # Stream-bounded to avoid buffering an attacker-controlled huge upload.
        buffer = bytearray()
        async for chunk in request.stream():
            buffer.extend(chunk)
            if len(buffer) > MAX_BODY_BYTES:
                raise HTTPException(status_code=413, detail="mautic_webhook_too_large")
        try:
            now = now_provider()
            evidence = preview_signed_mautic_webhook(
                raw_body=bytes(buffer), signature=signatures[0],
                secret=source.webhook_secret,
                authenticated_tenant_id=source.tenant_id,
                trusted_contact_bindings=source.contact_bindings,
                now=now,
            )
        except MauticWebhookReviewError:
            raise HTTPException(status_code=401, detail="mautic_webhook_invalid") from None

        tenant = evidence["tenant_id"]
        try:
            repo = resolve_tenant_reader(tenant)
            if repo is None or str(repo.tenant_id) != tenant:
                raise MauticIntegrationError("canonical reader tenant mismatch")
            if not allow_synthetic_test_reader and not isinstance(
                repo, PostgresRevenueCrmRepository
            ):
                raise MauticIntegrationError("dedicated canonical Postgres reader required")
            projections: list[dict[str, Any]] = []
            for signal in evidence["signals"]:
                row = repo.prospect(signal["prospect_id"])
                if not isinstance(row, Mapping):
                    raise MauticIntegrationError("canonical prospect unavailable")
                if (str(row.get("tenant_id")) != tenant
                        or str(row.get("prospect_id")) != signal["prospect_id"]):
                    raise MauticIntegrationError("cross-tenant or orphan canonical CRM row")
                journey = preview_crm_journey(row, now=now)
                projections.append({
                    "prospect_id": signal["prospect_id"],
                    "event_evidence_hmac": signal["event_evidence_hmac"],
                    "source_event": signal["source_event"],
                    "signal": signal["signal"],
                    "timestamp_state": signal["timestamp_state"],
                    "canonical_journey_segment": journey["segment"],
                    "canonical_journey_blockers": journey["blockers"],
                    "channel_actions": journey["channel_actions"],
                    "execution_authority": "none",
                    "send_authorized": False,
                })
            accepted = receipt_journal.reserve_new(
                tenant_id=tenant, source_id=source_id,
                evidence_hmacs=[p["event_evidence_hmac"] for p in projections],
                now=now,
            )
        except (MauticIntegrationError, RevenueCrmTransportError, ValueError, TypeError, OSError, sqlite3.Error):
            raise HTTPException(status_code=503, detail="mautic_crm_review_unavailable") from None
        except Exception:
            raise HTTPException(status_code=503, detail="mautic_crm_review_unavailable") from None
        seen: set[str] = set()
        novel = []
        for projection in projections:
            fingerprint = projection["event_evidence_hmac"]
            if fingerprint in accepted and fingerprint not in seen:
                novel.append(projection)
                seen.add(fingerprint)
        return {
            "schema_version": "empire.mautic_crm_journey_ingress_preview.v1",
            "tenant_id": tenant,
            "mode": "OBSERVE", "read_only": True,
            "signed_webhook_verified": True,
            "received_events": evidence["event_count"],
            "unbound_events": evidence["unbound_event_count"],
            "new_events": len(novel),
            "duplicate_events": len(projections) - len(novel),
            "journey_reviews": novel,
            "durable_staging_replay_journal": True,
            "canonical_crm_written": False,
            "workflow_server_execution": False,
            "marketing_consent_verified": False,
            "send_authorized": False,
            "execution_authority": "none",
        }

    return router
