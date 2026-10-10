"""Focused safety regressions for offline affiliate referral tracking."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import ast
from pathlib import Path

import pytest

from empire_os.affiliate_tracking import (
    AffiliateBinding, affiliate_tracking_readiness, mint_tracking_token,
    review_affiliate_outcomes, verify_tracking_token,
)


KEY = b"only-for-unit-testing-not-live-secret-key-987654321"
NOW = datetime(2026, 10, 10, 20, tzinfo=timezone.utc)


def binding(**changes):
    base = AffiliateBinding(
        tenant_ref="empire:tenant-founder",
        source_ref="publisher:roofpitch.net",
        source_domain="roofpitch.net",
        programme_ref="programme:us-roofing-review-only",
        offer_format="PUBLISHER_PPC",
        country_code="US",
    )
    return replace(base, **changes)


def token(b=None):
    return mint_tracking_token(
        b or binding(), hmac_key=KEY, issued_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(days=5),
        nonce="opaqueRandomSourceABC123456",
    )


def claimed_event(b=None, **changes):
    b = b or binding()
    event = {
        "event_id": "ringba:event_123",
        "tracking_token": token(b),
        "source_ref": b.source_ref,
        "offer_format": b.offer_format,
        "opaque_enquiry_ref": "subject-hmac-sha256:" + "a" * 64,
        "buyer_acceptance_ref": "canonical:commercial_events:acceptance-1",
        "collected_payment_ref": "canonical:verified_payments:payment-1",
        "fulfilment_ref": "canonical:fulfilment_orders:order-1",
        "approved_terms_ref": "canonical:commercial_events:terms-1",
        "currency": "USD",
        "claimed_collected_cents": 10_000,
        "claimed_reversed_cents": 0,
    }
    return {**event, **changes}


def test_signed_referral_token_source_bound_expiring_and_private():
    b = binding()
    signed = token(b)
    assert signed.startswith("af1.")
    assert "roofpitch" not in signed
    assert "@" not in signed and "phone" not in signed
    review = verify_tracking_token(signed, b, hmac_key=KEY, now=NOW)
    assert review["source_ref"] == b.source_ref
    assert review["programme_ref"] == b.programme_ref
    assert review["traffic_or_payout_authorized"] is False
    assert "tracking_token" not in review


@pytest.mark.parametrize("change", [
    {"tenant_ref": "empire:tenant-other"},
    {"source_ref": "publisher:other.net"},
    {"source_domain": "other.net"},
    {"programme_ref": "programme:different"},
    {"offer_format": "PUBLISHER_PPL"},
    {"country_code": "UK"},
])
def test_tracking_cannot_cross_source_programme_country_or_format(change):
    with pytest.raises(ValueError, match="token source"):
        verify_tracking_token(token(), binding(**change), hmac_key=KEY, now=NOW)


def test_tracking_tamper_expired_future_wrong_key_short_key_and_long_ttl():
    signed = token()
    with pytest.raises(ValueError, match="signature mismatch"):
        verify_tracking_token(signed[:-1] + ("A" if signed[-1] != "A" else "B"),
                              binding(), hmac_key=KEY, now=NOW)
    with pytest.raises(ValueError, match="signature mismatch"):
        verify_tracking_token(signed, binding(), hmac_key=b"x" * 32, now=NOW)
    with pytest.raises(ValueError, match="not currently valid"):
        verify_tracking_token(signed, binding(), hmac_key=KEY,
                              now=NOW + timedelta(days=6))
    with pytest.raises(ValueError, match="not currently valid"):
        verify_tracking_token(signed, binding(), hmac_key=KEY,
                              now=NOW - timedelta(days=2))
    with pytest.raises(ValueError, match="32-byte"):
        token_b = mint_tracking_token(
            binding(), hmac_key=b"short",
            issued_at=NOW, expires_at=NOW + timedelta(days=1),
            nonce="longOpaqueNonce1244",
        )
    with pytest.raises(ValueError, match="lifetime"):
        mint_tracking_token(binding(), hmac_key=KEY, issued_at=NOW,
                            expires_at=NOW + timedelta(days=31),
                            nonce="longOpaqueNonce1244")


def test_commercial_approval_and_commission_never_inferred_from_legacy_defaults():
    b = binding()
    readiness = affiliate_tracking_readiness(b)
    assert readiness["tracking_link_live"] is False
    assert readiness["payout_authorized"] is False
    assert "commission_terms_unverified" in readiness["blocking_evidence"]
    r = review_affiliate_outcomes(b, [claimed_event()], hmac_key=KEY, now=NOW)
    assert r["unique_reviewable_event_count"] == 1
    assert r["claims"][0]["provisional_commission_review_cents"] is None
    assert r["claims"][0]["collected_amount_independently_verified"] is False
    assert r["recognized_revenue_cents"] is None
    assert r["commission_payable_cents"] is None
    assert not r["publisher_payment_authorized"]
    assert not r["durable_tracking_event_written"]


def test_even_fully_claimed_approvals_do_not_act_as_payment_proof():
    b = binding(source_owner_verified=True, terms_approved=True,
                source_and_subaffiliate_approved=True,
                consent_and_privacy_approved=True,
                founder_live_authorized=True,
                commission_bps=1250)
    event = claimed_event(b)
    r = review_affiliate_outcomes(b, [event], hmac_key=KEY, now=NOW)
    assert r["unique_reviewable_event_count"] == 1
    assert r["claims"][0]["provisional_commission_review_cents"] == 1250
    assert r["claims"][0]["payable_commission"] is False
    assert r["recognized_revenue_cents"] is None
    assert r["publisher_payment_authorized"] is False
    assert "canonical_payment_event_join_not_performed" in r["blockers"]
    assert "durable_global_event_idempotency_not_verified" in r["blockers"]


def test_duplicates_and_cross_conversion_reuse_hold():
    b = binding()
    same = claimed_event()
    r = review_affiliate_outcomes(b, [same, same], hmac_key=KEY, now=NOW)
    assert r["unique_reviewable_event_count"] == 1
    assert r["duplicate_event_count"] == 1
    assert "duplicate_events_require_canonical_review" in r["blockers"]
    other = claimed_event(event_id="ringba:event_456",
                          buyer_acceptance_ref="canonical:commercial_events:acceptance-2")
    r = review_affiliate_outcomes(b, [same, other], hmac_key=KEY, now=NOW)
    assert r["duplicate_event_count"] == 1
    assert "duplicate_subject_across_attributed_events" in r["blockers"]
    other = claimed_event(event_id="ringba:event_456",
                          opaque_enquiry_ref="subject-hmac-sha256:" + "b" * 64)
    r = review_affiliate_outcomes(b, [same, other], hmac_key=KEY, now=NOW)
    assert "buyer_acceptance_reused_by_multiple_events" in r["blockers"]
    other = claimed_event(claimed_collected_cents=20_000)
    r = review_affiliate_outcomes(b, [same, other], hmac_key=KEY, now=NOW)
    assert "conflicting_duplicate_event_id" in r["blockers"]


@pytest.mark.parametrize("field,value", [
    ("claimed_collected_cents", True), ("claimed_collected_cents", 0),
    ("claimed_reversed_cents", -1), ("claimed_reversed_cents", 10001),
    ("currency", "GBP"),
    ("source_ref", "publisher:other.net"), ("offer_format", "PUBLISHER_PPL"),
    ("buyer_acceptance_ref", "unverified:acceptance"),
    ("collected_payment_ref", "canonical:fulfilment_orders:order-1"),
    ("opaque_enquiry_ref", "email@example.com"),
    ("opaque_enquiry_ref", "+12125550123"),
])
def test_invalid_or_unbound_conversion_never_becomes_money(field, value):
    r = review_affiliate_outcomes(
        binding(), [claimed_event(**{field: value})],
        hmac_key=KEY, now=NOW,
    )
    assert r["invalid_event_count"] == 1
    assert not r["claims"]
    assert r["commission_payable_cents"] is None
    assert not r["publisher_payment_authorized"]


def test_same_tokens_for_saas_affiliates_without_cross_programme_leakage():
    b = binding(
        source_ref="publisher:trackover.io", source_domain="trackover.io",
        programme_ref="empire:software-test", offer_format="SAAS_REFERRAL",
    )
    t = token(b)
    assert verify_tracking_token(t, b, hmac_key=KEY, now=NOW)["offer_format"] == "SAAS_REFERRAL"
    with pytest.raises(ValueError):
        verify_tracking_token(t, binding(), hmac_key=KEY, now=NOW)


def test_no_legacy_sqlite_or_network_side_effects_from_tracking_module():
    import empire_os.affiliate_tracking as tracker
    module = ast.parse(Path(tracker.__file__).read_text())
    imports = {
        node.module for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom)
    } | {
        name.name for node in ast.walk(module)
        if isinstance(node, ast.Import) for name in node.names
    }
    assert "sqlite3" not in imports and "requests" not in imports
    assert "subprocess" not in imports and "psycopg" not in imports
    assert "aiohttp" not in imports


def test_existing_six_pipeline_revenue_projection_exposes_offline_tracking():
    from empire_os.revenue_distribution_review import build_revenue_multi_pipeline_review
    report = {
        "sources": {},
        "publisher_supply_recruitment": {
            "state": "HUMAN_REVIEW_ONLY", "candidate_count": 12,
            "homeowner_supply_candidates": 10,
            "contractor_software_affiliate_candidates": 2,
        },
    }
    row = build_revenue_multi_pipeline_review(report)
    tracker = row["affiliate_tracking"]
    assert tracker["researched_publishers_not_enabled_affiliates"] == 12
    assert tracker["supported_referral_products"] == [
        "PUBLISHER_PPC", "PUBLISHER_PPL", "SAAS_REFERRAL",
    ]
    assert tracker["signed_expiring_source_bound_token_codec_testable"] is True
    assert tracker["legacy_sqlite_commission_engine_in_use"] is False
    assert tracker["canonical_empiredb_event_reader_connected"] is False
    assert tracker["public_tracking_link_endpoint_enabled"] is False
    assert tracker["conversion_ingestion_enabled"] is False
    assert tracker["commission_payout_authorized"] is False
    assert tracker["execution_authority"] == "none"
    assert row["independent_pipeline_count"] == 6
    report["publisher_supply_recruitment"]["state"] = "HOLD_INVALID_OR_CONFLICTING_EVIDENCE"
    assert build_revenue_multi_pipeline_review(report)["affiliate_tracking"][
        "researched_publishers_not_enabled_affiliates"
    ] is None


def test_canonical_attribution_candidate_reuses_immutable_empiredb_ledger():
    import uuid
    import json
    from empire_os.affiliate_tracking import prepare_canonical_attribution_event
    b = binding()
    options = {
        "tracking_token": token(b),
        "external_event_ref": "buyer:click-e6b5",
        "opaque_enquiry_ref": "subject-hmac-sha256:" + "c" * 64,
        "hmac_key": KEY,
        "occurred_at": NOW,
    }
    first = prepare_canonical_attribution_event(b, **options)
    second = prepare_canonical_attribution_event(b, **options)
    assert first == second
    assert uuid.UUID(first["deterministic_event_id"]).version == 5
    assert first["canonical_table"] == "public.commercial_events"
    assert first["insert_performed"] is False
    assert first["database_connection_used"] is False
    assert first["idempotent_insert_and_exact_readback_required"] is True
    row = first["candidate_record"]
    assert row["id"] == first["deterministic_event_id"]
    assert row["event_type"] == "affiliate_attribution_observed"
    assert row["amount_cents"] is None
    assert row["cost_cents"] is None and row["margin_cents"] is None
    assert row["payload"]["tenant_ref"] == b.tenant_ref
    assert row["payload"]["source_ref"] == b.source_ref
    assert row["payload"]["funds_received"] is False
    assert row["payload"]["actual_revenue"] is False
    assert "tracking_token" not in json.dumps(row)
    assert "@example" not in json.dumps(row)
    changed = prepare_canonical_attribution_event(
        b, **{**options, "external_event_ref": "buyer:click-new"}
    )
    assert changed["deterministic_event_id"] != first["deterministic_event_id"]
    changed_tenant = binding(tenant_ref="empire:tenant-other")
    with pytest.raises(ValueError, match="token source"):
        prepare_canonical_attribution_event(changed_tenant, **options)


def test_canonical_attribution_candidate_rejects_personal_data_and_expired_links():
    from empire_os.affiliate_tracking import prepare_canonical_attribution_event
    b = binding()
    kwargs = {
        "tracking_token": token(b), "hmac_key": KEY,
        "external_event_ref": "click-1",
        "opaque_enquiry_ref": "subject-hmac-sha256:" + "d" * 64,
        "occurred_at": NOW,
    }
    for raw in ("customer@example.com", "447562779261", "not-a-hmac"):
        with pytest.raises(ValueError, match="opaque privacy-safe"):
            prepare_canonical_attribution_event(
                b, **{**kwargs, "opaque_enquiry_ref": raw}
            )
    with pytest.raises(ValueError, match="not currently valid"):
        prepare_canonical_attribution_event(
            b, **{**kwargs, "occurred_at": NOW + timedelta(days=31)}
        )


def test_unexpected_pii_fields_and_any_duplicate_cancel_provisional_commission():
    b = binding(
        source_owner_verified=True, terms_approved=True,
        source_and_subaffiliate_approved=True,
        consent_and_privacy_approved=True,
        founder_live_authorized=True, commission_bps=1500,
    )
    clean = claimed_event(b)
    extra = claimed_event(b, customer_phone="NOT_PERMITTED")
    reviewed = review_affiliate_outcomes(
        b, [clean, extra], hmac_key=KEY, now=NOW
    )
    assert reviewed["invalid_event_count"] == 1
    assert reviewed["claims"][0]["provisional_commission_review_cents"] is None
    assert reviewed["claims"][0]["reconciliation_state"] == "HOLD_BATCH_DUPLICATE_OR_INVALID"
    assert not reviewed["publisher_payment_authorized"]
    repeated = review_affiliate_outcomes(
        b, [clean, clean], hmac_key=KEY, now=NOW
    )
    assert repeated["duplicate_event_count"] == 1
    assert repeated["claims"][0]["provisional_commission_review_cents"] is None
    assert repeated["recognized_revenue_cents"] is None


def test_affiliate_event_uses_existing_empiredb_idempotency_index():
    from empire_os.affiliate_tracking import prepare_canonical_attribution_event

    b = binding()
    kwargs = {
        "tracking_token": token(b), "external_event_ref": "buyer:click-durable-1",
        "opaque_enquiry_ref": "subject-hmac-sha256:" + "e" * 64,
        "hmac_key": KEY, "occurred_at": NOW,
    }
    result = prepare_canonical_attribution_event(b, **kwargs)
    key = result["candidate_record"]["idempotency_key"]
    assert key == result["canonical_idempotency_key"]
    assert key.startswith("affiliate:attribution:v1:")
    assert len(key) < 160
    assert key == prepare_canonical_attribution_event(b, **kwargs)[
        "canonical_idempotency_key"
    ]
    assert key != prepare_canonical_attribution_event(
        b, **{**kwargs, "external_event_ref": "buyer:click-durable-2"}
    )["canonical_idempotency_key"]
    assert result["insert_performed"] is False


def test_affiliate_exact_canonical_readback_is_comparison_not_db_proof():
    from copy import deepcopy
    from datetime import datetime
    from empire_os.affiliate_tracking import (
        compare_canonical_attribution_readback,
        prepare_canonical_attribution_event,
    )

    b = binding()
    result = prepare_canonical_attribution_event(
        b, tracking_token=token(b),
        external_event_ref="click:readback001",
        opaque_enquiry_ref="subject-hmac-sha256:" + "e" * 64,
        hmac_key=KEY, occurred_at=NOW,
    )
    candidate = result["candidate_record"]
    observed = deepcopy(candidate)
    observed["occurred_at"] = datetime.fromisoformat(
        observed["occurred_at"]
    )
    matched = compare_canonical_attribution_readback(candidate, [observed])
    assert matched["exact_row_shape_matches"] is True
    assert matched["independent_canonical_session_verified"] is False
    assert matched["durable_event_written_here"] is False
    assert matched["attribution_or_payment_approved"] is False
    assert matched["execution_authority"] == "none"
    for field, other_value in (
        ("id", "00000000-0000-4000-8000-000000000001"),
        ("idempotency_key", "affiliate:attribution:v1:modified"),
        ("event_type", "revenue_collected"),
        ("amount_cents", 10000),
        ("actor", "unauthorized"),
    ):
        tampered = deepcopy(observed)
        tampered[field] = other_value
        assert compare_canonical_attribution_readback(
            candidate, [tampered]
        )["candidate_key_collision_or_missing"] is True
    tampered = deepcopy(observed)
    tampered["payload"]["tenant_ref"] = "tenant:foreign"
    assert not compare_canonical_attribution_readback(
        candidate, [tampered]
    )["exact_row_shape_matches"]
    assert not compare_canonical_attribution_readback(
        candidate, []
    )["exact_row_shape_matches"]
    assert not compare_canonical_attribution_readback(
        candidate, [observed, observed]
    )["exact_row_shape_matches"]


def test_canonical_replay_requires_exact_identity_even_when_key_matches():
    from copy import deepcopy
    from empire_os.affiliate_tracking import (
        compare_canonical_attribution_readback,
        prepare_canonical_attribution_event,
    )
    b = binding()
    candidate = prepare_canonical_attribution_event(
        b, tracking_token=token(b),
        external_event_ref="click:replayed",
        opaque_enquiry_ref="subject-hmac-sha256:" + "f" * 64,
        hmac_key=KEY, occurred_at=NOW,
    )["candidate_record"]
    altered = deepcopy(candidate)
    altered["payload"]["opaque_subject_hmac"] = (
        "subject-hmac-sha256:" + "a" * 64
    )
    assert candidate["idempotency_key"] == altered["idempotency_key"]
    assert not compare_canonical_attribution_readback(
        candidate, [altered]
    )["exact_row_shape_matches"]

    forged = deepcopy(candidate)
    forged["idempotency_key"] = "affiliate:attribution:v1:" + "0" * 64
    with pytest.raises(ValueError, match="event identity tampered"):
        compare_canonical_attribution_readback(forged, [altered])
    forged = deepcopy(candidate)
    forged["amount_cents"] = 100
    with pytest.raises(ValueError, match="invalid nonfinancial"):
        compare_canonical_attribution_readback(forged, [altered])
