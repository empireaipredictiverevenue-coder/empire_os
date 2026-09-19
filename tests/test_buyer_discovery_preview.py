from scripts.buyer_discovery_preview import filter_market_rows


def rows():
    return [
        {"id": "a", "niche": "roofing", "metro": "Austin, TX"},
        {"id": "b", "niche": "commercial roofing", "metro": "austin, tx"},
        {"id": "c", "niche": "roofing", "metro": "Dallas, TX"},
        {"id": "d", "niche": "plumbing", "metro": "Austin, TX"},
    ]


def test_filter_market_rows_uses_canonical_niche_family_and_metro():
    selected = filter_market_rows(
        rows(),
        niche="roofing",
        metro="Austin, TX",
    )
    assert [row["id"] for row in selected] == ["a", "b"]


def test_filter_market_rows_allows_single_dimension_or_unscoped():
    assert [row["id"] for row in filter_market_rows(
        rows(),
        metro="Austin, TX",
    )] == ["a", "b", "d"]
    assert [row["id"] for row in filter_market_rows(rows())] == [
        "a", "b", "c", "d",
    ]
