"""Isolated direct-USDT buyer status issuance coordinator; never an API route.

No mail, payment, orders, database credentials or live checkout activation.
The caller must authorise the recipient privately and persist a one-way token
fingerprint transactionally *before* delivering the bearer exactly once.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
import hmac
import os
from typing import Any

from empire_os.direct_bsc_buyer_status import (
    BuyerAccessDenied, aware, deny, issue, uid, HEX_RE,
)

ISSUER_ROLE = "empire_direct_checkout_status_issuer"
ISSUER_SQL = "SELECT public.issue_direct_bsc_buyer_status(%s,%s,%s,%s,%s)"
ISSUER_DSN_ENV = "EMPIRE_DIRECT_BSC_STATUS_ISSUER_DSN"
MAX_TTL = timedelta(hours=2)


def mint_private_buyer_access(
    *, approved_order_id: str, approved_request_id: str, hmac_key: bytes,
    payment_request: Mapping[str, Any], persist: Callable[[dict[str, Any]], Any],
    now: datetime, ttl: timedelta = MAX_TTL,
) -> str:
    """Return bearer only following successful, exact, committed persistence.

    Only a prior authenticated operator may supply an approved request;
    this module never asserts recipient authentication or sends mail.
    """
    try:
        issued = aware(now)
        oid = uid(approved_order_id)
        rid = uid(approved_request_id)
        if not isinstance(payment_request, Mapping) or not callable(persist):
            deny()
        if (uid(payment_request.get("id")) != rid or
            uid(payment_request.get("fulfilment_order_id")) != oid or
            payment_request.get("settlement_mode") != "direct" or
            payment_request.get("status") != "pending"):
            deny()
        deadline = aware(payment_request.get("expires_at"))
        created = aware(payment_request.get("created_at"))
        if (type(ttl) is not timedelta or ttl <= timedelta(0) or
            ttl > MAX_TTL or not created <= issued < deadline):
            deny()
        expiry = min(issued + ttl, deadline)
        # Issue has its own stronger 48h hard limit and CSPRNG checks.
        result = issue(key=hmac_key, order_id=oid,
                       now=issued, expires_at=expiry)
        saved = result["persist_only"]
        payload = {
            "token_fingerprint": saved["token_fingerprint"],
            "fulfilment_order_id": oid,
            "request_id": rid,
            "issued_at": saved["issued_at"],
            "expires_at": saved["expires_at"],
        }
        # A single DB transaction must commit the insert. Any exception
        # discards this freshly generated bearer, never logs it.
        response = persist(payload)
        if (not isinstance(response, Mapping) or
            response.get("decision") != "created" or
            not isinstance(response.get("token_fingerprint"), str) or
            not HEX_RE.fullmatch(response["token_fingerprint"]) or
            not hmac.compare_digest(response["token_fingerprint"],
                                    payload["token_fingerprint"])):
            deny()
        return result["deliver_token_once"]
    except Exception:
        raise BuyerAccessDenied("payment_status_unavailable") from None


class PrivateBuyerIssuerPostgresWriter:
    """No autoconfiguration, distinct connection and role, no arbitrary SQL."""
    def __init__(self, dsn: str, *, connect_factory: Callable | None = None):
        if not isinstance(dsn, str) or not dsn.strip() or (
            os.getenv("EMPIREDB_DSN") and
            dsn.strip() == os.getenv("EMPIREDB_DSN", "").strip()
        ):
            deny()
        self._dsn = dsn.strip()
        if connect_factory is None:
            import psycopg
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, params: dict[str, Any]) -> Mapping[str, Any]:
        expected = {"token_fingerprint","fulfilment_order_id","request_id",
                    "issued_at","expires_at"}
        if not isinstance(params, dict) or set(params) != expected:
            deny()
        digest = params["token_fingerprint"]
        if not isinstance(digest, str) or HEX_RE.fullmatch(digest) is None:
            deny()
        try:
            uid(params["fulfilment_order_id"])
            uid(params["request_id"])
            issued = aware(params["issued_at"])
            expiry = aware(params["expires_at"])
            if not issued < expiry <= issued + MAX_TTL:
                deny()
            with self._connect(self._dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout='2500ms'")
                    cur.execute("SET LOCAL ROLE " + ISSUER_ROLE)
                    cur.execute(ISSUER_SQL, (
                        digest,params["fulfilment_order_id"],
                        params["request_id"],issued,expiry,
                    ))
                    row = cur.fetchone()
                # Transaction MUST successfully commit on leaving context.
            if row is None or len(row) != 1:
                deny()
            return row[0]
        except Exception:
            raise BuyerAccessDenied("payment_status_unavailable") from None
