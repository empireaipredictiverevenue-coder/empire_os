"""Read-only observation adapters for typed-decision evaluation.

These adapters convert already-governed canonical records into evaluation
candidates. They do not query providers, mutate CRM/reply state, or send data.
"""
from __future__ import annotations

from typing import Any, Mapping


def _text(v: Any) -> str:
    return str(v or "").strip()


def reply_record_to_observation(raw: Mapping[str, Any]) -> dict[str, Any]:
    reply_id = _text(raw.get("reply_id"))
    body_text = _text(raw.get("body_text"))
    subject = _text(raw.get("subject"))
    received_at = _text(raw.get("received_at"))
    provider_message_id = _text(raw.get("provider_message_id"))

    blockers=[]
    if not reply_id: blockers.append("reply_id_required")
    if not body_text: blockers.append("body_text_required")
    if not received_at: blockers.append("received_at_required")
    if not provider_message_id: blockers.append("provider_message_id_required")

    return {
        "schema_version":"typed_decision_reply_observation.v1",
        "ready":not blockers,
        "blockers":blockers,
        "task_key":"reply_classification",
        "case_id":f"reply:{reply_id}" if reply_id else None,
        "inputs":{
            "body_text":body_text,
            "subject":subject,
        } if body_text else {},
        "source_ref":f"outbound_reply:{reply_id}" if reply_id else None,
        "point_in_time_ref":received_at or None,
        "provider_message_ref":provider_message_id or None,
        "untrusted_content":True,
        "executable":False,
        "crm_mutation":False,
        "reply_state_mutation":False,
        "outbound_send":False,
        "execution_authority":"none",
    }


def reviewed_reply_to_real_eval_case(
    raw_reply: Mapping[str, Any],
    *,
    consensus_label: str,
    consensus_source_ref: str,
) -> dict[str, Any]:
    obs=reply_record_to_observation(raw_reply)
    if not obs["ready"]:
        return {
            "schema_version":"typed_decision_reviewed_reply_case.v1",
            "ready":False,
            "blockers":obs["blockers"],
            "execution_authority":"none",
        }
    if not consensus_label:
        return {
            "schema_version":"typed_decision_reviewed_reply_case.v1",
            "ready":False,
            "blockers":["consensus_label_required"],
            "execution_authority":"none",
        }
    if not consensus_source_ref:
        return {
            "schema_version":"typed_decision_reviewed_reply_case.v1",
            "ready":False,
            "blockers":["consensus_source_ref_required"],
            "execution_authority":"none",
        }

    return {
        "schema_version":"typed_decision_reviewed_reply_case.v1",
        "ready":True,
        "case":{
            "case_id":obs["case_id"],
            "task_key":"reply_classification",
            "inputs":obs["inputs"],
            "ground_truth":consensus_label,
            "label_source":"reviewed_real_observation",
            "source_ref":obs["source_ref"],
            "synthetic_test_fixture":False,
        },
        "point_in_time_ref":obs["point_in_time_ref"],
        "consensus_source_ref":consensus_source_ref,
        "commercial_evidence":False,
        "execution_authority":"none",
    }
