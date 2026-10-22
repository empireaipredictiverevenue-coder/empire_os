#!/usr/bin/env python3
"""One-shot real filesystem queue + signed peer handoff, in an isolated root.

Uses existing department role definitions and DepartmentWorkQueue only.
Temporary Ed25519 keys live in process memory; broker stores public keys.
This is NOT activation of production workers, model inference or outreach.
"""
from __future__ import annotations

import json
import secrets
import sys
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from empire_os.department_collaboration import (
    AgentPublicCredential,
    CollaborationDenied,
    DepartmentCollaboration,
    _canonical,
    build_kanban_board,
    existing_role_profile,
)
from empire_os.department_work_queue import DepartmentWorkQueue, DepartmentWorkStatus

AGENT = "empire_coder_canary"
RESEARCH = "market_research_canary"
PLAN = "department_collaboration_canary_20261022"
STEP = "signed_handoff_reviewer_protocol"
CANARY_ONLY = "Synthetic protocol validation. No external contact or model execution."


def signature(private: Ed25519PrivateKey, envelope: dict) -> str:
    return private.sign(_canonical(envelope)).hex()


def run_isolated_canary() -> dict:
    # Each private key exists only inside this one-shot process and is never
    # registered in production, written to a file or printed.
    builder_private = Ed25519PrivateKey.generate()
    research_private = Ed25519PrivateKey.generate()
    profiles = {
        AGENT: AgentPublicCredential(
            existing_role_profile(
                agent_id=AGENT, department="engineering", role="coder",
                capabilities=("empire_coder",),
                persona="Exact evidence first; request research when blocked.",
            ), builder_private.public_key(),
        ),
        RESEARCH: AgentPublicCredential(
            existing_role_profile(
                agent_id=RESEARCH, department="market_intelligence", role="research",
                capabilities=("intelligence_fabric",),
                persona="Cite only verified sources; no asserted revenue outcomes.",
            ), research_private.public_key(),
        ),
    }

    with tempfile.TemporaryDirectory(prefix="empire_collab_canary_") as temporary:
        root = Path(temporary)
        queue = DepartmentWorkQueue(root)
        item, created = queue.enqueue_step(
            plan_id=PLAN,
            step={
                "step_id": STEP,
                "goal_key": "governed_agent_communication",
                "department_keys": ["engineering"],
                "target_component": "empire_coder",
                "action": "local_signed_a2a_protocol_observation",
                "authority": "observe",
                "success_condition": "replay_safe_peer_reply_and_review_evidence",
                "intelligence_request": {
                    "canary_only": True,
                    "no_external_research": True,
                    "no_model_inference": True,
                },
            }, priority=75,
        )
        assert created and item.status is DepartmentWorkStatus.READY
        assert build_kanban_board(root)["lanes"]["ready"]["total"] == 1

        bus = DepartmentCollaboration(root, profiles)
        pickup = {"op": "pickup", "agent_id": AGENT, "nonce": secrets.token_urlsafe(24)}
        claimed = bus.pickup(pickup, signature(builder_private, pickup))
        if claimed.get("state") != "LEASED_NOT_EXECUTED" or claimed["work_id"] != item.id:
            raise RuntimeError("canonical_claim_missing")
        if build_kanban_board(root)["lanes"]["running"]["total"] != 1:
            raise RuntimeError("lease_state_not_running")
        try:
            bus.pickup(pickup, signature(builder_private, pickup))
        except CollaborationDenied as exc:
            if str(exc) != "pickup_nonce_already_used":
                raise
            pickup_replay_denied = True
        else:
            raise RuntimeError("pickup_replay_was_accepted")

        ask = {
            "op": "send", "agent_id": AGENT, "recipient": RESEARCH,
            "work_id": item.id, "kind": "help_request",
            "body": "Review the local protocol canary's scope; no external queries.",
            "nonce": secrets.token_urlsafe(24),
        }
        ask_receipt = bus.send(ask, signature(builder_private, ask))
        inbox_env = {"op": "inbox", "agent_id": RESEARCH,
                     "nonce": secrets.token_urlsafe(24)}
        inbox = bus.inbox(inbox_env, signature(research_private, inbox_env))
        if len(inbox["messages"]) != 1 or inbox["messages"][0]["id"] != ask_receipt["message_id"]:
            raise RuntimeError("researcher_inbox_not_verified")

        reply = {
            "op": "send", "agent_id": RESEARCH, "recipient": AGENT,
            "work_id": item.id, "kind": "evidence",
            "body": "Scope review: only local synthetic protocol steps observed.",
            "reply_to": ask_receipt["message_id"],
            "nonce": secrets.token_urlsafe(24),
        }
        reply_receipt = bus.send(reply, signature(research_private, reply))
        inbox_env = {"op": "inbox", "agent_id": AGENT,
                     "nonce": secrets.token_urlsafe(24)}
        builder_inbox = bus.inbox(inbox_env, signature(builder_private, inbox_env))
        messages = builder_inbox["messages"]
        if len(messages) != 1 or messages[0]["reply_to"] != ask_receipt["message_id"]:
            raise RuntimeError("verified_reply_chain_missing")
        if messages[0]["id"] != reply_receipt["message_id"]:
            raise RuntimeError("incorrect_reply_message")

        # Independently re-validate BOTH immutable on-disk records using
        # verifier-only public keys, not either message author's assertion.
        checked_ask = bus._verified_message(ask_receipt["message_id"])
        checked_reply = bus._verified_message(reply_receipt["message_id"])
        if (
            checked_ask is None or checked_reply is None
            or checked_ask["sender"] != AGENT
            or checked_reply["sender"] != RESEARCH
            or checked_reply["reply_to"] != checked_ask["id"]
            or checked_ask["work_id"] != claimed["work_id"]
            or checked_reply["work_id"] != claimed["work_id"]
        ):
            raise RuntimeError("independent_public_key_review_failed")

        # The task itself is a genuine local cryptographic protocol exercise.
        # Mark this *synthetic isolated task* DONE only after deterministic
        # independent-of-authors verification; never touch EmpireOS live queue.
        active = queue._load(queue.running / f"{item.id}.json")
        if active.lease_id != claimed["lease_id"]:
            raise RuntimeError("original_lease_binding_lost")
        completed = queue.complete(
            active,
            {
                "status": "DONE",
                "scope": "isolated_protocol_canary_only",
                "independent_public_key_checks": 2,
                "actual_model_agents_connected": False,
                "external_execution_performed": False,
            },
            evidence_refs=(
                "local_message:" + ask_receipt["message_id"],
                "local_message:" + reply_receipt["message_id"],
            ),
            execution_completed=False,
        )
        counts = queue.counts()
        if completed.status is not DepartmentWorkStatus.DONE or counts["done"] != 1:
            raise RuntimeError("isolated_protocol_completion_not_verified")

        return {
            "schema_version": "empire.agent_collaboration_protocol_canary.v1",
            "status": "ISOLATED_CANONICAL_QUEUE_AND_ED25519_CHAIN_PASS",
            "canonical_queue": True,
            "existing_department_role_profiles": True,
            "agent_signatures": "ed25519_public_verification",
            "pickup_replay_denied": pickup_replay_denied,
            "help_request_verified": True,
            "signed_reply_verified": True,
            "on_disk_records_independently_verified": 2,
            "local_canary_kanban": {"ready": 0, "running": 0, "done": counts["done"]},
            "task_scope": "synthetic_isolated_protocol_only",
            "production_queue_modified": False,
            "actual_managed_worker_credential_registration": False,
            "independent_real_world_work_completion_proven": False,
            "live_agent_communication_activated": False,
            "external_outbound": False,
            "money_moved": False,
        }


def main() -> int:
    if sys.argv[1:] != ["--run-isolated-once"]:
        print("CANARY_HELD_EXACT_FLAG_REQUIRED")
        return 2
    result = run_isolated_canary()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
