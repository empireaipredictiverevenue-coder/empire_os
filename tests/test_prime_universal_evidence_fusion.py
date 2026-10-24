"""Cross-source, owner-bound PRIME shadow evidence integration contracts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from empire_os.prime_universal_evidence_fusion import (
    APPROVED_PURPOSE, RECEIPT_SCHEMA, OWNER_CLASSES, PrimeFusionHold,
    review_prime_universal_evidence,
)
from empire_os.predictive_revenue_brain_bridge import (
    build_predictive_revenue_brain_review,
)

NOW = datetime(2026, 10, 24, 0, 0, tzinfo=timezone.utc)
TENANT = "tenant-test-only"


def sha(value):
    return sha256(value.encode()).hexdigest()


def entry(
    label, *, owner="buyer_acquisition", klass="EXPLICIT_ENQUIRY",
    entity="same-company", origin=None, **changes,
):
    row = {
        "schema_version": RECEIPT_SCHEMA,
        "owner": owner,
        "evidence_class": klass,
        "event_sha256": sha("event-" + label),
        "origin_sha256": sha(origin or "origin-" + label),
        "entity_sha256": sha(entity),
        "source_sha256": sha("source-" + owner),
        "tenant_scope_sha256": sha(TENANT),
        "tenant_binding_sha256": sha("original-owner-tenant-bind"),
        "observed_at": (NOW - timedelta(minutes=6)).isoformat(),
        "received_at": (NOW - timedelta(minutes=5)).isoformat(),
        "provenance_status": "ORIGINAL_OWNER_CUSTODY_REVIEWED",
        "source_rights_status": "OWNER_REVIEWED_PERMITTED",
        "permitted_purpose": APPROVED_PURPOSE,
        "supports_sha256": [],
        "contradicts_sha256": [],
        "prediction_as_of": None,
        "execution_authority": "none",
    }
    row.update(changes)
    return row


def review(*entries):
    return review_prime_universal_evidence(
        tenant_id=TENANT, as_of=NOW, original_owner_summaries=list(entries)
    )


def test_not_connected_is_not_zero_and_bridge_reuses_original():
    r = review_prime_universal_evidence(
        tenant_id=TENANT, as_of=NOW, original_owner_summaries=None,
    )
    assert r["status"] == "NOT_CONNECTED_NOT_VERIFIED_ZERO"
    assert r["record_count_owner_supplied"] is None
    assert r["prediction_accuracy_proven"] is False
    bridged = build_predictive_revenue_brain_review(
        tenant_id=TENANT, as_of=NOW,
    )
    assert bridged["prime_universal_evidence_shadow"] == r
    assert bridged["astra_dispatch_executed"] is False
    assert bridged["database_writes"] is False
    assert bridged["recognized_revenue_cents"] is None


def test_all_original_source_families_are_bounded_and_owner_only():
    rows = []
    for owner, classes in sorted(OWNER_CLASSES.items()):
        klass = sorted(classes)[0]
        time_overrides = ({"observed_at": (NOW - timedelta(seconds=25)).isoformat(),
                           "received_at": (NOW - timedelta(seconds=20)).isoformat()}
                          if owner == "trading_quant" else {})
        rows.append(entry(owner, owner=owner, klass=klass, entity=owner,
                          **time_overrides))
    result = review(*rows)
    assert result["record_count_owner_supplied"] == len(OWNER_CLASSES)
    assert len(result["source_family_counts"]) == len(OWNER_CLASSES)
    assert result["buyer_enquiries_independently_verified"] is False
    assert result["source_provenance_independently_authenticated_by_this_module"] is False
    assert result["revenue_recognized_cents"] is None
    assert result["financial_execution"] is False
    assert result["execution_authority"] == "none"
    bridge = build_predictive_revenue_brain_review(
        tenant_id=TENANT, as_of=NOW, original_owner_evidence_summaries=rows,
    )
    assert bridge["prime_universal_evidence_shadow"] == result
    assert bridge["prime_scenarios"] is None


def test_independent_claims_collapsed_by_origin_and_no_confidence_inflation():
    a = entry("a", owner="buyer_acquisition", klass="EXPLICIT_ENQUIRY", origin="article-1")
    b = entry("b", owner="search_intelligence", klass="GENERAL_INTEREST", origin="article-1")
    c = entry("c", owner="permits", klass="ACTIVITY", origin="official-record-2")
    r = review(a, b, c)
    grouped = r["group_reviews"][0]
    assert grouped["owner_supplied_record_count"] == 3
    assert grouped["distinct_origin_count"] == 2
    assert grouped["correlated_repeat_count"] == 1
    assert grouped["linked_independent_origin_support_count"] == 0
    assert grouped["highest_owner_asserted_commercial_evidence_level"] == 3
    assert grouped["confidence_or_probability"] is None
    assert grouped["buyer_intent_independently_verified"] is False


def test_evidence_levels_not_conflated_with_proven_revenue():
    weather = entry("weather", owner="storm", klass="ACTIVITY")
    crm = entry("crm", owner="smart_crm", klass="COMMITMENT")
    financial = entry("settled", owner="economic_memory", klass="REALIZED_OUTCOME")
    trading = entry("trading", owner="trading_quant", klass="TRADING_RESEARCH")
    r = review(weather, crm, financial, trading)
    group = r["group_reviews"][0]
    assert group["highest_owner_asserted_commercial_evidence_level"] == 5
    assert r["settled_revenue_independently_verified"] is False
    assert r["accepted_orders_independently_verified"] is False
    assert r["trading_outcomes_mixed_into_commercial_calibration"] is False
    assert r["predictions_evaluated"] is False
    assert r["revenue_recognized_cents"] is None
    assert r["prediction_accuracy_proven"] is False


@pytest.mark.parametrize("field,value,reason", [
    ("tenant_scope_sha256", sha("other-tenant"), "cross_tenant"),
    ("source_rights_status", "NOT_REVIEWED", "source_usage_rights"),
    ("provenance_status", "UNKNOWN", "source_provenance"),
    ("permitted_purpose", "OUTBOUND_CAMPAIGN", "cross_purpose"),
    ("execution_authority", "trade", "financial_or_external"),
    ("event_sha256", "raw-person@example.com", "event_sha256"),
    ("tenant_binding_sha256", "", "tenant_binding"),
    ("source_sha256", "buyer@example.com", "source_sha256"),
    ("evidence_class", "REALIZED_OUTCOME", "unsupported_owner"),
    ("owner", "attacker_bot", "unsupported_original"),
    ("evidence_class", [], "unsupported_owner"),
])
def test_untrusted_or_privacy_leaking_claims_rejected(field, value, reason):
    r = review(entry("one", **{field: value}))
    assert r["record_count_owner_supplied"] == 0
    assert r["rejected_count"] == 1
    assert any(reason in key for key in r["rejected_reasons_aggregate"])


def test_unexpected_private_record_fields_are_rejected():
    x = entry("one")
    x["raw_email"] = "PRIVATE_PERSON@example.com"
    r = review(x)
    assert r["rejected_count"] == 1
    assert "PRIVATE_PERSON" not in str(r)
    assert "raw_email" not in str(r)


def test_future_stale_and_noncausal_event_times_rejected():
    future = entry("future", received_at=(NOW + timedelta(seconds=1)).isoformat())
    impossible = entry("impossible", observed_at=NOW.isoformat())
    stale = entry("stale", owner="storm", klass="ACTIVITY",
                  received_at=(NOW - timedelta(days=1)).isoformat(),
                  observed_at=(NOW - timedelta(days=1, minutes=1)).isoformat())
    r = review(future, impossible, stale)
    assert r["record_count_owner_supplied"] == 0
    assert r["rejected_count"] == 3


def test_forward_prediction_timestamp_cannot_use_later_observation():
    row = entry("leak", prediction_as_of=(NOW - timedelta(hours=2)).isoformat())
    r = review(row)
    assert r["rejected_count"] == 1
    assert "prediction_foreknowledge_or_future_time" in r["rejected_reasons_aggregate"]


def test_verified_financial_outcome_is_never_a_prediction_feature():
    row = entry("finance", owner="economic_memory", klass="REALIZED_OUTCOME",
                prediction_as_of=NOW.isoformat())
    assert review(row)["record_count_owner_supplied"] == 0


def test_contradiction_preserved_and_cross_entity_links_refused_for_support():
    a = entry("alpha")
    b = entry("beta", contradicts_sha256=[a["event_sha256"]])
    r = review(a, b)
    assert r["group_reviews"][0]["contradiction_or_invalid_link_present"] is True
    assert r["group_reviews"][0]["review_status"] == "CONTRADICTION_REVIEW_HOLD"
    assert r["group_reviews"][0]["linked_contradictory_event_pair_count"] == 1
    third = entry("third", entity="other-company", supports_sha256=[a["event_sha256"]])
    r2 = review(a, third)
    assert r2["cross_entity_link_violation_count"] == 1
    assert any(g["contradiction_or_invalid_link_present"] for g in r2["group_reviews"])


def test_unknown_refs_cannot_be_claimed_as_independent_corroboration():
    x = entry("link", supports_sha256=[sha("not-in-source-batch")])
    r = review(x)
    assert r["unresolved_evidence_link_count"] == 1
    assert r["group_reviews"][0]["distinct_origin_count"] == 1


def test_duplicate_idempotency_and_conflicting_revisions_are_quarantined():
    a = entry("same")
    assert review(a, dict(a))["record_count_owner_supplied"] == 1
    different = entry("same", evidence_class="GENERAL_INTEREST")
    r = review(a, different, a)
    assert r["record_count_owner_supplied"] == 0
    assert r["conflicting_event_count"] == 1


def test_no_private_tenant_or_source_identifiers_in_founder_aggregates():
    row = entry("do-not-leak", entity="PrivateCo", origin="secret-provider")
    r = review(row)
    encoded = str(r)
    for private in (TENANT, sha(TENANT), sha("PrivateCo"),
                    sha("secret-provider"), row["event_sha256"],
                    row["source_sha256"], row["tenant_binding_sha256"]):
        assert private not in encoded
    assert r["founder_summary_safe_aggregates_only"] is True


def test_bounds_unknown_inputs_and_bad_clocks_fail_closed():
    with pytest.raises(PrimeFusionHold, match="bounded"):
        review_prime_universal_evidence(
            tenant_id=TENANT, as_of=NOW,
            original_owner_summaries=[entry(str(i)) for i in range(101)],
        )
    with pytest.raises(PrimeFusionHold, match="aware"):
        review_prime_universal_evidence(
            tenant_id=TENANT, as_of=NOW.replace(tzinfo=None),
            original_owner_summaries=[],
        )
    assert review(entry("test", received_at="2026-10-24T01:00:00+01:00"))["rejected_count"] == 1


def test_corroboration_requires_explicit_link_and_distinct_origin():
    a = entry("source-a", owner="permits", klass="ACTIVITY", origin="official-1")
    b = entry("source-b", owner="buyer_acquisition", klass="EXPLICIT_ENQUIRY",
              origin="independent-2", supports_sha256=[a["event_sha256"]])
    duplicate = entry("source-c", owner="media_os", klass="GENERAL_INTEREST",
                      origin="independent-2", supports_sha256=[a["event_sha256"]])
    r = review(a, b, duplicate)
    group = r["group_reviews"][0]
    assert group["distinct_origin_count"] == 2
    assert group["linked_independent_origin_support_count"] == 1
    assert group["confidence_or_probability"] is None


def test_empty_owner_input_cannot_be_reported_as_a_true_zero():
    r = review()
    assert r["status"] == "OWNER_INPUT_EMPTY_NOT_VERIFIED_ZERO"
    assert r["record_count_owner_supplied"] == 0
    assert r["predictions_evaluated"] is False
    assert r["independent_scientific_validation_status"] == "HOLD_NO_VALIDATED_FORWARD_COHORT"
