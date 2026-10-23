"""Existing canonical CRM reader to PRIME, no secondary tenant or deal authority."""
from decimal import Decimal

import pytest

from empire_os.predictive_revenue_prime_crm import (
    PrimeCrmReadUnavailable, review_authenticated_crm_prospects,
)
from empire_os.revenue_crm_transport import (
    PostgresRevenueCrmRepository, RevenueCrmTransportError,
)

TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"
P1 = "00000000-0000-0000-0000-000000000011"
P2 = "00000000-0000-0000-0000-000000000012"


def repository(rows, *, tenant=TENANT):
    repo = PostgresRevenueCrmRepository(
        "postgresql://not-used.invalid", tenant_id=tenant,
        connect_factory=lambda _: (_ for _ in ()).throw(
            AssertionError("do not access real db"),
        ),
    )
    repo.prospects = lambda *, limit: list(rows)
    return repo


def row(prospect_id=P1, **updates):
    result = {
        "tenant_id": TENANT,
        "prospect_id": prospect_id,
        "business_name": "private-business-name",
        "conversation_id": "convo-1",
        "conversation_state": "engaged",
        "closer_case_id": "case-1",
        "closer_state": "proposal_ready",
        "price_cents": Decimal("500000"),
        "deal_probability": Decimal("0.9"),
    }
    result.update(updates)
    return result


def test_authenticated_reader_aggregates_only_and_cannot_pretend_revenue():
    result = review_authenticated_crm_prospects(
        repository=repository([row(), row(P2, closer_state="awaiting_payment")]),
        tenant_id=TENANT,
    )
    assert result["returned_prospect_rows"] == 2
    assert result["engaged_conversation_rows"] == 2
    assert result["proposal_ready_rows"] == 1
    assert result["awaiting_payment_rows"] == 1
    assert result["priced_closer_rows"] == 2
    assert result["probability_field_present_rows"] == 2
    assert result["source_exhaustive"] is False
    assert result["modelled_pipeline_forecast_cents"] is None
    assert result["recognized_revenue_cents"] is None
    assert result["prospects_are_not_verified_deals"] is True
    assert result["execution_authority"] == "none"
    assert "private-business-name" not in str(result)
    assert P1 not in str(result)


def test_genuine_reader_zero_is_only_a_bounded_empty_read():
    result = review_authenticated_crm_prospects(
        repository=repository([]), tenant_id=TENANT,
    )
    assert result["returned_prospect_rows"] == 0
    assert result["source_exhaustive"] is False
    assert result["recognized_revenue_cents"] is None


def test_wrong_tenant_rejected_before_repository_access():
    with pytest.raises(PrimeCrmReadUnavailable, match="tenant mismatch"):
        review_authenticated_crm_prospects(
            repository=repository([row()]), tenant_id=OTHER,
        )


@pytest.mark.parametrize("rows", [
    [row(tenant_id=OTHER)],
    [row(), row()],
    [row(prospect_id="not-uuid")],
    [row(price_cents=-1)],
    [row(price_cents="1000")],
    [row(deal_probability=float("nan"))],
    [row(deal_probability=1.5)],
])
def test_bad_source_cannot_be_promoted(rows):
    with pytest.raises(PrimeCrmReadUnavailable):
        review_authenticated_crm_prospects(
            repository=repository(rows), tenant_id=TENANT,
        )


def test_reader_failure_has_sanitized_error():
    repo = repository([])
    repo.prospects = lambda *, limit: (_ for _ in ()).throw(
        RevenueCrmTransportError("fake-password-SECRET"),
    )
    with pytest.raises(PrimeCrmReadUnavailable, match="canonical CRM read unavailable") as exc:
        review_authenticated_crm_prospects(repository=repo, tenant_id=TENANT)
    assert "SECRET" not in str(exc.value)


def test_no_ungrounded_reader_accepted():
    with pytest.raises(PrimeCrmReadUnavailable):
        review_authenticated_crm_prospects(
            repository=object(), tenant_id=TENANT,
        )


def test_crm_reader_is_composed_into_original_brain_without_forged_deals():
    from datetime import datetime, timezone
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    result = build_predictive_revenue_brain_review(
        tenant_id=TENANT,
        as_of=datetime(2026, 10, 23, tzinfo=timezone.utc),
        authenticated_crm_repository=repository([row()]),
    )
    crm = result["authenticated_crm_prospect_review"]
    assert crm["source_status"] == "AUTHENTICATED_TENANT_CRM_VIEW_READ"
    assert crm["returned_prospect_rows"] == 1
    assert result["source_freshness"]["crm_source"] == "AUTHENTICATED_TENANT_CRM_VIEW_NOT_DEALS"
    assert result["crm_pipeline"]["source_rows"] == 0
    assert result["recognized_revenue_cents"] is None
    assert result["execution_authority"] == "none"


def test_authenticated_prospects_cannot_be_mixed_with_untrusted_deals():
    from datetime import datetime, timezone
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    with pytest.raises(ValueError, match="mix CRM prospect"):
        build_predictive_revenue_brain_review(
            tenant_id=TENANT,
            as_of=datetime(2026, 10, 23, tzinfo=timezone.utc),
            authenticated_crm_repository=repository([row()]),
            crm_deals=[{"tenant_id": TENANT}],
        )
