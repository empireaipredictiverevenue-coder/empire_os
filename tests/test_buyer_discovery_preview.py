from scripts.buyer_discovery_preview import (
    filter_market_rows,
    load_rows,
)


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



def test_load_rows_projects_only_accepted_acquisition_site():
    prospect_id = "11111111-1111-4111-8111-111111111111"

    class FakeRepository:
        def prospects(self):
            return [{
                "id": prospect_id,
                "business_name": "All Star Roofing",
                "niche": "roofing",
                "metro": "Austin, TX",
                "website": None,
            }]

        def active_entity_links(self):
            return [{
                "prospect_id": prospect_id,
                "entity_id": "22222222-2222-4222-8222-222222222222",
                "match_score": 1.0,
                "active": True,
            }]

        def acquisitions(self):
            return [{
                "prospect_id": prospect_id,
                "created_at": "2026-09-17T09:40:11Z",
                "evidence": {
                    "quality": {
                        "accepted": True,
                        "confidence": 100,
                        "source_role": "identity_or_direct",
                    },
                    "raw": {
                        "business_website": "https://www.allstarroofingtexas.com/"
                    },
                },
            }]

    loaded = load_rows(repository=FakeRepository())
    assert len(loaded) == 1
    assert loaded[0]["entity_id"] == "22222222-2222-4222-8222-222222222222"
    assert loaded[0]["_acquisition_evidence"]["quality"]["accepted"] is True
