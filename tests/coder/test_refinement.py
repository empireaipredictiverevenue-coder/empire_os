import pytest

from empire_os.coder.context import ContextPack
from empire_os.coder.models import ModelRoute
from empire_os.coder.provider import ModelRequest, ModelResponse
from empire_os.coder.refinement import (
    ModelProposal,
    OutputRefiner,
    ProposalStage,
    RefinementPolicy,
)


class FakeProvider:
    name = "fake"

    def __init__(self, responses=None):
        self.calls = []
        self.responses = list(responses or [
            "candidate one",
            "candidate two",
            "comparative critique",
            "synthesized final candidate",
        ])

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request.instruction)
        return ModelResponse(
            "fake",
            "fake-model",
            self.responses[len(self.calls) - 1],
        )


def context():
    return ContextPack("goal", {}, (), (), 1000)


def route():
    return ModelRoute("fake", "fake-model", "test")


def test_raw_first_output_is_never_actionable():
    provider = FakeProvider(["first draft"])
    proposal = OutputRefiner(provider).draft(
        task_id="coder_test",
        instruction="build it",
        context=context(),
        route=route(),
    )
    assert proposal.stage is ProposalStage.DRAFT
    assert proposal.actionable is False


def test_polished_requires_two_candidates_critique_and_synthesis():
    provider = FakeProvider()
    proposal = OutputRefiner(provider).polished(
        task_id="coder_test",
        instruction="build it",
        context=context(),
        route=route(),
    )
    assert proposal.stage is ProposalStage.REFINED
    assert proposal.candidate_drafts == [
        "candidate one",
        "candidate two",
    ]
    assert proposal.critique == "comparative critique"
    assert proposal.refined == "synthesized final candidate"
    assert proposal.revision_count == 1
    assert proposal.actionable is True
    assert len(provider.calls) == 4
    assert "candidate 2" in provider.calls[1].lower()
    assert "compare all candidates" in provider.calls[2].lower()
    assert "synthesize a new final candidate" in provider.calls[3].lower()


def test_single_candidate_cannot_be_polished():
    proposal = ModelProposal(
        task_id="coder_test",
        instruction="build it",
        route=route(),
        draft="only candidate",
        candidate_drafts=["only candidate"],
    )
    with pytest.raises(RuntimeError, match="at least two"):
        OutputRefiner(FakeProvider()).polish(
            proposal,
            context=context(),
        )


def test_synthesis_identical_to_candidate_one_is_rejected():
    provider = FakeProvider([
        "same answer",
        "alternative",
        "critique",
        "same answer",
    ])
    with pytest.raises(RuntimeError, match="did not produce actionable"):
        OutputRefiner(provider).polished(
            task_id="coder_test",
            instruction="build it",
            context=context(),
            route=route(),
        )


def test_policy_cannot_disable_candidate_or_revision_requirement():
    with pytest.raises(ValueError, match="never be actionable"):
        RefinementPolicy(minimum_revisions=0)
    with pytest.raises(ValueError, match="at least two"):
        RefinementPolicy(minimum_candidate_drafts=1)
