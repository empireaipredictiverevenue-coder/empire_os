"""Original reply linkage design tests: schema != validated join or buyer intent."""
from datetime import datetime, timezone
import json

from empire_os.conversation_reply_linkage_plan import plan, refresh, OUTPUT

NOW = datetime(2026, 10, 9, 15, tzinfo=timezone.utc)


def contract():
    return {"database_candidates": [
        {"table": "public.outbound_replies", "columns": [
            {"column": x} for x in (
                "intent_id", "provider_message_id", "normalized_from_contact",
                "received_at",
            )]},
        {"table": "public.empire_conversations", "columns": [
            {"column": x} for x in (
                "id", "outbound_intent_id", "external_conversation_id",
            )]},
        {"table": "public.outbound_intents", "columns": [
            {"column": x} for x in (
                "id", "prospect_id", "entity_id", "buyer_id", "opportunity_id",
            )]},
    ]}


def test_original_relation_names_form_proposed_path_without_verifying_data():
    proposed = plan(contract(), {"decision": {
        "status": "CROSS_TABLE_BRIDGE_REQUIRED",
    }}, now=NOW)
    assert proposed["schema_join_path_available"] is True
    assert proposed["verification_status"] == "SCHEMA_PATH_FOUND_DATA_PROOF_REQUIRED"
    assert proposed["join_edges"][0]["left"] == "public.outbound_replies.intent_id"
    assert proposed["join_edges"][1]["right"] == "public.empire_conversations.outbound_intent_id"
    assert all(not x["join_cardinality_verified"] for x in proposed["join_edges"])
    assert "TENANT_AUTHORITY_BINDING_NOT_PROVEN" in proposed["blockers"]
    assert proposed["actual_joined_rows_proven"] == 0
    assert proposed["database_access_attempted"] is False
    assert proposed["buyer_intent_verified"] is False
    assert proposed["canonical_messages_promoted"] == 0
    assert proposed["external_execution_authority"] == "none"


def test_missing_column_does_not_pretend_linkage_exists():
    source = contract()
    source["database_candidates"][1]["columns"] = [
        {"column": "id"}, {"column": "outbound_intent_id"},
    ]
    result = plan(source, {}, now=NOW)
    assert not result["schema_join_path_available"]
    assert result["verification_status"] == "SCHEMA_INCOMPLETE"
    assert result["required_tables"]["public.empire_conversations"][
        "missing_required_columns"
    ] == ["external_conversation_id"]
    assert result["buyer_intent_verified"] is False


def test_refresh_writes_only_planning_artifact_without_reading_db(tmp_path):
    source=contract()
    first = tmp_path / "runtime/control_plane/conversations_replies_binding_truth_latest.json"
    second = tmp_path / "runtime/control_plane/conversations_replies_identity_gap_latest.json"
    for path,data in ((first,source), (second,{"decision": {"status":"CROSS_TABLE_BRIDGE_REQUIRED"}})):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    before=(first.read_bytes(),second.read_bytes())
    actual=refresh(tmp_path)
    assert actual["schema_join_path_available"]
    assert (first.read_bytes(),second.read_bytes())==before
    output=tmp_path/OUTPUT
    assert output.exists()
    saved=json.loads(output.read_text())
    assert saved["normalized_scores_written"]==0
    assert saved["contact_records_read"]==0
    assert saved["buyer_intent_verified"] is False


def test_linkage_structural_aggregate_remains_unverified():
    market = {
        "generated_at": NOW.isoformat(),
        "execution_authority": "none",
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "raw_reply_records_are_commercial_proof": False,
        "inbound_reply_authenticity_verified": False,
        "restricted_reply_lineage": {
            "schema": "empire.market_gps_restricted_reply_lineage.v1",
            "window_days": 90,
            "reply_records_observed": 1,
            "reply_records_with_intent_pointer": 1,
            "reply_records_matched_to_intent": 1,
            "reply_records_matched_to_prospect": 1,
            "reply_records_missing_intent_pointer": 0,
            "reply_records_with_unmatched_intent": 0,
            "reply_records_with_unmatched_prospect": 0,
            "positive_classification_records_unverified": 1,
            "original_provider_message_id_checked": False,
            "canonical_contact_identity_verified": False,
            "provider_thread_binding_verified": False,
            "tenant_binding_verified": False,
            "buyer_intent_verified": False,
            "commercial_demand_inferred": False,
            "read_only_aggregate": True,
            "execution_authority": "none",
        }
    }
    result = plan(contract(), {}, now=NOW, market_gps=market)
    assert result["structural_reply_lineage"]["status"] == "CURRENT_STRUCTURAL_COUNTS_ONLY"
    assert result["actual_joined_rows_proven"] == 0
    assert result["buyer_intent_verified"] is False
    assert not any(x["join_cardinality_verified"] for x in result["join_edges"])


def test_linkage_without_aggregate_stays_pending(tmp_path):
    output = refresh(tmp_path)
    assert output["structural_reply_lineage"]["status"] == "PENDING_RESTRICTED_LINEAGE_SNAPSHOT"
    assert output["buyer_intent_verified"] is False
