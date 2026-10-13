"""Offline private reader for buyer-bound DIRECT BSC USDT checkout status.

NO public route, no production credentials, and no privileges are enabled.
The future status login must have ONLY the dedicated NOLOGIN reader role,
and the database function must own the strict fingerprint -> order binding.
Never accept an order UUID, email or wallet as a replacement for the bearer.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
import os
from typing import Any

from empire_os.direct_bsc_buyer_status import (
    BuyerAccessDenied,
    aware,
    deny,
    fingerprint,
    status as project_status,
)

READER_ROLE = "empire_direct_checkout_status_reader"
READ_SQL = "SELECT public.read_direct_bsc_buyer_status(%s)"
READER_CONFIG_KEY = "EMPIRE_DIRECT_BSC_BUYER_STATUS_READER_DSN"
TIME_FIELDS = {
    "access": ("issued_at", "expires_at", "revoked_at"),
    "payment": ("approved_at", "expires_at"),
}


def _timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value) if type(value) is str else value
        return aware(parsed)
    except (TypeError, ValueError):
        deny()


def project_private_buyer_status(
    *, bearer_token: str, hmac_key: bytes,
    read_by_fingerprint: Callable[[str], Mapping[str, Any] | None],
    approved_treasury: str,
    now: datetime,
) -> dict[str, Any]:
    """No public disclosure of raw join rows; only the existing safe projector."""
    digest = fingerprint(bearer_token, hmac_key)
    if not callable(read_by_fingerprint):
        deny()
    # The database receives a keyed digest, never the raw buyer bearer.
    try:
        record = read_by_fingerprint(digest)
    except Exception:
        raise BuyerAccessDenied("payment_status_unavailable") from None
    if not isinstance(record, Mapping) or set(record) != {
        "access", "order", "payment", "evidence"
    }:
        deny()
    access = record.get("access")
    order = record.get("order")
    payment = record.get("payment")
    evidence = record.get("evidence")
    if not isinstance(access, Mapping) or not isinstance(order, Mapping):
        deny()
    if payment is not None and not isinstance(payment, Mapping):
        deny()
    if evidence is not None and not isinstance(evidence, Mapping):
        deny()
    access = dict(access)
    payment = dict(payment) if payment is not None else None
    for field in TIME_FIELDS["access"]:
        if field not in access:
            deny()
        access[field] = _timestamp(access[field])
    if payment is not None:
        for field in TIME_FIELDS["payment"]:
            if field not in payment:
                deny()
            payment[field] = _timestamp(payment[field])
    return project_status(
        token=bearer_token,
        key=hmac_key,
        access=access,
        order=order,
        payment=payment,
        evidence=evidence,
        treasury=approved_treasury,
        now=now,
    )


class PrivateBuyerStatusPostgresReader:
    """Dedicated, unconnected-at-import, read-only DB transport.

    This is NOT connected to the public app. Credentials and login-role
    membership require future founder approvals and separate verification.
    """

    def __init__(
        self, dsn: str, *,
        connect_factory: Callable[..., Any] | None = None,
    ):
        if not isinstance(dsn, str) or not dsn.strip():
            deny()
        # Even in offline tests we refuse to reuse the general app DSN.
        app_dsn = os.getenv("EMPIREDB_DSN")
        if app_dsn and dsn.strip() == app_dsn.strip():
            deny()
        self._dsn = dsn.strip()
        if connect_factory is None:
            import psycopg
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, digest: str) -> Mapping[str, Any] | None:
        from empire_os.direct_bsc_buyer_status import HEX_RE
        if not isinstance(digest, str) or HEX_RE.fullmatch(digest) is None:
            deny()
        try:
            with self._connect(self._dsn) as connection:
                with connection.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
                    cur.execute("SET LOCAL statement_timeout='2500ms'")
                    cur.execute("SET LOCAL ROLE " + READER_ROLE)
                    cur.execute(READ_SQL, (digest,))
                    row = cur.fetchone()
        except Exception:
            raise BuyerAccessDenied("payment_status_unavailable") from None
        if row is None or len(row) != 1:
            deny()
        return row[0]
