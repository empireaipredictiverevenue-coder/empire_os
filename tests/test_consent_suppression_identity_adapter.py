# EMPIRE_WAVE_090C_B3
from empire_os.consent_suppression_identity_adapter import (
    discover_direct_identities,
    strong_join_columns,
)


def test_opaque_column_email_is_detected():

    found = discover_direct_identities(
        {
            "suppression_value":
                "person@example.com",
        }
    )

    assert any(
        x.entity_type == "EMAIL"
        for x in found
    )


def test_numeric_id_is_not_phone():

    found = discover_direct_identities(
        {
            "lead_id":
                "123456789",
        }
    )

    assert not any(
        x.entity_type == "PHONE"
        for x in found
    )


def test_named_phone_is_detected():

    found = discover_direct_identities(
        {
            "recipient_phone":
                "+44 7700 900123",
        }
    )

    assert any(
        x.entity_type == "PHONE"
        for x in found
    )


def test_semantic_lead_join():

    pairs = strong_join_columns(
        {
            "lead_id",
            "reason",
        },
        {
            "id",
            "email",
        },
    )

    assert (
        "lead_id",
        "id",
        "SEMANTIC_LEAD_ID",
    ) in pairs
