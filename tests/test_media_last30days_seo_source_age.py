from datetime import datetime,timedelta,timezone

import pytest

from empire_os.media_last30days_seo_review import (
    _source_publication_age, build_seo_owner_review,
)
from test_media_last30days_seo_review import handoff, NOW


@pytest.mark.parametrize("days,band,in_window", [
    (0,"RECENT_0_TO_7_DAYS",True),
    (7,"RECENT_0_TO_7_DAYS",True),
    (8,"ACTIVE_8_TO_21_DAYS",True),
    (21,"ACTIVE_8_TO_21_DAYS",True),
    (22,"EXPIRING_22_TO_30_DAYS",True),
    (30,"EXPIRING_22_TO_30_DAYS",True),
    (31,"OUTSIDE_LAST30DAYS_SCOPE_HOLD",False),
])
def test_source_date_age_bands_days_utc(days,band,in_window):
    date=(NOW-timedelta(days=days)).date().isoformat()
    age,actual,inside=_source_publication_age(date,now=NOW)
    assert (age,actual,inside)==(days,band,in_window)


@pytest.mark.parametrize("invalid",[
    None,"","yesterday","2026-17-77","2026-10-26T10:10:00",
    "999999999999999999999999999999999999999999999999999"
])
def test_unknown_or_invalid_publication_dates_do_not_count_as_fresh(invalid):
    age,band,eligible=_source_publication_age(invalid,now=NOW)
    assert age is None and band=="UNVERIFIED_SOURCE_DATE" and eligible is False


def test_future_dates_are_held_not_called_new_research():
    age,band,eligible=_source_publication_age("2026-11-02T00:00:00Z",now=NOW)
    assert (age,band,eligible)==(-6,"FUTURE_SOURCE_DATE_HOLD",False)


def test_existing_owner_handoff_keeps_expired_citation_for_audit_but_holds_from_fresh_queue():
    data=handoff()
    data["topics"][0]["observations"][0]["published_at"]=(NOW-timedelta(days=32)).isoformat()
    out=build_seo_owner_review(data,now=NOW)
    assert out["review_first_unique_citation_count"]==1
    assert out["source_age_review"]["active_in_last30_days_title_matches"]==0
    assert out["source_age_review"]["held_outside_window_or_invalid_date"]==1
    assert out["source_age_review"]["source_age_bands"]["OUTSIDE_LAST30DAYS_SCOPE_HOLD"]==1
    row=out["topics"][0]["references_for_manual_review"][0]
    assert row["source_age_band"]=="OUTSIDE_LAST30DAYS_SCOPE_HOLD"
    assert row["inside_30_day_discovery_window"] is False
    assert row["publication_date_independently_verified"] is False
    assert out["publication_authorized"] is False


def test_valid_age_is_approximate_metadata_never_independent_verification():
    out=build_seo_owner_review(handoff(),now=NOW)
    r=out["topics"][0]["references_for_manual_review"][0]
    assert r["source_publication_age_days_from_unverified_metadata"]==0
    assert r["source_age_band"]=="RECENT_0_TO_7_DAYS"
    assert r["inside_30_day_discovery_window"] is True
    assert r["publication_date_independently_verified"] is False
    assert out["gsc_queries_or_impressions_observed"] is False


def test_new_age_projection_must_refresh_legacy_same_source_snapshot(tmp_path):
    from empire_os.media_last30days_seo_review import refresh_seo_owner_review, OUTPUT, PROJECTION_REVISION
    from test_media_last30days_seo_review import handoff
    import json
    d=handoff()
    file=tmp_path/OUTPUT
    file.parent.mkdir(parents=True)
    previous=build_seo_owner_review(d,now=NOW)
    previous.pop("projection_revision")
    previous.pop("source_age_review")
    for topic in previous["topics"]:
        for row in topic["references_for_manual_review"]:
            for key in ("source_publication_age_days_from_unverified_metadata", "source_age_band", "inside_30_day_discovery_window", "publication_date_independently_verified", "source_must_be_checked_by_owner"):
                row.pop(key,None)
    file.write_text(json.dumps(previous),encoding="utf-8")
    file.chmod(0o600)
    refresh_seo_owner_review(tmp_path,d,now=NOW)
    got=json.loads(file.read_text())
    assert got["projection_revision"]==PROJECTION_REVISION
    assert got["topics"][0]["references_for_manual_review"][0]["source_age_band"]=="RECENT_0_TO_7_DAYS"
    assert got["source_age_review"]["active_in_last30_days_title_matches"]==1
