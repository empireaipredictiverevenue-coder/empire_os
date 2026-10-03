import json
from pathlib import Path

import pytest

from empire_os.all_products_premarket_gauntlet import (
    build_all_products_premarket_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "runtime" / "commercial_catalog" / "latest.json"


def current_snapshot():
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def test_current_catalog_classifies_every_product_code():
    value = build_all_products_premarket_snapshot(current_snapshot())
    assert value.total_catalog_rows == 86
    assert value.verified_sellable_count == 26
    assert value.active_pending_count == 9
    assert value.inactive_recovery_count == 51
    assert value.all_rows_classified is True
    assert len(value.rows) == 86
    assert len({row.product_code for row in value.rows}) == 86


def test_catalog_verification_does_not_make_product_campaign_ready():
    value = build_all_products_premarket_snapshot(current_snapshot())
    assert len(value.verified_sellable_codes) == 26
    assert value.campaign_ready_product_codes == ()
    assert set(value.live_smoke_missing_codes) == set(
        value.verified_sellable_codes
    )


def test_explicit_live_smoke_evidence_unlocks_only_that_verified_product():
    base = build_all_products_premarket_snapshot(current_snapshot())
    code = base.verified_sellable_codes[0]
    value = build_all_products_premarket_snapshot(
        current_snapshot(),
        live_smoke_evidence={code: "prod-smoke:evidence:v1"},
    )
    assert value.live_smoke_verified_codes == (code,)
    assert value.live_smoke_evidence_refs[code] == "prod-smoke:evidence:v1"
    assert value.campaign_ready_product_codes == (code,)
    assert code not in value.campaign_blocked_product_codes


def test_smoke_evidence_for_pending_product_fails_closed():
    with pytest.raises(
        ValueError,
        match="live smoke evidence supplied for non-sellable product",
    ):
        build_all_products_premarket_snapshot(
            current_snapshot(),
            live_smoke_evidence={
                "predictive_revenue_diagnostic": "prod-smoke:bad"
            },
        )


def test_pending_and_inactive_products_are_not_public_or_campaign_ready():
    value = build_all_products_premarket_snapshot(current_snapshot())
    ready = set(value.campaign_ready_product_codes)
    for row in value.rows:
        if row.classification != "verified_sellable":
            assert row.public_catalog_visible is False
            assert row.product_code not in ready


def test_predictive_revenue_and_commercial_exchange_are_active_pending():
    value = build_all_products_premarket_snapshot(current_snapshot())
    pending = set(value.active_pending_codes)
    assert {
        "predictive_revenue_diagnostic",
        "predictive_revenue_command_center",
        "predictive_revenue_intelligence_os",
        "predictive_revenue_autonomous_os",
        "predictive_revenue_private_strategic",
        "exchange_seat_starter",
        "exchange_seat_growth",
        "exchange_seat_pro",
        "exchange_seat_enterprise",
    }.issubset(pending)


def test_all_recovered_mrr_rows_are_inactive_recovery():
    value = build_all_products_premarket_snapshot(current_snapshot())
    recovered = [
        row for row in value.rows
        if row.product_family == "recovered_mrr"
    ]
    assert len(recovered) == 51
    assert all(
        row.classification == "inactive_recovery"
        for row in recovered
    )
    assert all(not row.public_catalog_visible for row in recovered)


def test_digital_avatar_products_remain_proposal_only_and_campaign_blocked():
    value = build_all_products_premarket_snapshot(current_snapshot())
    assert value.digital_avatar_proposal_codes == (
        "digital_avatar_copilot",
        "digital_avatar_workforce",
        "digital_avatar_white_label_workforce",
    )
    current_codes = {row.product_code for row in value.rows}
    assert not set(value.digital_avatar_proposal_codes).intersection(
        current_codes
    )
    assert set(value.digital_avatar_proposal_codes).issubset(
        value.campaign_blocked_product_codes
    )


def test_gauntlet_has_zero_irreversible_authority():
    value = build_all_products_premarket_snapshot(current_snapshot())
    assert value.mode == "OBSERVE"
    assert value.outbound_send_performed is False
    assert value.checkout_created is False
    assert value.payment_request_created is False
    assert value.funds_moved is False
    assert value.binding_terms_mutated is False
    assert value.live_meeting_join_performed is False
    assert value.revenue_recognized is False
    assert value.execution_authority == "none"


def test_duplicate_product_code_fails_closed():
    snapshot = current_snapshot()
    rows = list(snapshot["products"])
    rows.append(dict(rows[0]))
    with pytest.raises(ValueError, match="duplicate product codes"):
        build_all_products_premarket_snapshot({"products": rows})


def test_proposal_only_avatar_product_cannot_silently_appear_in_catalog():
    snapshot = current_snapshot()
    rows = list(snapshot["products"])
    injected = dict(rows[0])
    injected["product_code"] = "digital_avatar_copilot"
    rows.append(injected)
    with pytest.raises(
        ValueError,
        match="proposal-only Digital Avatar product already in catalog",
    ):
        build_all_products_premarket_snapshot({"products": rows})
