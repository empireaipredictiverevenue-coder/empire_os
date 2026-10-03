from empire_os.outbound_source_reputation import evaluate_source_reputation


def test_source_with_complaint_is_quarantined():
    result = evaluate_source_reputation(
        "scraper:a",
        [
            {"source_key": "scraper:a", "kind": "sent", "count": 50},
            {"source_key": "scraper:a", "kind": "complaint"},
        ],
    )
    assert result["posture"] == "QUARANTINE"
    assert "source_complaint_present" in result["blockers"]
    assert result["mutation_authorized"] is False


def test_high_bounce_source_is_quarantined_after_sample_floor():
    events = [{"source_key": "scraper:a", "kind": "sent", "count": 20}]
    events += [
        {"source_key": "scraper:a", "kind": "hard_bounce"}
        for _ in range(2)
    ]
    result = evaluate_source_reputation("scraper:a", events)
    assert result["posture"] == "QUARANTINE"
    assert result["hard_bounce_rate"] == 0.1


def test_elevated_bounce_source_is_degraded():
    events = [{"source_key": "dataset:a", "kind": "sent", "count": 50}]
    events += [
        {"source_key": "dataset:a", "kind": "hard_bounce"}
        for _ in range(2)
    ]
    result = evaluate_source_reputation("dataset:a", events)
    assert result["posture"] == "DEGRADED"
    assert "source_hard_bounce_rate_elevated" in result["warnings"]


def test_small_clean_source_stays_learning():
    result = evaluate_source_reputation(
        "scout:new",
        [
            {"source_key": "scout:new", "kind": "sent", "count": 5},
            {"source_key": "scout:new", "kind": "positive_reply"},
        ],
    )
    assert result["posture"] == "LEARNING"


def test_clean_source_with_commercial_outcomes_is_healthy():
    result = evaluate_source_reputation(
        "scout:good",
        [
            {"source_key": "scout:good", "kind": "sent", "count": 40},
            {"source_key": "scout:good", "kind": "positive_reply"},
            {"source_key": "scout:good", "kind": "meeting_booked"},
            {"source_key": "scout:good", "kind": "revenue", "amount": 5000},
        ],
    )
    assert result["posture"] == "HEALTHY"
    assert result["score"] > 0
    assert result["revenue"] == 5000


def test_generator_input_replays_once_without_losing_sent_total():
    def events():
        yield {"source_key": "source:g", "kind": "positive_reply", "sent_total": 20}
        yield {"source_key": "source:g", "kind": "hard_bounce", "sent_total": 20}

    result = evaluate_source_reputation("source:g", events())
    assert result["sent"] == 20
    assert result["hard_bounce_rate"] == 0.05
    assert result["posture"] == "QUARANTINE"
