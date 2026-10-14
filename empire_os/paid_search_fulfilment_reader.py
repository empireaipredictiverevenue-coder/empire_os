"""Bounded existing-role EmpireDB readback for one paid-search order.

Financially sensitive: never output returned rows to a public channel or logs.
No database writes, transaction approval, fresh on-chain assertion or customer
delivery. Requires existing dedicated revenue-recognizer DSN and existing RLS.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID

ROLE="empire_revenue_recognizer"
DATABASE="empiredb"
SETUP=(
    "SET TRANSACTION READ ONLY",
    "SET LOCAL statement_timeout = '4000ms'",
    "SET LOCAL ROLE "+ROLE,
)
IDENTITY_SQL="SELECT current_database(), current_user, pg_is_in_recovery()"
ORDER_SQL="""
SELECT pg_catalog.jsonb_build_object(
    'id',o.id,'buyer_id',o.buyer_id,'state',o.state,
    'price_cents',o.price_cents,
    'commercial_payload',pg_catalog.jsonb_build_object(
      'product_code',o.commercial_payload->>'product_code',
      'buyer_terms_accepted',
        CASE WHEN o.commercial_payload->>'buyer_terms_accepted'='true'
             THEN true ELSE false END,
      'commercial_terms_sha256',o.commercial_payload->>'commercial_terms_sha256',
      'payer_wallet',o.commercial_payload->>'payer_wallet',
      'settlement_mode',o.commercial_payload->>'settlement_mode'),
    'delivery_payload',pg_catalog.jsonb_build_object(
      'target_domain',o.delivery_payload->>'target_domain')
) FROM public.fulfilment_orders o
WHERE o.id=%s::uuid LIMIT 2
"""
PAYMENT_SQL="""
SELECT pg_catalog.jsonb_build_object(
  'id',p.id,'buyer_id',p.buyer_id,
  'fulfilment_order_id',p.fulfilment_order_id,
  'settlement_mode',p.settlement_mode,
  'commercial_terms_sha256',p.commercial_terms_sha256,
  'payer_address',p.payer_address,'treasury_address',p.treasury_address,
  'amount_usdt',p.amount_usdt::text,'status',p.status,
  'approved_by',p.approved_by,'approved_at',p.approved_at,
  'expires_at',p.expires_at)
FROM public.bsc_payment_requests p
WHERE p.fulfilment_order_id=%s::uuid AND p.settlement_mode='direct'
ORDER BY p.created_at DESC,p.id LIMIT 2
"""
EVIDENCE_SQL="""
SELECT pg_catalog.jsonb_build_object(
  'id',e.id,'request_id',e.request_id,
  'fulfilment_order_id',e.fulfilment_order_id,'chain_id',e.chain_id,
  'token_contract',e.token_contract,'transaction_hash',e.transaction_hash,
  'block_hash',e.block_hash,'block_number',e.block_number,
  'log_index',e.log_index,'amount_raw',e.amount_raw::text,
  'confirmations',e.confirmations,'verified_at',e.verified_at,
  'sender_address',e.sender_address,
  'treasury_address',e.treasury_address,
  'commercial_terms_sha256',e.commercial_terms_sha256)
FROM public.bsc_payment_evidence e
WHERE e.request_id=%s::uuid LIMIT 2
"""


class PaidOrderReadbackHold(RuntimeError):
    """Redacted fail-closed readiness, never include financial row data."""


def _uuid(value: Any) -> str:
    try:
        canonical=str(UUID(str(value)))
        if not isinstance(value,str) or value!=canonical:
            raise ValueError("not canonical")
        return canonical
    except (TypeError,ValueError,AttributeError):
        raise PaidOrderReadbackHold("invalid canonical order identity") from None


def _unique(cur: Any, query: str, identity: str) -> dict[str,Any] | None:
    cur.execute(query,(identity,))
    rows=cur.fetchall()
    if not isinstance(rows,list) or len(rows)>1:
        raise PaidOrderReadbackHold("ambiguous canonical readback")
    if not rows:
        return None
    if not isinstance(rows[0],tuple) or len(rows[0])!=1 or not isinstance(rows[0][0],Mapping):
        raise PaidOrderReadbackHold("invalid canonical readback")
    return dict(rows[0][0])


class PaidOrderReadOnlyReader:
    """Use only an existing dedicated revenue-recognizer connection/login.

    No service-role fallback; no personal Gmail, no buyer bearer/token lookup.
    This does not check fresh RPC chain consensus and never accepts payment
    proof directly from a buyer: caller supplies a DB-confirmed request ID.
    """
    def __init__(
        self, dsn: str, *,
        connect_factory: Callable[..., Any] | None = None,
    ):
        self._dsn=str(dsn or "").strip()
        if not self._dsn:
            raise PaidOrderReadbackHold("dedicated recognizer DSN required")
        if connect_factory is None:
            import psycopg
            connect_factory=psycopg.connect
        self._connect=connect_factory

    def __call__(self, order_id: str) -> dict[str,Any]:
        oid=_uuid(order_id)
        try:
            with self._connect(self._dsn) as connection:
                with connection.cursor() as cur:
                    for statement in SETUP:
                        cur.execute(statement)
                    cur.execute(IDENTITY_SQL)
                    if cur.fetchone()!=(DATABASE,ROLE,False):
                        raise PaidOrderReadbackHold("canonical database role unavailable")
                    order=_unique(cur,ORDER_SQL,oid)
                    if order is None:
                        raise PaidOrderReadbackHold("order unavailable")
                    payment=_unique(cur,PAYMENT_SQL,oid)
                    evidence=None
                    if payment is not None:
                        rid=_uuid(payment.get("id"))
                        evidence=_unique(cur,EVIDENCE_SQL,rid)
                    connection.rollback()
        except PaidOrderReadbackHold:
            raise
        except Exception:
            raise PaidOrderReadbackHold("dedicated canonical readback unavailable") from None
        return {"order":order,"payment":payment,"evidence":evidence}

    def review_order(
        self, order_id: str, *,
        report_evidence: Mapping[str,Any] | None = None,
        solar_payload: Mapping[str,Any] | None = None,
    ) -> dict[str,Any]:
        """Explicit offline review of one canonical readback.

        Read-only data access does not attest to fresh on-chain consensus or
        the truth of caller-provided search-report evidence. Human review is
        mandatory even for a completed, evidence-matched report.
        """
        from empire_os.paid_search_fulfilment_review import review_paid_search_order
        return review_paid_search_order(
            **self(order_id),
            report_evidence=report_evidence,
            solar_payload=solar_payload,
        )
