from empire_os.legacy_permit_recovery import (
    build_recovery_observer,
    parse_legacy_lane_notes,
)


def _row(name: str):
    return {
        "id": 1,
        "lane_id": "lane-1",
        "prospect_id": "prospect-project-only",
        "status": "pending",
        "omega_score": 70,
        "omega_tier": "silver",
        "notes": (
            f"name={name} email= phone=(917) 785-5031 "
            "metro=NYC state=NY details=A2.PL permit 400723954 "
            "issued 2026-08-16: . BBL 4000000001. "
            "Address: 1 TEST STREET, Queens"
        ),
        "created_at": "2026-08-18T00:00:00+00:00",
        "buyer_id": None,
        "niche": "plumbing",
        "metro": "NYC",
    }


def test_same_is_not_a_real_owner_identity():
    parsed = parse_legacy_lane_notes(_row("SAME")["notes"])

    assert parsed["identity_recoverable"] is False
    assert parsed["opportunity_recoverable"] is True
    assert parsed["legacy_name_role"] == "property_owner"


def test_current_placeholder_owner_is_preserved_as_project_only():
    payload = build_recovery_observer(
        [_row("N.A")],
        nyc_validation={
            "400723954": {
                "validation_state": "VERIFIED_CURRENT",
                "validation_reason": "current_public_source_match",
                "source_system": "nyc_dob_permits",
                "source_freshness": "SOURCE_REVALIDATED_CURRENT",
                "source_owner_names": ["N.A"],
            }
        },
    )

    record = payload["records"][0]
    assert record["identity_recoverable"] is False
    assert record["opportunity_recoverable"] is True
    assert record["inventory_identity_mode"] == "PROJECT_ONLY"
    assert record["current_identity_match_state"] == "NOT_ELIGIBLE"
    assert record["recovery_classification"] == "REUSE"
    assert record["recovery_state"] == "VERIFIED_CURRENT_PROJECT_ONLY"
    assert record["canonical_prospect_id"] is None
    assert record["canonical_promotion_performed"] is False
    assert record["commercial_ready"] is False
