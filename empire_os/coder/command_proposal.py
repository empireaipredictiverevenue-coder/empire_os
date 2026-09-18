"""Best-of-N next-command proposals for Empire Coder."""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

from .context import ContextPack
from .models import ModelRoute, ToolDecision
from .policy import classify_command
from .provider import ModelProvider, ModelRequest


class CommandProposalStage(str, Enum):
    CANDIDATES_READY = "CANDIDATES_READY"
    CRITIQUED = "CRITIQUED"
    SYNTHESIZED = "SYNTHESIZED"
    POLICY_CHECKED = "POLICY_CHECKED"


@dataclass
class CommandProposal:
    task_id: str
    route: ModelRoute
    candidate_texts: list[str]
    critique: str = ""
    synthesized_text: str = ""
    argv: tuple[str, ...] = ()
    decision: ToolDecision = ToolDecision.DENY
    stage: CommandProposalStage = CommandProposalStage.CANDIDATES_READY

    @property
    def eligible(self) -> bool:
        return (
            self.stage is CommandProposalStage.POLICY_CHECKED
            and len(self.candidate_texts) >= 2
            and bool(self.critique.strip())
            and bool(self.argv)
            and self.decision in {
                ToolDecision.ALLOW,
                ToolDecision.REQUIRE_APPROVAL,
            }
        )


class CommandProposalError(RuntimeError):
    pass


class CommandRefiner:
    """Generate two commands, compare, synthesize JSON argv, then policy-check."""

    def __init__(self, provider: ModelProvider) -> None:
        self.provider = provider

    def propose(
        self,
        *,
        task_id: str,
        objective: str,
        context: ContextPack,
        route: ModelRoute,
        max_output_chars: int = 1_200,
    ) -> CommandProposal:
        candidates = []
        for index in range(2):
            response = self.provider.complete(ModelRequest(
                task_id=task_id,
                instruction=(
                    "Propose one safe next development command for the "
                    "objective below. It must be local/workspace scoped, "
                    "non-destructive, and compatible with OBSERVE mode. "
                    "Do not use shell chaining, pipes, redirection, sudo, "
                    "network tools, service control, deployment, or secrets. "
                    f"This is independent candidate {index + 1}. "
                    "Return only a concise command proposal.\n\nOBJECTIVE:\n"
                    + objective
                ),
                context=context,
                route=route,
                max_output_chars=max_output_chars,
            ))
            if response.error:
                raise CommandProposalError(response.error)
            candidates.append(response.text)

        block = "\n\n".join(
            f"CANDIDATE {i + 1}:\n{text}"
            for i, text in enumerate(candidates)
        )
        critique = self.provider.complete(ModelRequest(
            task_id=task_id,
            instruction=(
                "Compare both next-command candidates. Reject unsafe, "
                "unnecessary, stale, overly broad, or state-assuming commands. "
                "Explain what the synthesized command should accomplish. "
                "Do not merely select candidate 1.\n\n" + block
            ),
            context=context,
            route=route,
            max_output_chars=900,
        ))
        if critique.error:
            raise CommandProposalError(critique.error)

        synthesis = self.provider.complete(ModelRequest(
            task_id=task_id,
            instruction=(
                "Synthesize a NEW safest next command from the candidates and "
                "critique. Return STRICT JSON only, shaped exactly as "
                '{"argv":["executable","arg1","arg2"]}. '
                "Use an argv array, never a shell command string. "
                "No chaining, pipes, redirection, sudo, network, service "
                "control, deployment, secrets, or destructive Git.\n\n"
                + block
                + "\n\nCRITIQUE:\n"
                + critique.text
            ),
            context=context,
            route=route,
            max_output_chars=600,
        ))
        if synthesis.error:
            raise CommandProposalError(synthesis.error)

        argv = self._parse_argv(synthesis.text)
        decision = classify_command(argv)
        proposal = CommandProposal(
            task_id=task_id,
            route=route,
            candidate_texts=candidates,
            critique=critique.text,
            synthesized_text=synthesis.text,
            argv=argv,
            decision=decision,
            stage=CommandProposalStage.POLICY_CHECKED,
        )
        if decision is ToolDecision.DENY:
            raise CommandProposalError(
                "synthesized command denied by Empire Coder policy"
            )
        return proposal

    @staticmethod
    def _parse_argv(text: str) -> tuple[str, ...]:
        raw = text.strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CommandProposalError(
                "synthesized command was not strict JSON"
            ) from exc
        argv = payload.get("argv") if isinstance(payload, dict) else None
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(item, str) or not item for item in argv)
        ):
            raise CommandProposalError("invalid argv proposal")
        return tuple(argv)
