"""Evidence-bound, offline first-sale report review.

Combines existing search-report builder with exact DIRECT BSC payment/order
contract. Consumes caller-supplied CANONICAL readbacks, never queries,
changes or trusts production DB by itself. Never sends reports, flips
fulfilment states, or recognizes revenue. A READY_FOR_REVIEW packet is not
permission to deliver; independent origin checks and human signoff remain.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Mapping
from urllib.parse import urlsplit
from uuid import UUID

from empire_os.bsc_usdt_verifier import BSC_USDT_CONTRACT
from empire_os.search_intelligence.products import get_search_product
from empire_os.search_intelligence.reports import build_search_product_report

ALLOWED=frozenset({
    "competitor_search_gap",
    "search_opportunity_map",
    "technical_search_audit",
    "solar_opportunity_map_us",
})
TREASURY="0x1339b487046b0ad924a10c20b1791608ea8595a8"
HEX64=re.compile(r"^[0-9a-f]{64}$")
ADDR=re.compile(r"^0x[0-9a-f]{40}$")
TX=re.compile(r"^0x[0-9a-f]{64}$")
DOMAIN=re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def _uuid(value: Any) -> str | None:
    try:
        normalized=str(UUID(str(value)))
        return normalized if normalized==value else None
    except (TypeError,ValueError,AttributeError):
        return None


def _when(value: Any) -> datetime | None:
    try:
        dt=(datetime.fromisoformat(value) if type(value) is str else value)
        if not isinstance(dt,datetime) or dt.tzinfo is None or dt.utcoffset() is None:
            return None
        return dt.astimezone(timezone.utc)
    except (TypeError,ValueError,OverflowError):
        return None


def _whole(value: Any) -> int | None:
    # Database NUMERIC can come back as Decimal or string; bool/float fail.
    if type(value) not in (str,int,Decimal):
        return None
    try:
        n=Decimal(str(value))
        if not n.is_finite() or n<0 or n!=n.to_integral_value():
            return None
        return int(n)
    except (InvalidOperation,ValueError,OverflowError):
        return None


def _domain(value: Any) -> str | None:
    if not isinstance(value,str) or not DOMAIN.fullmatch(value):
        return None
    return value


def _site_domain(value: Any) -> str | None:
    if not isinstance(value,str):
        return None
    try:
        parsed=urlsplit(value)
        if parsed.scheme not in ("http","https") or parsed.username or parsed.password:
            return None
        return _domain(parsed.hostname)
    except ValueError:
        return None


def _verified_payment(order: Mapping[str,Any], payment: Mapping[str,Any],
                      evidence: Mapping[str,Any], *, now: datetime) -> bool:
    oid=_uuid(order.get("id"))
    buyer=_uuid(order.get("buyer_id"))
    rid=_uuid(payment.get("id"))
    terms=(order.get("commercial_payload") or {})
    if (not oid or not buyer or not rid or not isinstance(terms,Mapping)
            or order.get("state") not in ("accepted","invoiced","delivered","confirmed")
            or payment.get("status")!="approved"
            or payment.get("settlement_mode")!="direct"
            or payment.get("fulfilment_order_id")!=oid
            or payment.get("buyer_id")!=buyer):
        return False
    cost=order.get("price_cents")
    sha=terms.get("commercial_terms_sha256")
    payer=str(terms.get("payer_wallet") or "").lower()
    if (type(cost) is not int or not 1<=cost<=29900
            or not isinstance(sha,str) or not HEX64.fullmatch(sha)
            or not ADDR.fullmatch(payer)
            or payment.get("commercial_terms_sha256")!=sha
            or str(payment.get("payer_address") or "").lower()!=payer
            or str(payment.get("treasury_address") or "").lower()!=TREASURY):
        return False
    try:
        amount=Decimal(str(payment.get("amount_usdt")))
        if not amount.is_finite() or amount!=Decimal(cost)/100:
            return False
    except (InvalidOperation,ValueError,TypeError):
        return False
    approved=_when(payment.get("approved_at"))
    verified=_when(evidence.get("verified_at"))
    expires=_when(payment.get("expires_at"))
    if (not approved or not verified or not expires
            or not approved<=verified<=now
            or not approved<expires or verified>expires
            or not isinstance(payment.get("approved_by"),str)
            or not payment["approved_by"].strip()):
        return False
    return bool(
        _uuid(evidence.get("id")) is not None
        and evidence.get("request_id")==rid
        and evidence.get("fulfilment_order_id")==oid
        and evidence.get("chain_id")==56
        and str(evidence.get("token_contract") or "").lower()==BSC_USDT_CONTRACT
        and str(evidence.get("treasury_address") or "").lower()==TREASURY
        and str(evidence.get("sender_address") or "").lower()==payer
        and evidence.get("commercial_terms_sha256")==sha
        and type(evidence.get("confirmations")) is int
        and evidence["confirmations"]>=12
        and type(evidence.get("transaction_hash")) is str
        and TX.fullmatch(evidence["transaction_hash"]) is not None
        and type(evidence.get("block_hash")) is str
        and TX.fullmatch(evidence["block_hash"]) is not None
        and type(evidence.get("block_number")) is int
        and evidence["block_number"]>0
        and type(evidence.get("log_index")) is int
        and evidence["log_index"]>=0
        and _whole(evidence.get("amount_raw"))==cost*10**16
    )


def review_paid_search_order(*, order: Mapping[str,Any] | None,
                             payment: Mapping[str,Any] | None,
                             evidence: Mapping[str,Any] | None,
                             report_evidence: Mapping[str,Any] | None = None,
                             solar_payload: Mapping[str,Any] | None = None,
                             now: datetime | None = None) -> dict[str,Any]:
    """Review only; all caller records must come from separately verified readers."""
    result={
        "schema_version":"empire.checkout.paid-search-review.v1",
        "mode":"OFFLINE_REVIEW",
        "decision":"HOLD_ORDER",
        "delivery_authorized":False,
        "outbound_sent":False,
        "order_mutated":False,
        "payment_executed":False,
        "revenue_recognized":False,
        "report":None,
        "source_verified_by_this_function":False,
        "next_action":"VERIFY_CANONICAL_ORDER_AND_PAYMENT_RECORDS",
    }
    if not isinstance(order,Mapping) or not _uuid(order.get("id")):
        return result
    code=(order.get("commercial_payload") or {})
    if not isinstance(code,Mapping):
        return result
    sku=code.get("product_code")
    if type(sku) is not str or sku not in ALLOWED or code.get("buyer_terms_accepted") is not True:
        return result
    target=order.get("delivery_payload")
    if not isinstance(target,Mapping) or not _domain(target.get("target_domain")):
        return result
    site="https://"+target["target_domain"]
    if code.get("settlement_mode")!="direct":
        return result
    if not isinstance(payment,Mapping) or not isinstance(evidence,Mapping):
        result["decision"]="HOLD_CANONICAL_PAYMENT_EVIDENCE"
        return result
    current=now or datetime.now(timezone.utc)
    if not _when(current) or not _verified_payment(order,payment,evidence,now=current):
        result["decision"]="HOLD_CANONICAL_PAYMENT_EVIDENCE"
        return result
    result["payment_record_contract"]="MATCHED_FOR_REVIEW_ONLY"
    result["order_ref"]=_uuid(order["id"])
    result["payment_evidence_ref"]=_uuid(evidence.get("id"))
    result["payment_transaction_hash"]=evidence.get("transaction_hash")
    if sku=="solar_opportunity_map_us":
        result["decision"]="HOLD_SOLAR_ORDER_PROSPECT_BINDING"
        result["next_action"]="VERIFY_ORDER_LINK_TO_EXISTING_SOLAR_PROSPECT_ARTIFACT"
        if isinstance(solar_payload,Mapping):
            offer=solar_payload.get("offer")
            prospect=solar_payload.get("prospect")
            if (isinstance(offer,Mapping) and isinstance(prospect,Mapping)
                    and offer.get("product_code")==sku
                    and offer.get("country_code")=="US"
                    and _site_domain(prospect.get("website"))==target["target_domain"]):
                result["solar_artifact_matches_domain"]=True
        return result

    product=get_search_product(sku)
    if product is None:
        result["decision"]="HOLD_PRODUCT_REPORT_CONTRACT"
        return result
    if not isinstance(report_evidence,Mapping):
        result["decision"]="HOLD_OBSERVED_REPORT_EVIDENCE"
        return result
    observed={}
    for required in product.deliverables:
        record=report_evidence.get(required)
        if not isinstance(record,Mapping):
            result["decision"]="HOLD_OBSERVED_REPORT_EVIDENCE"
            return result
        refs=record.get("source_refs")
        stamp=_when(record.get("observed_at"))
        if (record.get("synthetic") is not False or
                not isinstance(refs,list) or not refs or
                any(not isinstance(x,str) or not x.strip() for x in refs) or
                stamp is None or stamp>current or
                "value" not in record or record["value"] in (None,"",[],{})):
            result["decision"]="HOLD_OBSERVED_REPORT_EVIDENCE"
            return result
        observed[required]={
            "value":record["value"],
            "source_refs":list(refs),
            "observed_at":stamp.isoformat(),
            "synthetic":False,
        }
    # Never invent findings: the existing report builder receives only
    # values with explicit, time-bound provenance for each required section.
    report=build_search_product_report(
        product_key=sku,site=site,generated_at=current.isoformat(),
        evidence=observed,
    )
    if (report["unavailable_sections"]!=0 or report["synthetic_metrics"]!=0):
        result["decision"]="HOLD_INCOMPLETE_PRODUCT_REPORT"
        return result
    result["report"]=report
    result["decision"]="READY_FOR_HUMAN_REPORT_REVIEW"
    result["next_action"]="VERIFY_SOURCE_RECORD_ORIGINS_AND_APPROVE_DELIVERY_SEPARATELY"
    return result
