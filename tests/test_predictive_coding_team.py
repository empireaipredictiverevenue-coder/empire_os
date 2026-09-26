from empire_os.agent_execution_plane import (
    ExecutionJob,
    route_execution_job,
)
from empire_os.predictive_coding_team import (
    predictive_cloud_coding_team_requests,
)


def _route(request):
    return route_execution_job(
        ExecutionJob(
            job_id=request.request_id,
            capability=request.capability,
            department=request.department,
            risk_class=request.risk_class,
            authority=request.authority,
            source_ref=request.source_ref,
            allowed_paths=request.allowed_paths,
            evidence_domains=request.evidence_domains,
            success_condition=request.success_condition,
            required_tests=request.required_tests,
        )
    )


def test_predictive_coding_team_has_five_non_overlapping_lanes():
    requests = predictive_cloud_coding_team_requests()
    assert len(requests) == 5

    ids = [request.request_id for request in requests]
    assert len(set(ids)) == 4

    mutating_paths = []
    for request in requests:
        request.validate()
        if request.authority == "internal_write":
            mutating_paths.extend(request.allowed_paths)

    assert len(mutating_paths) == len(set(mutating_paths))


def test_predictive_coding_team_routes_to_expected_workers():
    requests = {
        request.request_id: request
        for request in predictive_cloud_coding_team_requests()
    }

    assert _route(
        requests["predictive-quantum-exchange-bridge-v1"]
    ).worker_key == "hermes"

    assert _route(
        requests["predictive-action-portfolio-design-v1"]
    ).worker_key == "pi"

    assert _route(
        requests["predictive-action-portfolio-implementation-v2"]
    ).worker_key == "hermes"

    assert _route(
        requests["predictive-algorithm-verification-hardening-v1"]
    ).worker_key == "empire_coder"

    assert _route(
        requests["predictive-algorithm-integration-qa-v1"]
    ).worker_key == "swarm_v6"


def test_coding_team_tasks_preserve_authority_boundaries():
    for request in predictive_cloud_coding_team_requests():
        assert request.authority in {"observe", "internal_write"}
        assert request.risk_class != "consequential"
        assert all(
            target.startswith("tests/")
            for target in request.required_tests
        )
