"""Empire AI's two usable, internal-first proprietary research products.

Vane/OpenManus ideas informed earlier engineering; these interfaces are
EmpireOS-authored and use EmpireOS's existing governed source engine.
No upstream framework copy, generic shell/browser access, finance or sender.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
import json

from empire_os.research.brokerage_niche_profiles import NICHES
from scripts.run_brokerage_deep_research_20261021 import run as run_evidence

CATALOG_SCHEMA = "empire.research.product_catalog.v1"
RESULT_SCHEMA = "empire.research.product_result.v1"
PRODUCTS = {
    "empire_research": {
        "title": "Empire Research",
        "inspiration": "Vane-style bounded source-backed research",
        "description": "Inspect permitted primary sources, show traceable passages and editorial gaps",
        "modes": ["speed", "balanced", "quality"],
        "customer_release": "not_authorized",
    },
    "empire_agent": {
        "title": "Empire Agent",
        "inspiration": "OpenManus-style planned work and step receipts",
        "description": "Execute a bounded evidence-review workflow and record every step or hold",
        "modes": ["speed", "balanced", "quality"],
        "customer_release": "not_authorized",
    },
}


def product_catalog() -> dict[str, Any]:
    return {
        "schema_version": CATALOG_SCHEMA,
        "status": "INTERNAL_PRIVATE_SOURCE_REVIEW_CANDIDATE",
        "products": PRODUCTS,
        "markets": ["US", "GB", "both"],
        "niches": list(NICHES),
        "default_niche": "dental",
        "editorial_approval_required": True,
        "source_licence_required": True,
        "commercial_actions_authorized": False,
    }


def _step(step: str, state: str, explanation: str, *, source_hash: str | None = None):
    return {
        "step": step,
        "state": state,
        "explanation": explanation,
        "source_evidence_fingerprint": source_hash,
        "step_is_commercial_authority": False,
    }


def _agent_plan(source_report: dict) -> dict:
    """Interpret actual existing source work; don't invent tool execution."""
    states = []
    observed = source_report.get("market_reports", [])
    is_complete = bool(observed) and all(
        x.get("status") == "SOURCE_EVIDENCE_READY_FOR_EDITORIAL_REVIEW"
        for x in observed
    )
    fingerprint = sha256(
        json.dumps(
            [
                {"country": x.get("country"), "sha": x.get("evidence_fingerprint_sha256"),
                 "status": x.get("status")}
                for x in observed
            ], sort_keys=True
        ).encode()
    ).hexdigest()
    states.append(_step("scope", "DONE",
                        "Validated niche, country, research-depth and buyer-decision scope",
                        source_hash=fingerprint))
    states.append(_step("discover_original_sources",
                        "DONE" if observed else "HELD",
                        "Using previously reviewed publisher URLs only; new niches require their own intake",
                        source_hash=fingerprint if observed else None))
    states.append(_step("inspect_originals",
                        "DONE" if is_complete else "HELD",
                        "Bounded original HTTPS document inspection and checksum receipts"
                        if is_complete else "Curated source coverage incomplete",
                        source_hash=fingerprint if is_complete else None))
    states.append(_step("evidence_crosscheck",
                        "DONE_FOR_REVIEW" if is_complete else "HELD",
                        "Original-page passage integrity verified; medical/market claims still require reviewer",
                        source_hash=fingerprint if is_complete else None))
    states.append(_step("independent_editorial_review", "AWAITING_OWNER",
                        "Actual Research owner must check interpretation, sources, licence and editorial authority"))
    states.append(_step("customer_delivery_or_outbound", "BLOCKED",
                        "A research job never grants customer publication, emails, CRM, billing or funds"))
    return {
        "workflow_schema": "empire.agent.original_evidence_workflow.v1",
        "status": ("WORK_COMPLETED_FOR_EDITORIAL_REVIEW"
                   if is_complete else "HELD_SOURCE_INTAKE_REQUIRED"),
        "step_receipts": states,
        "tool_calls": (
            "EXISTING_BOUNDED_ORIGINAL_SOURCE_INSPECTOR"
            if observed else "NONE_NO_ADMITTED_SOURCES"
        ),
        "unbounded_shell_or_browser_allowed": False,
        "autonomous_retry_or_external_actions_enabled": False,
        "independent_editorial_signoff": False,
        "accepted_customer_order": False,
    }


def use_product(
    product: str, *,
    country: str = "both", niche: str = "dental", depth: str = "quality",
    inspect_fn=None, observed_at: datetime | None = None,
) -> dict:
    """Runs actual bounded inspect work, or a guarded intake for unsupported sectors.

    No implicit stdout writes or persistence; explicit CLI save is separate.
    """
    if product not in PRODUCTS:
        raise ValueError("UNKNOWN_EMPIRE_RESEARCH_PRODUCT")
    if observed_at is None:
        observed_at = datetime.now(timezone.utc)
    if observed_at.utcoffset() is None:
        raise ValueError("TIMEZONE_AWARE_JOB_CLOCK_REQUIRED")
    opts = {"country": country, "niche": niche, "depth": depth}
    if inspect_fn is not None:
        opts["inspect_fn"] = inspect_fn
    evidence = run_evidence(**opts)
    payload = {
        "schema_version": RESULT_SCHEMA,
        "product_id": product,
        "product_title": PRODUCTS[product]["title"],
        "as_of_utc": observed_at.astimezone(timezone.utc).isoformat(),
        "market": country,
        "niche": niche,
        "depth": depth,
        "status": evidence["status"],
        "research": evidence,
        "execution_mode": "READ_ONLY_BOUNDED_ORIGINAL_SOURCES",
        "original_source_count": sum(
            item.get("original_pages_inspected", 0)
            for item in evidence.get("market_reports", [])
        ),
        "editorial_owner": "existing_search_and_market_intelligence",
        "editorial_approval_verified": False,
        "customer_delivery_authorized": False,
        "outbound_authorized": False,
        "finance_authorized": False,
        "database_writes": False,
    }
    if product == "empire_agent":
        payload["agent_workflow"] = _agent_plan(evidence)
        payload["status"] = payload["agent_workflow"]["status"]
    return payload
