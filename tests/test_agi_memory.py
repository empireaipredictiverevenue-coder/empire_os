import pytest

from empire_os.agi_memory import build_memory_query, review_memory_item


def test_commercial_decision_retrieves_verified_outcome_memory_class():
    query = build_memory_query(
        task_type="commercial_decision",
        task_id="t1",
        entity_refs=["company:1", "company:1"],
        topic_keys=["territory"],
    )
    assert "outcome_conditioned" in query["memory_types"]
    assert query["entity_refs"] == ["company:1"]
    assert query["retrieval_only"] is True
    assert query["execution_authority"] == "none"


def test_unknown_task_type_fails_closed():
    with pytest.raises(ValueError, match="unsupported"):
        build_memory_query(task_type="magic", task_id="t1")


def test_outcome_memory_requires_real_verified_outcome():
    bad = review_memory_item({
        "memory_type": "outcome_conditioned",
        "ref": "memory:1",
        "evidence_refs": ["e:1"],
        "verified_outcome": False,
        "synthetic": True,
    })
    assert bad["accepted_for_retrieval"] is False
    assert "verified_outcome_required" in bad["blockers"]
    assert "synthetic_cannot_be_outcome_conditioned_memory" in bad["blockers"]

    good = review_memory_item({
        "memory_type": "outcome_conditioned",
        "ref": "memory:2",
        "evidence_refs": ["e:2"],
        "verified_outcome": True,
        "outcome_ref": "outcome:2",
        "synthetic": False,
    })
    assert good["accepted_for_retrieval"] is True
