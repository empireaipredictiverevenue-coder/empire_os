"""Existing Ops Control: live original first-sale evidence vs stale funnel.

Owner sources: pre-existing canonical first-party acquisition count query and
existing private self-serve checkout GET health. No new daemon, prospect joins,
database writer, customer disclosures, contact/send or payment authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import json
import os
import urllib.request
import urllib.error

SCHEMA = "empire.commercial.first_sale_live_conversion_observer.v1"
ORIGINAL_ACQUISITION_SCHEMA = "empire.founder.canonical_sales_source_aggregate.v1"
FUNNEL_SCHEMA = "empire.founder_commercial_funnel.v1"
FOUNDER_ROOT = Path("/srv/empire_os")
FRESH_SECONDS = 1800
COUNT_KEYS = (
    "commercial_acquisition_rows", "predictive_acquisition_rows",
    "sales_acquisition_rows", "distinct_sales_prospects",
    "source_evidence_consistent_rows", "entity_unlinked_acquisition_rows",
    "founder_binding_exact_one_rows",
    "founder_binding_missing_or_ambiguous_rows",
)
MAX_COUNT = 20_000_000


def _freshness(root: Path, now: datetime) -> str:
    p = root / "runtime/commercial_funnel/latest.json"
    try:
        if p.is_symlink() or not p.is_file() or p.stat().st_size > 2_000_000:
            return "UNAVAILABLE"
        original = json.loads(p.read_text(encoding="utf-8"))
        if (
            not isinstance(original, dict)
            or original.get("schema_version") != FUNNEL_SCHEMA
            or original.get("mode") != "OBSERVE"
            or original.get("execution_authority") != "none"
        ):
            return "UNTRUSTED"
        at = datetime.fromisoformat(str(original.get("generated_at")).replace("Z", "+00:00"))
        if at.utcoffset() is None:
            return "UNTRUSTED"
        seconds = (now - at.astimezone(timezone.utc)).total_seconds()
        return "FRESH" if -120 <= seconds <= FRESH_SECONDS else "STALE_OR_FUTURE"
    except (OSError, TypeError, ValueError, OverflowError):
        return "UNAVAILABLE"


def _checkout_health() -> dict:
    """Exact loopback GET; never submits an order, token or personal details."""
    request = urllib.request.Request(
        "http://127.0.0.1:8098/health",
        method="GET",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        if response.status != 200 or response.headers.get_content_type() != "application/json":
            raise ValueError("untrusted original checkout response")
        raw = response.read(6001)
        if len(raw) > 6000:
            raise ValueError("original checkout health too large")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("invalid original checkout source")
    return data


def _public_conversion_gets() -> bool:
    """GET-only first-party route canary, NEVER submit lead/order forms.

    405 is the correct response to GET on POST-only intake endpoints.
    This establishes route reachability, NOT that a POST/CRM journey works.
    """
    expected = (
        ("/commercial", 200, "text/html"),
        ("/buy", 200, "text/html"),
        ("/v1/checkout/commercial/offers", 200, "application/json"),
        ("/v1/checkout/catalog", 200, "application/json"),
        ("/v1/checkout/commercial/interests", 405, "application/json"),
        ("/v1/checkout/orders", 405, "application/json"),
    )
    for route, code, content in expected:
        request = urllib.request.Request(
            "http://127.0.0.1" + route,
            method="GET",
            headers={"Host": "empire-ai.co.uk", "Accept": "*/*"},
        )
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                actual_code = response.status
                content_type = response.headers.get_content_type()
        except urllib.error.HTTPError as error:
            actual_code = error.code
            content_type = error.headers.get_content_type()
            error.close()
        if actual_code != code or content_type != content:
            return False
    return True


def _canonical_sales_counts():
    # The pre-existing original owner operates a bounded privileged READ ONLY
    # SQL aggregation under the founder tenant. It returns counts, not records.
    from scripts.probe_canonical_sales_intake_aggregate_readonly import run
    return run()


def _counts(source: Mapping[str, Any] | None) -> dict[str, int] | None:
    if (
        not isinstance(source, Mapping)
        or source.get("schema_version") != ORIGINAL_ACQUISITION_SCHEMA
        or source.get("mode") != "OBSERVE"
        or source.get("read_only") is not True
        or source.get("source") != "CANONICAL_EMPIREDB"
        or source.get("status") not in (
            "NO_SALES_ACQUISITION_IN_CANONICAL_SOURCE",
            "SALES_ACQUISITION_SOURCE_OBSERVED_REVIEW_REQUIRED",
        )
        or source.get("execution_authority") != "NONE"
        or source.get("customer_rows_disclosed") is not False
        or source.get("contact_data_disclosed") is not False
        or source.get("tenant_identifier_disclosed") is not False
        or source.get("database_writes") is not False
        or source.get("outbound_sent") is not False
        or source.get("payment_action") is not False
    ):
        return None
    result = {}
    for key in COUNT_KEYS:
        val = source.get(key)
        if type(val) is not int or not 0 <= val <= MAX_COUNT:
            return None
        result[key] = val
    n = result["sales_acquisition_rows"]
    if (
        result["commercial_acquisition_rows"] + result["predictive_acquisition_rows"] != n
        or any(result[k] > n for k in COUNT_KEYS if k not in (
            "commercial_acquisition_rows", "predictive_acquisition_rows",
            "sales_acquisition_rows",
        ))
        or result["founder_binding_exact_one_rows"] +
           result["founder_binding_missing_or_ambiguous_rows"] != n
        or (
            (n == 0) !=
            (source["status"] == "NO_SALES_ACQUISITION_IN_CANONICAL_SOURCE")
        )
    ):
        return None
    return result


def _checkout_status(health: Mapping[str, Any] | None) -> str:
    if (
        not isinstance(health, Mapping)
        or health.get("status") != "online"
        or health.get("service") != "empire-self-serve-checkout"
        or health.get("payment_execution") is not False
        or health.get("revenue_recognition") is not False
        or health.get("founder_led_commercial_interest_enabled") is not True
    ):
        return "CHECKOUT_OR_ENQUIRY_HEALTH_UNVERIFIED"
    if (
        health.get("binding_order_creation_authorized") is True
        and health.get("payment_proposal_authorized") is True
        and health.get("checkout_settlement_mode") == "direct"
        and health.get("bsc_payment_configuration_status") ==
            "BSC_CONFIGURED_CHAIN_UNVERIFIED"
    ):
        return "ORDER_ADMISSION_FLAGS_ON_CHAIN_STILL_UNVERIFIED"
    if (
        health.get("binding_order_creation_authorized") is True
        and health.get("payment_proposal_authorized") is True
        and health.get("checkout_settlement_mode") == "direct"
    ):
        return "ORDER_ADMISSION_FLAGS_ON_CHAIN_STATUS_REQUIRES_PROOF"
    return "FIRST_PARTY_ENQUIRY_ENABLED_PAYMENT_ADMISSION_HELD"


def _safe_old(previous: Mapping[str, Any] | None):
    if not isinstance(previous, Mapping):
        return None
    if (
        previous.get("schema_version") != SCHEMA
        or previous.get("mode") != "OBSERVE"
        or previous.get("execution_authority") != "none"
        or previous.get("outbound_sent") is not False
        or previous.get("database_writes") is not False
        or previous.get("payment_action") is not False
    ):
        return None
    n = previous.get("canonical_sales_acquisition_counts")
    if n is not None and (
        not isinstance(n, dict) or
        set(n) != set(COUNT_KEYS) or
        any(type(n[k]) is not int or not 0 <= n[k] <= MAX_COUNT for k in COUNT_KEYS)
    ):
        return None
    return previous


def evaluate_first_sale_readiness(
    *, sales: Mapping[str, Any] | None,
    checkout: Mapping[str, Any] | None,
    funnel_freshness: str,
    previous: Mapping[str, Any] | None = None,
    public_routes: bool | None = None,
) -> dict[str, Any]:
    count = _counts(sales)
    checkout_status = _checkout_status(checkout)
    public_status = (
        "PUBLIC_CONVERSION_GET_ROUTES_PRESENT_POST_UNTESTED" if public_routes is True
        else "PUBLIC_CONVERSION_ROUTE_REVIEW_REQUIRED" if public_routes is False
        else "PUBLIC_CONVERSION_GET_ROUTES_NOT_CHECKED"
    )
    if count is None:
        status = "FIRST_PARTY_CANONICAL_SOURCE_UNVERIFIED"
    elif count["sales_acquisition_rows"] == 0:
        status = "NO_CANONICAL_FIRST_PARTY_SALES_ENQUIRIES"
    elif count["founder_binding_exact_one_rows"] == 0:
        status = "FIRST_PARTY_ENQUIRY_TO_FOUNDER_BINDING_HOLD"
    else:
        status = "FIRST_PARTY_ENQUIRY_PRESENT_OWNER_REVIEW_REQUIRED"
    current = {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": status,
        "canonical_sales_acquisition_counts": count,
        "checkout_status": checkout_status,
        "public_conversion_route_status": public_status,
        "public_post_or_customer_submission_attempted": False,
        "legacy_founder_funnel_snapshot_freshness": (
            funnel_freshness if funnel_freshness in (
                "FRESH", "STALE_OR_FUTURE", "UNAVAILABLE", "UNTRUSTED",
            ) else "UNTRUSTED"
        ),
        "old_funnel_counts_used_as_current": False,
        "canonical_order_or_settlement_evidence_checked": False,
        "canonical_order_created": False,
        "verified_first_sale": None,
        "recognized_revenue_cents": None,
        "verified_gross_profit_cents": None,
        "first_party_source_count_not_authenticated_buyer": True,
        "checkout_admission_flag_not_fresh_bsc_chain_proof": True,
        "outbound_sent": False,
        "crm_mutations": False,
        "payment_action": False,
        "database_writes": False,
        "agent_tasks_created": False,
        "execution_authority": "none",
    }
    prev = _safe_old(previous)
    stable_fields = (
        "status", "canonical_sales_acquisition_counts",
        "checkout_status", "public_conversion_route_status",
        "legacy_founder_funnel_snapshot_freshness",
    )
    if prev is None:
        transition = "INITIAL_FIRST_SALE_BASELINE"
    elif all(current[k] == prev.get(k) for k in stable_fields):
        transition = "UNCHANGED_FIRST_SALE_EVIDENCE_HOLD"
    else:
        transition = "FIRST_SALE_SOURCE_CHANGE_OWNER_REVIEW_REQUIRED"
    current["transition"] = transition
    current["repeated_owner_attention_suppressed"] = (
        transition == "UNCHANGED_FIRST_SALE_EVIDENCE_HOLD"
    )
    current["next_existing_owner_action"] = (
        "WEBSITE_CONVERSION_ROUTE_OWNER_REPAIR" if public_routes is False
        else "CHECK_ORIGINAL_FIRST_PARTY_INTAKE_AND_WEB_CONVERSION"
        if count is not None and count["sales_acquisition_rows"] == 0
        else "VERIFY_FIRST_PARTY_CANONICAL_SOURCE"
        if count is None
        else "EXISTING_SALES_CRM_OWNER_REVIEW_ORIGINAL_ENQUIRY"
    )
    return current


def observe_first_sale_readiness(
    *, root: Path, now: datetime,
    previous: Mapping[str, Any] | None,
    sales_probe=None,
    health_probe=None,
    public_probe=None,
) -> dict:
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("offset-aware observation required")
    canonical = (
        isinstance(root, Path)
        and root.resolve() == FOUNDER_ROOT
        and os.geteuid() == 0
    )
    # Sandbox fixtures use no real database, systemd, network or client data.
    source = None
    health = None
    if canonical or sales_probe is not None:
        try:
            source = (sales_probe or _canonical_sales_counts)()
        except (OSError, ValueError, RuntimeError, TypeError):
            source = None
    if canonical or health_probe is not None:
        try:
            health = (health_probe or _checkout_health)()
        except (OSError, ValueError, RuntimeError, TypeError, TimeoutError):
            health = None
    public = None
    if canonical or public_probe is not None:
        try:
            check = (public_probe or _public_conversion_gets)()
            public = check if type(check) is bool else False
        except (OSError, ValueError, RuntimeError, TypeError, TimeoutError):
            public = False
    return evaluate_first_sale_readiness(
        sales=source, checkout=health,
        funnel_freshness=_freshness(root,now.astimezone(timezone.utc)),
        previous=previous, public_routes=public,
    )
