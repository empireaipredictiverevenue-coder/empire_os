"""Optional local, first-party model reasoning for the Empire Data Exchange.

Uses the shared llama.cpp Qwen adapter (127.0.0.1 only), NOT a new runtime.
Model proposals are untrusted choices from verified AGI research packet enums.
An independent deterministic verifier checks provenance and plan consistency.
No externally supplied prose, contacts, URLs, private data or secrets are
sent to the model. No execution, publishing, outreach, payments or learning.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping, Protocol

from empire_os.data_exchange_agi_bridge import SCHEMA as AGI_SCHEMA

SCHEMA = "empire.data_exchange.local_reasoning_shadow.v1"
MODEL = "qwen2.5-coder:1.5b"
ENDPOINT = "http://127.0.0.1:11435"
MAX_OUTPUT_CHARS = 4096


class ChatProvider(Protocol):
    def chat(
        self, messages: list[dict], system: str | None = None,
        temperature: float = 0.2, max_tokens: int = 2048,
    ) -> str: ...


@dataclass(frozen=True)
class ModelResearchContext:
    source_change_count: int
    procurement_context_count: int
    hypotheses: tuple[tuple[str, tuple[str, ...], str], ...]
    actions: tuple[str, ...]
    evidence: tuple[str, ...]
    gaps: tuple[str, ...]
    deterministic_priority: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_change_count": self.source_change_count,
            "procurement_context_count": self.procurement_context_count,
            "hypotheses": [
                {"key": key, "alternatives": list(alt),
                 "disconfirmation": check}
                for key, alt, check in self.hypotheses
            ],
            "actions": list(self.actions),
            "evidence": list(self.evidence),
            "gaps": list(self.gaps),
            "deterministic_priority": self.deterministic_priority,
        }


def validated_context(packet: Mapping[str, Any]) -> ModelResearchContext:
    """Hard boundary: never pass arbitrary AGI packet text to a local model."""
    if not isinstance(packet, Mapping) or packet.get("schema_version") != AGI_SCHEMA:
        raise ValueError("AGI research packet schema not trusted")
    if (
        packet.get("mode") != "OBSERVE"
        or packet.get("execution_authority") != "NONE"
        or packet.get("human_level_agi_claimed") is not False
        or packet.get("predictive_marketing_claim_ready") is not False
        or any(packet.get(key) is not False for key in (
            "customer_delivery_enabled", "data_resale_authorized",
            "outbound_enabled", "payment_execution", "production_writes",
            "model_mutation",
        ))
    ):
        raise ValueError("AGI packet scope or authority invalid")

    hypotheses = packet.get("hypotheses")
    tasks = packet.get("research_workstreams")
    refs = packet.get("evidence_refs")
    gaps = packet.get("unresolved_evidence")
    counts = (packet.get("source_change_count"), packet.get("procurement_context_count"))
    if (
        not isinstance(hypotheses, list) or len(hypotheses) != 2
        or not isinstance(tasks, list) or len(tasks) != 5
        or not isinstance(refs, list) or not 1 <= len(refs) <= 6
        or not isinstance(gaps, list) or not 1 <= len(gaps) <= 24
        or any(type(value) is not int or value < 0 or value > 100
               for value in counts)
    ):
        raise ValueError("AGI research packet size/scope invalid")
    from re import fullmatch
    # These are the *only* permitted values from the trusted packet.
    hypothesis_catalog = {
        "stage_change_precedes_opportunity": (
            ("The site may never proceed",
             "Registry updates may lag project activity",
             "A contractor may already have been appointed"),
            "Timestamped independent outcomes and a no-change baseline",
        ),
        "procurement_corroborates_project": (
            ("Both events may be unrelated despite shared geography",
             "Tender publication is not evidence of site identity"),
            "Official common project identifier or direct document citation",
        ),
    }
    built = []
    for hyp in hypotheses:
        if not isinstance(hyp, Mapping) or set(hyp) != {
            "key", "claim", "state", "alternatives", "required_disconfirmation",
        }:
            raise ValueError("untrusted hypothesis fields")
        key = hyp.get("key")
        if key not in hypothesis_catalog or hyp.get("state") != "UNTESTED":
            raise ValueError("hypothesis cannot claim verification")
        allowed_alt, check = hypothesis_catalog[key]
        if tuple(hyp.get("alternatives") or ()) != allowed_alt or (
            hyp.get("required_disconfirmation") != check
        ):
            raise ValueError("hypothesis alternatives or disconfirmation changed")
        built.append((key, allowed_alt, check))
    if {row[0] for row in built} != set(hypothesis_catalog):
        raise ValueError("missing approved hypothesis")
    allowed_tasks = {
        "review_dataset_rights",
        "capture_later_observations",
        "independently_verify_source_transitions",
        "collect_independent_procurement_context",
        "verify_cross_source_project_identity",
        "validate_commercial_outcomes",
        "test_independent_holdout",
        "research_first_paid_buyer",
    }
    action_names: list[str] = []
    for task in tasks:
        if not isinstance(task, Mapping) or set(task) != {
            "workstream", "summary", "priority",
        } or task.get("workstream") not in allowed_tasks:
            raise ValueError("unreviewed research action")
        action_names.append(task["workstream"])
    if len(set(action_names)) != len(action_names):
        raise ValueError("duplicate research action")
    if (
        action_names[0] != "review_dataset_rights"
        or packet.get("recommended_workstream") != action_names[0]
    ):
        raise ValueError("deterministic rights priority tampered")
    if (
        action_names[1] != (
            "independently_verify_source_transitions" if counts[0]
            else "capture_later_observations"
        )
        or action_names[2] != (
            "verify_cross_source_project_identity" if counts[1]
            else "collect_independent_procurement_context"
        )
    ):
        raise ValueError("AGI action does not match source evidence")
    for ref in refs:
        if (
            not isinstance(ref, str)
            or not (
                fullmatch(r"empire:construction_history:[0-9a-f]{64}", ref)
                or fullmatch(r"find-a-tender:notice:[0-9]{6}-20[0-9]{2}", ref)
            )
        ):
            raise ValueError("AGI evidence reference not allowlisted")
    if len(set(refs)) != len(refs) or counts[1] != len(refs) - 1:
        raise ValueError("unmatched procurement evidence references")
    if any(
        not isinstance(gap, str)
        or not fullmatch(r"[A-Z][A-Z0-9_]{3,80}", gap)
        for gap in gaps
    ):
        raise ValueError("unreviewed AGI evidence gap")
    return ModelResearchContext(
        source_change_count=counts[0],
        procurement_context_count=counts[1],
        hypotheses=tuple(built),
        actions=tuple(action_names),
        evidence=tuple(refs),
        gaps=tuple(gaps),
        deterministic_priority=action_names[0],
    )


def _parse_choices(raw: str, context: ModelResearchContext) -> dict[str, Any]:
    if not isinstance(raw, str) or len(raw) > MAX_OUTPUT_CHARS:
        raise ValueError("local model response missing or oversized")
    stripped = raw.strip()
    if stripped.startswith("```"):
        fenced = re.fullmatch(
            r"```(?:json)?[ \t]*\n(\{[\s\S]*\})[ \t]*\n```",
            stripped, flags=re.IGNORECASE,
        )
        if fenced is None:
            raise ValueError("model fenced output contains unsupported content")
        stripped = fenced.group(1)
    try:
        response = json.loads(stripped)
    except (ValueError, TypeError) as exc:
        raise ValueError("local model did not produce strict JSON") from exc
    if not isinstance(response, dict):
        raise ValueError("local model output must be object")
    if set(response) == {"h", "a", "e", "c"}:
        indexes = tuple(response[k] for k in ("h", "a", "e", "c"))
        if any(type(i) is not int or i < 0 for i in indexes):
            raise ValueError("model choice indexes must be nonnegative integers")
        h, a, e, c = indexes
        if (h >= len(context.hypotheses) or a >= len(context.actions)
                or e >= len(context.evidence)
                or c >= len(context.hypotheses[h][1])):
            raise ValueError("model choice index out of catalogue bounds")
        chosen_hypothesis = context.hypotheses[h]
        response = {
            "hypothesis_key": chosen_hypothesis[0],
            "research_action": context.actions[a],
            "evidence_ref": context.evidence[e],
            "counterargument": chosen_hypothesis[1][c],
            "falsification_test": chosen_hypothesis[2],
        }
    elif set(response) != {
        "hypothesis_key", "research_action", "evidence_ref",
        "counterargument", "falsification_test",
    }:
        raise ValueError("unreviewed model output fields")
    item = next(
        (row for row in context.hypotheses if row[0] == response["hypothesis_key"]),
        None,
    )
    if item is None:
        raise ValueError("unsupported model hypothesis")
    if (
        response["research_action"] not in context.actions
        or response["evidence_ref"] not in context.evidence
        or response["counterargument"] not in item[1]
        or response["falsification_test"] != item[2]
    ):
        raise ValueError("model invented evidence or unchecked research claim")
    return response


def review_local_reasoning(
    packet: Mapping[str, Any], *, client: ChatProvider | None = None,
    allow_inference: bool = False,
) -> dict[str, Any]:
    """One bounded local inference when explicitly opted in; no background work.

    Provider outage or malformed output is a HOLD, never a fallback to a
    fabricated successful inference.
    """
    context = validated_context(packet)
    review: dict[str, Any] = {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "provider": "existing_local_llama_cpp",
        "model": MODEL,
        "model_inference_performed": False,
        "model_output_review_status": "NOT_RUN",
        "model_candidate": None,
        "deterministic_recommendation": context.deterministic_priority,
        "does_not_override_base_plan": True,
        "independent_model_critic_completed": False,
        "policy_verifier": "strict_enum_and_evidence_reference_check",
        "hypotheses_remain_untested": True,
        "predictive_claim_ready": False,
        "customer_delivery_enabled": False,
        "outbound_enabled": False,
        "payment_execution": False,
        "production_writes": False,
        "execution_authority": "NONE",
    }
    if not allow_inference:
        return review
    if client is None:
        from empire_os.coder.llama_cpp_provider import LlamaCppProvider
        client = LlamaCppProvider(
            base_url=ENDPOINT, timeout_seconds=30, model=MODEL,
        )
    system = (
        "You are a SHADOW-ONLY research option selector, not an executor. "
        "Choose four zero-based integer indexes from the supplied catalogues. "
        "h=index in hypotheses, a=index in actions, e=index in evidence, "
        "c=index in alternatives of the selected hypothesis. "
        "Return ONLY a single JSON object with exactly four integer keys: "
        "h, a, e, c. No markdown, comments, explanations or unlisted values. "
        "Do not assert proven intent, sales, revenue, approvals or permissions."
    )
    user = json.dumps(context.as_dict(), sort_keys=True, separators=(",", ":"))
    if len(user) > 6500:
        raise ValueError("model evidence context unexpectedly oversized")
    try:
        raw = client.chat(
            [{"role": "user", "content": user}],
            system=system, temperature=0.0, max_tokens=110,
        )
    except (OSError, ValueError, RuntimeError, TimeoutError):
        return {**review, "model_output_review_status": "HOLD_PROVIDER_FAILURE"}
    try:
        possible_error = json.loads(raw) if isinstance(raw, str) else None
    except (ValueError, TypeError):
        possible_error = None
    if isinstance(possible_error, dict) and set(possible_error) == {"error"}:
        return {**review, "model_output_review_status": "HOLD_PROVIDER_FAILURE"}
    try:
        candidate = _parse_choices(raw, context)
    except (ValueError, TypeError):
        return {**review, "model_inference_performed": True,
                "model_output_review_status": "REJECTED_UNTRUSTED_OUTPUT"}
    return {
        **review,
        "model_inference_performed": True,
        "model_output_review_status": "ADVISORY_CANDIDATE_SCHEMA_VERIFIED",
        "model_candidate": candidate,
        "candidate_agrees_with_base_priority": (
            candidate["research_action"] == context.deterministic_priority
        ),
    }
