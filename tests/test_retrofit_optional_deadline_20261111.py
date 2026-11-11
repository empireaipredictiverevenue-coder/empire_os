"""Owner-scoped regression: optional official deadline is not event provenance."""
from datetime import date, datetime, timezone
import pytest
from empire_os.data_exchange_procurement_context import OGL_V3
from empire_os.retrofit_official_tenders import review_official_retrofit_tender_sample

NOW=datetime(2026,11,11,0,20,tzinfo=timezone.utc)
DAY=date(2026,11,10)


def package(deadline):
    return {
        "license": OGL_V3, "publisher": {"name": "Cabinet Office"},
        "releases": [{
            "id": "106870-2026", "ocid": "ocds-h6vhtk-07b8fd",
            "date": "2026-11-10T16:42:17Z", "tag": ["tender"],
            "tender": {"title": "Heat pump retrofit installation",
                       "status": "active", "tenderPeriod": {"endDate": deadline}},
            "parties": [{"roles": ["buyer"], "name": "Example Council"}],
        }],
    }


def review(payload):
    return review_official_retrofit_tender_sample(
        start_date=DAY, end_date=DAY, limit=20, observed_at=NOW,
        fetch_json=lambda _: payload)


def test_unzoned_optional_deadline_is_held_not_whole_real_notice():
    result=review(package("2026-12-03T15:00:00"))
    assert result["sample_count"] == 1
    notice=result["notices"][0]
    assert notice["retrofit_title_relevance_review_needed"] is True
    assert notice["deadline_as_published"] is None
    assert notice["deadline_format_unverified"] is True
    assert notice["deadline_verified"] is False
    assert notice["supplier_bid_eligible"] is False
    assert notice["buyer_of_empire_services_verified"] is False
    assert result["outbound_enabled"] is False


def test_valid_zoned_published_deadline_preserved_not_verified():
    notice=review(package("2026-12-03T15:00:00Z"))["notices"][0]
    assert notice["deadline_as_published"]=="2026-12-03T15:00:00+00:00"
    assert notice["deadline_format_unverified"] is False
    assert notice["deadline_verified"] is False


def test_invalid_official_event_timestamp_still_fails_closed():
    payload=package("2026-12-03T15:00:00")
    payload["releases"][0]["date"]="2026-11-10T16:42:17"
    with pytest.raises(ValueError,match="timezone"):
        review(payload)


def test_wrong_publisher_still_fails_closed():
    payload=package("2026-12-03T15:00:00")
    payload["publisher"]["name"]="Not Cabinet Office"
    with pytest.raises(ValueError,match="publisher"):
        review(payload)
