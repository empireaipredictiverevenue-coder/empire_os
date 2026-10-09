"""Canonical Revenue Capacity Board.

Read-only projection over existing EmpireOS commercial truth.

This module does not:
- recognize revenue;
- create commercial terms;
- price prospects;
- infer buyer capacity;
- authorize execution;
- mutate EmpireDB;
- convert pipeline into revenue truth.

Unknown stays unknown.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from empire_os.commercial_pricing_policy import (
    build_launch_pricing_proposal,
)
from empire_os.phase4_exchange_mrr_products import (
    build_exchange_mrr_product_plan,
)
from empire_os.revenue_command_queue import (
    build_revenue_command_queue_runtime,
)
from empire_os.revenue_pulse import (
    build_revenue_pulse_runtime,
)


SCHEMA_VERSION = "empire.revenue_capacity_board.v1"

TARGET_MRR_CENTS = (
    10_000_000,    # $100,000
    25_000_000,    # $250,000
    100_000_000,   # $1,000,000
)

RECURRING_BILLING_MODELS = {
    "monthly_subscription",
    "usage_and_subscription",
}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None

    try:
        number = int(value)
    except (TypeError, ValueError):
        return None

    return number if number >= 0 else None


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}

    return raw if isinstance(raw, dict) else {}


def _usd(cents: int | None) -> float | None:
    if cents is None:
        return None

    return round(cents / 100, 2)


def _catalog_rows(
    catalog: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    rows: dict[str, Mapping[str, Any]] = {}

    for raw in _list(catalog.get("products")):
        if not isinstance(raw, Mapping):
            continue

        code = str(
            raw.get("product_code") or ""
        ).strip()

        if code:
            rows[code] = raw

    return rows


def _pricing_rows(
    pricing: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    rows: dict[str, Mapping[str, Any]] = {}

    for raw in _list(pricing.get("products")):
        if not isinstance(raw, Mapping):
            continue

        code = str(
            raw.get("product_code") or ""
        ).strip()

        if code:
            rows[code] = raw

    return rows


def _extract_amount_cents(
    row: Mapping[str, Any],
) -> int | None:
    for key in (
        "amount_cents",
        "monthly_price_cents",
        "price_cents",
    ):
        value = _nonnegative_int(
            row.get(key)
        )

        if value is not None and value > 0:
            return value

    for key in (
        "price_basis",
        "pricing",
        "price",
    ):
        nested = _mapping(
            row.get(key)
        )

        value = _nonnegative_int(
            nested.get("amount_cents")
        )

        if value is not None and value > 0:
            return value

    return None


def _verified_catalog_price(
    row: Mapping[str, Any],
) -> tuple[int | None, str]:
    price_basis = _mapping(
        row.get("price_basis")
    )

    amount = _nonnegative_int(
        price_basis.get("amount_cents")
    )

    state = str(
        price_basis.get("state") or ""
    ).upper()

    if (
        amount is not None
        and amount > 0
        and state == "VERIFIED"
    ):
        return (
            amount,
            "canonical_catalog_verified_price",
        )

    return (
        None,
        "canonical_catalog_verified_price_unavailable",
    )


def _stage2_ready_codes(
    stage2: Mapping[str, Any],
) -> set[str]:
    return {
        str(code).strip()
        for code in _list(
            stage2.get(
                "campaign_ready_product_codes"
            )
        )
        if str(code).strip()
    }


def _catalog_sellable(
    row: Mapping[str, Any],
) -> bool:
    return (
        row.get("active") is True
        and row.get("binding_terms_ready") is True
        and str(
            row.get("catalog_state") or ""
        ).upper() == "VERIFIED"
        and str(
            row.get("version_state") or ""
        ).upper() == "VERIFIED"
    )


def _policy_billing_model(
    row: Mapping[str, Any],
) -> str:
    return str(
        row.get("billing_model")
        or row.get("pricing_model")
        or ""
    ).strip()


def _ceil_customers(
    target_cents: int,
    monthly_cents: int | None,
) -> int | None:
    if not monthly_cents:
        return None

    return math.ceil(
        target_cents / monthly_cents
    )


def _recurring_capacity(
    *,
    catalog: Mapping[str, Any],
    stage2: Mapping[str, Any],
    pricing: Mapping[str, Any],
) -> dict[str, Any]:
    catalog_by_code = _catalog_rows(
        catalog
    )
    pricing_by_code = _pricing_rows(
        pricing
    )
    ready = _stage2_ready_codes(
        stage2
    )

    sellable: list[dict[str, Any]] = []
    unpriced: list[str] = []

    for code in sorted(ready):
        catalog_row = catalog_by_code.get(
            code
        )

        pricing_row = pricing_by_code.get(
            code
        )

        if not catalog_row or not pricing_row:
            continue

        if not _catalog_sellable(
            catalog_row
        ):
            continue

        billing_model = _policy_billing_model(
            pricing_row
        )

        if billing_model not in RECURRING_BILLING_MODELS:
            continue

        amount_cents, price_state = (
            _verified_catalog_price(
                catalog_row
            )
        )

        if amount_cents is None:
            # Policy prices remain useful planning evidence,
            # but they are not silently promoted to a
            # verified catalog price.
            policy_amount = _extract_amount_cents(
                pricing_row
            )

            if policy_amount is not None:
                sellable.append({
                    "product_code": code,
                    "billing_model": billing_model,
                    "monthly_price_cents": policy_amount,
                    "monthly_price_usd": _usd(
                        policy_amount
                    ),
                    "price_state":
                        "PLANNING_POLICY_PRICE_ONLY",
                    "catalog_sellable": True,
                    "stage2_ready": True,
                    "binding_customer_terms_inferred": False,
                })
            else:
                unpriced.append(code)

            continue

        sellable.append({
            "product_code": code,
            "billing_model": billing_model,
            "monthly_price_cents": amount_cents,
            "monthly_price_usd": _usd(
                amount_cents
            ),
            "price_state": price_state,
            "catalog_sellable": True,
            "stage2_ready": True,
            "binding_customer_terms_inferred": False,
        })

    stack_cents = sum(
        int(
            row["monthly_price_cents"]
        )
        for row in sellable
        if _nonnegative_int(
            row.get("monthly_price_cents")
        )
    )

    cohorts = []

    for customers in (
        10,
        25,
        50,
        100,
        250,
        500,
    ):
        amount = (
            stack_cents * customers
        )

        cohorts.append({
            "customer_count": customers,
            "stack_mrr_cents": amount,
            "stack_mrr_usd": _usd(amount),
            "planning_only": True,
        })

    return {
        "stage2_ready_recurring_count":
            len(sellable),
        "products": sellable,
        "unpriced_ready_recurring_codes":
            unpriced,
        "one_of_each_stack_mrr_cents":
            stack_cents,
        "one_of_each_stack_mrr_usd":
            _usd(stack_cents),
        "cohort_scenarios": cohorts,
        "recognized_revenue_inferred":
            False,
    }


def _locked_exchange_capacity(
    *,
    catalog: Mapping[str, Any],
    exchange_plan: Mapping[str, Any],
) -> dict[str, Any]:
    catalog_by_code = _catalog_rows(
        catalog
    )

    products = []

    for raw in _list(
        exchange_plan.get("products")
    ):
        if not isinstance(raw, Mapping):
            continue

        code = str(
            raw.get("product_code") or ""
        ).strip()

        if not code:
            continue

        catalog_row = catalog_by_code.get(
            code,
            {},
        )

        amount = _nonnegative_int(
            raw.get(
                "monthly_price_cents"
            )
        )

        products.append({
            "product_code": code,
            "monthly_price_cents": amount,
            "monthly_price_usd": _usd(
                amount
            ),
            "catalog_state":
                catalog_row.get(
                    "catalog_state"
                ),
            "version_state":
                catalog_row.get(
                    "version_state"
                ),
            "binding_terms_ready":
                catalog_row.get(
                    "binding_terms_ready"
                ) is True,
            "scenario_only": True,
            "paying_customer_inferred": False,
        })

    return {
        "state":
            "LOCKED_UNTIL_COMMERCIAL_READINESS",
        "product_count": len(products),
        "products": products,
        "seat_records_counted_as_customers":
            False,
        "recognized_revenue_inferred":
            False,
    }


def _pipeline(
    queue: Mapping[str, Any],
) -> dict[str, Any]:
    items = [
        row
        for row in _list(
            queue.get("items")
        )
        if isinstance(row, Mapping)
    ]

    stages = Counter(
        str(
            row.get(
                "current_commercial_state"
            )
            or "UNKNOWN"
        )
        for row in items
    )

    product_bound = sum(
        bool(
            str(
                row.get("product_code")
                or ""
            ).strip()
        )
        and row.get(
            "offer_known"
        ) is True
        for row in items
    )

    return {
        "item_count": len(items),
        "stage_counts": dict(
            sorted(stages.items())
        ),
        "product_bound_offer_known_count":
            product_bound,
        "monetary_value_state":
            "UNKNOWN_NO_CANONICAL_PIPELINE_VALUE",
        "monetary_value_cents": None,
        "weighted_value_cents": None,
        "probability_inferred": False,
        "catalog_price_used_as_pipeline_value":
            False,
    }


def _account_product_capacity(
    offer_book: Mapping[str, Any],
) -> dict[str, Any]:
    """Expose verified product bindings without inventing pipeline revenue."""

    bindings: list[dict[str, Any]] = []
    account_names: set[str] = set()

    for row in _list(
        offer_book.get("offer_ready")
    ):
        if not isinstance(row, Mapping):
            continue

        company = str(
            row.get("company") or ""
        ).strip()

        if not company:
            continue

        ready_codes = {
            str(code).strip()
            for code in _list(
                row.get(
                    "ready_product_codes"
                )
            )
            if str(code).strip()
        }

        if not ready_codes:
            continue

        for product in _list(
            row.get("products")
        ):
            if not isinstance(
                product,
                Mapping,
            ):
                continue

            code = str(
                product.get(
                    "product_code"
                )
                or ""
            ).strip()

            if (
                not code
                or code
                not in ready_codes
            ):
                continue

            if (
                str(
                    product.get(
                        "catalog_state"
                    )
                    or ""
                ).upper()
                != "VERIFIED"
            ):
                continue

            if (
                str(
                    product.get(
                        "version_state"
                    )
                    or ""
                ).upper()
                != "VERIFIED"
            ):
                continue

            if (
                product.get(
                    "binding_terms_ready"
                )
                is not True
            ):
                continue

            amount_cents = (
                _extract_amount_cents(
                    product
                )
            )

            billing_model = str(
                product.get(
                    "billing_model"
                )
                or ""
            ).strip()

            recurring = (
                billing_model
                in RECURRING_BILLING_MODELS
            )

            bindings.append({
                "company":
                    company,
                "canonical_prospect_id":
                    row.get(
                        "canonical_prospect_id"
                    ),
                "person_name":
                    row.get(
                        "person_name"
                    ),
                "person_verified":
                    row.get(
                        "person_verified"
                    )
                    is True,
                "conversation_state":
                    row.get(
                        "conversation_state"
                    ),
                "commercial_role":
                    row.get(
                        "commercial_role"
                    ),
                "offer_state":
                    row.get(
                        "state"
                    ),
                "offer_package_ready":
                    row.get(
                        "offer_package_ready"
                    )
                    is True,
                "buyer_demand_verified":
                    row.get(
                        "buyer_demand_verified"
                    )
                    is True,
                "commercial_authority_verified":
                    row.get(
                        "commercial_authority_verified"
                    )
                    is True,
                "live_send_ready":
                    row.get(
                        "live_send_ready"
                    )
                    is True,
                "execution_authority":
                    row.get(
                        "execution_authority"
                    ),
                "product_code":
                    code,
                "billing_model":
                    billing_model,
                "catalog_price_cents":
                    amount_cents,
                "catalog_price_usd":
                    _usd(
                        amount_cents
                    ),
                "planning_mrr_cents": (
                    amount_cents
                    if recurring
                    else None
                ),
                "planning_mrr_usd": (
                    _usd(
                        amount_cents
                    )
                    if recurring
                    else None
                ),
                "value_classification":
                    "CATALOG_PLANNING_VALUE_NOT_ACCOUNT_COMMITMENT",
                "expected_revenue_cents":
                    row.get(
                        "expected_revenue_cents"
                    ),
                "send_blockers":
                    list(
                        _list(
                            row.get(
                                "send_blockers"
                            )
                        )
                    ),
                "evidence_refs":
                    list(
                        _list(
                            row.get(
                                "evidence_refs"
                            )
                        )
                    ),
                "recognized_revenue_inferred":
                    False,
                "committed_mrr_inferred":
                    False,
                "probability_inferred":
                    False,
            })

            account_names.add(
                company
            )

    planning_mrr = sum(
        int(
            row["planning_mrr_cents"]
        )
        for row in bindings
        if _nonnegative_int(
            row.get(
                "planning_mrr_cents"
            )
        )
    )

    return {
        "state":
            "EVIDENCE_BOUND_PLANNING_ONLY",
        "account_count":
            len(account_names),
        "binding_count":
            len(bindings),
        "bindings":
            bindings,
        "catalog_planning_mrr_if_one_unit_each_cents":
            planning_mrr,
        "catalog_planning_mrr_if_one_unit_each_usd":
            _usd(
                planning_mrr
            ),
        "pipeline_value_cents":
            None,
        "weighted_pipeline_value_cents":
            None,
        "committed_mrr_cents":
            None,
        "recognized_revenue_cents":
            None,
        "catalog_price_is_commitment":
            False,
        "catalog_price_is_pipeline_value":
            False,
        "planning_only":
            True,
    }


def _enterprise_locked_opportunities(
    *,
    enterprise_targets: Mapping[str, Any],
    catalog: Mapping[str, Any],
) -> dict[str, Any]:
    """Keep high-value hypotheses visible without promoting them to revenue."""

    catalog_by_code = _catalog_rows(
        catalog
    )

    rows: list[dict[str, Any]] = []

    for target in _list(
        enterprise_targets.get(
            "targets"
        )
    ):
        if not isinstance(
            target,
            Mapping,
        ):
            continue

        account = str(
            target.get(
                "account_name"
            )
            or ""
        ).strip()

        if not account:
            continue

        products = []

        for raw_code in _list(
            target.get(
                "target_product_codes"
            )
        ):
            code = str(
                raw_code
                or ""
            ).strip()

            if not code:
                continue

            catalog_row = (
                catalog_by_code.get(
                    code,
                    {},
                )
            )

            sellable = (
                bool(catalog_row)
                and _catalog_sellable(
                    catalog_row
                )
            )

            products.append({
                "product_code":
                    code,
                "catalog_present":
                    bool(
                        catalog_row
                    ),
                "catalog_state":
                    catalog_row.get(
                        "catalog_state"
                    ),
                "version_state":
                    catalog_row.get(
                        "version_state"
                    ),
                "binding_terms_ready":
                    catalog_row.get(
                        "binding_terms_ready"
                    )
                    is True,
                "currently_sellable":
                    sellable,
            })

        if not products:
            continue

        all_sellable = all(
            row.get(
                "currently_sellable"
            )
            is True
            for row in products
        )

        rows.append({
            "account_key":
                target.get(
                    "account_key"
                ),
            "account_name":
                account,
            "account_type":
                target.get(
                    "account_type"
                ),
            "fit_classification":
                target.get(
                    "fit_classification"
                ),
            "evidence_classification":
                target.get(
                    "evidence_classification"
                ),
            "target_roles":
                list(
                    _list(
                        target.get(
                            "target_roles"
                        )
                    )
                ),
            "observed_scale":
                list(
                    _list(
                        target.get(
                            "observed_scale"
                        )
                    )
                ),
            "observed_triggers":
                list(
                    _list(
                        target.get(
                            "observed_triggers"
                        )
                    )
                ),
            "products":
                products,
            "product_state": (
                "SELLABLE"
                if all_sellable
                else
                "LOCKED_PRODUCT_READINESS"
            ),
            "binding_intent_verified":
                target.get(
                    "binding_intent_verified"
                )
                is True,
            "budget_verified":
                target.get(
                    "budget_verified"
                )
                is True,
            "commercial_terms_verified":
                target.get(
                    "commercial_terms_verified"
                )
                is True,
            "outreach_authorized":
                target.get(
                    "outreach_authorized"
                )
                is True,
            "execution_authority":
                target.get(
                    "execution_authority"
                ),
            "planning_value_cents":
                None,
            "expected_revenue_cents":
                None,
            "committed_mrr_cents":
                None,
            "recognized_revenue_inferred":
                False,
            "value_state":
                "UNKNOWN_UNTIL_PRODUCT_AND_ACCOUNT_TERMS_READY",
        })

    locked_count = sum(
        row.get(
            "product_state"
        )
        != "SELLABLE"
        for row in rows
    )

    return {
        "state":
            "INTERNAL_HYPOTHESES_ONLY",
        "account_count":
            len(rows),
        "locked_account_count":
            locked_count,
        "opportunities":
            rows,
        "planning_value_cents":
            None,
        "committed_mrr_cents":
            None,
        "recognized_revenue_cents":
            None,
        "buyer_intent_inferred":
            False,
        "budget_inferred":
            False,
    }


def _relationship_signals(
    *,
    lead_smart: Mapping[str, Any],
    connexis: Mapping[str, Any],
) -> dict[str, Any]:
    signals = []

    if lead_smart:
        signals.append({
            "account_name":
                lead_smart.get(
                    "buyer"
                )
                or "Lead Smart",
            "relationship_type":
                "publisher_affiliate_partner",
            "state":
                lead_smart.get(
                    "mode"
                ),
            "launch_ready":
                lead_smart.get(
                    "launch_ready"
                )
                is True,
            "blockers":
                list(
                    _list(
                        lead_smart.get(
                            "blockers"
                        )
                    )
                ),
            "product_code":
                None,
            "commercial_value_cents":
                None,
            "committed_mrr_cents":
                None,
            "recognized_revenue_inferred":
                False,
        })

    conversation = _mapping(
        connexis.get(
            "conversation_evidence"
        )
    )

    if (
        conversation.get(
            "connexis_genuine_decision_maker_reply"
        )
        is True
    ):
        signals.append({
            "account_name":
                "Connexis",
            "relationship_type":
                "genuine_buyer_conversation",
            "state": (
                "BUY_BOX_DETAILS_REQUIRED"
                if conversation.get(
                    "connexis_buy_box_details_received"
                )
                is not True
                else
                "BUY_BOX_DETAILS_OBSERVED"
            ),
            "observed_at":
                connexis.get(
                    "recorded_at"
                ),
            "product_code":
                None,
            "commercial_value_cents":
                None,
            "committed_mrr_cents":
                None,
            "next_action":
                connexis.get(
                    "next_action"
                ),
            "founder_gated":
                True,
            "recognized_revenue_inferred":
                False,
        })

    return {
        "signal_count":
            len(signals),
        "signals":
            signals,
        "signals_are_pipeline_revenue":
            False,
        "signals_are_committed_mrr":
            False,
    }


def _targets(
    *,
    recurring_capacity: Mapping[str, Any],
    locked_exchange: Mapping[str, Any],
    verified_mrr_cents: int | None,
) -> list[dict[str, Any]]:
    stack_cents = (
        _nonnegative_int(
            recurring_capacity.get(
                "one_of_each_stack_mrr_cents"
            )
        )
        or 0
    )

    recurring_products = [
        row
        for row in _list(
            recurring_capacity.get(
                "products"
            )
        )
        if isinstance(row, Mapping)
    ]

    exchange_products = [
        row
        for row in _list(
            locked_exchange.get(
                "products"
            )
        )
        if isinstance(row, Mapping)
    ]

    output = []

    for target in TARGET_MRR_CENTS:
        canonical_gap = (
            max(
                target - verified_mrr_cents,
                0,
            )
            if verified_mrr_cents is not None
            else None
        )

        product_equivalents = []

        for row in recurring_products:
            monthly = _nonnegative_int(
                row.get(
                    "monthly_price_cents"
                )
            )

            product_equivalents.append({
                "product_code":
                    row.get("product_code"),
                "monthly_price_cents":
                    monthly,
                "customers_if_sold_alone":
                    _ceil_customers(
                        target,
                        monthly,
                    ),
            })

        exchange_equivalents = []

        for row in exchange_products:
            monthly = _nonnegative_int(
                row.get(
                    "monthly_price_cents"
                )
            )

            exchange_equivalents.append({
                "product_code":
                    row.get("product_code"),
                "monthly_price_cents":
                    monthly,
                "customers_if_sold_alone":
                    _ceil_customers(
                        target,
                        monthly,
                    ),
                "locked_scenario_only":
                    True,
            })

        output.append({
            "target_mrr_cents": target,
            "target_mrr_usd": _usd(
                target
            ),
            "verified_mrr_gap_cents":
                canonical_gap,
            "verified_mrr_gap_usd":
                _usd(canonical_gap),
            "gap_state": (
                "VERIFIED"
                if canonical_gap is not None
                else
                "UNKNOWN_VERIFIED_MRR_UNAVAILABLE"
            ),
            "zero_baseline_planning_gap_cents":
                target,
            "zero_baseline_planning_gap_usd":
                _usd(target),
            "full_sellable_recurring_stack_customer_equivalent":
                _ceil_customers(
                    target,
                    stack_cents,
                ),
            "sellable_product_equivalents":
                product_equivalents,
            "locked_exchange_equivalents":
                exchange_equivalents,
            "planning_only_fields_do_not_equal_forecast":
                True,
        })

    return output


def build_revenue_capacity_board(
    *,
    revenue_pulse: Mapping[str, Any],
    revenue_command_queue: Mapping[str, Any],
    commercial_catalog: Mapping[str, Any],
    stage2: Mapping[str, Any],
    commercial_exchange: Mapping[str, Any],
    pricing_policy: Mapping[str, Any],
    exchange_plan: Mapping[str, Any],
    commercial_offer_book: Mapping[str, Any] | None = None,
    enterprise_targets: Mapping[str, Any] | None = None,
    lead_smart_readiness: Mapping[str, Any] | None = None,
    connexis_checkpoint: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    revenue_truth = _mapping(
        revenue_pulse.get(
            "recognized_revenue_truth"
        )
    )

    current_window = _mapping(
        revenue_pulse.get(
            "current_window"
        )
    )

    recognized_cents = (
        _nonnegative_int(
            revenue_truth.get(
                "recognized_revenue_cents"
            )
        )
    )

    realized_gp_cents = (
        _nonnegative_int(
            revenue_truth.get(
                "realized_gp_cents"
            )
        )
    )

    # The captured canonical contract currently
    # exposes recognized revenue but no explicit,
    # durable recurring-revenue/MRR field.
    verified_mrr_cents = None

    recurring_capacity = (
        _recurring_capacity(
            catalog=commercial_catalog,
            stage2=stage2,
            pricing=pricing_policy,
        )
    )

    locked_exchange = (
        _locked_exchange_capacity(
            catalog=commercial_catalog,
            exchange_plan=exchange_plan,
        )
    )

    pipeline = _pipeline(
        revenue_command_queue
    )

    commercial_opportunities = {
        "product_bound": (
            _account_product_capacity(
                commercial_offer_book
                or {}
            )
        ),
        "enterprise_locked": (
            _enterprise_locked_opportunities(
                enterprise_targets=(
                    enterprise_targets
                    or {}
                ),
                catalog=
                    commercial_catalog,
            )
        ),
        "relationship_signals": (
            _relationship_signals(
                lead_smart=(
                    lead_smart_readiness
                    or {}
                ),
                connexis=(
                    connexis_checkpoint
                    or {}
                ),
            )
        ),
    }

    pulse_source = str(
        revenue_pulse.get(
            "snapshot_source"
        )
        or ""
    ).strip()

    stale_legacy_source_label = (
        "supabase"
        in pulse_source.casefold()
    )

    return {
        "schema_version":
            SCHEMA_VERSION,
        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
        "mode":
            "OBSERVE",
        "execution_authority":
            "none",
        "execution_allowed":
            False,
        "database_mutation":
            False,
        "outbound_mutation":
            False,
        "payment_mutation":
            False,
        "revenue_mutation":
            False,

        "actual": {
            "time_scope":
                current_window.get(
                    "label"
                ),
            "recognized_revenue_cents":
                recognized_cents,
            "recognized_revenue_usd":
                _usd(
                    recognized_cents
                ),
            "realized_gp_cents":
                realized_gp_cents,
            "realized_gp_usd":
                _usd(
                    realized_gp_cents
                ),
            "verified_payments":
                current_window.get(
                    "verified_payments"
                ),
            "fulfilments":
                current_window.get(
                    "fulfilments"
                ),
            "actual_mrr_inferred":
                False,
        },

        "verified_mrr": {
            "state":
                "UNKNOWN_NO_CANONICAL_MRR_FIELD",
            "amount_cents":
                verified_mrr_cents,
            "amount_usd":
                None,
            "recognized_revenue_used_as_mrr":
                False,
        },

        "committed_mrr": {
            "state":
                "UNKNOWN_NO_CANONICAL_BINDING_RECURRING_VALUE_READER",
            "amount_cents":
                None,
            "amount_usd":
                None,
            "terms_count_used_as_value":
                False,
        },

        "pipeline":
            pipeline,

        "commercial_opportunities":
            commercial_opportunities,

        "sellable_capacity":
            recurring_capacity,

        "locked_capacity":
            locked_exchange,

        "exchange_runtime": {
            "buyer_seat_count":
                commercial_exchange.get(
                    "buyer_seat_count"
                ),
            "corridor_count":
                commercial_exchange.get(
                    "corridor_count"
                ),
            "inventory_count":
                commercial_exchange.get(
                    "inventory_count"
                ),
            "allocation_candidate_count":
                commercial_exchange.get(
                    "allocation_candidate_count"
                ),
            "actual_revenue":
                commercial_exchange.get(
                    "actual_revenue"
                ),
            "commercial_authority":
                commercial_exchange.get(
                    "commercial_authority"
                ),
            "execution_authority":
                commercial_exchange.get(
                    "execution_authority"
                ),
            "seat_records_are_customers":
                False,
            "corridors_are_revenue":
                False,
        },

        "usage_upside": {
            "state":
                "LOCKED_WITH_EXCHANGE_COMMERCIAL_READINESS",
            "base_usage_prices_cents":
                dict(
                    _mapping(
                        exchange_plan.get(
                            "base_usage_prices_cents"
                        )
                    )
                ),
            "included_in_mrr":
                False,
            "included_in_recognized_revenue":
                False,
        },

        "enterprise_upside": {
            "state":
                "EXCLUDED_UNTIL_EXACT_PRODUCT_COMMERCIAL_READINESS",
            "included_in_targets":
                False,
            "recognized_revenue_inferred":
                False,
        },

        "targets":
            _targets(
                recurring_capacity=
                    recurring_capacity,
                locked_exchange=
                    locked_exchange,
                verified_mrr_cents=
                    verified_mrr_cents,
            ),

        "current_bottleneck": {
            "revenue_pulse":
                revenue_pulse.get(
                    "highest_priority_blocker"
                ),
            "revenue_command_queue":
                revenue_command_queue.get(
                    "highest_priority_blocker"
                ),
        },

        "source_integrity": {
            "revenue_pulse_snapshot_source":
                pulse_source or None,
            "legacy_supabase_label_detected":
                stale_legacy_source_label,
            "backend_inferred_from_label":
                False,
            "source_label_state": (
                "STALE_LEGACY_LABEL_REQUIRES_RECONCILIATION"
                if stale_legacy_source_label
                else "NO_LEGACY_LABEL_DETECTED"
            ),
        },

        "truth_guards": {
            "seat_record_is_customer":
                False,
            "corridor_is_revenue":
                False,
            "observed_rate_is_binding_price":
                False,
            "review_is_proposal":
                False,
            "proposal_is_commitment":
                False,
            "commitment_is_recognized_revenue":
                False,
            "payment_request_is_payment":
                False,
            "pipeline_is_revenue":
                False,
            "forecast_is_revenue":
                False,
            "unknown_stays_unknown":
                True,
        },
    }


def build_revenue_capacity_board_runtime(
    repo_root: Path,
) -> dict[str, Any]:
    runtime = repo_root / "runtime"

    commercial_catalog = _load_json(
        runtime
        / "commercial_catalog"
        / "latest.json"
    )

    stage2 = _load_json(
        runtime
        / "product_verification"
        / "premarket_unified_current.json"
    )

    commercial_exchange = _load_json(
        runtime
        / "commercial_exchange"
        / "latest.json"
    )

    commercial_offer_book = _load_json(
        runtime
        / "predictive_revenue"
        / "commercial_offer_book"
        / "reconciled_observed.json"
    )

    enterprise_targets = _load_json(
        runtime
        / "predictive_revenue"
        / "enterprise_targets_latest.json"
    )

    lead_smart_readiness = _load_json(
        runtime
        / "revenue"
        / "lead_smart"
        / "launch_readiness"
        / "latest.json"
    )

    checkpoint_candidates = sorted(
        (
            runtime
            / "execution_plane"
            / "completion_checkpoints"
        ).glob(
            "*marketplace_commercial_evidence*.json"
        )
    )

    connexis_checkpoint = (
        _load_json(
            checkpoint_candidates[-1]
        )
        if checkpoint_candidates
        else {}
    )

    revenue_pulse = (
        build_revenue_pulse_runtime(
            repo_root
        )
    )

    revenue_command_queue = (
        build_revenue_command_queue_runtime(
            repo_root
        )
    )

    return build_revenue_capacity_board(
        revenue_pulse=revenue_pulse,
        revenue_command_queue=
            revenue_command_queue,
        commercial_catalog=
            commercial_catalog,
        stage2=stage2,
        commercial_exchange=
            commercial_exchange,
        pricing_policy=
            build_launch_pricing_proposal(),
        exchange_plan=
            build_exchange_mrr_product_plan(),
        commercial_offer_book=
            commercial_offer_book,
        enterprise_targets=
            enterprise_targets,
        lead_smart_readiness=
            lead_smart_readiness,
        connexis_checkpoint=
            connexis_checkpoint,
    )
