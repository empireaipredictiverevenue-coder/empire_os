"""Dormant EmpireDB original conversion registry transport (migration-held).

Uses dedicated NOLOGIN per-operation capabilities after separate DBA grant.
Disabled by default. Does not create tables, provision roles or credentials.
Canonical session-user tenant identity is enforced INSIDE the DB functions.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, Callable, Mapping
import json

from empire_os.original_conversion_registry import (
    OriginalConversionRegistryUnavailable, build_registration_request,
    inspect_prospective_registry_readback,
)

WRITE_SQL = (
    "SELECT public.record_original_conversion_prediction_v1("
    "%s,%s,%s::text,%s)"
)
READ_SQL = (
    "SELECT public.read_original_conversion_prediction_v1(%s,%s)"
)
WRITER_ROLE = "empire_original_conversion_prediction_writer"
READER_ROLE = "empire_original_conversion_prediction_reader"


class PostgresOriginalConversionRegistry:
    def __init__(
        self,
        writer_dsn: str | None = None,
        reader_dsn: str | None = None,
        *,
        enabled: bool = False,
        connect_factory: Callable[..., Any] | None = None,
    ) -> None:
        if type(enabled) is not bool:
            raise ValueError("enabled must be boolean")
        self.enabled = enabled
        self.writer_dsn = writer_dsn
        self.reader_dsn = reader_dsn
        self._connect = connect_factory
        if self.enabled:
            if (not isinstance(writer_dsn, str) or not writer_dsn.strip()
                    or not isinstance(reader_dsn, str) or not reader_dsn.strip()):
                raise OriginalConversionRegistryUnavailable(
                    "dedicated, tenant-bound writer and reader DSNs required"
                )

    def _connection(self, dsn: str):
        if not self.enabled:
            raise OriginalConversionRegistryUnavailable(
                "original conversion registry is not activated"
            )
        if self._connect is not None:
            return self._connect(dsn)
        try:
            import psycopg
        except ImportError as exc:
            raise OriginalConversionRegistryUnavailable(
                "psycopg unavailable"
            ) from exc
        return psycopg.connect(dsn)

    def register(
        self, candidate: Mapping[str, Any], *, as_of: datetime,
    ) -> dict[str, Any]:
        request = build_registration_request(candidate, as_of=as_of)
        if not self.enabled:
            raise OriginalConversionRegistryUnavailable(
                "registration disabled; no source data written"
            )
        payload = request["payload"]
        serialized = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        )
        digest = sha256(serialized.encode()).hexdigest()
        try:
            with self._connection(self.writer_dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE " + WRITER_ROLE)
                    cursor.execute(
                        WRITE_SQL, (
                            request["tenant_id"], request["prediction_ref"],
                            serialized, digest,
                        ),
                    )
                    row = cursor.fetchone()
        except Exception as exc:
            raise OriginalConversionRegistryUnavailable(
                "canonical original prediction registration unavailable"
            ) from exc
        if not row or not isinstance(row[0], Mapping):
            raise OriginalConversionRegistryUnavailable(
                "canonical writer returned no structured receipt"
            )
        return dict(row[0])

    def readback(
        self, *, tenant_id: str, prediction_ref: str,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            raise OriginalConversionRegistryUnavailable(
                "readback disabled; no source data accessed"
            )
        if not all(isinstance(value, str) and value.strip()
                   and len(value) < 200
                   for value in (tenant_id, prediction_ref)):
            raise ValueError("bounded tenant and prediction ref required")
        try:
            with self._connection(self.reader_dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL ROLE " + READER_ROLE)
                    cursor.execute(READ_SQL, (tenant_id, prediction_ref))
                    row = cursor.fetchone()
        except Exception as exc:
            raise OriginalConversionRegistryUnavailable(
                "canonical original prediction readback unavailable"
            ) from exc
        if not row or row[0] is None:
            return None
        if not isinstance(row[0], Mapping):
            raise OriginalConversionRegistryUnavailable(
                "untrusted registry readback response"
            )
        return dict(row[0])

    def register_review(
        self, candidate: Mapping[str, Any], *, as_of: datetime,
    ) -> dict[str, Any]:
        """Explicit opt-in write and independent reader round trip.

        Readback equality is necessary but not sufficient for permission to
        calibrate; separate DBA-issued deployment and authenticated provenance
        are still required. Never output raw DB predictions to the UI.
        """
        request = build_registration_request(candidate, as_of=as_of)
        receipt = self.register(candidate, as_of=as_of)
        readback = self.readback(
            tenant_id=request["tenant_id"],
            prediction_ref=request["prediction_ref"],
        )
        return inspect_prospective_registry_readback(
            candidate, receipt=receipt, readback=readback, as_of=as_of,
        )
