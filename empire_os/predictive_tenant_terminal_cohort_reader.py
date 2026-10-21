"""Authenticated EmpireDB tenant terminal-outcome candidate reader.

Real restricted SQL source read; no private rows are exported and no
self-attested customer outcomes are passed into the Scientific Agent.

Candidates are NOT verified economic outcomes; evidence/settlement/revenue
certification belongs to original Finance and CRM owners.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

from empire_os.predictive_tenant_outcome_reader_preflight import (
    TABLE_POLICY, ROLE_SQL, IDENTITY_SQL, TABLE_SQL, POLICY_SQL, READER_ROLE,
    _role, _catalogue, TenantEvidencePolicyHold,
)

SCHEMA = "empire.predictive_revenue.tenant_terminal_cohort_candidates.v1"
LIMIT = 200
CANDIDATE_SQL = """
SELECT o.id::text,o.product_id::text,o.buyer_id::text,
       o.commercial_payload->'causal_lineage'->>'tenant_id',
       co.id::text,co.conversion_outcome,co.recorded_at,
       co.evidence->>'verified',co.evidence->>'synthetic',
       co.evidence->>'forecast_derived',
       o.created_at,o.delivered_at,o.confirmed_at,
       (
        SELECT count(*) FROM public.commercial_events ce
        WHERE ce.fulfilment_order_id=o.id
          AND ce.event_type='revenue_recognized'
          AND ce.buyer_id=o.buyer_id
          AND ce.product_id=o.product_id
          AND ce.opportunity_id IS NOT DISTINCT FROM o.opportunity_id
          AND ce.payload->>'actual_revenue'='true'
          AND ce.occurred_at >= o.created_at
          AND ce.created_at >= o.created_at
          AND ce.occurred_at <= %s
          AND ce.created_at <= %s
       ) AS recognized_event_candidates
FROM public.fulfilment_orders o
JOIN public.commercial_outcomes co ON co.fulfilment_order_id=o.id
JOIN public.buyers b ON b.id=o.buyer_id
WHERE b.org_id=public.empire_current_tenant_id()
  AND o.product_id IS NOT NULL
  AND co.conversion_outcome IN ('won','lost','no_response')
ORDER BY co.recorded_at DESC,co.id DESC
LIMIT %s
""".strip()


class TenantCohortSourceHold(ValueError):
    """Sanitized source rejection; never return database exception/tenant data."""


def _canonical_uuid(value: Any) -> bool:
    if type(value) is not str:
        return False
    try:
        return str(UUID(value)) == value.lower()
    except ValueError:
        return False


def _clock(value: Any, now: datetime) -> bool:
    return (isinstance(value, datetime) and value.tzinfo is not None
            and value.utcoffset() is not None
            and value.astimezone(timezone.utc) <= now)


def _rows_report(rows: Any, *, tenant: str, as_of: datetime) -> dict[str, Any]:
    if type(rows) is not list or len(rows) > LIMIT + 1:
        raise TenantCohortSourceHold("bounded source not proven")
    if len(rows) > LIMIT:
        # Never imply complete cohort when cap is reached.
        return {
            "status": "TENANT_SOURCE_COHORT_READ_BOUND_HOLD",
            "candidate_rows_observed": LIMIT,
            "candidate_terminal_wins": None,
            "candidate_terminal_losses": None,
            "candidate_revenue_events_present": None,
            "candidate_products_observed": None,
            "largest_candidate_product_terminal_cohort": None,
            "candidate_product_cohorts_reaching_20": None,
            "source_census_complete": False,
        }
    seen_outcomes: set[str] = set()
    seen_orders: set[str] = set()
    wins = losses = events = 0
    per_product: dict[str, int] = {}
    for item in rows:
        if type(item) not in (list, tuple) or len(item) != 14:
            raise TenantCohortSourceHold("canonical row shape invalid")
        (order, product, buyer, lineage_tenant, outcome, label, recorded,
         verified, synthetic, forecast_derived, created, delivered,
         confirmed, event_count) = item
        if (not all(_canonical_uuid(x) for x in
                    (order, product, buyer, lineage_tenant, outcome))
                or lineage_tenant != tenant or outcome in seen_outcomes
                or order in seen_orders or label not in
                ("won", "lost", "no_response")
                or not _clock(recorded, as_of)
                or not _clock(created, as_of)
                or recorded < created
                or verified != "true" or synthetic != "false"
                or forecast_derived != "false"
                or type(event_count) is not int or not 0 <= event_count <= 1):
            raise TenantCohortSourceHold("unverified source order/outcome lineage")
        if (delivered is not None and not _clock(delivered, as_of)) or (
            confirmed is not None and not _clock(confirmed, as_of)
        ):
            raise TenantCohortSourceHold("invalid source fulfilment timestamp")
        if label == "won":
            if not (delivered or confirmed) or event_count != 1:
                raise TenantCohortSourceHold("won candidate lacks fulfilment/event")
            wins += 1
            events += 1
        else:
            if event_count:
                raise TenantCohortSourceHold("loss and recognized revenue conflict")
            losses += 1
        per_product[product] = per_product.get(product, 0) + 1
        seen_outcomes.add(outcome)
        seen_orders.add(order)
    return {
        "status": "AUTHENTICATED_TENANT_TERMINAL_CANDIDATES_UNVERIFIED",
        "candidate_rows_observed": len(rows),
        "candidate_terminal_wins": wins,
        "candidate_terminal_losses": losses,
        "candidate_revenue_events_present": events,
        "candidate_products_observed": len(per_product),
        "largest_candidate_product_terminal_cohort": max(per_product.values(), default=0),
        "candidate_product_cohorts_reaching_20": sum(size >= 20 for size in per_product.values()),
        "source_census_complete": False,  # an as-of bounded read is not lifetime completeness
    }


def read_tenant_terminal_candidates(
    *, dsn: str, as_of: datetime | None = None,
    connect_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Read original tenant-bound *candidates*, with verified DB role and RLS.

    No row payloads, UUIDs, tenant IDs, credentials or financial numbers emitted.
    Fails closed on any malformed/out-of-scope candidate and source truncation.
    """
    if type(dsn) is not str or not dsn.strip():
        raise TenantCohortSourceHold("dedicated tenant outcome reader unavailable")
    now = as_of or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise TenantCohortSourceHold("trusted review time required")
    now = now.astimezone(timezone.utc)
    if connect_factory is None:
        try:
            import psycopg
            connect_factory = psycopg.connect
        except ImportError:
            raise TenantCohortSourceHold("database driver unavailable") from None
    try:
        with connect_factory(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout = '4000ms'")
                cur.execute("SET LOCAL ROLE " + READER_ROLE)
                cur.execute("SET LOCAL client_encoding = 'UTF8'")
                cur.execute(IDENTITY_SQL)
                identity = cur.fetchone()
                if type(identity) not in (list, tuple) or len(identity) != 5:
                    raise TenantCohortSourceHold("session identity missing")
                db, readonly, login_role, current_role, tenant = identity
                if (db != "empiredb" or readonly != "on"
                        or type(login_role) is not str
                        or not login_role or login_role in ("postgres", READER_ROLE)
                        or current_role != READER_ROLE
                        or not _canonical_uuid(tenant)):
                    raise TenantCohortSourceHold("tenant session not authenticated")
                cur.execute(ROLE_SQL, (login_role,))
                login = cur.fetchone()
                cur.execute(ROLE_SQL, (READER_ROLE,))
                role = cur.fetchone()
                if not (_role(login, login=True) and _role(role, login=False)):
                    raise TenantCohortSourceHold("unsafe original read identity")
                cur.execute(TABLE_SQL, (list(TABLE_POLICY),))
                tables = cur.fetchall()
                cur.execute(POLICY_SQL, (list(TABLE_POLICY),))
                policies = cur.fetchall()
                report = _catalogue(tables, policies)
                if not all(all(flags.values()) for flags in report.values()):
                    raise TenantCohortSourceHold("tenant table policies missing")
                cur.execute(CANDIDATE_SQL, (now, now, LIMIT + 1))
                candidates = cur.fetchall()
                stats = _rows_report(candidates, tenant=tenant, as_of=now)
    except Exception:
        raise TenantCohortSourceHold("original tenant cohort source unavailable") from None
    return {
        "schema_version": SCHEMA,
        **stats,
        "mode": "OBSERVE",
        "canonical_database": "EmpireDB",
        "dedicated_session_tenant_authenticated": True,
        "source_order_and_outcome_rls_policy_metadata_checked": True,
        "original_rows_read_in_memory_only": True,
        "source_ids_or_tenant_exposed": False,
        "original_terminal_outcomes_independently_attested": False,
        "payment_and_cost_receipts_verified": False,
        "frozen_conversion_forecast_registry_verified": False,
        "source_rows_exported_to_scientific_training": False,
        "model_weights_changed": False,
        "customer_forecast_eligible": False,
        "database_writes": False,
        "production_activated": False,
        "execution_authority": "none",
    }
