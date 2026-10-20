"""Authenticated tenant CRM handoff tests. Fixtures never access production."""
from dataclasses import replace
from datetime import datetime, timezone
import json
import pytest

from empire_os.campaign_intelligence import (
    AccountIntelligenceContext, TrustedAccountRoute, TrustedBuyingMember,
    TrustedJourneyProjection, CampaignIntelligenceHeld,
    review_authenticated_crm_campaign_handoff,
)
from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository
from scripts.review_tam_full_funnel_strategy_20261020 import (
    review_authenticated_campaign_intelligence,
)

NOW = datetime(2026, 10, 20, 11, tzinfo=timezone.utc)
TENANT = "11223344-2233-4433-8833-223344556677"
PROSPECT = "11223344-2233-4433-8833-223344556688"
ACCOUNT = "a" * 32
EMP_TENANT = "tenant_empireai"
CAMPAIGN = "campaign_" + "a" * 24


def crm_row(**changes):
    return {
        "tenant_id": TENANT, "prospect_id": PROSPECT,
        "prospect_status": "research", "niche": "solar",
        "company_name": "SENSITIVE_COMPANY_FICTIONAL_FIXTURE",
        **changes,
    }


def mock_handoff(monkeypatch, rows=None, *, tenant=TENANT):
    repo = PostgresRevenueCrmRepository(
        "offline_fixture_dsn_not_used", tenant_id=TENANT,
        connect_factory=lambda value: None,
    )
    bound_rows = [crm_row()] if rows is None else rows
    monkeypatch.setattr(repo, "prospects", lambda *, limit: bound_rows)
    return AuthenticatedRevenueCrmRead(tenant_id=tenant, repository=repo)


def owner_projection(row):
    ctx = AccountIntelligenceContext(
        tenant_ref=EMP_TENANT, account_key=ACCOUNT,
        market_scope="GB:solar:buyers", campaign_id=CAMPAIGN,
        canonical_account_verified=True, suppression_clear=True,
        inbound_response_basis_verified=True,
        marketing_contact_basis_verified=True,
        offer_evidence_current=True,
    )
    person = TrustedBuyingMember(
        person_key="b"*32, account_key=ACCOUNT, tenant_ref=EMP_TENANT,
        decision_role="economic_buyer", observed_at=NOW,
        canonical_person_link_verified=True,
        contact_route_verified=True, source_provenance_verified=True,
    )
    route = TrustedAccountRoute(
        context=ctx, buying_members=(person,),
        warm_introductions=(), contact_history=(),
        contact_history_complete=True, market_and_buyer_fit_verified=True,
        offer_fulfilment_verified=True,
        marketing_channel_lawfulness_verified=True,
    )
    return TrustedJourneyProjection(
        account_route=route, crm_row=row,
        canonical_account_to_crm_binding_verified=True,
        crm_snapshot_observed_at=NOW, channel_receipts=(),
    )


def empty_verified_signals(_):
    return ()


def review(handoff, **changes):
    return review_authenticated_crm_campaign_handoff(
        handoff, account_projection_owner=owner_projection,
        signal_owner=empty_verified_signals, now=NOW, **changes,
    )


def test_existing_tenant_authenticated_postgres_crm_read_to_adaptive_owning_sales():
    from pytest import MonkeyPatch
    with MonkeyPatch.context() as patch:
        handoff = mock_handoff(patch)
        result = review(handoff)
    assert result["authenticated_tenant_source_verified"] is True
    assert result["canonical_crm_rows_read"] == 1
    assert result["bound_account_journeys_reviewed"] == 1
    assert result["human_next_play_counts"] == {"HOLD_CHANNEL_EVIDENCE": 1}
    assert result["canonical_account_join_unavailable"] == 0
    assert result["sender_enabled"] is False
    assert result["canonical_crm_contacts_returned"] == 0
    text = json.dumps(result)
    assert "SENSITIVE_COMPANY_FICTIONAL_FIXTURE" not in text
    assert PROSPECT not in text
    assert ACCOUNT not in text


def test_missing_canonical_account_join_is_not_invented(monkeypatch):
    handoff = mock_handoff(monkeypatch)
    result = review_authenticated_crm_campaign_handoff(
        handoff, account_projection_owner=lambda _: None,
        signal_owner=empty_verified_signals, now=NOW,
    )
    assert result["canonical_crm_rows_read"] == 1
    assert result["canonical_account_join_unavailable"] == 1
    assert result["bound_account_journeys_reviewed"] == 0
    assert result["human_next_play_counts"] == {}
    assert result["sender_enabled"] is False


def test_existing_full_funnel_accepts_authenticated_owner_handoff(monkeypatch):
    handoff = mock_handoff(monkeypatch)
    result = review_authenticated_campaign_intelligence(
        now=NOW, authenticated_crm_owner_read=handoff,
        account_projection_owner=owner_projection,
        signal_owner=empty_verified_signals,
    )
    assert result["authenticated_tenant_crm_handoff"]["canonical_crm_rows_read"] == 1
    assert result["adaptive_buyer_journeys"] is None
    assert result["database_writes"] is False


def test_without_authenticated_owner_no_crm_access_or_fake_zero():
    result = review_authenticated_campaign_intelligence(now=NOW)
    assert result["authenticated_tenant_crm_handoff"] is None
    with pytest.raises(ValueError, match="authenticated tenant owner"):
        review_authenticated_campaign_intelligence(
            now=NOW, account_projection_owner=owner_projection,
        )


def test_cross_tenant_authentication_or_record_is_rejected(monkeypatch):
    handoff = mock_handoff(monkeypatch, tenant="11223344-2233-4433-8833-223344556699")
    with pytest.raises(CampaignIntelligenceHeld, match="TENANT_MISMATCH"):
        review(handoff)
    handoff = mock_handoff(monkeypatch, rows=[crm_row(
        tenant_id="11223344-2233-4433-8833-223344556699"
    )])
    with pytest.raises(CampaignIntelligenceHeld, match="CROSS_TENANT"):
        review(handoff)


def test_duplicate_prospect_id_cannot_count_as_twice_revenue(monkeypatch):
    handoff = mock_handoff(monkeypatch, rows=[crm_row(), crm_row()])
    with pytest.raises(CampaignIntelligenceHeld, match="DUPLICATE"):
        review(handoff)


def test_credentialless_synthetic_repository_object_is_not_accepted():
    with pytest.raises(CampaignIntelligenceHeld, match="OWNER_BOUNDARY_REQUIRED"):
        review_authenticated_crm_campaign_handoff(
            object(), account_projection_owner=owner_projection,
            signal_owner=empty_verified_signals, now=NOW,
        )


def test_forged_join_and_fabricated_crm_state_are_rejected(monkeypatch):
    handoff = mock_handoff(monkeypatch)
    def forged(row):
        val = owner_projection(row)
        return replace(val, crm_row={**row, "prospect_status": "engaged"})
    with pytest.raises(CampaignIntelligenceHeld, match="FORGED"):
        review_authenticated_crm_campaign_handoff(
            handoff, account_projection_owner=forged,
            signal_owner=empty_verified_signals, now=NOW,
        )
    def unknown_binding(row):
        return replace(
            owner_projection(row),
            canonical_account_to_crm_binding_verified=False,
        )
    with pytest.raises(CampaignIntelligenceHeld, match="FORGED"):
        review_authenticated_crm_campaign_handoff(
            handoff, account_projection_owner=unknown_binding,
            signal_owner=empty_verified_signals, now=NOW,
        )


def test_db_failure_is_masked_without_leaking_private_credentials(monkeypatch):
    handoff = mock_handoff(monkeypatch)
    def fail(*, limit):
        raise RuntimeError("secret fake DSN or company")
    monkeypatch.setattr(handoff.repository, "prospects", fail)
    with pytest.raises(CampaignIntelligenceHeld, match="AUTHENTICATED_CRM_READ_UNAVAILABLE") as error:
        review(handoff)
    assert "secret" not in str(error.value)
    assert "company" not in str(error.value)


def test_owner_receipts_must_be_typed_and_bounded(monkeypatch):
    handoff = mock_handoff(monkeypatch)
    with pytest.raises(CampaignIntelligenceHeld, match="SIGNAL_OWNER_UNAVAILABLE"):
        review_authenticated_crm_campaign_handoff(
            handoff, account_projection_owner=owner_projection,
            signal_owner=lambda _: {"fake": "event"},
            now=NOW,
        )
    with pytest.raises(CampaignIntelligenceHeld, match="OWNER_BOUNDARY_REQUIRED"):
        review(handoff, limit=501)


def test_source_rows_limit_and_partial_page_signaled(monkeypatch):
    handoff = mock_handoff(monkeypatch)
    result = review(handoff, limit=1)
    assert result["read_result_may_be_partial"] is True
    assert result["mode"] == "OBSERVE"


def test_no_live_send_authority_from_tenant_crm_reader(monkeypatch):
    handoff = mock_handoff(monkeypatch)
    result = review(handoff)
    assert result["marketing_subscription_inferred"] is False
    assert result["crm_mutation"] is False
    assert result["sender_enabled"] is False
    assert result["execution_authority"] == "NONE"
