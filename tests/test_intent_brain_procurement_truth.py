from empire_os.intent_brain import assess_intent
from empire_os.intent_jev import adjudicate_intent


def classify(title, text):
    result = assess_intent({
        "source": "linkedin",
        "title": title,
        "text": text,
        "url": "https://linkedin.com/posts/observed",
    })
    return result, adjudicate_intent(result)


def test_seo_project_is_direct_procurement():
    result, jev = classify(
        "I'm looking for an SEO expert",
        (
            "I'm looking for an SEO expert to help with a small "
            "one-time project optimizing my new therapy website."
        ),
    )

    assert result["signal_orientation"] == "buyer_procurement"
    assert result["decision"] == "RESOLVE_IDENTITY"
    assert jev["recommendation"] == "RESOLVE_IDENTITY"


def test_seo_agency_search_is_direct_procurement():
    result, _ = classify(
        "Looking for an SEO Team / Agency",
        (
            "We're looking for an experienced SEO team with "
            "proven expertise in Technical SEO and Content Strategy."
        ),
    )

    assert result["signal_orientation"] == "buyer_procurement"
    assert result["decision"] == "RESOLVE_IDENTITY"


def test_n8n_freelancer_is_direct_procurement():
    result, _ = classify(
        "Looking for a freelancer to develop sales and marketing automation",
        (
            "Looking for a freelancer to develop sales and marketing "
            "automation using n8n and AI workflows for a SMB SaaS solution."
        ),
    )

    assert result["signal_orientation"] == "buyer_procurement"
    assert result["decision"] == "RESOLVE_IDENTITY"


def test_fractional_cmo_role_is_hiring_signal():
    result, _ = classify(
        "Fractional CMO / Head of Marketing",
        (
            "We're building a marketing operation focused on U.S. law "
            "firms and looking for someone who can help us build and lead it."
        ),
    )

    assert result["signal_orientation"] == "employment_hiring"
    assert result["commercial_intent"] is False
    assert result["decision"] == "WATCH"


def test_commission_sales_role_is_hiring_signal():
    result, _ = classify(
        "Looking for a Sales Specialist on a commission-based model",
        (
            "Looking for a Sales Specialist on a commission-based model. "
            "The role involves finding B2B SaaS projects and new clients."
        ),
    )

    assert result["signal_orientation"] == "employment_hiring"
    assert result["commercial_intent"] is False
    assert result["decision"] == "WATCH"


def test_third_party_help_him_is_not_direct_procurement():
    result, _ = classify(
        "Looking for seo specialist who can help him",
        "Looking for seo specialist who can help him.",
    )

    assert result["signal_orientation"] == "third_party_referral"
    assert result["commercial_intent"] is False
    assert result["decision"] == "WATCH"


def test_manual_followup_thought_leadership_is_seller_content():
    result, _ = classify(
        "Losing Leads Due to Manual Follow-up",
        (
            "That's the difference between: Manual follow-up Smart "
            "automation. The businesses winning right now aren't "
            "working harder. They're responding faster."
        ),
    )

    assert result["signal_orientation"] == "seller_content"
    assert result["commercial_intent"] is False
    assert result["decision"] == "REJECT"


def test_procurement_never_becomes_seed_without_identity():
    result, jev = classify(
        "Looking for a HubSpot CRM + Sales Automation Expert",
        (
            "I'm looking to connect with a HubSpot expert who has "
            "solid experience in CRM setup and sales automation."
        ),
    )

    assert result["decision"] == "RESOLVE_IDENTITY"
    assert jev["recommendation"] == "RESOLVE_IDENTITY"
    assert result["execution_authority"] == "none"
    assert jev["execution_authority"] == "none"


def test_bracketed_hiring_sales_partner_is_not_procurement():
    result, jev = classify(
        "[HIRING] Client Acquisition / Sales Partner for Video Editing Agency — Remote",
        (
            "[HIRING] Client Acquisition / Sales Partner for "
            "Video Editing Agency — Remote. We are looking for "
            "someone to acquire clients and support sales."
        ),
    )

    assert result["signal_orientation"] == "employment_hiring"
    assert result["commercial_intent"] is False
    assert result["decision"] == "WATCH"
    assert jev["recommendation"] == "WATCH"
