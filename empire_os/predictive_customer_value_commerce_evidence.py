"""Read-only source-owner commerce evidence join for Predictive value experiments.

Product orders, paid app renewals, service bookings and licensed data charges
become *typed, reversals-aware owner claims* bound to an original pilot design.
No caller-provided dict can authenticate payment, customer identity, registry,
tax/accounting revenue, a forecast or a measured time/money benefit.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence
import re

from empire_os.predictive_customer_value_demand import _time
from empire_os.predictive_customer_value_pilot_preflight import SCHEMA as PILOT_SCHEMA

SCHEMA = "empire.predictive.customer_value_commerce_evidence.v1"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CURRENCIES = frozenset(("USD", "GBP", "EUR"))
OWNER = {
    "product": "commerce_orders",
    "app": "app_subscription_billing",
    "service": "service_booking_billing",
    "data_product": "licensed_data_billing",
}
LIFECYCLE = {
    "product": frozenset(("paid","fulfilled","returned","refunded","charged_back","cancelled")),
    "app": frozenset(("paid","renewed","refunded","charged_back","cancelled")),
    "service": frozenset(("booked","paid","fulfilled","refunded","charged_back","cancelled")),
    "data_product": frozenset(("paid","renewed","refunded","charged_back","cancelled")),
}
CHARGE = frozenset(("paid", "renewed"))
REVERSAL = frozenset(("refunded", "charged_back"))
NO_MONEY = frozenset(("booked", "fulfilled", "returned", "cancelled"))
FIELDS = frozenset((
    "tenant_ref_sha256", "opportunity_key", "pilot_design_sha256",
    "product_type", "source_owner", "source_event_sha256", "purchase_ref_sha256",
    "lifecycle", "event_at", "evidence_available_at", "currency",
    "amount_minor", "variable_cost_minor", "reuse_scope", "evidence_status",
))
MAX_RECEIPTS = 250
MAX_MINOR = 10_000_000_000
REUSE_SCOPE = "INTERNAL_AGGREGATE_RESEARCH_ONLY"


def _nonnegative_minor(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= MAX_MINOR:
        raise ValueError("amount must be nonnegative bounded minor currency units")
    return value


def _validated_pilot(pilot: Mapping[str, Any], now: datetime) -> tuple[datetime,datetime]:
    if (not isinstance(pilot, Mapping)
            or pilot.get("schema_version") != PILOT_SCHEMA
            or pilot.get("status") != "PROSPECTIVE_VALUE_PILOT_DESIGN_UNREGISTERED"
            or pilot.get("prospective_design_durably_registered") is not False
            or pilot.get("original_quant_forecast_registered") is not False
            or pilot.get("customer_outcomes_collected") is not False
            or pilot.get("customer_savings_verified") is not False
            or pilot.get("execution_authority") != "none"):
        raise ValueError("original pilot source cannot assert registered or verified authority")
    design_sha = pilot.get("design_revision_sha256")
    if not isinstance(design_sha, str) or not SHA256.fullmatch(design_sha):
        raise ValueError("bounded original pilot design revision required")
    start = _time(pilot.get("planned_pilot_start_at"))
    end = _time(pilot.get("planned_pilot_end_at"))
    if not start < end <= start + timedelta(days=90):
        raise ValueError("invalid original prospective pilot clock")
    return start, end


def review_customer_value_commerce_evidence(
    pilot: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]], *,
    tenant_ref_sha256: str,
    as_of: datetime,
) -> dict[str, Any]:
    """Bounded review of owner-supplied claims; no receipt truth promotion."""
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted aware observation clock required")
    now = as_of.astimezone(timezone.utc)
    if not isinstance(tenant_ref_sha256, str) or not SHA256.fullmatch(tenant_ref_sha256):
        raise ValueError("opaque tenant custody reference required")
    start, end = _validated_pilot(pilot, now)
    if (not isinstance(receipts, (list, tuple)) or len(receipts) > MAX_RECEIPTS
            or any(not isinstance(event, Mapping) for event in receipts)):
        raise ValueError("bounded typed owner source receipts required")

    observed: set[str] = set()
    classified = Counter()
    charges: dict[tuple[str,str], dict[str, Any]] = {}
    reversals: list[tuple[tuple[str,str], datetime, int]] = []
    distinct_currencies: set[str] = set()
    reported_charged = 0
    reported_reversed = 0
    reported_variable_cost = 0
    inferred_event_kinds = defaultdict(Counter)

    for event in receipts:
        if set(event) != FIELDS:
            raise ValueError("exact, privacy-scoped owner evidence fields required")
        if event["tenant_ref_sha256"] != tenant_ref_sha256:
            raise ValueError("cross-tenant receipt leakage blocked")
        if (event["opportunity_key"] != pilot.get("opportunity_key")
                or event["pilot_design_sha256"] != pilot["design_revision_sha256"]):
            raise ValueError("original opportunity or pilot design revision drift")
        product_type = event["product_type"]
        if not isinstance(product_type, str) or product_type not in OWNER:
            raise ValueError("unsupported purchase class")
        if event["source_owner"] != OWNER[product_type]:
            raise ValueError("source-owner and purchase class do not agree")
        if (not isinstance(event["lifecycle"],str)
                or event["lifecycle"] not in LIFECYCLE[product_type]):
            raise ValueError("unsupported lifecycle transition for purchase class")
        if (event["reuse_scope"] != REUSE_SCOPE
                or event["evidence_status"] != "SOURCE_OWNER_REPORTED_UNAUTHENTICATED"):
            raise ValueError("owner claim must not elevate evidence or processing rights")
        for field in ("source_event_sha256", "purchase_ref_sha256"):
            token = event[field]
            if not isinstance(token, str) or not SHA256.fullmatch(token):
                raise ValueError("hashed owner event and purchase references required")
        if event["source_event_sha256"] in observed:
            raise ValueError("replayed event ID; no independent dedup authority")
        observed.add(event["source_event_sha256"])
        currency = event["currency"]
        if not isinstance(currency, str) or currency not in CURRENCIES:
            raise ValueError("unsupported unconverted currency")
        distinct_currencies.add(currency)
        if len(distinct_currencies) > 1:
            raise ValueError("mixed currency aggregation requires authenticated FX")
        amount = _nonnegative_minor(event["amount_minor"])
        variable_cost = _nonnegative_minor(event["variable_cost_minor"])
        life = event["lifecycle"]
        timestamp = _time(event["event_at"])
        available = _time(event["evidence_available_at"])
        # Refunds and returns may settle after the originally planned trial;
        # that fact cannot silently change the original forecast horizon.
        upper = end + timedelta(days=30) if life in (REVERSAL | frozenset(("returned","cancelled"))) else end
        if not start <= timestamp <= upper or not timestamp <= available <= now:
            raise ValueError("out-of-cohort or future observation/evidence")
        if life in CHARGE and amount <= 0:
            raise ValueError("paid event requires a positive price")
        if life in REVERSAL and amount <= 0:
            raise ValueError("a reversal must state the amount actually reversed")
        if life in NO_MONEY and amount != 0:
            raise ValueError("booking/return/cancellation alone is not a payment")
        if life not in CHARGE and variable_cost != 0:
            raise ValueError("unproven variable costs must attach only to purchase event")
        ref = (product_type, event["purchase_ref_sha256"])
        if life in CHARGE:
            if ref in charges:
                raise ValueError("duplicate paid transaction reference or renewal period")
            charges[ref] = {"amount": amount, "time": timestamp, "currency": currency}
            reported_charged += amount
            reported_variable_cost += variable_cost
        if life in REVERSAL:
            reversals.append((ref, timestamp, amount))
            reported_reversed += amount
        classified[life] += 1
        inferred_event_kinds[product_type][life] += 1

    reversed_by_purchase = Counter()
    for ref, reversal_at, amount in reversals:
        if ref not in charges or reversal_at < charges[ref]["time"]:
            raise ValueError("unanchored or pre-payment refund / chargeback")
        reversed_by_purchase[ref] += amount
        if reversed_by_purchase[ref] > charges[ref]["amount"]:
            raise ValueError("cumulative refunds exceed original paid amount")

    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "OWNER_REPORTED_COMMERCE_EVIDENCE_RECONCILED_UNAUTHENTICATED",
        "original_pilot_design_revision_matched": True,
        "pilot_design_durably_registered": False,
        "original_quant_forecast_registered": False,
        "original_forecast_issued_before_outcome_proven": False,
        "tenant_authentication_proven": False,
        "source_owner_authentication_proven": False,
        "transaction_set_complete": False,
        "refund_window_complete": False,
        "original_source_records_independently_authenticated": False,
        "source_event_count": len(receipts),
        "claimed_paid_event_count": sum(classified[k] for k in CHARGE),
        "claimed_booked_not_paid_count": classified["booked"],
        "claimed_return_count": classified["returned"],
        "claimed_cancelled_count": classified["cancelled"],
        "claimed_reversal_count": sum(classified[k] for k in REVERSAL),
        "event_counts_by_purchase_class": {
            group: dict(sorted(inferred_event_kinds[group].items()))
            for group in OWNER
        },
        "source_reported_currency": next(iter(distinct_currencies)) if distinct_currencies else None,
        "source_reported_gross_minor_unverified": reported_charged if receipts else None,
        "source_reported_reversals_minor_unverified": reported_reversed if receipts else None,
        "source_reported_variable_cost_minor_unverified": reported_variable_cost if receipts else None,
        "source_reported_net_after_reversals_and_variable_cost_minor_unverified": (
            reported_charged - reported_reversed - reported_variable_cost if receipts else None
        ),
        "verified_paid_orders": None,
        "verified_subscriptions": None,
        "verified_service_revenue": None,
        "verified_customer_savings": None,
        "recognized_revenue_minor": None,
        "quant_calibration_ready": False,
        "economic_memory_outcome_write": False,
        "new_customer_contact": False,
        "next_owner": "commerce_app_service_source_owner_and_original_quant_registry",
        "next_action": "AUTHENTICATE_SOURCE_EVENTS_REFUNDS_TENANT_AND_PRE_OUTCOME_REGISTERED_FORECAST",
        "database_writes": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }
