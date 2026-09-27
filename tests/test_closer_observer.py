import json

import pytest

from empire_os.closer_observer import (
    CloserObserverError,
    bounded_closer_limit,
    recommend_closer_work,
    run_closer_observer_cycle,
)


class FakeRpc:
    def __init__(self, dsn, role, rows, calls):
        self.role = role
        self.rows = rows
        self.calls = calls

    def __call__(self, name, params):
        self.calls.append((self.role, name, params))
        return self.rows


def _factory(rows, calls):
    def build(dsn, role):
        return FakeRpc(dsn, role, rows, calls)
    return build


def test_recommendations_never_execute_or_invent_message():
    opened = recommend_closer_work({
        "reply_id": "r1",
        "classification": "positive",
        "confidence": 0.91,
        "case_id": None,
        "case_state": None,
    })
    assert opened.recommendation_type == "open_case"
    assert opened.execution_allowed is False
    assert opened.proposed_message is None

    objection = recommend_closer_work({
        "reply_id": "r2",
        "classification": "objection",
        "confidence": 0.8,
        "case_id": "c2",
        "case_state": "engaged",
    })
    assert objection.recommendation_type == "handle_objection"
    assert objection.execution_allowed is False


def test_state_driven_recommendations_preserve_gates():
    assert recommend_closer_work({
        "reply_id": "r1", "classification": "positive",
        "case_id": "c1", "case_state": "qualified",
    }).recommendation_type == "prepare_proposal"
    assert recommend_closer_work({
        "reply_id": "r1", "classification": "positive",
        "case_id": "c1", "case_state": "proposal_ready",
    }).recommendation_type == "escalate_human"
    assert recommend_closer_work({
        "reply_id": "r1", "classification": "positive",
        "case_id": "c1", "case_state": "awaiting_payment",
    }).recommendation_type == "await_payment"


def test_cycle_uses_observer_role_only_and_writes_local_artifact(tmp_path):
    rows = [{
        "reply_id": "r1",
        "classification": "question",
        "confidence": 0.82,
        "case_id": "c1",
        "case_state": "engaged",
    }]
    calls = []
    output = tmp_path / "latest.json"
    result = run_closer_observer_cycle(
        dsn="postgresql://observer",
        limit=9999,
        output_path=output,
        rpc_factory=_factory(rows, calls),
    )
    assert calls == [(
        "empire_closer_observer",
        "list_closer_work",
        {"p_limit": 500},
    )]
    assert result["mode"] == "OBSERVE"
    assert result["mutations_performed"] == 0
    assert result["outbound_sent"] == 0
    assert result["actual_revenue_declared"] is False
    assert result["recommendations"][0]["recommendation_type"] == "answer_question"
    assert json.loads(output.read_text()) == result


def test_worker_fails_closed_for_live_or_missing_dsn(tmp_path):
    with pytest.raises(CloserObserverError, match="OBSERVE only"):
        run_closer_observer_cycle(
            dsn="postgresql://observer",
            mode="LIVE",
            output_path=tmp_path / "x.json",
            rpc_factory=_factory([], []),
        )
    with pytest.raises(CloserObserverError, match="DSN"):
        run_closer_observer_cycle(
            dsn="",
            output_path=tmp_path / "x.json",
            rpc_factory=_factory([], []),
        )


def test_limit_is_bounded_and_missing_reply_is_rejected():
    assert bounded_closer_limit(0) == 1
    assert bounded_closer_limit(9999) == 500
    assert bounded_closer_limit("bad") == 50
    with pytest.raises(CloserObserverError, match="reply_id"):
        recommend_closer_work({"classification": "positive"})
