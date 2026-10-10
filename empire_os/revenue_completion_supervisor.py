"""Observe-only supervisor for TAM planning and buyer evidence progression."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping


ROOT = Path("/srv/empire_os")
DEFAULT_TAM_RUNTIME = ROOT / "runtime/coder_tam_lane"
DEFAULT_DEFERRED = ROOT / "runtime/hunter/buyer_deferred_enrichment.json"
DEFAULT_MATERIALIZER = ROOT / "runtime/buyer_review_materializer/latest.json"
DEFAULT_OUTPUT = ROOT / "runtime/revenue_completion_supervisor/latest.json"
DEFAULT_TAM_SNAPSHOT = ROOT / "runtime/tam_market_intelligence/latest.json"
DEFAULT_TAM_READER_CATALOG_PROBE = (
    ROOT / "runtime/market_sweeps/tam_reader_capability_latest.json"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _job_rows(runtime_root: Path, state: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    folder = runtime_root / "jobs" / state
    for path in sorted(folder.glob("*.json")) if folder.exists() else ():
        value = _read_json(path)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def tam_status(runtime_root: Path = DEFAULT_TAM_RUNTIME) -> dict[str, Any]:
    completed = _job_rows(runtime_root, "completed")
    failed = _job_rows(runtime_root, "failed")
    running = _job_rows(runtime_root, "running")
    pending = _job_rows(runtime_root, "pending")

    state = "NOT_QUEUED"
    job: Mapping[str, Any] | None = None
    if running:
        state, job = "RUNNING", running[-1]
    elif pending:
        state, job = "PENDING", pending[-1]
    elif completed:
        state, job = "COMPLETED", completed[-1]
    elif failed:
        state, job = "FAILED", failed[-1]

    worker_alive = None
    if state == "RUNNING" and job is not None:
        worker_id = str(job.get("worker_id") or "")
        if worker_id.startswith("pid:"):
            try:
                pid = int(worker_id.split(":", 1)[1])
                os.kill(pid, 0)
                worker_alive = True
            except (ValueError, ProcessLookupError, PermissionError):
                worker_alive = False

    historical = failed[-1] if failed else None
    active_job = state in {"PENDING", "RUNNING"}
    # A bounded exhausted job is diagnostic history, not an actively
    # failing model service. No automatic re-enqueue or retry is implied.
    operational_state = (
        "ACTIVE_PLAN_JOB" if active_job else
        "IDLE_HISTORIC_TERMINAL_FAILURE" if state == "FAILED" else
        "IDLE_NO_PLAN_JOB"
    )
    return {
        "state": state,
        "operational_state": operational_state,
        "active_job": active_job,
        "terminal_failure_history_count": len(failed),
        "last_terminal_failure_at": (
            historical.get("updated_at") if historical else None
        ),
        "last_terminal_failure_reason": (
            "MODEL_INFERENCE_TIMEOUT"
            if historical and "TimeoutError" in str(historical.get("error"))
            else "OTHER_TERMINAL_FAILURE" if historical else None
        ),
        "job_id": job.get("id") if job else None,
        "task_id": job.get("task_id") if job else None,
        "attempts": int(job.get("attempts") or 0) if job else 0,
        "worker_alive": worker_alive,
        "error": job.get("error") if job else None,
    }


def _genuine_review_rows(materializer: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in materializer.get("outcomes") or []:
        if not isinstance(raw, Mapping):
            continue
        decision_name = str(raw.get("decision_name") or "").strip()
        preferred_email = str(raw.get("preferred_email") or "").strip()
        if (
            raw.get("review_ready") is True
            and raw.get("outreach_ready") is True
            and decision_name
            and preferred_email
        ):
            rows.append(dict(raw))
    return rows


def buyer_status(
    deferred_path: Path = DEFAULT_DEFERRED,
    materializer_path: Path = DEFAULT_MATERIALIZER,
) -> dict[str, Any]:
    deferred = _read_json(deferred_path)
    materializer = _read_json(materializer_path)
    deferred = deferred if isinstance(deferred, dict) else {}
    materializer = materializer if isinstance(materializer, dict) else {}

    rows = [row for row in deferred.values() if isinstance(row, Mapping)]
    reasons = Counter(str(row.get("reason") or "unknown") for row in rows)
    statuses = Counter(str(row.get("status") or "unknown") for row in rows)
    now = datetime.now(timezone.utc)
    pending_ages: list[float] = []
    due_now = 0
    for row in rows:
        status = str(row.get("status") or "")
        if status == "pending":
            try:
                created = datetime.fromisoformat(str(row.get("created_at") or "").replace("Z", "+00:00"))
            except ValueError:
                created = None
            if created is not None:
                pending_ages.append(max(0.0, (now - created).total_seconds() / 3600))
        if status in {"pending", "deferred"}:
            retry_text = str(row.get("next_retry_at") or "").strip()
            try:
                retry_at = datetime.fromisoformat(retry_text.replace("Z", "+00:00")) if retry_text else None
            except ValueError:
                retry_at = None
            if retry_at is None or retry_at <= now:
                due_now += 1
    oldest_pending_hours = max(pending_ages, default=0.0)
    stale_pending_count = sum(age >= 6.0 for age in pending_ages)
    pending_count = int(statuses.get("pending") or 0)
    backlog_health = (
        "CRITICAL" if oldest_pending_hours >= 24.0 or pending_count >= 1500
        else "DEGRADED" if oldest_pending_hours >= 6.0 or pending_count >= 500
        else "HEALTHY"
    )

    evidence_rich = 0
    saturated = 0
    for row in rows:
        target_people = [
            x for x in (row.get("target_people") or [])
            if isinstance(x, Mapping)
            and str(x.get("name") or "").strip()
            and str(x.get("title") or "").strip()
        ]
        verified_routes = [
            x for x in (row.get("company_contact_routes") or [])
            if isinstance(x, Mapping)
            and x.get("verified") is True
            and str(x.get("value") or "").strip()
        ]
        if int(row.get("priority_score") or 0) >= 90 and (
            target_people or verified_routes
        ):
            evidence_rich += 1
        if int(row.get("attempts") or 0) >= 8:
            saturated += 1

    genuine = _genuine_review_rows(materializer)
    return {
        "deferred_total": len(rows),
        "status_counts": dict(sorted(statuses.items())),
        "reason_counts": dict(reasons.most_common()),
        "due_now": due_now,
        "oldest_pending_hours": round(oldest_pending_hours, 2),
        "stale_pending_count": stale_pending_count,
        "backlog_health": backlog_health,
        "evidence_rich_high_priority": evidence_rich,
        "retry_saturated": saturated,
        "materializer_eligible": int(materializer.get("eligible") or 0),
        "materializer_deferred_enrichment": int(
            materializer.get("deferred_enrichment") or 0
        ),
        "genuine_review_ready_count": len(genuine),
        "genuine_review_ready": genuine[:25],
    }


def _tam_market_row_contract(candidate: Mapping[str, Any]) -> bool:
    """Require independently coherent scope counts and research-only classes."""
    scopes = candidate.get("market_scopes")
    classes = candidate.get("opportunity_classes")
    total = candidate.get("source_row_count")
    if (not isinstance(scopes, list) or not isinstance(classes, list)
            or type(total) is not int or not 0 <= total <= 5000
            or len(scopes) > 5000 or len(classes) > 15000):
        return False
    by_scope: dict[tuple[str, str], Mapping[str, Any]] = {}
    unique_entities = 0
    for scope in scopes:
        if not isinstance(scope, Mapping):
            return False
        industry, country = scope.get("industry"), scope.get("country_code")
        count = scope.get("observed_entity_count")
        tam_count = scope.get("tam_entity_count")
        state = scope.get("tam_state")
        if (not isinstance(industry, str) or not industry.strip()
                or not isinstance(country, str) or len(country) != 2
                or not country.isascii() or not country.isalpha()
                or country != country.upper()
                or type(count) is not int or not 0 <= count <= 5000
                or state not in ("UNKNOWN", "VERIFIED")):
            return False
        if state == "UNKNOWN":
            if tam_count is not None:
                return False
        elif (
            type(tam_count) is not int or not 0 <= tam_count <= 1_000_000_000
            or tam_count < count
            or not isinstance(scope.get("tam_evidence_ref"), str)
            or not scope["tam_evidence_ref"].strip()
        ):
            return False
        key = (industry.casefold(), country)
        if key in by_scope:
            return False
        by_scope[key] = scope
        unique_entities += count
    if unique_entities > total:
        return False
    found: set[str] = set()
    for row in classes:
        if not isinstance(row, Mapping):
            return False
        kind = row.get("opportunity_class")
        industry = row.get("industry")
        country = row.get("country_code")
        key = (
            (industry.casefold(), country)
            if isinstance(industry, str) and isinstance(country, str)
            else None
        )
        scope = by_scope.get(key)
        if (scope is None or kind not in (
                "new_industry", "new_country", "new_industry_country")
                or row.get("decision") != "research"
                or row.get("execution_authority") != "none"
                or any(row.get(f) is not False for f in (
                    "buyer_intent_proven","demand_proven",
                    "commercial_terms_verified","revenue_verified"
                ))):
            return False
        if (
            (kind in ("new_industry", "new_industry_country")
             and scope.get("new_industry") is not True)
            or (kind in ("new_country", "new_industry_country")
                and scope.get("new_country") is not True)
        ):
            return False
        ref = row.get("opportunity_key")
        expected = (
            f"tam:{candidate['tenant_id']}:{kind}:"
            f"{industry.casefold()}:{country}"
        )
        if (ref != expected or ref in found
                or type(row.get("observed_entity_count")) is not int
                or row.get("observed_entity_count")
                    != scope.get("observed_entity_count")
                or row.get("tam_entity_count") != scope.get("tam_entity_count")
                or row.get("tam_state") != scope.get("tam_state")):
            return False
        refs = row.get("evidence_refs")
        if (not isinstance(refs,list) or not refs
                or any(not isinstance(r,str) or not r.strip() for r in refs)):
            return False
        found.add(ref)
    return True


def tam_snapshot_truth(
    candidate: Any, *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Fail-close canonical TAM projection; a JSON file is not runtime proof."""
    clock = now or datetime.now(timezone.utc)
    reason = "SNAPSHOT_MISSING"
    age = None
    if isinstance(candidate, Mapping):
        reason = "SNAPSHOT_CONTRACT_NOT_VERIFIED"
        required_false = (
            "tam_inferred_from_observed_roster", "buyer_intent_inferred",
            "demand_inferred", "pricing_inferred", "revenue_inferred",
            "prospect_created", "outreach_enabled", "external_execution",
        )
        generated = candidate.get("generated_at")
        ts = None
        if isinstance(generated, str):
            try:
                ts = datetime.fromisoformat(
                    generated.replace("Z", "+00:00")
                )
                if ts.tzinfo is None:
                    ts = None
            except ValueError:
                pass
        if ts is not None:
            age = (clock - ts).total_seconds()
        evidence_valid = (
            candidate.get("schema_version")
                == "empire.tam-market-intelligence.v1"
            and candidate.get("mode") == "OBSERVE"
            and candidate.get("source") == "empiredb_restricted_tam_reader"
            and candidate.get("canonical_data") is True
            and candidate.get("tenant_source_scope_verified") is False
            and candidate.get("data_scope") == "PLATFORM_MARKET_RESEARCH_ONLY"
            and candidate.get("execution_authority") == "none"
            and isinstance(candidate.get("tenant_id"), str)
            and bool(candidate["tenant_id"].strip())
            and isinstance(candidate.get("market_scopes"), list)
            and isinstance(candidate.get("opportunity_classes"), list)
            and isinstance(candidate.get("market_scope_count"), int)
            and candidate["market_scope_count"] == len(candidate["market_scopes"])
            and type(candidate.get("source_row_count")) is int
            and _tam_market_row_contract(candidate)
            and all(candidate.get(k) is False for k in required_false)
        )
        if evidence_valid and age is not None:
            if age < -300:
                reason = "SNAPSHOT_CLOCK_IN_FUTURE"
            elif age > 72 * 3600:
                reason = "SNAPSHOT_STALE_REQUIRES_RESTRICTED_REFRESH"
            else:
                reason = "CANONICAL_TAM_OBSERVE_SNAPSHOT_VERIFIED"
        elif evidence_valid:
            reason = "SNAPSHOT_FRESHNESS_UNVERIFIED"
    passed = reason == "CANONICAL_TAM_OBSERVE_SNAPSHOT_VERIFIED"
    return {
        "available": passed,
        "reason_code": reason,
        "schema_version": (
            candidate.get("schema_version") if passed else None
        ),
        "market_scope_count": candidate["market_scope_count"] if passed else 0,
        "opportunity_class_count": (
            len(candidate["opportunity_classes"]) if passed else 0
        ),
        "source_row_count": candidate["source_row_count"] if passed else None,
        "tam_counts_inferred_from_roster": False,
        "buyer_intent_inferred": False,
        "execution_authority": "none",
    }


def tam_restricted_reader_catalog_status(
    path: Path = DEFAULT_TAM_READER_CATALOG_PROBE,
    *, now: datetime | None = None,
) -> dict[str, Any]:
    """Check only a fresh private artifact from existing Market GPS service.

    This is a read-only catalog attestation, not a migration approval, a TAM
    tenant authorization, or proof of population/market-size results.
    """
    result = {
        "status": "NOT_YET_OBSERVED",
        "restricted_catalog_verified": False,
        "fresh": False,
        "no_data_rows_read": True,
        "execution_authority": "none",
    }
    try:
        if (path.is_symlink() or not path.is_file()
                or path.stat().st_mode & 0o077
                or path.stat().st_size > 8192):
            return result
        doc = _read_json(path)
    except (OSError, ValueError):
        return result
    if not isinstance(doc, Mapping):
        return result
    if (doc.get("schema_version")
            != "empire.tam_restricted_reader_capability_preflight.v1"
            or doc.get("source")
            != "existing_market_gps_protected_systemd_credential"
            or doc.get("mode") != "OBSERVE"
            or doc.get("execution_authority") != "none"
            or doc.get("no_data_rows_read") is not True
            or doc.get("no_migration_applied") is not True
            or doc.get("no_credential_exported") is not True):
        result["status"] = "INVALID_READ_ONLY_PROVENANCE"
        return result
    try:
        ts = datetime.fromisoformat(
            str(doc.get("observed_at")).replace("Z", "+00:00")
        )
        if ts.tzinfo is None:
            raise ValueError("unaware timestamp")
        age = ((now or datetime.now(timezone.utc)) - ts).total_seconds()
    except (ValueError, TypeError, OverflowError):
        result["status"] = "INVALID_CHECK_TIMESTAMP"
        return result
    if not 0 <= age <= 3 * 3600:
        result["status"] = "CATALOG_CHECK_STALE_OR_FUTURE"
        return result
    allowed = {
        "PASS", "RESTRICTED_CATALOG_CONTRACT_INCOMPLETE",
        "RESTRICTED_CATALOG_PROBE_UNAVAILABLE",
        "INVALID_RESTRICTED_CATALOG_RESPONSE",
    }
    status = doc.get("status")
    if not isinstance(status, str) or status not in allowed:
        result["status"] = "INVALID_CATALOG_STATUS"
        return result
    proven = (
        status == "PASS"
        and all(doc.get(k) is True for k in (
            "migration_028_contract_verified", "restricted_login_verified",
            "capability_role_verified", "function_exists",
            "security_definer_verified", "capability_execute_verified",
            "source_tables_present",
        ))
        and doc.get("source_table_direct_read_grants") is False
    )
    return {
        "status": status,
        "restricted_catalog_verified": proven,
        "fresh": True,
        "no_data_rows_read": True,
        "execution_authority": "none",
    }


def tam_reader_prerequisites(
    env: Mapping[str, str] | None = None,
    *, catalog_probe_path: Path = DEFAULT_TAM_READER_CATALOG_PROBE,
) -> dict[str, Any]:
    """Report protected-reader readiness without exposing identifiers/secrets.

    Only values exported into the actual service process count as operational
    configuration. Protected root env files need an authorised preflight and
    configured systemd EnvironmentFile before unprivileged workers can use them.
    """
    config = env if env is not None else os.environ
    catalog = tam_restricted_reader_catalog_status(catalog_probe_path)
    missing = [
        name for name in (
            "EMPIRE_TAM_TENANT_ID", "EMPIRE_TAM_ACTIVE_INDUSTRIES",
            "EMPIRE_TAM_ACTIVE_COUNTRIES",
            "EMPIRE_INTELLIGENCE_MATERIALIZER_DSN",
        ) if not isinstance(config.get(name), str) or not config[name].strip()
    ]
    return {
        "runtime_environment_configured": len(missing) == 0,
        "missing_runtime_environment_keys": missing,
        "restricted_empiredb_sql_reader_live_verified": catalog[
            "restricted_catalog_verified"
        ],
        "restricted_reader_catalog_check": catalog,
        "migration_028_live_authority": (
            "READ_ONLY_CATALOG_CONTRACT_VERIFIED_NO_DDL_AUTHORITY"
            if catalog["restricted_catalog_verified"]
            else "UNVERIFIED_NOT_AUTHORISED_HERE"
        ),
        "auto_planner_retry_authorized": False,
        "service_restart_authorized": False,
        "execution_authority": "none",
    }


def build_snapshot() -> dict[str, Any]:
    tam = tam_status()
    tam_runtime = _read_json(DEFAULT_TAM_SNAPSHOT)
    tam_truth = tam_snapshot_truth(tam_runtime)
    tam_runtime_available = tam_truth["available"]
    tam_prerequisites = tam_reader_prerequisites()
    buyers = buyer_status()
    if buyers["genuine_review_ready_count"] > 0:
        next_action = "founder_review_genuine_buyers"
    elif buyers["evidence_rich_high_priority"] > 0:
        next_action = "continue_targeted_buyer_enrichment"
    else:
        next_action = "refresh_buyer_scout_research"

    blockers: list[str] = []
    if not tam_runtime_available:
        blockers.append("tam_runtime_evidence_unavailable")
        if not tam_prerequisites["runtime_environment_configured"]:
            blockers.append("tam_restricted_reader_runtime_configuration_required")
    # A completed/failed historical AI plan job is diagnostic only. Canonical
    # TAM is built by the restricted deterministic EmpireDB reader, never
    # promoted by rerunning an Ollama proposal.
    if tam["state"] == "RUNNING" and tam["worker_alive"] is False:
        blockers.append("tam_planner_worker_missing")
    backlog_health = str(buyers.get("backlog_health") or "UNKNOWN")
    if backlog_health == "CRITICAL":
        blockers.append("buyer_enrichment_backlog_critical")
    elif backlog_health == "DEGRADED":
        blockers.append("buyer_enrichment_backlog_degraded")
    if buyers["genuine_review_ready_count"] == 0:
        blockers.append("no_genuine_review_ready_buyer")

    return {
        "schema_version": "empire.revenue-completion-supervisor.v1",
        "observed_at": _now(),
        "mode": "OBSERVE",
        "tam": tam,
        "tam_runtime": tam_truth,
        "tam_reader_prerequisites": tam_prerequisites,
        "tam_diagnostics": {
            "historical_planner_failure": tam["terminal_failure_history_count"] > 0,
            "planner_failure_not_retried": tam["active_job"] is False,
            "canonical_source_separate_from_llm_planner": True,
        },
        "tam_next_evidence_task": (
            "VERIFY_RESTRICTED_TAM_CATALOG_WITH_PROTECTED_CREDENTIAL"
            if not tam_prerequisites["restricted_empiredb_sql_reader_live_verified"]
            else "CONFIGURE_EXPLICIT_TAM_SCOPE_AND_RUN_BOUNDED_READER"
            if not tam_runtime_available
            else "VALIDATE_DOWNSTREAM_RADAR_EVIDENCE_CONSUMPTION"
        ),
        "buyers": buyers,
        "revenue_stream_portfolio": stream_portfolio_status(),
        "next_action": next_action,
        "blockers": blockers,
        "outbound_sent": False,
        "call_execution": False,
        "binding_terms": False,
        "payment_action": False,
        "revenue_recognition": False,
        "execution_authority": "none",
    }


def write_snapshot(
    path: Path = DEFAULT_OUTPUT,
    payload: Mapping[str, Any] | None = None,
) -> Path:
    value = dict(payload or build_snapshot())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)
    return path

# A portfolio-wide commercial projection belongs to the EXISTING completion
# supervisor, not a new agent or parallel source of commercial authority.
# Canonical EmpireDB-derived artifacts remain the only product/revenue inputs.
PORTFOLIO_SOURCES = {
    "catalog": "runtime/commercial_catalog/latest.json",
    "relationships": "runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json",
    "enterprise": "runtime/predictive_revenue/enterprise_activation_latest.json",
    "exchange": "runtime/commercial_exchange/latest.json",
    "lead_smart": "runtime/revenue/lead_smart/effective_pilot_state/latest.json",
    "payment": "runtime/orders_payments_revenue_control/orders_payments_revenue_runtime_latest.json",
    "funnel": "runtime/commercial_funnel/latest.json",
    "contractors": "runtime/revenue_strike/contractor_founder_review_latest.json",
    "claims_research": "runtime/claims_exchange/research_latest.json",
}
PORTFOLIO_SCHEMAS = {
    "catalog": "empire.commercial-product-catalog.v1",
    "relationships": "empire.commercial_relationship_registry.v1",
    "enterprise": "empire.predictive-revenue-enterprise-activation.v1",
    "exchange": "empire.commercial_exchange_snapshot.v1",
    "lead_smart": "empire.lead_smart.effective_pilot_state.v1",
    "payment": "empire-orders-payments-revenue-runtime-control-v1",
    "funnel": "empire.founder_commercial_funnel.v1",
    "contractors": "empire.revenue_strike.contractor_founder_review.v1",
    "claims_research": "empire.claims_exchange.existing_sources_preview_v2",
}
PORTFOLIO_GATES = (
    "real_counterparty", "current_buy_box_or_customer_need",
    "verified_product_terms", "complete_onboarding",
    "delivery_or_route_proven", "payment_proven", "realised_revenue_proven",
)
PORTFOLIO_SINGLE_REQUEST_GROUPS = (
    "verified_business_identity_authorized_decision_maker",
    "actual_buy_box_or_customer_need_and_geographies",
    "approved_product_scope_price_payout_and_settlement",
    "licensing_consent_source_rules_and_data_protection",
    "technical_integration_delivery_and_safe_test",
    "agreement_onboarding_support_payment_and_renewal",
)
# One portfolio, many commercially different streams. None of these
# descriptions establishes buyer approval, a current claim or cash.
REVENUE_STREAM_CONTRACTS = (
    ("lead_calls", "Buyer-led qualified calls and leads", (), "Get one exact approved partner buy-box, source/landing sign-off, route and payout"),
    ("search_aeo_geo", "SEO/AEO/GEO intelligence and monitoring", ("search_core",), "Prove buyer-specific baseline, named customer, fulfilment and recurring billing"),
    ("solar_intelligence", "Regional solar opportunity intelligence", ("solar_catalog",), "Verify qualified UK/other local buyer, delivery and source-specific price"),
    ("predictive_revenue", "Predictive Revenue / Predictive Cloud", ("predictive_revenue",), "Qualify two founder-review enterprise targets and prove delivery/pricing"),
    ("exchange_seats", "Commercial Exchange buyer seats and territories", ("commercial_exchange",), "Validate one real buyer seat, accepted capacity, exclusive rights and contracted terms"),
    ("property_permit_capital", "Property, permits and private-capital intelligence", ("property", "private_capital", "public_record_intelligence"), "Qualify one actual data buyer and prove the purchased deliverable"),
    ("managed_growth", "Managed growth and opportunity intelligence", ("opportunity_intelligence",), "Qualify client, define scoped deliverables and acceptance/retention proof"),
    ("avatar_voice_workforce", "Digital Avatar, AI Workforce and voice", (), "Complete product-specific pilot tests, live unit economics and first authorised customer"),
    ("saas_white_label", "SaaS tenants and white-label licences", ("recovered_mrr",), "Verify login/tenant isolation, current sellable offer and a paying tenant"),
    ("affiliate_distribution", "Affiliate, reseller and referral channels", (), "Verify lawful referral rules, partner agreement, source attribution and payouts"),
    ("contractor_direct", "Contractor growth, storm and roofing pilots", (), "Qualify a current contractor, verified human contact, scoped pilot and founder-approved outbound"),
    ("insurance_carrier_network", "Insurance carrier / managed-repair B2B intelligence", (), "Verify actual software buyer or authorised managed-repair programme requirements; do not treat vendor onboarding as a purchase"),
    ("claims_settlement_regulated", "Insurance claims / settlement-linked services", (), "Hold: obtain jurisdiction, licence, business model and independent qualified legal approval"),
    ("legal_mass_tort", "Legal and mass-tort intelligence", (), "Verify genuine law-firm buyer, ethical advertising/referral compliance and accepted commercial scope"),
)


def _archived_complete_buyer_requests(root: Path) -> int:
    """Review-only proof of previous comprehensive requests despite newer replies."""
    from empire_os.commercial_relationship_registry import (
        LAST_CONSOLIDATED_BUYER_REQUEST, PARTNER_PILOT_SCOPES,
    )
    path = root / (
        "runtime/buyer_network_intelligence/"
        "buyer_partner_message_index_20261010.json"
    )
    if (not path.is_file() or path.is_symlink()
            or path.stat().st_mode & 0o077 or path.stat().st_size > 500_000):
        return 0
    index = _read_json(path)
    if (not isinstance(index, Mapping)
            or index.get("schema_version")
                != "empire.buyer_gmail_original_message_index.v1"
            or index.get("source") not in (
                "connected_gmail_connector_read_only", "empire_gmail_api_readonly"
            )):
        return 0
    threads = index.get("threads")
    if not isinstance(threads, list) or len(threads) != 4:
        return 0
    indexed = {}
    for item in threads:
        if not isinstance(item, Mapping):
            return 0
        tid = item.get("thread_id")
        if tid in indexed or item.get("truncated") is not False:
            return 0
        messages = item.get("messages")
        if (not isinstance(messages, list)
                or item.get("message_count") != len(messages)):
            return 0
        indexed[tid] = messages
    seen = 0
    for key, expected_id in LAST_CONSOLIDATED_BUYER_REQUEST.items():
        tid = PARTNER_PILOT_SCOPES[key]["reviewed_thread"]
        messages = indexed.get(tid) or []
        if any(isinstance(m, Mapping)
               and m.get("id") == expected_id
               and isinstance(m.get("labels"), list)
               and "SENT" in m["labels"]
               for m in messages):
            seen += 1
    return seen


def stream_portfolio_status(root: Path = ROOT) -> dict[str, Any]:
    """Evidence-bound commercial maturity for EVERY blueprint revenue family.

    This produces no send, claim, price, routing or payment authority.
    Missing sources are UNKNOWN, never silently counted as zero successes.
    """
    sources: dict[str, dict[str, Any] | None] = {}
    source_status = {}
    for key, relative in PORTFOLIO_SOURCES.items():
        path = root / relative
        raw = _read_json(path) if path.is_file() and path.stat().st_size <= 8_000_000 else None
        expected = PORTFOLIO_SCHEMAS[key]
        schema = (raw.get("schema_version") or raw.get("schema")) if isinstance(raw, Mapping) else None
        valid = isinstance(raw, Mapping) and schema == expected
        sources[key] = dict(raw) if valid else None
        source_status[key] = "READABLE_SCHEMA_VERIFIED" if valid else "MISSING_OR_UNEXPECTED_SCHEMA"

    catalog = sources["catalog"]
    products = catalog.get("products") if catalog else None
    if not isinstance(products, list):
        products = []
    family_counts: dict[str, dict[str, int]] = {}
    for item in products:
        if not isinstance(item, Mapping):
            continue
        family = item.get("product_family")
        code = item.get("product_code")
        if not isinstance(family, str) or not isinstance(code, str):
            continue
        group = ("solar_catalog" if code.startswith("solar_opportunity_map_")
                 else "search_core" if family == "search_intelligence"
                 else family)
        counts = family_counts.setdefault(group, {"catalogued": 0, "active": 0, "terms_ready": 0})
        counts["catalogued"] += 1
        counts["active"] += item.get("active") is True
        counts["terms_ready"] += (item.get("active") is True
                                  and item.get("binding_terms_ready") is True)
    relationships = sources["relationships"]
    warm = relationships.get("warm_business_action_queue") if relationships else None
    genuine_partner_count = 0
    if isinstance(warm, list):
        genuine_partner_count = sum(
            isinstance(x, Mapping) and x.get("last_inbound_at") is not None
            and x.get("gmail_snapshot_fresh") is True
            and x.get("company") in (
                "Lead Smart", "LeadBank", "Connexis",
                "Validated / Home Services Lead Group",
            ) for x in warm
        )
    pilot_rows = relationships.get("partner_pilot_readiness_queue") if relationships else None
    if not isinstance(pilot_rows, list):
        pilot_rows = []
    partner_gates_verified = sum(
        x.get("gate_count_verified") == 9
        and x.get("gate_count_total") == 9
        for x in pilot_rows if isinstance(x, Mapping)
    )
    previous_full_request_count = max(
        _archived_complete_buyer_requests(root),
        sum(
            (x.get("single_pass_buyer_intake") or {}).get(
                "past_full_information_request_proven_in_import") is True
            for x in pilot_rows if isinstance(x, Mapping)
        ),
    )
    enterprise = sources["enterprise"]
    exchange = sources["exchange"]
    smart = sources["lead_smart"]
    contractor = sources["contractors"]
    claims_research = sources["claims_research"]
    claims_summary = (
        claims_research.get("summary")
        if isinstance(claims_research, Mapping) else None
    )
    claims_as_of = (
        claims_research.get("as_of") if isinstance(claims_research, Mapping) else None
    )
    # Published programme pages are research leads, not a carrier buyer.
    # A historical preview must not imply today's available network capacity.
    claims_date = None
    if isinstance(claims_as_of, str):
        try:
            claims_date = datetime.fromisoformat(claims_as_of).date()
        except ValueError:
            pass
    claims_age = (
        (datetime.now(timezone.utc).date() - claims_date).days
        if claims_date is not None else None
    )
    claims_current = (
        isinstance(claims_summary, Mapping)
        and type(claims_age) is int and 0 <= claims_age <= 7
        and claims_research.get("mode") == "OBSERVE"
        and claims_research.get("outbound_authorized") is False
        and claims_research.get("execution_authority") == "none"
    )
    payment = sources["payment"]
    funnel = sources["funnel"]

    payment_semantics = payment.get("semantic_truth") if payment else None
    payment_present = (
        isinstance(payment_semantics, Mapping)
        and payment_semantics.get("real_payment_observed") is True
    )
    # An aggregate payment observation, even if true in the future, does
    # not establish allocation to a specific product or customer.
    money_from_any_stream_proven = False
    tam_market_truth = tam_snapshot_truth(
        _read_json(root / "runtime/tam_market_intelligence/latest.json")
    )
    rows = []
    for key, title, families, next_action in REVENUE_STREAM_CONTRACTS:
        grouped = [family_counts.get(name, {}) for name in families]
        counts = {
            "catalogued": sum(n.get("catalogued", 0) for n in grouped),
            "active": sum(n.get("active", 0) for n in grouped),
            "terms_ready": sum(n.get("terms_ready", 0) for n in grouped),
        }
        counterparty = key == "lead_calls" and genuine_partner_count > 0
        offer_ready = counts["terms_ready"] > 0
        blockers = []
        if key == "claims_settlement_regulated":
            blockers.append("REGULATED_CLAIMS_COMPENSATION_AND_LICENSING_HOLD")
        if not counterparty:
            blockers.append("NO_PROVEN_CURRENT_BUYER_CONVERSATION_FOR_STREAM")
        if not offer_ready:
            blockers.append("NO_VERIFIED_IN_SCOPE_CATALOG_TERMS")
        blockers.extend(("CURRENT_CUSTOMER_NEED_OR_BUY_BOX_NOT_VERIFIED",
                         "ONBOARDING_AND_ACCEPTED_AGREEMENT_NOT_VERIFIED",
                         "BUYER_SPECIFIC_DELIVERY_NOT_VERIFIED",
                         "PAYMENT_AND_RECOGNISED_REVENUE_NOT_VERIFIED"))
        if key == "lead_calls":
            if smart is None or smart.get("traffic_enabled") is not False:
                blockers.append("LEAD_SMART_RUNTIME_TRUTH_UNAVAILABLE")
            elif not smart.get("routing", {}).get("runtime_verified") is True:
                blockers.append("LEAD_SMART_BUYER_ROUTE_RUNTIME_NOT_VERIFIED")
            if partner_gates_verified == 0:
                blockers.append("NO_BUYER_PARTNER_FULL_ACTIVATION_GATES")
        if key == "exchange_seats" and exchange is not None:
            if exchange.get("verified_market_price_count") == 0:
                blockers.append("NO_VERIFIED_EXCHANGE_MARKET_PRICE")
        if key == "predictive_revenue" and enterprise is None:
            blockers.append("ENTERPRISE_TARGET_REVIEW_UNAVAILABLE")
        if key in {"insurance_carrier_network", "claims_settlement_regulated"}:
            blockers.append("CARRIER_VENDOR_PROGRAMME_NOT_PROOF_OF_PURCHASE")
            if not claims_current:
                blockers.append("CURRENT_CLAIMS_RESEARCH_EVIDENCE_UNAVAILABLE")
            elif claims_summary.get("founder_review_ready") == 0:
                blockers.append("NO_INDEPENDENTLY_QUALIFIED_CLAIMS_BUYER")
        if key == "contractor_direct" and contractor is None:
            blockers.append("CONTRACTOR_FOUNDER_REVIEW_UNAVAILABLE")
        stage = ("ENGAGED_AWAITING_VERIFIED_BUY_BOX" if counterparty
                 else "CATALOG_READY_NO_BUYER_PROOF" if offer_ready
                 else "RESEARCH_OR_PRODUCT_ACTIVATION_REQUIRED")
        if key == "claims_settlement_regulated":
            stage = "LEGAL_AND_LICENSING_BLOCKED"
        gates = {name: False for name in PORTFOLIO_GATES}
        gates["real_counterparty"] = counterparty
        gates["verified_product_terms"] = offer_ready
        rows.append({
            "stream_key": key, "name": title,
            "stage": stage, "catalog": counts, "gates": gates,
            "single_pass_intake_groups": list(PORTFOLIO_SINGLE_REQUEST_GROUPS),
            "past_complete_request_proven_count": (
                previous_full_request_count if key == "lead_calls" else 0
            ),
            "new_request_authorized": False,
            "claims_research_current": (
                claims_current if key in (
                    "insurance_carrier_network", "claims_settlement_regulated",
                    "contractor_direct",
                ) else None
            ),
            "blocking_evidence": blockers, "next_evidence_task": next_action,
            "legal_gate_required": key in (
                "insurance_carrier_network", "claims_settlement_regulated",
                "legal_mass_tort", "affiliate_distribution",
            ),
            "partner_approved_traffic": False,
            "founder_outbound_authorized": False,
            "actual_revenue": False,
            "execution_authority": "NONE",
        })
    return {
        "schema_version": "empire.revenue_stream_portfolio.v1",
        "mode": "OBSERVE", "stream_count": len(rows),
        "sources": source_status,
        "tam_market_evidence": {
            "available": tam_market_truth["available"],
            "reason_code": tam_market_truth["reason_code"],
            "market_scope_count": tam_market_truth["market_scope_count"],
            "opportunity_class_count": tam_market_truth["opportunity_class_count"],
            "tam_inferred_from_observed_roster": False,
            "buyer_intent_inferred": False,
            "execution_authority": "none",
        },
        "catalog_totals": {
            "total": catalog.get("product_count") if catalog else None,
            "active": catalog.get("active_count") if catalog else None,
            "binding_terms_ready": catalog.get("binding_terms_ready_count") if catalog else None,
        },
        "warm_buyer_conversations_observed": genuine_partner_count if relationships else None,
        "enterprise_internal_review_ready_count": (
            enterprise.get("review_ready_count") if enterprise else None),
        "exchange_seat_records_not_verified_sellable": (
            exchange.get("buyer_seat_count") if exchange else None),
        "exchange_verified_market_price_count": (
            exchange.get("verified_market_price_count") if exchange else None),
        "claims_research": {
            "current": claims_current,
            "as_of": claims_as_of if claims_current else None,
            "input_candidates": claims_summary.get("input_candidates") if claims_current else None,
            "founder_review_ready": claims_summary.get("founder_review_ready") if claims_current else None,
            "matches_for_founder_review": claims_summary.get("matches_for_founder_review") if claims_current else None,
            "source_programs_are_not_verified_buyers": True,
        },
        "current_payment_observation": (
            "PRESENT_REQUIRES_INDEPENDENT_ATTRIBUTION" if payment_present
            else "NOT_OBSERVED" if payment_semantics is not None
            else "UNKNOWN"),
        "funnel_recognized_revenue_cents": (
            funnel.get("recognized_revenue_cents") if funnel else None),
        "payment_per_stream_attributed": money_from_any_stream_proven,
        "streams": rows,
        "external_outbound_authorized": False,
        "contract_acceptance_authorized": False,
        "routing_activation_authorized": False,
        "payment_action_authorized": False,
        "actual_revenue_from_portfolio_proven": False,
        "execution_authority": "NONE",
    }
