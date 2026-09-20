import pytest

from empire_os.typed_decision_store import TypedDecisionStore


def test_store_only_emits_private_schema_insert():
    calls=[]
    store=TypedDecisionStore(lambda sql,params: calls.append((sql,params)) or {"ok":True})
    result=store.append_shadow_observation({
        "task_key":"reply_classification",
        "case_id":"reply:r1",
        "source_ref":"outbound_reply:r1",
        "point_in_time_ref":"2026-09-20T10:00:00Z",
        "inputs":{"body_text":"Interested"},
    })
    assert result["ok"] is True
    sql,params=calls[0]
    assert sql.startswith("INSERT INTO empire_eval.shadow_observations")
    assert "public." not in sql
    assert "UPDATE " not in sql.upper()
    assert "DELETE " not in sql.upper()
    assert "TRUNCATE " not in sql.upper()


def test_store_rejects_unknown_table():
    store=TypedDecisionStore(lambda *_: None)
    with pytest.raises(ValueError,match="unsupported"):
        store.append("users",{"x":1})


def test_store_rejects_unsafe_column_name():
    store=TypedDecisionStore(lambda *_: None)
    with pytest.raises(ValueError,match="unsafe"):
        store.append("shadow_observations",{"x); drop table y; --":1})
