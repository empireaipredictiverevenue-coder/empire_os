from empire_os.entity_type_detection import (
    classify,
    syntactic_domain,
)


def test_modern_tlds_are_structurally_valid():

    assert syntactic_domain(
        "apinjury.law"
    )

    assert syntactic_domain(
        "capdata.tech"
    )

    assert syntactic_domain(
        "procycles.ch"
    )

    assert syntactic_domain(
        "gs.com.au"
    )


def test_files_rejected():

    result = classify(
        "2026-09-23.md",
        resolve_dns=False,
    )

    assert result.entity_type == (
        "FILE_OR_PATH"
    )

    assert not result.lane_allowed


def test_internal_tokens_rejected():

    result = classify(
        "empire.buyer",
        resolve_dns=False,
    )

    assert result.entity_type == (
        "INTERNAL_TOKEN"
    )


def test_known_non_target_rejected():

    result = classify(
        "semrush.com",
        resolve_dns=False,
    )

    assert result.entity_type == (
        "KNOWN_NON_TARGET"
    )


def test_direct_site_proof_wins():

    result = classify(
        "example.law",
        direct_site_success=True,
        resolve_dns=False,
    )

    assert result.entity_type == (
        "PUBLIC_DOMAIN"
    )

    assert result.lane_allowed


def test_person_like_without_proof_is_held():

    result = classify(
        "john.smith",
        resolve_dns=False,
    )

    assert result.entity_type == (
        "PERSON_LIKE_OR_UNKNOWN"
    )

    assert not result.lane_allowed


def test_unknown_domain_is_held_not_destroyed():

    result = classify(
        "possiblebuyer.tech",
        resolve_dns=False,
    )

    assert result.entity_type in {
        "PERSON_LIKE_OR_UNKNOWN",
        "DOMAIN_UNVERIFIED",
    }

    assert result.quarantine
