"""Mandatory best-of-N model-output refinement for Empire Coder."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .context import ContextPack
from .models import ModelRoute
from .provider import ModelProvider, ModelRequest


class ProposalStage(str, Enum):
    DRAFT = "DRAFT"
    CANDIDATES_READY = "CANDIDATES_READY"
    CRITIQUED = "CRITIQUED"
    REFINED = "REFINED"


@dataclass(frozen=True)
class RefinementPolicy:
    minimum_revisions: int = 1
    minimum_candidate_drafts: int = 2
    max_candidate_drafts: int = 3
    require_critique: bool = True
    require_verification: bool = True

    def __post_init__(self) -> None:
        if self.minimum_revisions < 1:
            raise ValueError("first model output may never be actionable")
        if self.minimum_candidate_drafts < 2:
            raise ValueError("at least two candidates are required")
        if not (
            self.minimum_candidate_drafts
            <= self.max_candidate_drafts
            <= 3
        ):
            raise ValueError(
                "candidate draft bounds must satisfy 2 <= min <= max <= 3"
            )


@dataclass
class ModelProposal:
    task_id: str
    instruction: str
    route: ModelRoute
    draft: str
    critique: str = ""
    refined: str = ""
    revision_count: int = 0
    stage: ProposalStage = ProposalStage.DRAFT
    candidate_drafts: list[str] = field(default_factory=list)

    @property
    def actionable(self) -> bool:
        return (
            self.stage is ProposalStage.REFINED
            and len(self.candidate_drafts) >= 2
            and self.revision_count >= 1
            and bool(self.critique.strip())
            and bool(self.refined.strip())
            and self.refined.strip()
            != self.candidate_drafts[0].strip()
        )

    @property
    def text(self) -> str:
        return self.refined if self.actionable else self.draft


class OutputRefiner:
    """Generate alternatives, compare them, then synthesize a replacement.

    Raw candidate #1 can never become actionable by itself.
    """

    def __init__(
        self,
        provider: ModelProvider,
        *,
        policy: RefinementPolicy | None = None,
    ) -> None:
        self.provider = provider
        self.policy = policy or RefinementPolicy()

    def draft(
        self,
        *,
        task_id: str,
        instruction: str,
        context: ContextPack,
        route: ModelRoute,
        max_output_chars: int = 4_000,
    ) -> ModelProposal:
        response = self.provider.complete(ModelRequest(
            task_id=task_id,
            instruction=instruction,
            context=context,
            route=route,
            max_output_chars=max_output_chars,
        ))
        if response.error:
            raise RuntimeError(response.error)
        return ModelProposal(
            task_id=task_id,
            instruction=instruction,
            route=route,
            draft=response.text,
            candidate_drafts=[response.text],
        )

    def generate_candidates(
        self,
        *,
        task_id: str,
        instruction: str,
        context: ContextPack,
        route: ModelRoute,
        max_output_chars: int = 4_000,
    ) -> ModelProposal:
        candidates: list[str] = []
        count = self.policy.minimum_candidate_drafts
        for index in range(count):
            response = self.provider.complete(ModelRequest(
                task_id=task_id,
                instruction=(
                    instruction
                    + "\n\nGenerate candidate "
                    + str(index + 1)
                    + " independently. Do not assume another candidate is "
                    "correct. Prefer a materially different implementation "
                    "or reasoning path where the evidence allows it."
                ),
                context=context,
                route=route,
                max_output_chars=max_output_chars,
            ))
            if response.error:
                raise RuntimeError(response.error)
            if not response.text.strip():
                raise RuntimeError("empty candidate output")
            candidates.append(response.text)

        proposal = ModelProposal(
            task_id=task_id,
            instruction=instruction,
            route=route,
            draft=candidates[0],
            candidate_drafts=candidates,
            stage=ProposalStage.CANDIDATES_READY,
        )
        return proposal

    def polish(
        self,
        proposal: ModelProposal,
        *,
        context: ContextPack,
        max_output_chars: int = 4_000,
    ) -> ModelProposal:
        if (
            len(proposal.candidate_drafts)
            < self.policy.minimum_candidate_drafts
        ):
            raise RuntimeError(
                "best-of-N policy requires at least two candidates"
            )

        candidate_block = "\n\n".join(
            f"CANDIDATE {index + 1}:\n{text}"
            for index, text in enumerate(proposal.candidate_drafts)
        )
        critique_response = self.provider.complete(ModelRequest(
            task_id=proposal.task_id,
            instruction=(
                "Act as a critical senior engineer. Compare ALL candidates "
                "below against the supplied repository evidence and task "
                "objective. Identify concrete strengths, errors, weak "
                "assumptions, missing edge cases, unnecessary complexity, "
                "architecture/guardrail violations, and which elements should "
                "survive synthesis. Do not simply pick candidate 1. Return "
                "only the comparative critique.\n\n"
                + candidate_block
            ),
            context=context,
            route=proposal.route,
            max_output_chars=max(512, min(max_output_chars, 2_000)),
        ))
        if critique_response.error:
            raise RuntimeError(critique_response.error)

        proposal.critique = critique_response.text
        proposal.stage = ProposalStage.CRITIQUED

        refinement_response = self.provider.complete(ModelRequest(
            task_id=proposal.task_id,
            instruction=(
                "Synthesize a NEW final candidate from the strongest "
                "evidence-backed parts of the alternatives and the comparative "
                "critique. Do not copy candidate 1 verbatim. Remove "
                "speculation, preserve EmpireOS OBSERVE/authority constraints, "
                "and return only the improved final candidate.\n\n"
                + candidate_block
                + "\n\nCOMPARATIVE CRITIQUE:\n"
                + proposal.critique
            ),
            context=context,
            route=proposal.route,
            max_output_chars=max_output_chars,
        ))
        if refinement_response.error:
            raise RuntimeError(refinement_response.error)

        proposal.refined = refinement_response.text
        proposal.revision_count += 1
        proposal.stage = ProposalStage.REFINED
        if not proposal.actionable:
            raise RuntimeError(
                "best-of-N refinement did not produce actionable output"
            )
        return proposal

    def polished(
        self,
        *,
        task_id: str,
        instruction: str,
        context: ContextPack,
        route: ModelRoute,
        max_output_chars: int = 4_000,
    ) -> ModelProposal:
        proposal = self.generate_candidates(
            task_id=task_id,
            instruction=instruction,
            context=context,
            route=route,
            max_output_chars=max_output_chars,
        )
        return self.polish(
            proposal,
            context=context,
            max_output_chars=max_output_chars,
        )
