"""EmpireDB closeout work wave for the governed execution plane.

This module creates bounded, non-overlapping engineering requests for the final
Empire Data Cloud gates. It does not execute a cutover, mutate canonical data,
change database schema itself, send outbound, move funds, or recognize revenue.

Workers remain constrained by the Agent & Tool Execution Plane and its lease,
sandbox, test and verification policies.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from empire_os.execution_plane_dispatcher import ExecutionRequest


SOURCE_REF = "empiredb-closeout-2026-09-27"
CLOSEOUT_BASE_BRANCH = "agent/data-cloud-wave4"


def closeout_requests() -> tuple[ExecutionRequest, ...]:
    return (
        ExecutionRequest(
            request_id="empiredb-closeout-observability-v2",
            capability="backend_code",
            department="platform_reliability",
            objective=(
                "Finish Empire Data Cloud observability root-cause work. "
                "Verify the postgres-owned pgBackRest observer, the privileged "
                "health projection, Reliability Agent ingestion and exactly one "
                "canonical Founder Dashboard system service. Fix production "
                "code only; do not weaken service hardening, expose credentials, "
                "change EMPIRE_DATA_BACKEND, create backups, restore data or "
                "perform cutover. Return tests and live-verification commands."
            ),
            authority="internal_write",
            risk_class="high",
            source_ref=SOURCE_REF,
            base_branch=CLOSEOUT_BASE_BRANCH,
            allowed_paths=(
                "empire_os/data_cloud_backup_observer.py",
                "empire_os/data_cloud_runtime_health.py",
                "empire_os/ops_privileged_helper.py",
                "empire_os/ops_privileged_client.py",
                "empire_os/reliability_agent.py",
                "empire_os/founder_dashboard.py",
                "deploy/systemd/empire-data-cloud-backup-observer.service",
                "deploy/systemd/empire-founder-dashboard-api.service",
                "scripts/install_empire_data_cloud_observability.sh",
                "tests/test_data_cloud_backup_observer.py",
                "tests/test_data_cloud_runtime_health.py",
                "tests/test_ops_privileged_helper.py",
                "tests/test_reliability_agent.py",
                "tests/test_founder_dashboard.py",
            ),
            lease_resources=("domain:data_cloud_observability",),
            success_condition=(
                "Local encrypted backup state, EmpireDB, PgBouncer, Reliability "
                "Agent and Founder Dashboard are observed read-only with no "
                "canonical cutover authority and focused regressions pass."
            ),
            required_tests=(
                "tests/test_data_cloud_backup_observer.py",
                "tests/test_data_cloud_runtime_health.py",
                "tests/test_ops_privileged_helper.py",
                "tests/test_reliability_agent.py",
            ),
            max_runtime_seconds=1200,
        ),
        ExecutionRequest(
            request_id="empiredb-closeout-rollback-proof",
            capability="backend_code",
            department="platform_reliability",
            objective=(
                "Build a deterministic READ-ONLY EmpireDB rollback readiness "
                "verifier. Prove Supabase configuration is retained, current "
                "canonical backend remains supabase_legacy before approval, "
                "the backend selection can be reverted without destructive "
                "database work, required services can be enumerated for bounded "
                "restart, and Supabase retirement has not occurred. Never print "
                "secrets and never change environment files or services."
            ),
            authority="internal_write",
            risk_class="high",
            source_ref=SOURCE_REF,
            base_branch=CLOSEOUT_BASE_BRANCH,
            allowed_paths=(
                "empire_os/data_cloud_rollback_readiness.py",
                "tests/test_data_cloud_rollback_readiness.py",
                "docs/EMPIRE_DATA_CLOUD_ROLLBACK.md",
            ),
            lease_resources=("domain:data_cloud_rollback",),
            success_condition=(
                "Read-only rollback verifier reports explicit reversible state, "
                "fails closed on missing legacy configuration and retains "
                "production_cutover_authority=false."
            ),
            required_tests=("tests/test_data_cloud_rollback_readiness.py",),
            max_runtime_seconds=1200,
        ),
        ExecutionRequest(
            request_id="empiredb-closeout-tenant-isolation",
            capability="backend_code",
            department="security_platform",
            objective=(
                "Design and implement the next additive EmpireDB tenant-security "
                "slice without breaking current single-tenant service semantics. "
                "First inventory tenant-bearing tables and trusted org identity "
                "paths. Introduce trusted session tenant context and tenant-scoped "
                "RLS only where ownership is structurally provable. Add cross-tenant "
                "negative tests. Unknown ownership must remain UNKNOWN and must "
                "not be backfilled with fabricated org IDs. Do not apply migrations "
                "to production and do not alter canonical backend."
            ),
            authority="internal_write",
            risk_class="high",
            source_ref=SOURCE_REF,
            base_branch=CLOSEOUT_BASE_BRANCH,
            allowed_paths=(
                "migrations/empiredb/018_tenant_context_foundation.sql",
                "empire_os/data_cloud_tenant_security.py",
                "tests/test_data_cloud_tenant_security.py",
                "docs/EMPIRE_DATA_CLOUD_TENANT_SECURITY.md",
            ),
            lease_resources=("domain:data_cloud_tenant_security",),
            success_condition=(
                "Tenant context is fail-closed, cross-tenant negative tests exist, "
                "no unknown org ownership is invented, and migration remains "
                "unapplied pending separate live verification."
            ),
            required_tests=("tests/test_data_cloud_tenant_security.py",),
            max_runtime_seconds=1800,
        ),
        ExecutionRequest(
            request_id="empiredb-closeout-recovery-pitr-plan",
            capability="backend_code",
            department="platform_reliability",
            objective=(
                "Produce the production architecture delta and executable proof "
                "plan for off-node encrypted pgBackRest backup, WAL archiving/PITR "
                "and single-node recovery. Reuse current PostgreSQL 18 + pgBackRest. "
                "Do not pretend a second target exists. Specify the exact external "
                "storage/failure-domain requirement, encryption, retention, restore "
                "drill, RPO/RTO evidence and fail-closed readiness criteria. "
                "No infrastructure mutation or paid resource commitment."
            ),
            authority="internal_write",
            risk_class="medium",
            source_ref=SOURCE_REF,
            base_branch=CLOSEOUT_BASE_BRANCH,
            allowed_paths=(
                "docs/EMPIRE_DATA_CLOUD_RECOVERY_PITR.md",
                "tests/test_data_cloud_recovery_contract.py",
            ),
            lease_resources=("domain:data_cloud_recovery_architecture",),
            success_condition=(
                "Architecture and automated contract tests make off-node/PITR "
                "requirements explicit and keep both gates false until real "
                "infrastructure evidence exists."
            ),
            required_tests=("tests/test_data_cloud_recovery_contract.py",),
            max_runtime_seconds=1200,
        ),
        ExecutionRequest(
            request_id="empiredb-closeout-runtime-canary",
            capability="backend_code",
            department="platform_reliability",
            objective=(
                "Build a bounded READ-ONLY production-service canary for the "
                "EmpireDB candidate through PgBouncer. Reuse the canonical gateway "
                "and existing application repositories where possible. Verify "
                "representative read paths and safe transaction-rollback write "
                "semantics without changing EMPIRE_DATA_BACKEND, moving funds, "
                "sending outbound, recognizing revenue or leaving persisted canary "
                "rows. Report exact services/paths proven and UNKNOWN for anything "
                "not exercised."
            ),
            authority="internal_write",
            risk_class="high",
            source_ref=SOURCE_REF,
            base_branch=CLOSEOUT_BASE_BRANCH,
            allowed_paths=(
                "empire_os/data_cloud_runtime_canary.py",
                "tests/test_data_cloud_runtime_canary.py",
                "docs/EMPIRE_DATA_CLOUD_RUNTIME_CANARY.md",
            ),
            lease_resources=("domain:data_cloud_runtime_canary",),
            success_condition=(
                "Representative EmpireOS application reads and rollback-only "
                "writes are proven through PgBouncer with no canonical switch "
                "and production_cutover_authority=false."
            ),
            required_tests=("tests/test_data_cloud_runtime_canary.py",),
            max_runtime_seconds=1500,
        ),
        ExecutionRequest(
            request_id="empiredb-closeout-final-manifest",
            capability="backend_code",
            department="platform_reliability",
            objective=(
                "Build a machine-readable final EmpireDB cutover manifest generator "
                "that consumes existing verified artifacts only. It must report every "
                "gate GREEN/OPEN/UNKNOWN with evidence refs, prohibit promotion while "
                "off-node backup, PITR, tenant isolation, rollback or runtime proof "
                "is open, and always return production_cutover_authority=false. "
                "Founder approval must remain an external explicit gate; never infer it."
            ),
            authority="internal_write",
            risk_class="high",
            source_ref=SOURCE_REF,
            base_branch=CLOSEOUT_BASE_BRANCH,
            allowed_paths=(
                "empire_os/data_cloud_cutover_manifest.py",
                "tests/test_data_cloud_cutover_manifest.py",
                "docs/EMPIRE_DATA_CLOUD_CUTOVER_RUNBOOK.md",
            ),
            lease_resources=("domain:data_cloud_cutover_manifest",),
            success_condition=(
                "Manifest fails closed, never infers approval and accurately "
                "aggregates readiness without performing cutover."
            ),
            required_tests=("tests/test_data_cloud_cutover_manifest.py",),
            max_runtime_seconds=1200,
        ),
        ExecutionRequest(
            request_id="empiredb-closeout-independent-verification",
            capability="integration_qa",
            department="platform_assurance",
            objective=(
                "Independently verify the complete EmpireDB closeout proposal wave. "
                "Check authority invariants, no canonical backend switch, no destructive "
                "database action, no secret exposure, test coverage, service topology, "
                "rollback readiness, tenant isolation negative tests, recovery/PITR "
                "truthfulness and final-manifest fail-closed behavior. Verification "
                "only; do not mutate production."
            ),
            authority="observe",
            risk_class="high",
            source_ref=SOURCE_REF,
            base_branch=CLOSEOUT_BASE_BRANCH,
            evidence_domains=(
                "data_cloud_observability",
                "data_cloud_rollback",
                "data_cloud_tenant_security",
                "data_cloud_recovery_architecture",
                "data_cloud_cutover_manifest",
            ),
            success_condition=(
                "Independent verification produces explicit pass/fail evidence "
                "for every closeout gate and no production mutation."
            ),
            max_runtime_seconds=1200,
        ),
    )


def request_snapshot() -> dict[str, object]:
    requests = closeout_requests()
    return {
        "schema_version": "empire.data-cloud-closeout-wave.v1",
        "source_ref": SOURCE_REF,
        "request_count": len(requests),
        "requests": [request.as_dict() for request in requests],
        "production_cutover_authority": False,
        "canonical_backend_change_authorized": False,
        "founder_approval_inferred": False,
    }
