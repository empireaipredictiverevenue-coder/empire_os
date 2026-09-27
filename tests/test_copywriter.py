import pytest

from empire_os.copywriter import CopyBrief, build_copy


def brief(channel="landing_hero", **kwargs):
    return CopyBrief(
        channel=channel,
        objective="generate qualified commercial interest",
        product_code="managed_service",
        product_name="Predictive Revenue Intelligence",
        audience="revenue leaders",
        business_name=kwargs.pop("business_name", "Acme Roofing"),
        niche=kwargs.pop("niche", "roofing"),
        metro=kwargs.pop("metro", "Dallas"),
        evidence=kwargs.pop(
            "evidence",
            {"rating": 4.8, "review_count": 114},
        ),
        expansion_offer=kwargs.pop(
            "expansion_offer",
            "Revenue Pulse monitoring",
        ),
        **kwargs,
    )


def test_cold_email_requires_real_evidence():
    draft = build_copy(brief("cold_email"))
    assert "4.8★ across 114 public reviews" in draft.body
    assert draft.evidence_used == ("public_profile_rating_reviews",)
    assert draft.requires_human_review is False


def test_cold_email_fails_without_observed_evidence():
    with pytest.raises(ValueError, match="observed trigger"):
        build_copy(brief("cold_email", evidence={}))


def test_mrr_expansion_has_explicit_upsell_path():
    draft = build_copy(brief("mrr_expansion"))
    assert "Revenue Pulse monitoring" in draft.headline
    assert "extends the same evidence trail" in draft.body


def test_mrr_expansion_requires_named_offer():
    with pytest.raises(ValueError, match="expansion_offer"):
        build_copy(brief("mrr_expansion", expansion_offer=""))


def test_vsl_is_outline_and_requires_review():
    draft = build_copy(brief("vsl_outline"))
    assert "signal → decision → governed execution" in draft.body
    assert draft.requires_human_review is True


def test_unsupported_channel_fails_closed():
    with pytest.raises(ValueError, match="unsupported copy channel"):
        build_copy(brief("made_up_channel"))


def test_cold_email_uses_short_subject_variants():
    draft = build_copy(brief(
        "cold_email",
        contact_title="CEO",
        sender_email="phil@empire-ai.co.uk",
        brand_domain="empire-ai.co.uk",
        enterprise_target=True,
    ))
    assert draft.subject is not None
    assert len(draft.subject) <= 40
    assert 1 <= len(draft.subject_variants) <= 4
    assert draft.quality_review["c_suite"] is True
    assert draft.sender_identity["brand_aligned"] is True
    assert draft.requires_human_review is False


def test_enterprise_consumer_sender_requires_review():
    draft = build_copy(brief(
        "cold_email",
        contact_title="Chief Revenue Officer",
        sender_email="flavag83@gmail.com",
        brand_domain="empire-ai.co.uk",
        enterprise_target=True,
    ))
    assert draft.requires_human_review is True
    assert "consumer_mailbox_for_enterprise_target" in (
        draft.sender_identity["blockers"]
    )
