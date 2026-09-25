from empire_os.outreach_message_optimizer import (
    build_subject_variants,
    optimise_first_touch,
    review_message,
    review_sender_identity,
)


def test_enterprise_consumer_mailbox_is_blocked_for_review():
    result = review_sender_identity(
        "Phil Livesley <flavag83@gmail.com>",
        brand_domain="empire-ai.co.uk",
        enterprise_target=True,
    )
    assert result["consumer_mailbox"] is True
    assert result["brand_aligned"] is False
    assert "consumer_mailbox_for_enterprise_target" in result["blockers"]
    assert "sender_not_brand_aligned" in result["blockers"]
    assert result["ready_for_enterprise_send_review"] is False
    assert result["send_enabled"] is False


def test_branded_workspace_mailbox_passes_identity_review():
    result = review_sender_identity(
        "Phil Livesley <phil@empire-ai.co.uk>",
        brand_domain="empire-ai.co.uk",
        enterprise_target=True,
    )
    assert result["consumer_mailbox"] is False
    assert result["brand_aligned"] is True
    assert result["blockers"] == []
    assert result["ready_for_enterprise_send_review"] is True


def test_subject_variants_are_short_and_never_fake_threaded():
    rows = build_subject_variants(
        business_name="Redwood Services",
        reason_now="Observed capacity is shifting across partner companies.",
        territory="US",
    )
    assert len(rows) >= 3
    assert rows[0]["score"] >= rows[-1]["score"]
    assert all(not row["subject"].lower().startswith(("re:", "fwd:")) for row in rows)
    assert all(row["word_count"] <= 4 for row in rows)


def test_c_suite_first_touch_is_brief_peer_level_and_evidence_led():
    result = optimise_first_touch(
        business_name="Redwood Services",
        reason_now="Redwood operates across multiple home-services partner companies",
        proof="the group publishes operating and growth updates across the portfolio",
        contact_title="CEO",
        territory="US",
        sender_email="phil@empire-ai.co.uk",
        brand_domain="empire-ai.co.uk",
        enterprise_target=True,
    )
    assert result["quality"]["c_suite"] is True
    assert result["quality"]["word_count"] <= 75
    assert "predictive revenue intelligence os" not in result["body"].lower()
    assert result["body"].count("?") == 1
    assert "Redwood Services" in result["body"]
    assert result["invented_claims"] is False
    assert result["sender_identity"]["ready_for_enterprise_send_review"] is True
    assert result["send_enabled"] is False


def test_quality_review_flags_vendorish_long_copy():
    body = (
        "I wanted to reach out because our Predictive Revenue Intelligence OS "
        "is a best-in-class game-changing platform that can leverage synergy "
        "across your entire organization. "
    ) * 6
    result = review_message(
        subject="A very long promotional enterprise revenue intelligence subject line",
        body=body,
        cta="Would you like a call?",
        contact_title="Chief Revenue Officer",
    )
    assert result["score"] < 70
    assert "vendor_or_ai_sounding_language" in result["issues"]
    assert "body_too_long_for_audience" in result["issues"]
