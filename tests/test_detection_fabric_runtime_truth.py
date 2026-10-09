from empire_os.detection_fabric import (
    lane_risk,
)


def test_controlled_requires_all_runtime_verified():

    statuses = (
        "VERIFIED_RUNTIME",
    ) * 11

    assert lane_risk(
        "ACTIVE_RUNTIME",
        statuses,
    ) == "CONTROLLED"


def test_source_only_active_runtime_not_controlled():

    statuses = (
        "SOURCE_EVIDENCE_ONLY",
    ) * 11

    assert lane_risk(
        "ACTIVE_RUNTIME",
        statuses,
    ) == "HIGH"


def test_source_present_not_controlled():

    statuses = (
        "SOURCE_EVIDENCE_ONLY",
    ) * 11

    assert lane_risk(
        "SOURCE_PRESENT",
        statuses,
    ) == "HIGH"


def test_one_unverified_control_is_low_not_controlled():

    statuses = (
        ("VERIFIED_RUNTIME",) * 10
        + ("SOURCE_EVIDENCE_ONLY",)
    )

    assert lane_risk(
        "ACTIVE_RUNTIME",
        statuses,
    ) == "LOW"


def test_missing_and_source_only_both_count_as_unverified():

    statuses = (
        ("VERIFIED_RUNTIME",) * 3
        + ("SOURCE_EVIDENCE_ONLY",) * 4
        + ("MISSING_OR_UNVERIFIED",) * 4
    )

    assert lane_risk(
        "ACTIVE_RUNTIME",
        statuses,
    ) == "HIGH"
