from datetime import datetime, timezone

from empire_os.intent_brain import assess_intent
from empire_os.intent_jev import adjudicate_intent


def test_job_seeker_is_rejected_not_buyer():
    row = {
        "source": "reddit",
        "title": "Where should I take my sales career?",
        "text": (
            "Need advice on what roles I should be going after. "
            "My goal is to land a sales job where I can earn six figures."
        ),
        "niche": "b2b",
        "url": "https://reddit.com/r/sales/example",
    }

    result = assess_intent(row)

    assert result["actor_type"] == "job_seeker"
    assert result["commercial_intent"] is False
    assert result["decision"] == "REJECT"
    assert "career_or_job_seeking" in result["negative_intent_classes"]
    assert result["execution_authority"] == "none"


def test_vendor_promotional_content_is_rejected():
    row = {
        "source": "linkedin",
        "title": "Stop losing leads to manual follow-up",
        "text": (
            "We help contractors automate their lead follow-up. "
            "Our platform qualifies leads automatically. "
            "Book a demo with our team."
        ),
        "niche": "b2b",
        "url": "https://linkedin.com/posts/example",
    }

    result = assess_intent(row)

    assert result["actor_type"] == "vendor"
    assert result["decision"] == "REJECT"
    assert "vendor_or_promotional_content" in (
        result["negative_intent_classes"]
    )


def test_real_roofing_owner_without_identity_routes_to_resolution():
    row = {
        "source": "reddit",
        "title": "Need a few more qualified roofing appointments",
        "text": (
            "I own a roofing company. We need 2-4 more qualified "
            "appointments per week. Google Ads have not been profitable "
            "and I am looking for a specialist who knows roofing."
        ),
        "niche": "roofing",
        "url": "https://reddit.com/r/roofing/example",
    }

    result = assess_intent(row)

    assert result["actor_type"] == "owner_operator"
    assert result["commercial_intent"] is True
    assert result["niche"] == "roofing"
    assert result["niche_path"] == ["home_services", "roofing"]
    assert "insufficient_qualified_demand" in result["pain_points"]
    assert "unprofitable_paid_acquisition" in result["pain_points"]
    assert result["decision"] == "RESOLVE_IDENTITY"


def test_first_party_candidate_still_requires_verification():
    row = {
        "source": "reddit",
        "title": "Need more roofing appointments",
        "text": (
            "I own a roofing company and need more qualified appointments "
            "because our Google Ads are not profitable."
        ),
        "niche": "roofing",
        "url": "https://reddit.com/r/roofing/example",
        "evidence_urls": ["https://example-roofing.com/"],
    }

    result = assess_intent(row)

    assert result["identity_state"] == "first_party_candidate"
    assert result["first_party_verified"] is False
    assert result["decision"] == "RESOLVE_IDENTITY"


def test_verified_roofing_owner_becomes_bounded_seed():
    row = {
        "source": "reddit",
        "title": "Need more roofing appointments",
        "text": (
            "I own a roofing company. We need 2-4 more qualified "
            "appointments per week. Google Ads are not profitable. "
            "I am actively looking for a specialist."
        ),
        "niche": "roofing",
        "url": "https://reddit.com/r/roofing/example",
        "evidence_urls": ["https://example-roofing.com/"],
        "first_party_verified": True,
    }

    result = assess_intent(row)
    jev = adjudicate_intent(result)

    assert result["decision"] == "BUYER_SCOUT_SEED"
    assert jev["recommendation"] == "BUYER_SCOUT_SEED"
    assert jev["buyer_intent_supported"] is True
    assert jev["first_party_identity_verified"] is True
    assert jev["execution_authority"] == "none"


def test_unknown_actor_cannot_become_seed():
    row = {
        "source": "reddit",
        "title": "Need more qualified appointments",
        "text": (
            "Need more qualified appointments. Google Ads are not profitable."
        ),
        "niche": "roofing",
        "evidence_urls": ["https://example-roofing.com/"],
        "first_party_verified": True,
    }

    result = assess_intent(row)
    jev = adjudicate_intent(result)

    assert result["actor_type"] == "unknown"
    assert result["decision"] != "BUYER_SCOUT_SEED"
    assert jev["recommendation"] != "BUYER_SCOUT_SEED"


def test_temporal_decay_reduces_stale_intent_confidence():
    row = {
        "source": "reddit",
        "title": "Need more roofing appointments",
        "text": (
            "I own a roofing company and need more qualified appointments."
        ),
        "niche": "roofing",
        "observed_at": "2026-01-01T00:00:00+00:00",
        "evidence_urls": ["https://example-roofing.com/"],
        "first_party_verified": True,
    }

    result = assess_intent(
        row,
        now=datetime(2026, 10, 4, tzinfo=timezone.utc),
    )

    assert result["temporal"]["freshness"] == "stale"
    assert result["confidence"]["intent"] < 0.50
    assert result["decision"] != "BUYER_SCOUT_SEED"


def test_repeated_signals_create_strengthening_state():
    row = {
        "source": "reddit",
        "title": "Need more roofing appointments",
        "text": (
            "I own a roofing business and need more qualified appointments."
        ),
        "niche": "roofing",
        "repeated_signal_count": 4,
    }

    result = assess_intent(row)

    assert result["intent_state"] == "strengthening"


def test_jev_never_grants_execution_authority():
    brain = {
        "schema_version": "empire.intent_brain.v1",
        "decision": "BUYER_SCOUT_SEED",
        "actor_type": "owner_operator",
        "commercial_intent": True,
        "niche": "roofing",
        "first_party_verified": True,
        "negative_intent_classes": [],
        "contradictions": [],
        "confidence": {
            "intent": 0.95,
            "actor": 0.95,
            "identity": 0.95,
            "evidence": 0.95,
        },
        "evidence": {
            "first_party_candidate_count": 1,
        },
    }

    result = adjudicate_intent(brain)

    assert result["recommendation"] == "BUYER_SCOUT_SEED"
    assert result["outreach_authorized"] is False
    assert result["database_write_performed"] is False
    assert result["payment_mutation"] is False
    assert result["actual_revenue"] is False
    assert result["execution_authority"] == "none"


def test_jev_cannot_upgrade_watch_to_seed():
    brain = {
        "schema_version": "empire.intent_brain.v1",
        "decision": "WATCH",
        "actor_type": "owner_operator",
        "commercial_intent": True,
        "niche": "roofing",
        "first_party_verified": True,
        "negative_intent_classes": [],
        "contradictions": [],
        "confidence": {
            "intent": 0.95,
            "actor": 0.95,
            "identity": 0.95,
            "evidence": 0.95,
        },
        "evidence": {
            "first_party_candidate_count": 1,
        },
    }

    result = adjudicate_intent(brain)

    assert result["recommendation"] == "WATCH"
    assert result["reason"] == "jev_cannot_upgrade_deterministic_brain"


def test_explicit_expert_procurement_routes_to_identity_resolution():
    row = {
        "source": "linkedin",
        "title": "Looking for a HubSpot CRM + Sales Automation Expert",
        "text": (
            "Looking for a HubSpot CRM and sales automation expert "
            "to help us improve our workflow."
        ),
        "url": "https://linkedin.com/posts/example-procurement",
    }

    result = assess_intent(row)
    jev = adjudicate_intent(result)

    assert result["signal_orientation"] == "buyer_procurement"
    assert result["commercial_intent"] is True
    assert result["decision"] == "RESOLVE_IDENTITY"
    assert jev["recommendation"] == "RESOLVE_IDENTITY"
    assert result["execution_authority"] == "none"


def test_freelance_specialist_search_is_procurement_not_job_seeker():
    row = {
        "source": "linkedin",
        "title": "Looking For : AI & Automation Specialist (Freelance)",
        "text": (
            "Looking for: AI & Automation Specialist (Freelance) "
            "to help with automating our internal workflows."
        ),
        "url": "https://linkedin.com/posts/example-freelance",
    }

    result = assess_intent(row)

    assert result["signal_orientation"] == "buyer_procurement"
    assert result["actor_type"] != "job_seeker"
    assert result["commercial_intent"] is True
    assert result["decision"] == "RESOLVE_IDENTITY"


def test_employee_hiring_post_stays_watch_not_buyer_seed():
    row = {
        "source": "linkedin",
        "title": "WE ARE HIRING – SALES EXECUTIVE | JAIPUR",
        "text": (
            "We are hiring a Sales Executive to join our team. "
            "Apply now."
        ),
        "url": "https://linkedin.com/posts/example-hiring",
    }

    result = assess_intent(row)

    assert result["signal_orientation"] == "employment_hiring"
    assert result["commercial_intent"] is False
    assert result["decision"] == "WATCH"


def test_case_study_promotion_is_rejected_as_buyer_intent():
    row = {
        "source": "linkedin",
        "title": "How we helped a consultancy do more business",
        "text": (
            "How we helped a consultancy do more business and attract "
            "better clients with automation."
        ),
        "url": "https://linkedin.com/posts/example-case-study",
    }

    result = assess_intent(row)

    assert result["signal_orientation"] == "seller_content"
    assert result["commercial_intent"] is False
    assert result["decision"] == "REJECT"


def test_stop_losing_leads_educational_content_not_promoted():
    row = {
        "source": "linkedin",
        "title": "Stop Losing Leads with Manual Follow-up",
        "text": (
            "Stop losing leads with manual follow-up. "
            "Here is how to fix your process."
        ),
        "url": "https://linkedin.com/posts/example-content",
    }

    result = assess_intent(row)

    assert result["signal_orientation"] == "seller_content"
    assert result["decision"] == "REJECT"


def test_anyone_looking_for_expert_is_seller_content_not_procurement():
    row = {
        "source": "linkedin",
        "title": "Anyone looking for expert B2B SEO & Growth help",
        "text": (
            "Anyone looking for expert B2B SEO & Growth help, "
            "message me to discuss how I can help."
        ),
        "url": "https://linkedin.com/posts/example-seller-offer",
    }

    result = assess_intent(row)

    assert result["signal_orientation"] == "seller_content"
    assert result["commercial_intent"] is False
    assert result["decision"] == "REJECT"
