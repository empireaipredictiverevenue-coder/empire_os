from types import SimpleNamespace

import pytest

from empire_os.prospect_ingest import (
    ProspectIngestError,
    acquisition_fingerprint,
    prepare_candidate,
)


def test_prepare_candidate_preserves_source_url_not_website():
    candidate = {
        "name": "Acme Roofing LLC",
        "phone": "(512) 555-0101",
        "niche": "Roofing",
        "metro": "Austin",
        "source": "permits_nyc",
        "url": (
            "https://example.gov/permit?id=123#details"
        ),
        "details": "Permit 123",
        "lead_score": 72,
    }

    result = prepare_candidate(candidate)

    prospect = result["prospect"]
    evidence = result["evidence"]

    assert prospect["business_name"] == "Acme Roofing LLC"
    assert prospect["niche"] == "roofing"
    assert prospect["metro"] == "austin"

    # Critical safety rule: source/reference URLs are not websites.
    assert "website" not in prospect

    assert evidence["source_url"] == (
        "https://example.gov/permit?id=123"
    )


def test_prepare_candidate_accepts_leadcandidate_like_object():
    candidate = SimpleNamespace(
        name="Example Plumbing",
        email="hello@example.test",
        phone="1-404-555-0112",
        niche="Plumbing",
        metro="Atlanta",
        state="GA",
        details="Public permit record",
        source="permits",
        lead_score=65,
        url="https://example.gov/jobs/77",
        raw={"job": "77"},
    )

    result = prepare_candidate(candidate)

    assert result["prospect"]["business_name"] == (
        "Example Plumbing"
    )
    assert result["prospect"]["niche"] == "plumbing"
    assert result["prospect"]["metro"] == "atlanta"
    assert result["evidence"]["email"] == (
        "hello@example.test"
    )
    assert result["evidence"]["raw"] == {"job": "77"}


def test_fingerprint_normalizes_phone_and_text():
    a = acquisition_fingerprint(
        source=" Permits ",
        source_url="https://example.gov/job/1",
        business_name="Acme Roofing",
        metro="Austin",
        phone="+1 (512) 555-0101",
    )

    b = acquisition_fingerprint(
        source="permits",
        source_url="https://example.gov/job/1",
        business_name="ACME ROOFING",
        metro="austin",
        phone="5125550101",
    )

    assert a == b


def test_fingerprint_changes_with_source_record():
    a = acquisition_fingerprint(
        source="permits",
        source_url="https://example.gov/job/1",
        business_name="Acme Roofing",
        metro="Austin",
        phone="5125550101",
    )

    b = acquisition_fingerprint(
        source="permits",
        source_url="https://example.gov/job/2",
        business_name="Acme Roofing",
        metro="Austin",
        phone="5125550101",
    )

    assert a != b


@pytest.mark.parametrize(
    "candidate,error",
    [
        (
            {
                "niche": "roofing",
                "metro": "austin",
            },
            "candidate missing business name",
        ),
        (
            {
                "name": "Acme",
                "metro": "austin",
            },
            "candidate missing niche",
        ),
        (
            {
                "name": "Acme",
                "niche": "roofing",
            },
            "candidate missing metro",
        ),
    ],
)
def test_missing_identity_fields_fail_closed(
    candidate,
    error,
):
    with pytest.raises(
        ProspectIngestError,
        match=error,
    ):
        prepare_candidate(candidate)


def test_lead_score_is_bounded():
    high = prepare_candidate(
        {
            "name": "A",
            "niche": "roofing",
            "metro": "austin",
            "lead_score": 999,
        }
    )

    low = prepare_candidate(
        {
            "name": "B",
            "niche": "roofing",
            "metro": "austin",
            "lead_score": -50,
        }
    )

    assert high["prospect"]["buy_signal_score"] == 100
    assert low["prospect"]["buy_signal_score"] == 0


def test_invalid_source_url_is_not_promoted():
    result = prepare_candidate(
        {
            "name": "Acme",
            "niche": "roofing",
            "metro": "austin",
            "url": "not-a-url",
        }
    )

    assert result["evidence"]["source_url"] == ""
    assert "website" not in result["prospect"]


def test_preparation_has_no_database_dependency():
    result = prepare_candidate(
        {
            "name": "Offline Candidate",
            "niche": "hvac",
            "metro": "tampa",
        }
    )

    assert result["prospect"]["business_name"] == (
        "Offline Candidate"
    )
    assert len(result["ingest_key"]) == 64


def test_dedupe_matches_exact_normalized_phone():
    prepared = prepare_candidate(
        {
            "name": "Acme Roofing",
            "phone": "+1 (512) 555-0101",
            "niche": "roofing",
            "metro": "austin",
        }
    )

    from empire_os.prospect_ingest import (
        match_existing_prospect,
    )

    result = match_existing_prospect(
        prepared,
        [
            {
                "id": "existing-1",
                "business_name": "Different Display Name",
                "phone": "5125550101",
                "metro": "Austin",
            }
        ],
    )

    assert result["decision"] == "matched"
    assert result["reason"] == "exact_phone"
    assert result["prospect"]["id"] == "existing-1"


def test_dedupe_multiple_phone_matches_fail_closed():
    prepared = prepare_candidate(
        {
            "name": "Acme Roofing",
            "phone": "5125550101",
            "niche": "roofing",
            "metro": "austin",
        }
    )

    from empire_os.prospect_ingest import (
        match_existing_prospect,
    )

    result = match_existing_prospect(
        prepared,
        [
            {
                "id": "one",
                "phone": "(512) 555-0101",
            },
            {
                "id": "two",
                "phone": "1-512-555-0101",
            },
        ],
    )

    assert result == {
        "decision": "ambiguous",
        "reason": "multiple_exact_phone_matches",
        "prospect": None,
    }


def test_dedupe_matches_exact_name_and_metro_without_phone():
    prepared = prepare_candidate(
        {
            "name": "Acme Roofing LLC",
            "niche": "roofing",
            "metro": "Austin",
        }
    )

    from empire_os.prospect_ingest import (
        match_existing_prospect,
    )

    result = match_existing_prospect(
        prepared,
        [
            {
                "id": "existing-2",
                "business_name": "  ACME ROOFING LLC ",
                "metro": "austin",
                "phone": "",
            }
        ],
    )

    assert result["decision"] == "matched"
    assert result["reason"] == "exact_name_metro"
    assert result["prospect"]["id"] == "existing-2"


def test_dedupe_name_metro_collision_is_ambiguous():
    prepared = prepare_candidate(
        {
            "name": "ABC Services",
            "niche": "roofing",
            "metro": "tampa",
        }
    )

    from empire_os.prospect_ingest import (
        match_existing_prospect,
    )

    result = match_existing_prospect(
        prepared,
        [
            {
                "id": "one",
                "business_name": "ABC Services",
                "metro": "Tampa",
            },
            {
                "id": "two",
                "business_name": "abc services",
                "metro": "tampa",
            },
        ],
    )

    assert result["decision"] == "ambiguous"
    assert result["prospect"] is None


def test_dedupe_never_matches_on_niche_and_metro_only():
    prepared = prepare_candidate(
        {
            "name": "Brand New Roofing Co",
            "niche": "roofing",
            "metro": "austin",
        }
    )

    from empire_os.prospect_ingest import (
        match_existing_prospect,
    )

    result = match_existing_prospect(
        prepared,
        [
            {
                "id": "existing-3",
                "business_name": "Other Roofing Co",
                "niche": "roofing",
                "metro": "austin",
            }
        ],
    )

    assert result == {
        "decision": "new",
        "reason": "no_strong_identity_match",
        "prospect": None,
    }


def test_readonly_lookup_paginates_and_matches_phone():
    from empire_os.prospect_ingest import (
        lookup_existing_prospect,
    )

    prepared = prepare_candidate(
        {
            "name": "Acme Roofing",
            "phone": "5125550101",
            "niche": "roofing",
            "metro": "austin",
        }
    )

    calls = []

    def reader(path, params):
        calls.append((path, dict(params)))

        if params["offset"] == "0":
            return [
                {
                    "id": "other",
                    "business_name": "Other Co",
                    "phone": "5551112222",
                    "metro": "austin",
                },
                {
                    "id": "target",
                    "business_name": "Acme Roofing",
                    "phone": "(512) 555-0101",
                    "metro": "Austin",
                },
            ]

        return []

    result = lookup_existing_prospect(
        prepared,
        reader,
        page_size=2,
        max_pages=3,
    )

    assert result["decision"] == "matched"
    assert result["reason"] == "exact_phone"
    assert result["prospect"]["id"] == "target"
    assert result["rows_scanned"] == 2
    assert result["pages_scanned"] == 2
    assert [call[1]["offset"] for call in calls] == [
        "0",
        "2",
    ]


def test_readonly_lookup_returns_new_after_complete_scan():
    from empire_os.prospect_ingest import (
        lookup_existing_prospect,
    )

    prepared = prepare_candidate(
        {
            "name": "Brand New Co",
            "niche": "hvac",
            "metro": "tampa",
        }
    )

    def reader(path, params):
        return [
            {
                "id": "different",
                "business_name": "Different Co",
                "metro": "tampa",
                "phone": "",
            }
        ]

    result = lookup_existing_prospect(
        prepared,
        reader,
        page_size=100,
        max_pages=2,
    )

    assert result["decision"] == "new"
    assert result["reason"] == "no_strong_identity_match"
    assert result["rows_scanned"] == 1


def test_readonly_lookup_fails_closed_when_truncated():
    from empire_os.prospect_ingest import (
        lookup_existing_prospect,
    )

    prepared = prepare_candidate(
        {
            "name": "Acme",
            "niche": "roofing",
            "metro": "large-metro",
        }
    )

    def reader(path, params):
        return [
            {
                "id": (
                    f"row-{params['offset']}-1"
                ),
                "business_name": "Other One",
                "metro": "large-metro",
            },
            {
                "id": (
                    f"row-{params['offset']}-2"
                ),
                "business_name": "Other Two",
                "metro": "large-metro",
            },
        ]

    result = lookup_existing_prospect(
        prepared,
        reader,
        page_size=2,
        max_pages=2,
    )

    assert result == {
        "decision": "ambiguous",
        "reason": "prospect_lookup_truncated",
        "prospect": None,
        "rows_scanned": 4,
        "pages_scanned": 2,
    }


def test_readonly_lookup_rejects_invalid_response():
    from empire_os.prospect_ingest import (
        lookup_existing_prospect,
    )

    prepared = prepare_candidate(
        {
            "name": "Acme",
            "niche": "roofing",
            "metro": "austin",
        }
    )

    with pytest.raises(
        ProspectIngestError,
        match="prospect lookup returned invalid response",
    ):
        lookup_existing_prospect(
            prepared,
            lambda path, params: {"bad": "shape"},
        )
