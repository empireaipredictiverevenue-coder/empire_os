from empire_os.truth_quality_control import (
    ALLOWED_BUYER_TLDS,
    input_domain_decision,
    looks_like_public_domain,
    near_duplicate_score,
    normalize_domain,
    output_decision,
)


def test_domain_normalization():

    assert normalize_domain(
        "https://www.Example.COM/path"
    ) == "example.com"


def test_garbage_rejected():

    assert not looks_like_public_domain(
        "latest.json",
        allowed_tlds=
            ALLOWED_BUYER_TLDS,
    )

    assert not looks_like_public_domain(
        "revenue.erv",
        allowed_tlds=
            ALLOWED_BUYER_TLDS,
    )


def test_internal_identity_rejected():

    assert not looks_like_public_domain(
        "empire.buyer",
        allowed_tlds=
            ALLOWED_BUYER_TLDS,
    )


def test_near_duplicate_detection():

    score = near_duplicate_score(
        "positioncalls.com",
        "positoncalls.com",
    )

    assert score >= 0.90


def test_near_duplicate_fails_closed():

    result = input_domain_decision(
        "positioncalls.com",

        peers=[
            "positioncalls.com",
            "positoncalls.com",
        ],

        evidence_lines=[
            "publisher program",
            "pay per call",
        ],

        source_ids=[
            "source-a",
            "source-b",
        ],

        allowed_tlds=
            ALLOWED_BUYER_TLDS,
    )

    assert result.verdict == (
        "HOLD_FOR_VERIFICATION"
    )

    assert not result.action_allowed


def test_fuzzy_does_not_auto_merge():

    result = input_domain_decision(
        "positioncalls.com",

        peers=[
            "positoncalls.com",
        ],

        evidence_lines=[
            "publisher program",
            "pay per call",
        ],

        source_ids=[
            "source-a",
            "source-b",
        ],

        allowed_tlds=
            ALLOWED_BUYER_TLDS,
    )

    assert (
        result.canonical_identity
        == "positioncalls.com"
    )


def test_missing_evidence_fails_closed():

    result = input_domain_decision(
        "example.com",

        evidence_lines=[],

        source_ids=[],

        allowed_tlds=
            ALLOWED_BUYER_TLDS,
    )

    assert (
        result.verdict
        == "INSUFFICIENT_EVIDENCE"
    )


def test_ready_without_active_verification_blocked():

    result = output_decision(
        domain=
            "buyer.example.com",

        status=
            "READY_TO_APPROACH",

        evidence={
            "publisher_program":
                True,

            "active_demand":
                True,
        },

        active_verification=
            False,

        source_lineage_present=
            True,

        authority=
            "FOUNDER_REVIEW_ONLY",

        outbound_authority=
            False,
    )

    assert result.verdict == "CONFLICT"


def test_ready_without_buyer_role_blocked():

    result = output_decision(
        domain=
            "buyer.example.com",

        status=
            "READY_TO_APPROACH",

        evidence={
            "integration":
                True,

            "contactable":
                True,
        },

        active_verification=
            True,

        source_lineage_present=
            True,

        authority=
            "FOUNDER_REVIEW_ONLY",

        outbound_authority=
            False,
    )

    assert result.verdict == "CONFLICT"


def test_forecast_without_economics_blocked():

    result = output_decision(
        domain=
            "buyer.example.com",

        status=
            "VERIFY_REQUIREMENTS",

        evidence={
            "publisher_program":
                True,
        },

        active_verification=
            True,

        source_lineage_present=
            True,

        authority=
            "OBSERVE",

        outbound_authority=
            False,

        forecast=
            100000,
    )

    assert result.verdict in {
        "HOLD_FOR_VERIFICATION",
        "CONFLICT",
    }
