import pytest

from empire_os.search_intelligence.attribution import (
    preview_search_revenue_attribution,
)


def revenue_event(**overrides):
    row = {
        "id": "event-1",
        "event_type": "revenue_recognized",
        "actual_revenue": True,
        "fulfilment_order_id": "order-1",
        "amount_cents": 25000,
        "occurred_at": "2026-09-19T23:45:00+00:00",
    }
    row.update(overrides)
    return row


def test_actual_revenue_can_be_previewed_against_observed_page():
    preview = preview_search_revenue_attribution(
        site_id="site-1",
        page_id="page-1",
        query="predictive revenue platform",
        external_session_id="session-1",
        prospect_id="prospect-1",
        opportunity_id="opportunity-1",
        commercial_event=revenue_event(),
    )
    assert preview.revenue_cents == 25000
    assert preview.commercial_event_id == "event-1"
    assert preview.fulfilment_order_id == "order-1"
    assert preview.actual_revenue is True
    assert preview.write_authority == "none"


def test_non_revenue_event_is_rejected():
    with pytest.raises(ValueError, match="not recognized actual revenue"):
        preview_search_revenue_attribution(
            site_id="site-1",
            page_id="page-1",
            commercial_event=revenue_event(
                event_type="payment_verified",
                actual_revenue=False,
            ),
        )


def test_revenue_claim_without_actual_flag_is_rejected():
    with pytest.raises(ValueError, match="not recognized actual revenue"):
        preview_search_revenue_attribution(
            site_id="site-1",
            page_id="page-1",
            commercial_event=revenue_event(actual_revenue=False),
        )


def test_attribution_requires_search_touch_evidence():
    with pytest.raises(ValueError, match="observed page, query, or session"):
        preview_search_revenue_attribution(
            site_id="site-1",
            commercial_event=revenue_event(),
        )


def test_missing_revenue_identity_fails_closed():
    with pytest.raises(ValueError, match="identity is incomplete"):
        preview_search_revenue_attribution(
            site_id="site-1",
            page_id="page-1",
            commercial_event=revenue_event(id=""),
        )
