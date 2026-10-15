"""V16 historical proof quality: synthetic, never production observation writes."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest

from empire_os.data_exchange_construction import build_construction_preview
from empire_os.data_exchange_observation_custody import (
    CustodyIntegrityError, plan_custody_append,
)
from empire_os.data_exchange_temporal_quality import (
    PILOT_IDS, SOURCE_SCOPE, build_temporal_quality,
)

NOW = datetime(2026, 10, 15, 8, 0, tzinfo=timezone.utc)


def snap(when, *, ids=None, status="non-permissioned"):
    ids = sorted(PILOT_IDS if ids is None else ids)
    return build_construction_preview([{
        "record_id": ident, "source_id":"gb_planning_data",
        "dataset_id":"brownfield-land", "region":"north_west_england",
        "record_type":"brownfield_land",
        "source_url":f"https://www.planning.data.gov.uk/entity/{ident}",
        "source_observed_at":when.isoformat(),
        "planning_permission_status":status,
        "site_area_hectares":"0.1",
        "source_entry_date":"2024-11-29",
    } for ident in ids], observed_at=when)


def custody(*pairs):
    previous=None
    rows=[]
    for when, status in pairs:
        item=snap(when,status=status)
        row=plan_custody_append(item,previous=previous,assessed_at=NOW)["row"]
        rows.append(row)
        previous=row
    return rows


def test_one_real_genesis_stays_held_not_a_fake_signal():
    rows=custody((NOW-timedelta(hours=1),"non-permissioned"))
    report=build_temporal_quality(rows,assessed_at=NOW)
    assert report["status"]=="HOLD_REVIEW_REQUIRED"
    assert "SECOND_CANONICAL_OBSERVATION_REQUIRED" in report["holds"]
    assert report["v14_board_status"]=="HOLD_NEED_TWO_CANONICAL_OBSERVATIONS"
    assert report["observed_source_field_changes"]==0
    assert report["pilot_entity_count"]==3
    assert report["pilot_entity_scope"]==SOURCE_SCOPE
    assert report["regional_market_coverage_percent"] is None
    assert report["customer_delivery_enabled"] is False
    assert report["external_anchor_verified"] is False


def test_same_source_repeat_corroboration_never_becomes_government_signature():
    rows=custody((NOW-timedelta(hours=50),"non-permissioned"),
                 (NOW-timedelta(hours=25),"non-permissioned"))
    live=snap(NOW-timedelta(minutes=4))
    report=build_temporal_quality(rows,assessed_at=NOW,recheck=live)
    assert report["status"]=="INTERNAL_REVIEW_READY"
    assert report["holds"]==[]
    assert report["canonical_observation_count_in_window"]==2
    assert report["minimum_24h_separation_met"] is True
    assert report["latest_interval_seconds"]==25*3600
    assert report["same_source_recheck"]=="REPEAT_SAME_SOURCE_MATCH"
    assert report["v14_board_status"]=="NO_OBSERVED_FIELD_CHANGES"
    assert report["source_authenticity"]=="NOT_INDEPENDENTLY_VERIFIED"
    assert report["source_recheck_independent_authority"] is False
    assert report["customer_delivery_enabled"] is False


def test_genuine_field_transition_enters_existing_v14_review_only():
    rows=custody((NOW-timedelta(hours=50),"non-permissioned"),
                 (NOW-timedelta(hours=25),"permissioned"))
    report=build_temporal_quality(
        rows,assessed_at=NOW,
        recheck=snap(NOW-timedelta(minutes=1),status="permissioned"))
    assert report["status"]=="INTERNAL_REVIEW_READY"
    assert report["observed_source_field_changes"]==3
    assert report["board_review_queue_count"]==3
    assert report["v14_board_status"]=="OBSERVED_CHANGES_REVIEW_ONLY"
    assert report["buyer_intent_verified"] is False
    assert report["actual_revenue"] is False


def test_early_second_snapshot_not_temporal_verification():
    rows=custody((NOW-timedelta(hours=3),"non-permissioned"),
                 (NOW-timedelta(hours=2),"permissioned"))
    r=build_temporal_quality(rows,assessed_at=NOW,
        recheck=snap(NOW-timedelta(minutes=1),status="permissioned"))
    assert "LATEST_OBSERVATIONS_LESS_THAN_24H_APART" in r["holds"]
    assert r["minimum_24h_separation_met"] is False
    assert r["observed_source_field_changes"]==3


def test_changed_live_recheck_does_not_append_or_promote_event():
    rows=custody((NOW-timedelta(hours=50),"non-permissioned"),
                 (NOW-timedelta(hours=25),"non-permissioned"))
    r=build_temporal_quality(rows,assessed_at=NOW,
        recheck=snap(NOW-timedelta(minutes=1),status="permissioned"))
    assert r["status"]=="HOLD_REVIEW_REQUIRED"
    assert r["same_source_recheck"]=="RECHECK_DIFFERS_FROM_STORED_SOURCE"
    assert set(r["recheck_mismatched_fields_by_id"])==PILOT_IDS
    assert "CURRENT_SOURCE_DIFFERS_REQUIRES_NEW_CANONICAL_OBSERVATION" in r["holds"]
    assert r["observed_source_field_changes"]==0
    assert r["production_writes"] is False


def test_pilot_membership_change_is_not_site_creation():
    now=NOW-timedelta(hours=1)
    snap_one=snap(now,ids={"1739547"})
    first=plan_custody_append(snap_one,previous=None,assessed_at=NOW)["row"]
    r=build_temporal_quality([first],assessed_at=NOW,
        recheck=snap(NOW-timedelta(minutes=1)))
    assert r["pinned_sample_fully_observed"] is False
    assert r["pilot_entity_count"]==1
    assert set(r["recheck_mismatched_entity_ids"])==PILOT_IDS-{"1739547"}
    assert r["regional_market_universe_verified"] is False


def test_stale_stored_custody_is_held_even_when_rechecked():
    rows=custody((NOW-timedelta(days=6),"non-permissioned"))
    r=build_temporal_quality(rows,assessed_at=NOW,
        recheck=snap(NOW-timedelta(minutes=1)))
    assert "LATEST_CANONICAL_OBSERVATION_OVER_72H_OLD" in r["holds"]
    assert r["customer_delivery_enabled"] is False


@pytest.mark.parametrize("bad",[
    lambda rows: rows[0]["snapshot_json"]["records"][0].update(
        {"contact_email":"private@example.org"}),
    lambda rows: rows[0].update({"chain_sha256":"0"*64}),
    lambda rows: rows[0].update({"source_id":"other_source"}),
])
def test_forged_custody_never_gets_quality_report(bad):
    rows=custody((NOW-timedelta(hours=50),"non-permissioned"))
    rows=deepcopy(rows)
    bad(rows)
    with pytest.raises((CustodyIntegrityError, ValueError)):
        build_temporal_quality(rows,assessed_at=NOW)


@pytest.mark.parametrize("bad_recheck",[
    lambda snap:snap.update({"customer_delivery_enabled":True}),
    lambda snap:snap["records"][0].update({"person_email":"private@invalid.test"}),
    lambda snap:snap["records"][0].update({"source_url":"https://evil.invalid/entity/1722645"}),
])
def test_forged_recheck_never_promotes_anything(bad_recheck):
    rows=custody((NOW-timedelta(hours=50),"non-permissioned"))
    recheck=snap(NOW-timedelta(hours=1))
    bad_recheck(recheck)
    with pytest.raises((CustodyIntegrityError,ValueError)):
        build_temporal_quality(rows,assessed_at=NOW,recheck=recheck)


def test_replayed_recheck_timestamp_is_not_independent_observation():
    at=NOW-timedelta(hours=1)
    rows=custody((at,"non-permissioned"))
    with pytest.raises(CustodyIntegrityError,match="must follow"):
        build_temporal_quality(rows,assessed_at=NOW,recheck=snap(at))


def test_history_quality_deterministic_and_no_customer_authority():
    rows=custody((NOW-timedelta(hours=50),"non-permissioned"),
                 (NOW-timedelta(hours=25),"non-permissioned"))
    a=build_temporal_quality(rows,assessed_at=NOW)
    assert a==build_temporal_quality(rows,assessed_at=NOW)
    assert a["data_resale_authorized"] is False
    assert a["payment_execution"] is False
    assert a["forecast_accuracy_verified"] is False
    assert a["external_anchor_verified"] is False


def test_sixteen_row_rolling_window_is_not_misrepresented_as_genesis():
    # The existing V15 reader returns only the latest 16 rows. Once the
    # true genesis has rolled out of view, the hash cannot be marketed as
    # a full-chain proof, even though all 15 visible links recompute.
    previous=None
    all_rows=[]
    for days_ago in range(17,0,-1):
        at=NOW-timedelta(days=days_ago)
        row=plan_custody_append(
            snap(at),previous=previous,assessed_at=NOW)["row"]
        all_rows.append(row)
        previous=row
    result=build_temporal_quality(all_rows[-16:],assessed_at=NOW)
    assert result["canonical_observation_count_in_window"]==16
    assert result["canonical_head_sequence"]==16
    assert result["genesis_present_in_window"] is False
    assert result["external_anchor_verified"] is False
    assert result["regional_market_coverage_percent"] is None
    assert result["observed_source_field_changes"]==0
