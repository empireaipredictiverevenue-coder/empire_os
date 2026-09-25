import pytest

from empire_os.agent_execution_plane import (
    ExecutionJob,
    default_worker_registry,
    execution_plane_authority_contract,
    route_execution_job,
    worker_registry_snapshot,
)


def test_registry_has_expected_workers_and_no_consequential_authority():
    snapshot = worker_registry_snapshot()
    keys = {row["key"] for row in snapshot["workers"]}
    assert {
        "hermes",
        "pi",
        "empire_coder",
        "space_agent",
        "agent_reach",
        "swarm_v6",
        "needle",
        "laya",
    }.issubset(keys)
    for row in snapshot["workers"]:
        assert row["mutates_canonical_data"] is False
        assert row["sends_external"] is False
        assert row["moves_funds"] is False
        assert row["recognizes_revenue"] is False
        assert row["production_deploy"] is False


def test_backend_internal_write_prefers_hermes():
    decision = route_execution_job(
        ExecutionJob(
            job_id="job-1",
            capability="backend_code",
            department="engineering",
            authority="internal_write",
            allowed_paths=("empire_os/example.py",),
        )
    )
    assert decision.eligible is True
    assert decision.worker_key == "hermes"
    assert decision.requires_mutation_lease is True


def test_frontend_internal_write_routes_to_pi():
    decision = route_execution_job(
        ExecutionJob(
            job_id="job-2",
            capability="frontend_code",
            department="product",
            authority="internal_write",
            allowed_paths=("apps/search-command-centre/",),
        )
    )
    assert decision.worker_key == "pi"


def test_public_research_routes_to_agent_reach_observe_only():
    decision = route_execution_job(
        ExecutionJob(
            job_id="job-3",
            capability="social_research",
            department="market_opportunity",
            authority="observe",
            evidence_domains=("reddit", "youtube"),
        )
    )
    assert decision.worker_key == "agent_reach"
    assert decision.requires_mutation_lease is False


def test_founder_workspace_routes_to_space_agent():
    decision = route_execution_job(
        ExecutionJob(
            job_id="job-4",
            capability="founder_workspace",
            department="strategy",
            authority="internal_write",
        )
    )
    assert decision.worker_key == "space_agent"


def test_hermes_unavailable_uses_pi_for_backend_fallback():
    decision = route_execution_job(
        ExecutionJob(
            job_id="job-5",
            capability="backend_code",
            department="engineering",
            authority="internal_write",
            allowed_paths=("empire_os/example.py",),
        ),
        unavailable_workers=frozenset({"hermes"}),
    )
    assert decision.worker_key == "pi"


def test_external_authority_is_rejected_before_routing():
    with pytest.raises(ValueError, match="observe/internal_write"):
        route_execution_job(
            ExecutionJob(
                job_id="job-6",
                capability="backend_code",
                department="engineering",
                authority="governed_external",
            )
        )


def test_authority_contract_keeps_empire_authoritative():
    contract = execution_plane_authority_contract()
    assert contract["worker_can_send_outbound"] is False
    assert contract["worker_can_move_funds"] is False
    assert contract["worker_can_recognize_revenue"] is False
    assert contract["canonical_truth_remains_empire"] is True


def test_every_registry_entry_validates():
    for worker in default_worker_registry():
        worker.validate()
