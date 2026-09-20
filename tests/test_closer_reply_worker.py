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
        if name == "provision_buyer_from_closer_case":
            return {
                "decision": (
                    "existing"
                    if params["p_case_id"].endswith("0010")
                    else "provisioned"
                ),
                "buyer_id": "00000000-0000-0000-0000-000000000004",
            }
        if name == "get_closer_reply_context":
            row = next(
                item for item in self.rows
                if item["reply_id"] == params["p_reply_id"]
            )
            return {
                "case_id": params["p_case_id"],
                "classification": row["classification"],
                "reply_body_text": (
                    "What does it cost?"
                    if row["classification"] == "question"
                    else "Yes, interested"
                ),
                "root_subject": "Roofing opportunities",
                "business_name": "Acme Roofing",
                "niche": "roofing",
                "metro": "Austin",
                "contact_name": "Jane Smith",
            }
        if name == "record_closer_recommendation":
            return {
                "decision": "recorded",
                "recommendation_id": "00000000-0000-0000-0000-000000000003",
            }
        if name == "propose_closer_reply_intent":
            return {
                "decision": "proposed",
                "intent_id": "00000000-0000-0000-0000-000000000005",
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
    assert result.buyers_provisioned == 1
    assert result.reply_intents_proposed == 1
    assert result.existing_cases_reused == 0
    assert result.errors == ()
    assert [name for name, _ in rpc.calls] == [
        "list_closer_work",
        "open_closer_case",
        "provision_buyer_from_closer_case",
        "get_closer_reply_context",
        "record_closer_recommendation",
        "propose_closer_reply_intent",
    ]
    recommendation = rpc.calls[-2][1]
    assert recommendation["p_type"] == "qualify"
    assert recommendation["p_confidence"] == 0.9
    assert "how many qualified opportunities per day" in recommendation["p_message"]


def test_existing_case_is_reused_for_later_reply():
    rpc = FakeRpc([
        {
            "reply_id": "00000000-0000-0000-0000-000000000011",
            "classification": "question",
            "confidence": 0.8,
            "case_id": "00000000-0000-0000-0000-000000000010",
            "case_origin": "threaded",
        }
    ])
    result = run_closer_reply_worker(rpc)
    assert result.cases_opened == 0
    assert result.existing_cases_reused == 1
    assert result.recommendations_recorded == 1
    assert result.buyers_provisioned == 0
    assert result.reply_intents_proposed == 1
    assert result.skipped_existing == 0
    assert [name for name, _ in rpc.calls] == [
        "list_closer_work",
        "provision_buyer_from_closer_case",
        "get_closer_reply_context",
        "record_closer_recommendation",
        "propose_closer_reply_intent",
    ]
    assert rpc.calls[-1][1]["p_reply_id"].endswith("0011")


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
    assert result.buyers_provisioned == 0
    assert result.reply_intents_proposed == 0
    assert result.existing_cases_reused == 0
    assert result.errors == ()
