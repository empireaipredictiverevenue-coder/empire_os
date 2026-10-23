"""PRIME edge/DePIN deployment review, without infrastructure authority.

Extends the existing EmpireOS sovereign host observer and PRIME workload
contracts. This is a pure *proposal evaluator*: no provider SDK, DNS,
network calls, secrets, subprocess, DB connection, WAL/slot action, spending,
or automation. False/unknown evidence can never be upgraded by the caller.

Review candidates are NOT verified quotes, running clusters, live databases,
finance authority or customer tenant access. No server is provisioned here.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

SCHEMA = "empire.predictive_cloud.edge_depin_governance.v1"
GPU_PROVIDERS = frozenset({"io.net", "akash", "render_network"})
GPU_WORKLOADS = frozenset({"private_llm_inference", "approved_embedding_batch", "scientific_scenario_batch"})
REPLICA_MODES = frozenset({"physical_standby", "logical_publication"})
REGIONS = frozenset({"us-east", "eu-central", "ap-south"})
MAX_CENTS = 1_000_000_000_000
# Founder policy: zero external GPU and edge expenditure until authentic
# realised revenue is independently read from the canonical financial source
# and a DIFFERENT, explicitly reviewed release changes this constant.
# A claimed CRM win, hypothetical P90, Boolean flag or caller-supplied receipt
# may never unlock GPU compute under this version of the module.
REVENUE_GATED_COMPUTE_SPEND_CAP_CENTS = 0


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip() or len(value) > 160:
        raise ValueError(f"{field} must be a bounded string")
    return value.strip()


def _integer(value: Any, name: str, *, maximum: int) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _date(value: Any) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware evaluation time required")
    return value.astimezone(timezone.utc)


def _strict(row: Mapping[str, Any], names: frozenset[str], *, name: str) -> None:
    if not isinstance(row, Mapping) or set(row) != names:
        raise ValueError(f"{name} must have exact approved fields")


GPU_FIELDS = frozenset({
    "provider", "region", "workload", "gpu_count", "hours", "currency",
    "quoted_gpu_hour_cents", "monthly_spend_cap_cents",
    "quote_ref", "quote_valid_until", "container_digest",
    "approved_data_classification", "data_residency_approved",
    "private_network_verified", "egress_cost_cents",
    "total_non_gpu_cost_cents", "founder_spend_approved",
})

REPLICA_FIELDS = frozenset({
    "region", "replication_mode", "purpose",
    "replicated_table_count", "inventory_source_ref",
    "data_owner_approved", "regional_processing_rights_verified",
    "tenant_isolation_evaluated", "encrypted_transport_verified",
    "read_only_access_verified", "restore_drill_verified",
    "schema_sequence_consistency_verified",
    "slot_wal_retention_limit_verified", "lag_monitoring_verified",
    "backup_chain_preserved", "rollback_procedure_reviewed",
    "release_owner_approved",
})


def review_gpu_candidate(raw: Mapping[str, Any], *, as_of: datetime) -> dict[str, Any]:
    """Finite quote math, explicit spend ceiling and fail-closed authority."""
    now = _date(as_of)
    _strict(raw, GPU_FIELDS, name="GPU candidate")
    provider = _text(raw["provider"], "provider")
    region = _text(raw["region"], "region")
    workload = _text(raw["workload"], "workload")
    currency = _text(raw["currency"], "currency")
    if provider not in GPU_PROVIDERS or region not in REGIONS:
        raise ValueError("provider/region not in approved research scope")
    if workload not in GPU_WORKLOADS:
        raise ValueError("unsupported GPU workload")
    # No invented BTC/AKT/IO conversion rates.
    if currency not in {"GBP", "USD"}:
        raise ValueError("only explicit fiat quote currencies supported")
    gpu_count = _integer(raw["gpu_count"], "gpu_count", maximum=8)
    hours = _integer(raw["hours"], "hours", maximum=720)
    cap = _integer(raw["monthly_spend_cap_cents"], "monthly_spend_cap_cents", maximum=MAX_CENTS)
    if cap != REVENUE_GATED_COMPUTE_SPEND_CAP_CENTS:
        raise ValueError("GPU budget is frozen until independently verified revenue")
    if not 1 <= gpu_count <= 8 or not 1 <= hours <= 720:
        raise ValueError("positive bounded GPU count and hours required")
    blockers = []
    price = raw["quoted_gpu_hour_cents"]
    ref = raw["quote_ref"]
    expiry = raw["quote_valid_until"]
    quote_complete = price is not None and ref is not None and expiry is not None
    total_cost = None
    if quote_complete:
        unit = _integer(price, "quoted_gpu_hour_cents", maximum=MAX_CENTS)
        _text(ref, "quote ref")
        if isinstance(expiry, str):
            try:
                expiry = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError("invalid quote expiry") from None
        if not isinstance(expiry, datetime) or expiry.tzinfo is None or expiry.utcoffset() is None:
            raise ValueError("timezone-aware quote expiry required")
        if expiry.astimezone(timezone.utc) <= now:
            blockers.append("GPU_QUOTE_EXPIRED")
        egress = raw["egress_cost_cents"]
        non_gpu = raw["total_non_gpu_cost_cents"]
        if egress is None or non_gpu is None:
            blockers.append("GPU_TOTAL_COSTS_UNVERIFIED")
        else:
            egress = _integer(egress, "egress_cost_cents", maximum=MAX_CENTS)
            non_gpu = _integer(non_gpu, "total_non_gpu_cost_cents", maximum=MAX_CENTS)
            total_cost = unit * hours * gpu_count + egress + non_gpu
            if total_cost > MAX_CENTS:
                blockers.append("GPU_TOTAL_COST_TOO_LARGE")
            if total_cost > cap:
                blockers.append("GPU_COST_EXCEEDS_SPEND_CAP")
    else:
        blockers.append("INDEPENDENT_PROVIDER_QUOTE_REQUIRED")
        if any(value is not None for value in (price, ref, expiry)):
            blockers.append("INCOMPLETE_GPU_QUOTE")
    image = raw["container_digest"]
    if type(image) is not str or not image.startswith("sha256:") or len(image) != 71:
        blockers.append("PINNED_SIGNED_IMAGE_REVIEW_REQUIRED")
    elif any(c not in "0123456789abcdef" for c in image[7:]):
        blockers.append("PINNED_SIGNED_IMAGE_REVIEW_REQUIRED")
    if raw["approved_data_classification"] != "public_or_synthetic":
        blockers.append("CUSTOMER_DATA_PROVIDER_AUTHORIZATION_REQUIRED")
    for flag, code in (
        ("data_residency_approved", "REGIONAL_DATA_RIGHTS_REQUIRED"),
        ("private_network_verified", "PRIVATE_NETWORK_UNVERIFIED"),
        ("founder_spend_approved", "FOUNDER_SPEND_APPROVAL_REQUIRED"),
    ):
        if raw[flag] is not True:
            blockers.append(code)
    if cap == 0:
        blockers.append("ZERO_SPEND_POLICY")
    # A supplied "founder_spend_approved" Boolean is not founder authority.
    # No bypass is possible from CRM stages, expected deal values, quoted
    # revenue, or untrusted simulated results. This is research-only.
    blockers.extend((
        "VERIFIED_REALIZED_REVENUE_REQUIRED_BEFORE_GPU_SPENDING",
        "SEPARATE_FOUNDER_GPU_RELEASE_APPROVAL_REQUIRED",
        "PROVIDER_API_AND_QUOTE_CUSTODY_NOT_INDEPENDENTLY_VERIFIED",
    ))
    return {
        "provider": provider, "region": region, "workload": workload,
        "gpu_count_requested": gpu_count,
        "hours_requested": hours,
        "currency": currency,
        "quoted_total_cost_minor_units": total_cost,
        "total_cost_is_quote_projection_only": True,
        "monthly_spend_cap_minor_units": cap,
        "provider_api_endpoint_verified": False,
        "provider_price_verified": False,
        "token_currency_conversion_proven": False,
        "supply_confirmed": False,
        "realized_revenue_eligibility_independently_verified": False,
        "paid_gpu_work_allowed": False,
        "existing_local_compute_preserved": True,
        "blockers": sorted(set(blockers)),
        "provisioning_authority": "none",
        "cluster_provisioned": False,
        "external_request_sent": False,
    }


def review_replica_candidate(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Review replica risk without modifying live EmpireDB/PostgreSQL 18."""
    _strict(raw, REPLICA_FIELDS, name="replica candidate")
    region = _text(raw["region"], "region")
    if region not in REGIONS:
        raise ValueError("unsupported replica geography")
    mode = _text(raw["replication_mode"], "mode")
    if mode not in REPLICA_MODES:
        raise ValueError("unsupported replication mode")
    purpose = _text(raw["purpose"], "purpose")
    if purpose != "analytics_read_only":
        raise ValueError("only read-only analytical replicas considered")
    count = _integer(raw["replicated_table_count"], "replicated_table_count", maximum=10000)
    if count < 1:
        raise ValueError("positive bounded replica table inventory required")
    blockers = []
    if raw["inventory_source_ref"] is None:
        blockers.append("TABLE_INVENTORY_NOT_VERIFIED")
    else:
        _text(raw["inventory_source_ref"], "inventory_source_ref")
    for flag, code in (
        ("data_owner_approved", "DATA_OWNER_PERMISSION_MISSING"),
        ("regional_processing_rights_verified", "REGIONAL_TRANSFER_RIGHTS_UNVERIFIED"),
        ("tenant_isolation_evaluated", "TENANT_RLS_REVIEW_REQUIRED"),
        ("encrypted_transport_verified", "MUTUAL_TLS_OR_PRIVATE_LINK_REQUIRED"),
        ("read_only_access_verified", "REPLICA_READ_ONLY_ACCESS_NOT_VERIFIED"),
        ("restore_drill_verified", "REPLICA_RECOVERY_REHEARSAL_REQUIRED"),
        ("schema_sequence_consistency_verified", "REPLICATION_SCHEMA_SEQUENCES_NOT_VERIFIED"),
        ("slot_wal_retention_limit_verified", "SLOT_WAL_RETENTION_CAP_MISSING"),
        ("lag_monitoring_verified", "REPLICA_LAG_MONITORING_REQUIRED"),
        ("backup_chain_preserved", "CANONICAL_PGBACKREST_CHAIN_MUST_BE_PRESERVED"),
        ("rollback_procedure_reviewed", "REPLICA_ROLLBACK_NOT_REVIEWED"),
        ("release_owner_approved", "CANONICAL_DB_OWNER_APPROVAL_REQUIRED"),
    ):
        if raw[flag] is not True:
            blockers.append(code)
    # Candidate checks cannot substitute for actual source DB privilege and
    # PostgreSQL run-state inspection; fail-closed even if booleans are True.
    blockers.append("REPLICA_TOPOLOGY_AND_LSN_NOT_INDEPENDENTLY_VERIFIED")
    if mode == "logical_publication":
        blockers.append("LOGICAL_DDL_SEQUENCE_AND_CONFLICT_POLICY_REVIEW_REQUIRED")
    return {
        "region": region, "replication_mode": mode,
        "purpose": purpose, "tables_requested": count,
        "publication_created": False, "replication_slot_created": False,
        "source_primary_relocated": False,
        "reader_authority": "none", "execution_authority": "none",
        "blockers": sorted(set(blockers)),
    }


def review_edge_expansion(
    *, as_of: datetime,
    gpu_candidates: Sequence[Mapping[str, Any]] = (),
    replica_candidates: Sequence[Mapping[str, Any]] = (),
    founder_spend_cap_cents: int = 0,
    observe_only: bool = True,
) -> dict[str, Any]:
    """No live deployment; zero-cost default and immutable core authority."""
    now = _date(as_of)
    if observe_only is not True:
        raise ValueError("edge proposals cannot request execution")
    cap = _integer(founder_spend_cap_cents, "founder_spend_cap_cents", maximum=MAX_CENTS)
    if cap != REVENUE_GATED_COMPUTE_SPEND_CAP_CENTS:
        raise ValueError("Founder compute spend stays at zero before verified revenue")
    if type(gpu_candidates) not in (tuple, list) or len(gpu_candidates) > 4:
        raise ValueError("bounded GPU candidate count required")
    if type(replica_candidates) not in (tuple, list) or len(replica_candidates) > 2:
        raise ValueError("bounded replica candidate count required")
    gpus = [review_gpu_candidate(row, as_of=now) for row in gpu_candidates]
    replicas = [review_replica_candidate(row) for row in replica_candidates]
    if any(row["monthly_spend_cap_minor_units"] > cap for row in gpus):
        raise ValueError("candidate spend cap exceeds founder-level cap")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "as_of": now.isoformat(),
        "canonical_database": "EmpireDB",
        "current_primary_location": "NOT_INDEPENDENTLY_GEO_VERIFIED",
        "current_primary_relocation": False,
        "disaster_recovery_owner": "existing EmpireDB pgBackRest programme",
        "edge_routing": "NOT_CONFIGURED_BY_THIS_REVIEW",
        "gpu_candidates": gpus, "replica_candidates": replicas,
        "compute_spend_cap_minor_units": cap,
        "zero_paid_gpu_until_realized_revenue": True,
        "independently_verified_realized_revenue_available": False,
        "existing_local_inference_preserved": True,
        "existing_astra_and_prime_unchanged": True,
        "existing_empiredb_primary_unchanged": True,
        "new_gpu_nodes_provisioned": 0, "new_replicas_created": 0,
        "dns_modified": False, "services_changed": False,
        "database_mutation": False, "database_wal_configuration_modified": False,
        "data_transfer_executed": False, "secrets_accessed": False,
        "provider_calls": 0, "payments_made": False,
        "outbound_sent": False, "production_deployment": False,
        "revenue_verified": False,
        "execution_authority": "none",
        "blockers": [
            "NO_GPU_OR_EDGE_SPENDING_BEFORE_VERIFIED_REALIZED_REVENUE",
            "EXISTING_SOVEREIGN_CAPACITY_MUST_BE_MEASURED_FIRST",
            "ANYCAST_MULTI_REGION_ROUTING_HAS_NOT_BEEN_PROVISIONED",
            "CANONICAL_OWNER_AND_EXACT_RELEASE_APPROVAL_REQUIRED",
        ],
    }
