from empire_os.data_cloud_closeout_wave import (
    CLOSEOUT_BASE_BRANCH,
    closeout_requests,
    request_snapshot,
)


def test_closeout_wave_covers_every_remaining_software_gate():
    requests = closeout_requests()
    ids = {request.request_id for request in requests}

    assert {
        "empiredb-closeout-observability-v2",
        "empiredb-closeout-rollback-proof",
        "empiredb-closeout-tenant-isolation",
        "empiredb-closeout-recovery-pitr-plan",
        "empiredb-closeout-runtime-canary",
        "empiredb-closeout-final-manifest",
        "empiredb-closeout-independent-verification",
    } <= ids


def test_closeout_jobs_are_pinned_and_authority_bounded():
    requests = closeout_requests()

    assert requests
    assert all(
        request.base_branch == CLOSEOUT_BASE_BRANCH
        for request in requests
    )
    assert all(
        request.authority in {"observe", "internal_write"}
        for request in requests
    )
    assert all(
        request.risk_class != "consequential"
        for request in requests
    )

    snapshot = request_snapshot()
    assert snapshot["production_cutover_authority"] is False
    assert snapshot["canonical_backend_change_authorized"] is False
    assert snapshot["founder_approval_inferred"] is False


def test_mutating_closeout_jobs_use_non_overlapping_logical_leases():
    requests = [
        request
        for request in closeout_requests()
        if request.authority == "internal_write"
    ]

    leases = [
        lease
        for request in requests
        for lease in request.lease_resources
    ]

    assert len(leases) == len(set(leases))
    assert all(lease.startswith("domain:data_cloud_") for lease in leases)


def test_tenant_job_forbids_fabricated_org_ownership():
    request = next(
        row
        for row in closeout_requests()
        if row.request_id == "empiredb-closeout-tenant-isolation"
    )

    objective = request.objective.lower()
    assert "unknown" in objective
    assert "fabricated org ids" in objective
    assert "do not apply migrations" in objective


def test_recovery_job_keeps_external_infrastructure_unproven():
    request = next(
        row
        for row in closeout_requests()
        if row.request_id == "empiredb-closeout-recovery-pitr-plan"
    )

    objective = request.objective.lower()
    assert "do not pretend a second target exists" in objective
    assert "no infrastructure mutation" in objective



def test_unfinished_implementation_lanes_route_to_hermes():
    by_id = {
        request.request_id: request
        for request in closeout_requests()
    }

    for request_id in (
        "empiredb-closeout-observability-v2",
        "empiredb-closeout-rollback-proof",
        "empiredb-closeout-tenant-isolation",
        "empiredb-closeout-recovery-pitr-plan",
        "empiredb-closeout-runtime-canary",
        "empiredb-closeout-final-manifest",
    ):
        assert by_id[request_id].capability == "backend_code"
