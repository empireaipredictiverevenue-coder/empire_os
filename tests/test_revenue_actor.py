import pytest

from empire_os.intent_brain_actor import run_intent_brain_actor
from empire_os.revenue_actor import (
    ActorDescriptor,
    build_actor_envelope,
    validate_actor_envelope,
)
from empire_os.revenue_actor_registry import (
    actor_catalog,
    run_registered_actor,
)


def roofing_owner(first_party_verified=False):
    return {
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
        "first_party_verified": first_party_verified,
    }


def test_actor_catalog_contains_intent_brain():
    rows = actor_catalog()

    by_key = {
        row["actor_key"]: row
        for row in rows
    }

    # The registry is intentionally composable now.
    # Intent Brain must remain present, but it is no longer
    # valid to assert that it is the only Revenue Actor.
    assert "intent_brain" in by_key
    assert (
        by_key["intent_brain"]["actor_version"]
        == "1.0.0"
    )


def test_intent_actor_is_replayable_for_same_input():
    payload = roofing_owner(False)

    one = run_intent_brain_actor(payload)
    two = run_intent_brain_actor(payload)

    assert one["run"]["run_id"] == two["run"]["run_id"]
    assert (
        one["run"]["input_fingerprint"]
        == two["run"]["input_fingerprint"]
    )


def test_actor_routes_unverified_identity_to_resolution():
    result = run_intent_brain_actor(roofing_owner(False))

    assert result["decision"] == "RESOLVE_IDENTITY"
    assert (
        result["recommended_next_action"]
        == "resolve_first_party_identity"
    )
    assert (
        result["output"]["commercial_state"]["niche"]
        == "roofing"
    )


def test_verified_buyer_can_become_bounded_scout_seed():
    result = run_intent_brain_actor(roofing_owner(True))

    assert result["decision"] == "BUYER_SCOUT_SEED"
    assert (
        result["recommended_next_action"]
        == "submit_bounded_buyer_scout_seed"
    )
    assert result["governance"]["execution_authority"] == "none"
    assert result["governance"]["outreach_authorized"] is False


def test_job_seeker_actor_is_rejected():
    result = run_registered_actor(
        "intent_brain",
        {
            "source": "reddit",
            "title": "Where should I take my sales career?",
            "text": (
                "Need advice about what roles I should go after. "
                "I want to land a sales job."
            ),
            "url": "https://reddit.com/r/sales/example",
        },
    )

    assert result["decision"] == "REJECT"
    assert result["recommended_next_action"] == "none"


def test_actor_envelope_contains_governed_contract():
    result = run_intent_brain_actor(roofing_owner(False))

    assert result["schema_version"] == "empire.revenue_actor.v1"
    assert result["truth_class"] == "mixed"
    assert result["evidence_refs"]

    assert "decision" in result
    assert "confidence" in result
    assert "blockers" in result
    assert "supports" in result
    assert "output" in result
    assert "observability" in result

    assert result["governance"] == {
        "outreach_authorized": False,
        "database_write_performed": False,
        "canonical_promotion_performed": False,
        "payment_mutation": False,
        "content_posted": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def test_actor_contract_rejects_authority_expansion():
    descriptor = ActorDescriptor(
        actor_key="bad_actor",
        actor_version="1",
        purpose="test",
        input_schema="test.in",
        output_schema="test.out",
        policy_version="test.policy",
    )

    with pytest.raises(
        ValueError,
        match="cannot grant execution authority",
    ):
        build_actor_envelope(
            descriptor=descriptor,
            actor_input={},
            decision="SEND",
            recommended_next_action="send",
            output={},
            execution_authority="send",
        )


def test_validation_fails_closed_on_outreach_authority():
    result = run_intent_brain_actor(roofing_owner(False))
    result["governance"]["outreach_authorized"] = True

    with pytest.raises(
        ValueError,
        match="governance violation",
    ):
        validate_actor_envelope(result)


def test_registry_unknown_actor_fails_closed():
    with pytest.raises(KeyError):
        run_registered_actor("unknown_actor", {})
