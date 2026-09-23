from empire_os.source_qualification_bridge import fetch_pending_source_prospects


def test_fetch_pending_source_prospects_filters_scored_and_preserves_source_order():
    calls = []

    def request(method, path, payload=None, prefer=None):
        calls.append((method, path))
        if path.startswith("/rest/v1/prospect_acquisitions?"):
            return [
                {"prospect_id": "00000000-0000-0000-0000-000000000001", "source": "recc_solar"},
                {"prospect_id": "00000000-0000-0000-0000-000000000002", "source": "recc_solar"},
                {"prospect_id": "00000000-0000-0000-0000-000000000003", "source": "recc_solar"},
            ]
        if path.startswith("/rest/v1/prospect_qualifications?"):
            return [
                {"prospect_id": "00000000-0000-0000-0000-000000000002"},
            ]
        if path.startswith("/rest/v1/prospects?"):
            return [
                {
                    "id": "00000000-0000-0000-0000-000000000003",
                    "business_name": "Third Solar",
                    "niche": "solar",
                },
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "business_name": "First Solar",
                    "niche": "solar",
                },
            ]
        raise AssertionError(path)

    rows = fetch_pending_source_prospects(
        source="recc_solar",
        niche="solar",
        limit=5,
        request=request,
    )

    assert [row["business_name"] for row in rows] == [
        "First Solar",
        "Third Solar",
    ]
    assert len(calls) == 3


def test_fetch_pending_source_prospects_returns_empty_when_source_has_no_rows():
    def request(method, path, payload=None, prefer=None):
        assert path.startswith("/rest/v1/prospect_acquisitions?")
        return []

    assert fetch_pending_source_prospects(
        source="recc_solar",
        niche="solar",
        request=request,
    ) == []
