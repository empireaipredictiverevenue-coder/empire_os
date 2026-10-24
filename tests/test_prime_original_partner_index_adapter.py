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


def test_temporal_denominators_and_message_codes_are_not_unique_buyers():
    report = run()
    assert report["messages_with_semantic_codes_not_enquiries"] == 2
    assert report["messages_without_semantic_codes_not_negatives"] == 1
    assert report["all_message_directions_not_canonical_buyer_authentication"] == {
        "INBOUND_INBOX": 2,
        "OUTBOUND_SENT": 1,
        "EXCLUDED_DRAFT_SPAM_OR_TRASH": 0,
        "UNCLASSIFIED_DIRECTION": 0,
    }
    assert report["semantic_occurrence_age_bands_not_current_demand"] == {
        "0_7_DAYS": 3, "8_30_DAYS": 0, "31_45_DAYS": 0,
        "OLDER_THAN_45_DAYS": 0,
    }
    assert report["inbound_semantic_occurrence_age_bands_not_verified_enquiries"]["0_7_DAYS"] == 2
    assert report["outbound_semantic_occurrence_age_bands_not_buyer_replies"]["0_7_DAYS"] == 1
    founder = report["founder_research_projection"]
    assert founder["semantic_observations_0_7d_count_band_if_at_least_five"] is None
    assert founder["inbound_semantic_observations_0_7d_count_band_if_at_least_five"] is None
    assert founder["fresh_owner_snapshot_does_not_make_old_messages_fresh"] is True
    assert founder["historical_older_than_7d_observations_are_not_current_demand"] is True


def test_fresh_original_poll_with_stale_historical_message_cannot_inflate_fresh_intent():
    i = index()
    i["threads"][0]["messages"][1]["date"] = "2026-08-24T11:01:00"
    r = run(idx=i)
    assert r["semantic_occurrence_age_bands_not_current_demand"]["OLDER_THAN_45_DAYS"] == 2
    assert r["semantic_occurrence_age_bands_not_current_demand"]["0_7_DAYS"] == 1
    assert r["inbound_semantic_occurrence_age_bands_not_verified_enquiries"]["OLDER_THAN_45_DAYS"] == 2
    assert r["founder_research_projection"]["inbound_semantic_observations_0_7d_count_band_if_at_least_five"] is None
    assert r["real_buyer_intent_verified"] is False


def test_original_owner_snapshot_clock_rejects_post_collection_message_even_without_code():
    i = index()
    i["threads"][0]["messages"][2]["date"] = "2026-10-24T12:30:00"
    with pytest.raises(PrimeIndexHold, match="message_postdates_original_owner_snapshot"):
        run(idx=i)


def test_unclassified_and_excluded_messages_are_not_counted_as_active_inbound_demand():
    i = index()
    i["threads"][0]["messages"][2]["labels"] = ["DRAFT"]
    r = run(idx=i)
    assert r["all_message_directions_not_canonical_buyer_authentication"]["EXCLUDED_DRAFT_SPAM_OR_TRASH"] == 1
    assert r["messages_without_semantic_codes_not_negatives"] == 1
    i["threads"][0]["messages"][2]["labels"] = ["Label_99"]
    r = run(idx=i)
    assert r["all_message_directions_not_canonical_buyer_authentication"]["UNCLASSIFIED_DIRECTION"] == 1
    assert r["inbound_semantic_occurrences_not_buyer_enquiries"] == 2


def test_all_original_message_rows_have_valid_clocks_even_when_uncoded():
    i = index()
    i["threads"][0]["messages"][2]["date"] = "not-a-valid-original-UTC-clock"
    with pytest.raises(PrimeIndexHold, match="UTC_wall_clock_contract"):
        run(idx=i)


def test_fresh_five_event_band_does_not_mark_any_event_authenticated():
    i = index()
    i["threads"][0]["messages"][0]["recognized_codes"] = [
        "COMPLETE_BUYER_REQUIREMENTS_SENT",
        "PILOT_TECHNICAL_REQUIREMENTS_SENT",
    ]
    # Two outbound codes + two inbound codes; add one legitimate extra
    # inbound code on the same original provider message.
    i["threads"][0]["messages"][1]["recognized_codes"].append(
        "RECORDING_ENABLED_REPORTED"
    )
    r = run(idx=i)
    founder = r["founder_research_projection"]
    assert founder["semantic_observations_0_7d_count_band_if_at_least_five"] == "5-9"
    assert founder["inbound_semantic_observations_0_7d_count_band_if_at_least_five"] is None
    assert founder["buyer_enquiries_independently_verified"] is False
    assert r["signed_owner_receipts_admitted"] is False


def test_duplicate_message_labels_fail_closed_before_any_aggregation():
    i = index()
    i["threads"][0]["messages"][2]["labels"] = ["INBOX", "INBOX"]
    with pytest.raises(PrimeIndexHold, match="malformed_original_owner_message_labels"):
        run(idx=i)
