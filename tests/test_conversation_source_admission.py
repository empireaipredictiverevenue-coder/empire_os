"""Evidence source admission: separate inbound messages from outbound telemetry."""
from empire_os.conversation_source_admission import (
    admit_candidate_rows, source_admission,
)
from empire_os.conversations_replies_control import adjudicate_records


def message():
    return {
        "message_id": "provider-original-msg",
        "thread_id": "provider-original-thread",
        "sender_email": "buyer@example.test",
        "received_at": "2026-10-09T13:01:00Z",
        "classification": "positive_reply",
    }


def test_outbound_events_even_with_reply_like_labels_are_not_messages():
    row = dict(message(), event_type="delivered", classification="reply")
    assert source_admission("public.outbound_events", row) == (
        "EXCLUDED_OUTBOUND_EVENT_TELEMETRY"
    )
    assert source_admission(
        "runtime/commercial/snapshot.json",
        dict(message(), direction="inbound"),
    ) == "EXCLUDED_UNRELATED_RUNTIME_SNAPSHOT"
    accepted, report = admit_candidate_rows([
        ("public.outbound_events", row),
        ("public.outbound_replies", message()),
    ])
    assert len(accepted) == 1
    assert report["excluded_nonmessage_rows"] == 1
    assert report["admission_does_not_authenticate_buyer_intent"] is True
    assert report["execution_authority"] == "none"
    final = adjudicate_records(accepted)
    assert final["semantic_effectiveness"]["canonical_message_count"] == 1
    assert final["control_effectiveness"]["action_authority"] is False


def test_missing_identity_in_true_reply_source_still_quarantined():
    row = message()
    del row["thread_id"]
    accepted, report = admit_candidate_rows([
        ("public.outbound_replies", row),
    ])
    assert len(accepted) == 1
    proof = adjudicate_records(accepted)
    assert proof["quarantine"]["quarantine_count"] == 1
    assert "MISSING_STABLE_THREAD_ID" in proof["quarantine"]["records"][0]["reasons"]
    assert report["missing_identity_records_remain_quarantined"] is True


def test_runtime_event_requires_explicit_inbound_direction_and_allowed_source():
    inbound = dict(message(), direction="inbound")
    accepted, report = admit_candidate_rows([
        ("runtime/conversations/received.json", inbound),
        ("runtime/conversations/sent.json", dict(message(), direction="outbound")),
        ("runtime/mailbox/source.json", dict(message(), classification="positive_reply")),
        ("runtime/other/snapshot.json", inbound),
    ])
    assert len(accepted) == 1
    assert report["total_source_rows_examined"] == 4
    assert report["excluded_nonmessage_rows"] == 3
    assert source_admission("runtime/inbound/raw.json", dict(message(), event_type="reply")) == (
        "EXCLUDED_RUNTIME_NON_INBOUND"
    )
    assert source_admission(
        "public.empire_conversations", {"external_conversation_id": "real-thread"}
    ) == "EXCLUDED_CONTEXT_ONLY_TABLE"
    assert source_admission(
        "public.empire_conversation_events",
        {"provider_event_id": "ev-1", "direction": "outbound"},
    ) == "EXCLUDED_CONVERSATION_EVENT_NOT_ORIGINAL_INBOUND"
    assert source_admission(
        "public.empire_conversation_events",
        {"provider_event_id": "ev-1", "direction": "inbound"},
    ) == "CANDIDATE_FROM_ORIGINAL_INBOUND_EVENT"


def test_unrelated_db_tables_do_not_qualify_just_for_message_fields():
    row = message()
    accepted, report = admit_candidate_rows([
        ("public.outbound_intents", row),
        ("public.fulfilment_orders", row),
        ("public.empire_conversation_events", row),
        ("public.intelligence_outcomes", row),
    ])
    assert accepted == []
    assert report["reason_counts"]["EXCLUDED_UNRELATED_DATABASE_TABLE"] == 2
    assert report["reason_counts"]["EXCLUDED_CONTEXT_ONLY_TABLE"] == 1
    assert report["reason_counts"]["EXCLUDED_CONVERSATION_EVENT_NOT_ORIGINAL_INBOUND"] == 1
    assert report["tenant_binding_established"] is False


def test_unknown_rows_are_not_upgraded_and_no_contact_data_in_summary():
    records = [
        ("untrusted", {"email": "private@example.test"}),
        ("public.outbound_events", {"to": "private@example.test"}),
        ("public.outbound_replies", {"from_email": "private@example.test"}),
        ("runtime/mailbox/event.json", {"direction": "unknown"}),
        ("public.outbound_replies", "invalid"),
    ]
    kept, result = admit_candidate_rows(records)  # type: ignore[arg-type]
    assert len(kept) == 1
    assert "private@example.test" not in str(result)
    assert result["admitted_conversation_candidate_rows"] == 1
    assert result["execution_authority"] == "none"


def test_collector_end_to_end_ignores_outbound_events_and_retains_real_quarantine(
    tmp_path, monkeypatch,
):
    """Isolated real runner: no real database, mailbox, service or runtime writes."""
    import importlib.util
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "run_conversations_replies_control_test",
        root / "scripts/run_conversations_replies_control.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    discovery = tmp_path / "discovery.json"
    discovery.write_text(json.dumps({
        "database_candidates": [
            {"table": "public.outbound_events", "columns": [{"column": "message_id"}]},
            {"table": "public.outbound_replies", "columns": [{"column": "message_id"}]},
            {"table": "public.empire_conversations", "columns": [{"column": "thread_id"}]},
            {"table": "public.outbound_intents", "columns": [{"column": "message_id"}]},
        ],
        "runtime_candidates": [],
    }))
    output = tmp_path / "snapshot.json"
    monkeypatch.setattr(module, "DISCOVERY", discovery)
    monkeypatch.setattr(module, "OUT", output)
    tables_queried = []

    def select(table):
        tables_queried.append(table)
        if table == "public.outbound_replies":
            return [message(), {"message_id": "incomplete-original"}]
        if table == "public.empire_conversations":
            return []
        raise AssertionError("unrelated table queried")

    monkeypatch.setattr(module, "query_table", select)
    monkeypatch.setattr(module, "runtime_records", lambda discovery: [
        ("runtime/commercial/telemetry.json", dict(message(), direction="inbound")),
        ("runtime/mailbox/inbound-original.json",
         dict(message(), message_id="mailbox-2", direction="inbound")),
    ])
    assert module.main() is None
    snapshot = json.loads(output.read_text())
    source = snapshot["source_admission"]
    assert tables_queried == ["public.outbound_replies"]
    assert source["total_source_rows_examined"] == 4
    assert source["admitted_conversation_candidate_rows"] == 3
    assert source["excluded_nonmessage_rows"] == 1
    assert snapshot["semantic_effectiveness"]["canonical_message_count"] == 2
    assert snapshot["quarantine"]["quarantine_count"] == 1
    assert "MISSING_STABLE_THREAD_ID" in snapshot["quarantine"]["records"][0]["reasons"]
    assert snapshot["governance"]["db_write"] is False
    assert snapshot["governance"]["outbound"] is False
    assert snapshot["control_effectiveness"]["action_authority"] is False


def test_collector_requires_reviewed_table_and_message_columns():
    import importlib.util
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "run_conversation_table_guard_test",
        root / "scripts/run_conversations_replies_control.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.useful_db_candidate({
        "table": "public.outbound_events", "columns": [{"column": "message_id"}]
    }) is False
    assert module.useful_db_candidate({
        "table": "public.outbound_replies", "columns": [{"column": "message_id"}]
    }) is True
    assert module.useful_db_candidate({
        "table": "public.outbound_replies", "columns": [{"column": "product_code"}]
    }) is False
    assert module.useful_db_candidate({
        "table": "public.empire_conversations", "columns": [{"column": "external_conversation_id"}]
    }) is False
    assert module.useful_db_candidate({
        "table": "public.empire_conversation_events", "columns": [{"column": "provider_event_id"}]
    }) is True
