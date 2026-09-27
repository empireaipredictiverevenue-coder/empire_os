from empire_os.typed_decision_search_observations import (
    keyword_record_to_observation,
    source_quality_record_to_observation,
)


def test_keyword_observation_preserves_existing_evidence_without_publishing():
    r=keyword_record_to_observation({
        "query_id":"q1",
        "query":"predictive revenue software",
        "intent":"commercial",
        "observed_at":"2026-09-20T09:00:00Z",
        "source_ref":"search:q1",
    })
    assert r["ready"] is True
    assert r["task_key"]=="keyword_intent"
    assert r["observed_existing_intent"]=="commercial"
    assert r["publishing_enabled"] is False
    assert r["indexation_enabled"] is False


def test_keyword_observation_missing_evidence_fails_closed():
    r=keyword_record_to_observation({"query":"predictive revenue"})
    assert r["ready"] is False
    assert "observed_at_required" in r["blockers"]


def test_source_quality_observation_is_read_only():
    r=source_quality_record_to_observation({
        "source_ref":"permits:manchester",
        "evidence_summary":"Freshness and parser checks passed.",
        "observed_at":"2026-09-20T09:00:00Z",
    })
    assert r["ready"] is True
    assert r["task_key"]=="source_quality"
    assert r["source_state_mutation"] is False
    assert r["execution_authority"]=="none"
