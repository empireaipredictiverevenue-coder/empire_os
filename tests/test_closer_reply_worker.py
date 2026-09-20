from empire_os.closer_reply_worker import run_closer_reply_worker


class FakeRpc:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def __call__(self, name, params):
        self.calls.append((name, params))
        if name == "list_closer_work":
            return self.rows
        if name == "open_closer_case":
            return {
                "decision": "opened",
                "case_id": "00000000-0000-0000-0000-000000000002",
                "state": "engaged",
            }
        if name == "record_closer_recommendation":
            return {
                "decision": "recorded",
                "recommendation_id": "00000000-0000-0000-0000-000000000003",
            }
        raise AssertionError(name)


def test_opens_case_and_records_deterministic_recommendation():
    rpc = FakeRpc([
        {
            "reply_id": "00000000-0000-0000-0000-000000000001",
            "classification": "positive",
            "confidence": 0.9,
            "case_id": None,
        }
    ])
    result = run_closer_reply_worker(rpc, limit=25)
    assert result.cases_opened == 1
    assert result.recommendations_recorded == 1
    assert result.errors == ()
    assert [name for name, _ in rpc.calls] == [
        "list_closer_work",
        "open_closer_case",
        "record_closer_recommendation",
    ]
    recommendation = rpc.calls[-1][1]
    assert recommendation["p_type"] == "qualify"
    assert recommendation["p_confidence"] == 0.9
    assert recommendation["p_message"] is None


def test_existing_case_is_not_duplicated():
    rpc = FakeRpc([
        {
            "reply_id": "00000000-0000-0000-0000-000000000001",
            "classification": "question",
            "confidence": 0.8,
            "case_id": "00000000-0000-0000-0000-000000000010",
        }
    ])
    result = run_closer_reply_worker(rpc)
    assert result.cases_opened == 0
    assert result.recommendations_recorded == 0
    assert result.skipped_existing == 1
    assert [name for name, _ in rpc.calls] == ["list_closer_work"]


def test_noncommercial_reply_is_ignored():
    rpc = FakeRpc([
        {
            "reply_id": "00000000-0000-0000-0000-000000000001",
            "classification": "negative",
            "confidence": 0.95,
            "case_id": None,
        }
    ])
    result = run_closer_reply_worker(rpc)
    assert result.cases_opened == 0
    assert result.recommendations_recorded == 0
    assert result.errors == ()
