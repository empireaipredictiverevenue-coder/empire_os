import json

from empire_os.call_manager import build_call_work


def test_call_manager_ranks_and_never_executes(tmp_path):
    queue_path = tmp_path / "call_ready.json"
    queue_path.write_text(json.dumps({
        "p1": {
            "prospect_id": "p1",
            "business_name": "Alpha Roofing",
            "phone": "+17135550101",
            "website": "https://alpha.example",
            "reason": "no_decision_maker",
            "enrichment_attempts": 1,
            "status": "ready_for_review",
        },
        "p2": {
            "prospect_id": "p2",
            "business_name": "Beta HVAC",
            "phone": "+15125550102",
            "website": "https://beta.example",
            "reason": "site_unavailable",
            "enrichment_attempts": 2,
            "status": "ready_for_review",
        },
    }))

    def request(method, path, payload=None):
        assert method == "GET"
        if path.startswith("/rest/v1/prospects?"):
            if "eq.p1" in path:
                return [{
                    "id": "p1",
                    "business_name": "Alpha Roofing",
                    "niche": "roofing",
                    "metro": "Houston",
                    "website": "https://alpha.example",
                    "phone": "+17135550101",
                    "buy_signal_score": 100,
                }]
            return [{
                "id": "p2",
                "business_name": "Beta HVAC",
                "niche": "hvac",
                "metro": "Austin",
                "website": "https://beta.example",
                "phone": "+15125550102",
                "buy_signal_score": 70,
            }]
        if path.startswith("/rest/v1/prospect_qualifications?"):
            if "eq.p1" in path:
                return [{"tier": "hot", "score": 90}]
            return [{"tier": "warm", "score": 55}]
        return []

    result = build_call_work(
        request,
        queue_path=queue_path,
        limit=10,
    )

    assert result["queue_total"] == 2
    assert result["selected"] == 2
    assert result["execution_allowed"] is False
    assert result["live_calls_placed"] == 0
    assert result["items"][0]["prospect_id"] == "p1"
    assert all(
        row["requires_live_call_authority"] is True
        for row in result["items"]
    )
    assert all(
        row["closer_brief"]["conversation_os"]["transcript_required"] is True
        for row in result["items"]
    )
