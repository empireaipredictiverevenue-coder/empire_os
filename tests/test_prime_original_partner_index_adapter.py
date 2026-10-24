"""Original Gmail metadata -> PRIME partner semantic shadow, wholly synthetic."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone, timedelta

import pytest

from empire_os.prime_original_partner_index_adapter import (
    review_original_partner_index, PrimeIndexHold,
)
from scripts.review_prime_original_partner_semantics_readonly_20261024 import inspect
from scripts.import_connected_gmail_buyer_metadata import SOURCE, INDEX

NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
TID = "1a0d9ce883c87d4a"
KNOWN = {TID: "partner-example"}
KEY = b"\x17" * 32


def original():
    return {
        "schema_version": "empire.buyer_mail_relationship_summary.v1",
        "origin": "connected_gmail_connector_read_only",
        "mailbox": "fixture-buyer@example.test",
        "threads": [
            {
                "gmail_thread_id": TID,
                "entity_key": "partner-example",
                "company": "Fixture Partnership",
            },
        ],
    }


def index():
    return {
        "schema_version": "empire.buyer_gmail_original_message_index.v1",
        "source": "empire_gmail_api_readonly",
        "scope": "reviewed_existing_warm_partner_threads",
        "original_message_bodies": "remain_in_gmail_not_copied_to_server",
        "collected_at": (NOW - timedelta(minutes=8)).isoformat(),
        "threads": [
            {
                "thread_id": TID,
                "partner": "Fixture Partnership",
                "message_count": 3,
                "truncated": False,
                "messages": [
                    {
                        "id": "1a15000000000001",
                        "date": "2026-10-24T11:00:00",
                        "labels": ["SENT"],
                        "from": "private-sender@private.test",
                        "subject": "Private outbound requirements",
                        "recognized_codes": [
                            "COMPLETE_BUYER_REQUIREMENTS_SENT",
                        ],
                    },
                    {
                        "id": "1a15000000000002",
                        "date": "2026-10-24T11:01:00",
                        "labels": ["INBOX"],
                        "from": "private-buyer@private.test",
                        "subject": "Private inbound",
                        "recognized_codes": [
                            "BUYER_INTERNAL_DECISION_PENDING_REPORTED",
                            "ROUTE_OR_NUMBER_LIVE_REPORTED",
                        ],
                    },
                    {
                        "id": "1a15000000000003",
                        "date": "2026-10-24T11:02:00",
                        "labels": ["INBOX"],
                        "recognized_codes": [],
                    },
                ],
            },
        ],
    }


def run(orig=None, idx=None, **kwargs):
    return review_original_partner_index(
        original=original() if orig is None else orig,
        index=index() if idx is None else idx,
        known_threads=KNOWN, as_of=NOW,
        ephemeral_hmac_key=KEY,
        **kwargs,
    )


def test_original_owner_index_to_prime_observed_only_cannot_infer_buyers():
    o, i = original(), index()
    before = deepcopy((o, i))
    report = run(o, i)
    assert (o, i) == before
    assert report["status"] == "PRIVATE_ORIGINAL_OWNER_METADATA_SHADOW_ONLY"
    assert report["monitored_thread_count_not_verified_buyers"] == 1
    assert report["indexed_message_count_not_verified_buyer_replies"] == 3
    assert report["semantic_occurrences_not_enquiries"] == 3
    assert report["inbound_semantic_occurrences_not_buyer_enquiries"] == 2
    assert report["outbound_semantic_occurrences_not_buyer_enquiries"] == 1
    assert report["real_buyer_intent_verified"] is False
    assert report["signed_owner_receipts_admitted"] is False
    assert report["atomic_nonce_replay_registry_verified"] is False
    assert report["realized_revenue_cents"] is None
    assert report["outbound_sent"] is False
    assert report["execution_authority"] == "none"
    for private in ("Fixture Partnership", "private-buyer", TID, "1a15000000000002"):
        assert private not in str(report)
    founder = report["founder_research_projection"]
    assert founder["observed_reported_event_count_band"] == "0-4"
    assert founder["category_count_band_when_at_least_five"] == {}
    assert founder["buyer_enquiries_independently_verified"] is False


def test_no_events_in_original_snapshot_is_observed_zero_not_buyer_zero():
    i = index()
    for m in i["threads"][0]["messages"]:
        m["recognized_codes"] = []
    report = run(idx=i)
    assert report["semantic_occurrences_not_enquiries"] == 0
    assert report["real_buyer_intent_verified"] is False
    assert report["founder_research_projection"]["buyer_enquiries_independently_verified"] is False


@pytest.mark.parametrize("mutator, reason", [
    (lambda x: x["threads"][0].update(partner="Impersonated company"), "link_conflict"),
    (lambda x: x["threads"][0].update(truncated=True), "complete_thread"),
    (lambda x: x["threads"][0].update(message_count=33), "message_integrity"),
    (lambda x: x["threads"][0]["messages"][1].update(id="1a15000000000001"), "duplicate_original_provider_message"),
    (lambda x: x["threads"][0]["messages"][1].update(labels=["SENT"]), "code_direction_conflict"),
    (lambda x: x["threads"][0]["messages"][1].update(labels=["SENT", "INBOX"]), "noncanonical"),
    (lambda x: x["threads"][0]["messages"][1].update(labels=["INBOX", "SPAM"]), "noncanonical"),
    (lambda x: x["threads"][0]["messages"][1].update(labels=["DRAFT"]), "noncanonical"),
    (lambda x: x["threads"][0]["messages"][1].update(recognized_codes=["FAKE_BUYER_PAID"]), "untrusted"),
    (lambda x: x["threads"][0]["messages"][1].update(recognized_codes=["ROUTE_OR_NUMBER_LIVE_REPORTED"] * 2), "untrusted"),
    (lambda x: x["threads"][0]["messages"][1].update(date="2026-10-24T11:01:00-05:00"), "UTC_wall_clock_contract"),
    (lambda x: x.update(collected_at=(NOW - timedelta(hours=4)).isoformat()), "not_fresh"),
    (lambda x: x.update(collected_at=(NOW + timedelta(minutes=10)).isoformat()), "not_fresh"),
    (lambda x: x.update(original_message_bodies="stored raw on disk"), "protected_buyer_metadata_contract"),
    (lambda x: x.update(scope="all-mail-unverified"), "protected_buyer_metadata_contract"),
])
def test_invalid_index_or_lookahead_fail_closed(mutator, reason):
    i = index()
    mutator(i)
    with pytest.raises(PrimeIndexHold, match=reason):
        run(idx=i)


def test_original_owner_mapping_mismatch_fails_closed():
    o = original()
    o["threads"][0]["entity_key"] = "someone-else"
    with pytest.raises(PrimeIndexHold, match="thread_entity_conflict"):
        run(orig=o)


def test_missing_original_mapping_fails_closed():
    o = original()
    o["threads"].clear()
    with pytest.raises(PrimeIndexHold, match="incomplete_original_owner_known_thread_join"):
        run(orig=o)


def test_duplicate_relationship_row_fails_closed():
    o = original()
    o["threads"].append(deepcopy(o["threads"][0]))
    with pytest.raises(PrimeIndexHold, match="duplicate_original_owner_relationship"):
        run(orig=o)


def test_caller_cannot_use_weak_hmac_key_as_original_source_authority():
    with pytest.raises(PrimeIndexHold, match="fresh_ephemeral_private_review_key_required"):
        review_original_partner_index(
            original=original(), index=index(), known_threads=KNOWN,
            as_of=NOW, ephemeral_hmac_key=b"unguarded",
        )


def test_private_source_reader_missing_file_returns_unknown_not_buyer_zero(tmp_path):
    result = inspect(tmp_path, now=NOW)
    assert result["status"] == "ORIGINAL_OWNER_PRIVATE_METADATA_UNAVAILABLE_OR_HELD"
    assert result["semantic_occurrences_not_enquiries"] is None
    assert result["real_buyer_intent_verified"] is False
    assert result["outbound_sent"] is False


def test_one_scope_hmac_digest_never_returned_to_founder():
    a = run()
    b = run()
    assert a["founder_research_projection"] == b["founder_research_projection"]
    assert "message_fingerprint" not in str(a)
    assert "message_fingerprint" not in str(b)
