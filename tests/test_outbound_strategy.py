from empire_os.outbound_strategy import build_contact_channel_plan


def test_verified_person_email_is_primary_and_company_phone_stays_separate():
    plan = build_contact_channel_plan(
        {"outreach_ready": True, "preferred_email": "frank@example.com"},
        channel_evidence=[
            {"channel": "voice", "value": "+12815551212", "verified": True,
             "person_bound": False, "source": "official_business_phone"},
        ],
    )
    assert plan["primary"]["channel"] == "email"
    assert plan["company_fallbacks"][0]["channel"] == "voice"
    assert plan["write_authorized"] is False


def test_sms_requires_verified_person_bound_mobile_and_valid_e164():
    plan = build_contact_channel_plan(
        {"outreach_ready": False},
        channel_evidence=[
            {"channel": "sms", "value": "+447700900123", "verified": True,
             "person_bound": True, "source": "first_party_mobile"},
            {"channel": "sms", "value": "+447700900124", "verified": True,
             "person_bound": False, "source": "company_directory"},
        ],
    )
    assert plan["primary"]["channel"] == "sms"
    assert any(x["reason"] == "person_binding_required" for x in plan["blocked"])


def test_unverified_paths_are_never_promoted():
    plan = build_contact_channel_plan(
        {"outreach_ready": False, "preferred_email": "guess@example.com"},
        channel_evidence=[
            {"channel": "voice", "value": "020 1234 5678", "verified": True,
             "person_bound": True, "source": "scrape"},
            {"channel": "a2a", "value": "agent://buyer", "verified": False,
             "person_bound": True, "source": "guess"},
        ],
    )
    assert plan["primary"] is None
    assert len(plan["blocked"]) == 2
