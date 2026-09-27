import pytest

from empire_os.lead_compat import (
    CanonicalLeadConflict,
    CanonicalLeadIntakeError,
    canonical_lead_intake,
    normalize_lead_payload,
)


def test_normalize_preserves_compatibility_evidence():
    payload = normalize_lead_payload({
        "lead_id": "ppl-42",
        "name": "Acme Ltd",
        "niche": "roofing",
        "metro": "London",
        "source": "ppl-9210",
        "email": "owner@example.com",
        "phone": "+44 20 0000 0000",
        "zip": "SW1A 1AA",
        "intent": "emergency_water_removal",
        "consent": "explicit_form_submit",
        "metadata": {"campaign": "storm"},
        "ip_address": "203.0.113.10",
        "user_agent": "test-agent",
    })

    assert payload["name"] == "Acme Ltd"
    assert payload["source"] == "ppl-9210"
    assert payload["raw"]["external_lead_id"] == "ppl-42"
    assert payload["raw"]["zip"] == "SW1A 1AA"
    assert payload["raw"]["intent"] == "emergency_water_removal"
    assert payload["raw"]["consent"] == "explicit_form_submit"
    assert payload["raw"]["metadata"] == {"campaign": "storm"}
    assert payload["raw"]["ip_address"] == "203.0.113.10"


def test_canonical_intake_returns_compatibility_response():
    seen = {}

    def ingestor(candidate):
        seen.update(candidate)
        return {
            "decision": "new",
            "prospect": {"id": "prospect-1"},
        }

    result = canonical_lead_intake(
        {
            "name": "Acme Ltd",
            "niche": "roofing",
            "metro": "London",
        },
        ingestor,
    )

    assert seen["name"] == "Acme Ltd"
    assert result == {
        "ok": True,
        "decision": "new",
        "prospect_id": "prospect-1",
        "niche": "roofing",
        "metro": "London",
        "status": "canonical_owned",
    }


def test_missing_required_identity_fails_before_ingestor():
    called = False

    def ingestor(candidate):
        nonlocal called
        called = True
        return {}

    with pytest.raises(
        CanonicalLeadIntakeError,
        match="name, niche and metro required",
    ):
        canonical_lead_intake(
            {"name": "Acme", "niche": "roofing"},
            ingestor,
        )

    assert called is False


def test_ambiguous_identity_becomes_conflict():
    def ingestor(candidate):
        return {
            "decision": "ambiguous",
            "prospect": None,
        }

    with pytest.raises(CanonicalLeadConflict):
        canonical_lead_intake(
            {
                "name": "Acme",
                "niche": "roofing",
                "metro": "London",
            },
            ingestor,
        )


def test_ingestor_exception_is_sanitized():
    def ingestor(candidate):
        raise RuntimeError("backend detail with secret")

    with pytest.raises(
        CanonicalLeadIntakeError,
        match="canonical prospect ingest unavailable",
    ) as raised:
        canonical_lead_intake(
            {
                "name": "Acme",
                "niche": "roofing",
                "metro": "London",
            },
            ingestor,
        )

    assert "backend detail" not in str(raised.value)
