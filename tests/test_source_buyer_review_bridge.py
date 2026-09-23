from empire_os.source_buyer_review_bridge import (
    fetch_hot_source_prospect_ids,
)


P1 = "00000000-0000-0000-0000-000000000001"
P2 = "00000000-0000-0000-0000-000000000002"
P3 = "00000000-0000-0000-0000-000000000003"


def test_hot_source_selector_requires_hot_scored_and_verified_website():
    calls = []

    def request(method, path, payload=None, prefer=None):
        calls.append(path)
        if path.startswith("/rest/v1/prospect_acquisitions?"):
            return [
                {"prospect_id": P1},
                {"prospect_id": P2},
                {"prospect_id": P3},
            ]
        if path.startswith("/rest/v1/prospect_qualifications?"):
            return [
                {
                    "prospect_id": P2,
                    "score": 93.0,
                    "tier": "hot",
                    "status": "scored",
                },
                {
                    "prospect_id": P1,
                    "score": 90.0,
                    "tier": "hot",
                    "status": "scored",
                },
            ]
        if path.startswith("/rest/v1/prospects?"):
            return [
                {"id": P1, "niche": "solar", "website": "https://one.example"},
                {"id": P2, "niche": "solar", "website": None},
            ]
        raise AssertionError(path)

    ids = fetch_hot_source_prospect_ids(
        source="recc_solar",
        niche="solar",
        request=request,
    )

    assert ids == [P1]
    assert len(calls) == 3


def test_hot_source_selector_returns_empty_without_acquisition_rows():
    def request(method, path, payload=None, prefer=None):
        return []

    assert fetch_hot_source_prospect_ids(
        source="recc_solar",
        niche="solar",
        request=request,
    ) == []
