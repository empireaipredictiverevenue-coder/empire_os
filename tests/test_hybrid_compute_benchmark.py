import json
from types import SimpleNamespace
from empire_os.hybrid_compute_benchmark import (
    BenchmarkCase,
    CandidateIdentity,
    candidate_identity,
    execute_candidate,
    summarize_runs,
)


CASE = BenchmarkCase(
    case_id="test",
    task="reasoning",
    prompt="Mention verify, evidence and fail closed.",
    required_groups=(
        ("verify", "verification"),
        ("evidence",),
        ("fail closed", "fail-closed"),
    ),
    max_tokens=50,
)


class FakeClient:
    def __init__(self, output):
        self.output = output
        self.kwargs = None

    def chat(
        self,
        messages,
        system=None,
        temperature=0.2,
        max_tokens=100,
    ):
        self.kwargs = {
            "messages": messages,
            "system": system,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        return self.output


def test_candidate_unknown_cost_stays_unknown():
    spec = SimpleNamespace(
        model_id="x",
        provider="remote",
        model="m",
        deployment="unknown",
        cost_known=lambda: False,
    )

    identity = candidate_identity(
        spec,
        estimated_cost=0.0,
    )

    assert identity.cost_known is False
    assert identity.estimated_cost is None


def test_candidate_known_zero_cost_is_preserved():
    spec = SimpleNamespace(
        model_id="local",
        provider="llamacpp",
        model="qwen",
        deployment="local",
        cost_known=lambda: True,
    )

    identity = candidate_identity(
        spec,
        estimated_cost=0.0,
    )

    assert identity.cost_known is True
    assert identity.estimated_cost == 0.0


def test_execute_candidate_scores_deterministically():
    client = FakeClient(
        "Verify with evidence and fail closed."
    )

    identity = CandidateIdentity(
        model_id="x",
        provider="p",
        model="m",
        deployment="local",
        cost_known=True,
        estimated_cost=0.0,
    )

    result = execute_candidate(
        client=client,
        candidate=identity,
        case=CASE,
    )

    assert result["ok"] is True
    assert result["coverage"] == 1.0
    assert (
        result["covered_groups"]
        == 3
    )
    assert (
        result["raw_output_persisted"]
        is False
    )
    assert result["output_sha256"]
    assert (
        client.kwargs["max_tokens"]
        == 50
    )


def test_provider_error_is_failure():
    client = FakeClient(
        json.dumps(
            {"error": "provider_down"}
        )
    )

    identity = CandidateIdentity(
        model_id="x",
        provider="p",
        model="m",
        deployment="unknown",
        cost_known=False,
        estimated_cost=None,
    )

    result = execute_candidate(
        client=client,
        candidate=identity,
        case=CASE,
    )

    assert result["ok"] is False
    assert (
        result["failure"]
        == "provider_down"
    )


def test_summary_does_not_hide_failed_calls():
    result = summarize_runs(
        [
            {
                "ok": True,
                "coverage": 1.0,
                "latency_ms": 100,
            },
            {
                "ok": False,
                "coverage": 0.0,
                "latency_ms": 200,
            },
        ]
    )

    assert result["sample_count"] == 2
    assert (
        result["successful_calls"]
        == 1
    )
    assert result["mean_coverage"] == 0.5
    assert (
        result["mean_latency_ms"]
        == 150.0
    )
    assert (
        result["all_successful"]
        is False
    )
