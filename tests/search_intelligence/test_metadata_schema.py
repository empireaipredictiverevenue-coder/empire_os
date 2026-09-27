from empire_os.search_intelligence.metadata import generate_metadata
from empire_os.search_intelligence.models import QualityResult, SearchPage
from empire_os.search_intelligence.schema import generate_schema_preview


def test_metadata_defaults_noindex_without_quality_approval():
    page = SearchPage(
        url="https://empire-ai.co.uk/guide",
        title="Guide",
        canonical_url="https://empire-ai.co.uk/guide",
    )
    result = generate_metadata(page)
    assert result.robots == "noindex,follow"
    assert result.title == "Guide"


def test_schema_blocks_unverified_reviews():
    result = generate_schema_preview("Product", {
        "name": "Empire Predictive Cloud",
        "aggregateRating": {"ratingValue": "5"},
        "review": [{"author": "Fake"}],
    })
    assert "name" in result.json_ld
    assert "aggregateRating" not in result.json_ld
    assert "review" not in result.json_ld
    assert result.warnings


def test_schema_blocks_nested_unverified_rating_fields():
    result = generate_schema_preview("Product", {
        "name": "Empire Predictive Cloud",
        "offers": {
            "price": "99",
            "aggregateRating": {"ratingValue": "5"},
        },
    })
    assert result.json_ld["offers"]["price"] == "99"
    assert "aggregateRating" not in result.json_ld["offers"]
    assert any("aggregateRating" in warning for warning in result.warnings)
