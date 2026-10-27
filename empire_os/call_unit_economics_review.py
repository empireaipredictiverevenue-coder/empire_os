"""Cash-per-qualified-call research, for a provisional CRU-scoped workstream.

CRU's original expansion is UNCONFIRMED. Do not rename, activate or claim
a canonical CRU service. This pure review of unit economics is a useful
independent commercial dimension beside CRO, with owner-verified inputs only.
"""
from __future__ import annotations

from typing import Any

SCHEMA = "empire.commercial.call_unit_economics_review.v1"
REQUIRED_FIELDS = (
    "provider_connected_calls",
    "buyer_accepted_payable_calls",
    "independently_settled_calls",
    "bank_verified_cash_received_cents",
    "actual_paid_media_cost_cents",
    "actual_publisher_cost_cents",
    "actual_processing_cost_cents",
    "actual_refund_or_chargeback_cost_cents",
)
REQUIRED_RECEIPTS = (
    "buyer_call_disposition",
    "verified_bank_settlement",
    "paid_media_invoices",
    "publisher_cost_receipts",
    "processing_cost_receipts",
    "reversal_evidence",
)


def review_call_unit_economics(
    *,
    source_id: str,
    cohort_ref: str,
    currency: str,
    values: dict[str, int | None],
    receipt_refs: dict[str, str | None],
    source_attribution_verified: bool = False,
    independent_finance_verified: bool = False,
    same_cohort_verified: bool = False,
) -> dict[str, Any]:
    """Compute cash unit margin only when same-cohort, evidence-backed.

    Cash received here is already net of refunds embedded in remittances;
    chargeback_cost counts ONLY separately evidenced additional costs.
    Strictly no conversion of traffic projections into financial metrics.
    """
    if (not isinstance(source_id, str) or not source_id
            or len(source_id) > 80 or not source_id.replace("_", "").isalnum()
            or not isinstance(cohort_ref, str) or not 6 <= len(cohort_ref) <= 200
            or currency not in ("USD", "GBP")
            or not isinstance(values, dict) or set(values) != set(REQUIRED_FIELDS)
            or not isinstance(receipt_refs, dict)
            or set(receipt_refs) != set(REQUIRED_RECEIPTS)
            or any(type(x) is not bool for x in (
                source_attribution_verified, independent_finance_verified,
                same_cohort_verified
            ))):
        raise ValueError("invalid unit-economics source and contract")
    for key in REQUIRED_FIELDS:
        n = values[key]
        if n is not None and (type(n) is not int or n < 0):
            raise ValueError("invalid owner-observed unit economics count/cost")
    for key in REQUIRED_RECEIPTS:
        ref = receipt_refs[key]
        if ref is not None and (
            not isinstance(ref, str) or not 6 <= len(ref) <= 240
        ):
            raise ValueError("invalid unit economics evidence ref")
    connected, accepted, settled = (
        values[key] for key in REQUIRED_FIELDS[:3]
    )
    if (connected is not None and accepted is not None and accepted > connected
            or accepted is not None and settled is not None and settled > accepted):
        raise ValueError("commercial event reconciliation impossible")

    needed = all(values[key] is not None for key in REQUIRED_FIELDS)
    receipts = all(receipt_refs[key] for key in REQUIRED_RECEIPTS)
    valid_owner_authority = (
        source_attribution_verified and independent_finance_verified
        and same_cohort_verified and needed and receipts
        and settled is not None and settled > 0
    )
    received = values["bank_verified_cash_received_cents"] if valid_owner_authority else None
    actual_cost = (
        sum(values[key] for key in REQUIRED_FIELDS[4:]) if valid_owner_authority else None
    )
    net_cash = received - actual_cost if received is not None else None
    unit_margin = (
        round(net_cash / settled, 2)
        if net_cash is not None and settled else None
    )
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "source_id": source_id,
        "cohort_ref": cohort_ref,
        "currency": currency,
        "cru_acronym_expansion_confirmed": False,
        "cru_provisional_scope": "CALL_REVENUE_PER_UNIT_ECONOMICS_RESEARCH_ONLY",
        "source_attribution_verified": source_attribution_verified,
        "independent_finance_verified": independent_finance_verified,
        "same_cohort_verified": same_cohort_verified,
        "provider_connected_calls": connected if valid_owner_authority else None,
        "buyer_accepted_payable_calls": accepted if valid_owner_authority else None,
        "independently_settled_calls": settled if valid_owner_authority else None,
        "actual_cash_received_cents": received,
        "actual_cost_cents": actual_cost,
        "cash_margin_cents": net_cash,
        "cash_margin_per_settled_call_cents": unit_margin,
        "profitability_calibrated": valid_owner_authority,
        "missing_evidence_categories": [
            x for x, ready in (
                ("SOURCE_LINEAGE", source_attribution_verified),
                ("INDEPENDENT_FINANCE", independent_finance_verified),
                ("SAME_COHORT", same_cohort_verified),
                ("CANONICAL_COUNTS_COSTS", needed),
                ("OWNER_EVIDENCE_REFS", receipts),
                ("REAL_SETTLED_UNIT_COUNT", settled is not None and settled > 0),
            ) if not ready
        ],
        "synthetic_estimates_are_not_received_cash": True,
        "spend_approved": False,
        "payment_approved": False,
        "source_activated": False,
        "execution_authority": "none",
    }
