"""Existing worker roles are inventory, NOT trusted online agent identities."""
from empire_os.agent_collaboration_readiness import review_existing_agent_collaboration


def test_no_credential_or_connected_worker_is_invented(tmp_path):
    result = review_existing_agent_collaboration(tmp_path)
    assert result["existing_department_definitions"] > 0
    assert result["existing_role_definitions"] > 0
    assert result["existing_execution_worker_catalogue"] > 0
    assert result["status"] == "CODE_INTEGRATED_CREDENTIAL_AND_RUNTIME_BINDING_HELD"
    assert result["trusted_agent_credentials_verified"] is False
    assert result["per_agent_process_identity_proven"] is False
    assert result["runtime_message_delivery_activated"] is False
    assert result["model_tool_execution_activated_by_collaboration"] is False
    assert result["external_outbound_authority"] == "none"
    assert result["payment_authority"] == "none"
    assert result["unbound_canonical_queue_counts"]["ready"] == 0
    assert not (tmp_path / "runtime").exists()


def test_no_secret_values_or_private_task_bodies_emitted(tmp_path):
    from empire_os.department_work_queue import DepartmentWorkQueue
    queue = DepartmentWorkQueue(tmp_path)
    queue.enqueue_step(
        plan_id="synthetic",
        step={
            "step_id": "task-one",
            "goal_key": "safe",
            "department_keys": ["sales_revenue"],
            "target_component": "identity_enrichment",
            "action": "inspect",
            "authority": "observe",
            "intelligence_request": {"untrusted": "NEVER_IN_READINESS"},
        },
    )
    result = review_existing_agent_collaboration(tmp_path)
    assert result["unbound_canonical_queue_counts"]["ready"] == 1
    assert "NEVER_IN_READINESS" not in str(result)
