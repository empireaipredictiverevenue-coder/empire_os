"""Read-only truth check for existing Department agent communication readiness.

"Role declared" is NOT "agent instance online". No runtime credential,
network, process, model or database access. No activation side effects.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from empire_os.agent_execution_plane import worker_registry_snapshot
from empire_os.departments import default_departments
from empire_os.department_collaboration import build_kanban_board


def review_existing_agent_collaboration(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    departments = default_departments()
    workers = worker_registry_snapshot()
    board = build_kanban_board(root, max_cards_per_lane=1)
    counts = {name: lane["total"] for name, lane in board["lanes"].items()}

    return {
        "schema_version": "empire.agent_collaboration_readiness.v1",
        "status": "CODE_INTEGRATED_CREDENTIAL_AND_RUNTIME_BINDING_HELD",
        "operating_mode": "OBSERVE",
        "existing_department_definitions": len(departments),
        "existing_role_definitions": sum(len(d.agent_roles) for d in departments),
        "existing_execution_worker_catalogue": len(workers.get("workers", ())),
        "roles_are_not_connected_agent_instances": True,
        "trusted_agent_credentials_verified": False,
        "per_agent_process_identity_proven": False,
        "runtime_message_delivery_activated": False,
        "model_tool_execution_activated_by_collaboration": False,
        "browser_kanban_authenticated": False,
        "crm_tenant_read_endpoint_source_present": (
            (root / "empire_os/revenue_crm_api.py").is_file()
        ),
        "global_internal_board_exposed_to_tenant": False,
        "unbound_canonical_queue_counts": counts,
        "untrusted_agent_messages_cannot_approve_work": True,
        "external_outbound_authority": "none",
        "payment_authority": "none",
        "execution_authority": "none",
        "next_gate": "identity_provenance_and_runtime_credential_provisioning",
    }
