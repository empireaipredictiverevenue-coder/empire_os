"""Restricted owner-side adapter for existing native EmpireDB BSC seat receipts.

This is a bounded SELECT-only contract, not a new access role. The caller must
already hold independent service/tenant authorisation; that cannot be inferred
from accepting a Python object. Results remain NOT AUTHENTICATED because proof
of role/RLS, chain finality and source provenance is not established here.

No generic SQL, no unbounded scans, no raw source/PII output, no payments,
entitlement state changes, CRM mutation or outbound action.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol
from uuid import UUID

from empire_os.data_cloud_contract import DataBackend
from empire_os.exchange_seat_payment_receipt_review_v1 import (
    review_exchange_membership_payment_join,
)

SCHEMA="empire.exchange.seat_native_owner_reader.v1"
# Select least-privilege only. Do not request buyers.email/contact or raw
# customer-profile fields, even if the invoking credential could read them.
COLUMNS={
    "buyers": "id,org_id,commercial_activation_state",
    "fulfilment_orders": "id,buyer_id,state,quantity,price_cents,commercial_payload",
    "bsc_payment_requests": (
        "id,buyer_id,fulfilment_order_id,status,approved_by,approved_at,"
        "expires_at,commercial_terms_sha256,amount_usdt,min_block_number,"
        "payer_address,treasury_address,settlement_mode"
    ),
    "bsc_payment_evidence": (
        "request_id,fulfilment_order_id,chain_id,token_contract,"
        "transaction_hash,block_number,amount_raw,confirmations,verified_at,"
        "commercial_terms_sha256,sender_address,treasury_address"
    ),
}


class OwnerReader(Protocol):
    @property
    def backend(self) -> DataBackend: ...
    @property
    def configured(self) -> bool: ...
    def select(
        self,table:str,columns:str="*",filters:Mapping[str,object]|None=None,
        order:str|None=None,limit:int=1000,offset:int=0,
    ) -> list[dict[str,Any]]: ...


def _valid_uuid(value:Any) -> bool:
    if type(value) is not str:
        return False
    try:
        return str(UUID(value))==value
    except ValueError:
        return False


def _hold(reason:str,*,read_count:int=0)->dict[str,Any]:
    return {
        "schema_version":SCHEMA,
        "state":"HOLD",
        "reason":reason,
        "source_tables_queried_count":read_count,
        "root_owner_identity_and_rls_proven":False,
        "canonical_rows_independently_authenticated":False,
        "seat_subscription_authorized":False,
        "recognized_mrr_cents":0,
        "bsc_payment_recorded":False,
        "native_checkout_mutated":False,
        "customer_details_emitted":False,
        "payment_wallets_or_transactions_emitted":False,
        "lead_delivery_authorized":False,
        "outbound_sent":0,
        "database_writes":False,
        "execution_authority":"none",
    }


def review_native_exchange_seat_by_order(
    reader:OwnerReader|None,
    *,
    order_id:str,
    buyer_id:str,
    expected_tenant_id:str,
    private_finance_quote:Mapping[str,Any]|None,
    read_intent_approved:bool=False,
    now=None,
)->dict[str,Any]:
    """Read exact native chain of existing rows for owner REVIEW only.

    read_intent_approved is a local invocation switch, **not** authorization.
    RLS, tenant session and database grants must be independently enforced in
    the owner transport, and this never returns actual MRR or entitlement.
    """
    if read_intent_approved is not True:
        return _hold("explicit_owner_read_intent_not_provided")
    if not all(_valid_uuid(i) for i in (order_id,buyer_id,expected_tenant_id)):
        return _hold("untrusted_exact_canonical_identity")
    if not isinstance(private_finance_quote,Mapping):
        return _hold("private_finance_quote_not_provided")
    if reader is None:
        return _hold("no_authorised_owner_reader")
    try:
        canonical_reader = (
            reader.backend is DataBackend.EMPIREDB and reader.configured is True
        )
    except Exception:
        # Provider errors must not echo DSNs, credentials or SQL context.
        return _hold("owner_reader_configuration_unavailable")
    if not canonical_reader:
        return _hold("canonical_empiredb_owner_reader_not_configured")
    read_count=0

    def _one(table:str, filter_column:str, identity:str)->dict[str,Any]:
        nonlocal read_count
        # Prevent broad reads even with a privileged injected mock/transport.
        results=reader.select(
            table,
            columns=COLUMNS[table],
            filters={filter_column:identity},
            order=None,limit=2,offset=0,
        )
        read_count+=1
        if not isinstance(results,list) or len(results)!=1 or not isinstance(results[0],Mapping):
            raise ValueError("missing_or_ambiguous_native_row")
        row=dict(results[0])
        # Never persist or emit full rows; keep only within the call frame.
        if row.get(filter_column)!=identity:
            raise ValueError("misrouted_owner_exact_read")
        return row
    try:
        buyer=_one("buyers","id",buyer_id)
        if (buyer.get("org_id")!=expected_tenant_id
                or buyer.get("commercial_activation_state")!="activated"):
            return _hold("buyer_tenant_or_activation_not_authoritative",read_count=read_count)
        order=_one("fulfilment_orders","id",order_id)
        if order.get("buyer_id")!=buyer_id:
            return _hold("order_buyer_identity_mismatch",read_count=read_count)
        payment=_one("bsc_payment_requests","fulfilment_order_id",order_id)
        if payment.get("buyer_id")!=buyer_id:
            return _hold("request_buyer_mismatch",read_count=read_count)
        request_id=payment.get("id")
        if not _valid_uuid(request_id):
            return _hold("request_identity_invalid",read_count=read_count)
        evidence=_one("bsc_payment_evidence","request_id",request_id)
        result=review_exchange_membership_payment_join(
            order=order,request=payment,evidence=evidence,
            finance_quote=private_finance_quote,now=now,
        )
    except Exception:
        # Driver exceptions may embed DSNs or SQL values. Never serialize them.
        return _hold("native_owner_read_missing_ambiguous_or_unavailable",read_count=read_count)

    return {
        "schema_version":SCHEMA,
        "state":(
            "OWNER_READ_RECEIPT_SHAPE_REVIEW_ONLY"
            if result["state"]=="CROSS_TABLE_PAYMENT_RECEIPT_SHAPE_CONSISTENT_NOT_AUTHENTICATED"
            else "HOLD"
        ),
        "source_tables_queried_count":read_count,
        "source_tables_allowed_only":True,
        "receipt_join_review":result,
        "root_owner_identity_and_rls_proven":False,
        "canonical_rows_independently_authenticated":False,
        "seat_subscription_authorized":False,
        "recognized_mrr_cents":0,
        "bsc_payment_recorded":False,
        "native_checkout_mutated":False,
        "customer_details_emitted":False,
        "payment_wallets_or_transactions_emitted":False,
        "lead_delivery_authorized":False,
        "outbound_sent":0,
        "database_writes":False,
        "execution_authority":"none",
    }
