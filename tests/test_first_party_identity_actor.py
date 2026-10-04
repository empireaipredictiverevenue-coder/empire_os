from empire_os.first_party_identity_actor import (
    run_first_party_identity_actor,
)
from empire_os.revenue_actor_registry import (
    actor_catalog,
)


def base_payload():
    return {
        "upstream_decision": "RESOLVE_IDENTITY",
        "signal_id": "sig-procurement-1",
        "business_name": "Example Roofing",
        "website": "https://example-roofing.com/",
        "first_party_site_verified": True,
        "metro": "Phoenixville, PA",
        "niche": "roofing",
    }


def test_actor_catalog_contains_identity_actor():
    keys = {
        row["actor_key"]
        for row in actor_catalog()
    }

    assert "intent_brain" in keys
    assert "first_party_identity" in keys


def test_actor_rejects_unqualified_upstream_state():
    payload = base_payload()
    payload["upstream_decision"] = "WATCH"

    result = run_first_party_identity_actor(payload)

    assert result["decision"] == "NOT_ELIGIBLE"
    assert result["recommended_next_action"] == "none"
    assert (
        result["governance"]["execution_authority"]
        == "none"
    )


def test_missing_business_name_fails_closed():
    payload = base_payload()
    payload["business_name"] = ""

    result = run_first_party_identity_actor(payload)

    assert result["decision"] == "NEEDS_BUSINESS_IDENTITY"
    assert (
        result["recommended_next_action"]
        == "resolve_business_identity"
    )


def test_missing_website_fails_closed():
    payload = base_payload()
    payload["website"] = ""

    result = run_first_party_identity_actor(payload)

    assert result["decision"] == "NEEDS_BUSINESS_IDENTITY"
    assert (
        result["recommended_next_action"]
        == "resolve_business_first_party_site"
    )


def test_unverified_business_site_never_calls_recovery():
    payload = base_payload()
    payload["first_party_site_verified"] = False

    called = False

    def recovery(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("must not run")

    result = run_first_party_identity_actor(
        payload,
        recovery_fn=recovery,
    )

    assert called is False
    assert result["decision"] == "VERIFY_BUSINESS_SITE"


def test_verified_first_party_decision_maker_is_accepted():
    payload = base_payload()

    def recovery(**kwargs):
        return {
            "recovered": True,
            "identity": {
                "name": "Wade Example",
                "title": "Owner",
                "source":
                    "empire_first_party_people_probe",
                "source_url":
                    "https://example-roofing.com/about/",
                "confidence": 0.91,
                "first_party": True,
            },
            "sources_tried": [
                "first_party_site_probe",
            ],
            "evidence": [],
        }

    result = run_first_party_identity_actor(
        payload,
        recovery_fn=recovery,
    )

    assert result["decision"] == "IDENTITY_VERIFIED"
    assert (
        result["recommended_next_action"]
        == "merge_verified_identity_and_reassess_intent"
    )

    person = result["output"]["decision_maker"]

    assert person["name"] == "Wade Example"
    assert person["title"] == "Owner"
    assert person["first_party"] is True
    assert person["confidence"] == 0.91

    assert result["governance"] == {
        "outreach_authorized": False,
        "database_write_performed": False,
        "canonical_promotion_performed": False,
        "payment_mutation": False,
        "content_posted": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def test_low_confidence_identity_cannot_verify():
    payload = base_payload()

    def recovery(**kwargs):
        return {
            "recovered": True,
            "identity": {
                "name": "Possible Person",
                "title": "Owner",
                "source":
                    "empire_first_party_people_probe",
                "source_url":
                    "https://example-roofing.com/team/",
                "confidence": 0.61,
                "first_party": True,
            },
            "sources_tried": [
                "first_party_site_probe",
            ],
            "evidence": [],
        }

    result = run_first_party_identity_actor(
        payload,
        recovery_fn=recovery,
    )

    assert result["decision"] == "NEEDS_REVIEW"
    assert (
        result["output"]["identity_verified"]
        is False
    )


def test_non_first_party_person_cannot_verify():
    payload = base_payload()

    def recovery(**kwargs):
        return {
            "recovered": True,
            "identity": {
                "name": "Directory Person",
                "title": "Owner",
                "source": "third_party_directory",
                "source_url":
                    "https://directory.example/person",
                "confidence": 0.95,
                "first_party": False,
            },
            "sources_tried": ["empire_serp"],
            "evidence": [],
        }

    result = run_first_party_identity_actor(
        payload,
        recovery_fn=recovery,
    )

    assert result["decision"] == "NEEDS_REVIEW"
    assert (
        result["output"]["identity_verified"]
        is False
    )


def test_unresolved_recovery_holds():
    payload = base_payload()

    def recovery(**kwargs):
        return {
            "recovered": False,
            "identity": None,
            "sources_tried": [
                "first_party_site_probe",
            ],
            "evidence": [],
        }

    result = run_first_party_identity_actor(
        payload,
        recovery_fn=recovery,
    )

    assert result["decision"] == "IDENTITY_UNRESOLVED"
    assert (
        result["recommended_next_action"]
        == "hold_for_more_identity_evidence"
    )
