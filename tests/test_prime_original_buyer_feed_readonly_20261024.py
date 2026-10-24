"""Read-only original source readiness: only aggregate output, no copied PII."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

from scripts.review_prime_original_buyer_feed_readonly_20261024 import inspect
from scripts.import_connected_gmail_buyer_metadata import INDEX, SOURCE

NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)


def put(root, relative, content, *, mode=0o600):
    dest = root / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(content), encoding="utf8")
    dest.chmod(mode)


def original(root, *, stamp=None):
    src = {
        "schema_version": "empire.buyer_mail_relationship_summary.v1",
        "origin": "connected_gmail_connector_read_only",
        "email": "private-contact@example.org",
        "threads": [],
    }
    idx = {
        "schema_version": "empire.buyer_gmail_original_message_index.v1",
        "source": "empire_gmail_api_readonly",
        "collected_at": stamp or (NOW - timedelta(minutes=10)).isoformat(),
        "threads": [
            {
                "thread_id": "original-private-thread-one",
                "truncated": False,
                "message_count": 2,
                "messages": [
                    {"id": "original-private-msg-one", "from": "private@example.org",
                     "subject": "private contents"},
                    {"id": "original-private-msg-two", "from": "private2@example.org",
                     "recognized_codes": []},
                ],
            },
        ],
    }
    put(root, SOURCE, src)
    put(root, INDEX, idx)
    return idx


def test_empty_or_missing_original_owner_proof_is_not_zero_buyers(tmp_path):
    output = inspect(tmp_path, now=NOW)
    assert output["original_message_index_available"] is False
    assert output["owner_thread_count_not_verified_buyers"] is None
    assert output["single_original_buyer_intent_receipt_authenticated"] is False
    assert output["source_admission_authorized"] is False
    assert output["execution_authority"] == "none"


def test_fresh_aggregated_original_metadata_never_exports_mail_headers(tmp_path):
    original(tmp_path)
    output = inspect(tmp_path, now=NOW)
    assert output["original_message_index_available"] is True
    assert output["original_message_index_fresh"] is True
    assert output["owner_thread_count_not_verified_buyers"] == 1
    assert output["owner_message_count_not_verified_replies"] == 2
    assert output["semantic_event_code_count_not_verified_intent"] == 0
    assert output["canonical_provider_contact_tenant_binding_verified"] is False
    assert output["single_original_buyer_intent_receipt_authenticated"] is False
    for secret in ("private-contact", "private@", "original-private-thread-one",
                   "private contents", "original-private-msg-one"):
        assert secret not in str(output)


def test_private_source_must_not_have_public_read_permissions(tmp_path):
    original(tmp_path)
    (tmp_path / SOURCE).chmod(0o644)
    output = inspect(tmp_path, now=NOW)
    assert output["original_message_index_available"] is False
    assert output["source_admission_authorized"] is False


def test_stale_original_metadata_remains_unverified_not_a_zero(tmp_path):
    original(tmp_path, stamp=(NOW - timedelta(days=5)).isoformat())
    output = inspect(tmp_path, now=NOW)
    assert output["original_message_index_available"] is True
    assert output["original_message_index_fresh"] is False
    assert output["status"] == "STALE_ORIGINAL_OWNER_METADATA_NO_VERIFIED_BUYER"
    assert output["single_original_buyer_intent_receipt_authenticated"] is False


def test_future_or_naive_source_clock_fails_closed(tmp_path):
    original(tmp_path, stamp=(NOW + timedelta(hours=1)).isoformat())
    assert inspect(tmp_path, now=NOW)["original_message_index_available"] is False
    original(tmp_path, stamp="2026-10-24T10:00:00")
    assert inspect(tmp_path, now=NOW)["original_message_index_available"] is False


def test_duplicate_original_message_fails_closed(tmp_path):
    index = original(tmp_path)
    index["threads"][0]["messages"][1]["id"] = index["threads"][0]["messages"][0]["id"]
    put(tmp_path, INDEX, index)
    result = inspect(tmp_path, now=NOW)
    assert result["original_message_index_available"] is False
    assert result["buyer_outbound_authorized"] is False


def test_unknown_semantic_code_not_interpreted_as_purchase(tmp_path):
    index = original(tmp_path)
    index["threads"][0]["messages"][0]["recognized_codes"] = ["CANONICAL_PAYMENT_RECEIVED"]
    put(tmp_path, INDEX, index)
    output = inspect(tmp_path, now=NOW)
    assert output["original_message_index_available"] is False
    assert output["single_original_buyer_intent_receipt_authenticated"] is False


def test_invalid_original_source_schema_fails_closed(tmp_path):
    original(tmp_path)
    put(tmp_path, SOURCE, {"schema_version": "fake-source"})
    output = inspect(tmp_path, now=NOW)
    assert output["status"] == "PRIVATE_ORIGINAL_BUYER_METADATA_UNAVAILABLE_OR_UNVERIFIED"
    assert output["database_writes"] is False
