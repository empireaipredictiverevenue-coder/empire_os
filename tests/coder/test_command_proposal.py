import pytest

from empire_os.coder.command_proposal import (
    CommandProposalError,
    CommandProposalStage,
    CommandRefiner,
)
from empire_os.coder.context import ContextPack
from empire_os.coder.models import ModelRoute, ToolDecision
from empire_os.coder.provider import ModelRequest, ModelResponse


class FakeProvider:
    name = "fake"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

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


def test_next_command_uses_two_candidates_critique_and_synthesis():
    provider = FakeProvider([
        "git status --short",
        "git diff --check",
        "Both are safe; diff-check verifies patch integrity.",
        '{"argv":["git","diff","--check"]}',
    ])
    proposal = CommandRefiner(provider).propose(
        task_id="coder_test",
        objective="Verify current candidate patch",
        context=context(),
        route=route(),
    )
    assert proposal.stage is CommandProposalStage.POLICY_CHECKED
    assert len(proposal.candidate_texts) == 2
    assert proposal.argv == ("git", "diff", "--check")
    assert proposal.decision is ToolDecision.ALLOW
    assert proposal.eligible is True
    assert len(provider.calls) == 4


def test_policy_denied_synthesized_command_is_rejected():
    provider = FakeProvider([
        "inspect status",
        "inspect diff",
        "compare",
        '{"argv":["git","gc"]}',
    ])
    with pytest.raises(CommandProposalError, match="denied"):
        CommandRefiner(provider).propose(
            task_id="coder_test",
            objective="verify",
            context=context(),
            route=route(),
        )


def test_non_json_command_is_rejected():
    provider = FakeProvider([
        "git status",
        "git diff",
        "compare",
        "git status --short",
    ])
    with pytest.raises(CommandProposalError, match="strict JSON"):
        CommandRefiner(provider).propose(
            task_id="coder_test",
            objective="verify",
            context=context(),
            route=route(),
        )
