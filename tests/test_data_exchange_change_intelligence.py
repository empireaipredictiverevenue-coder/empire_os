"""Tests use fabricated fixtures only; no mock source record enters production."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from empire_os.data_exchange_change_intelligence import assess_construction_changes
from empire_os.data_exchange_construction import build_construction_preview

NOW = datetime(2026, 10, 14, 17, 0, tzinfo=timezone.utc)
OLD = "2026-10-13T09:00:00+00:00"
NEW = "2026-10-14T09:00:00+00:00"


def raw(entity="1739547", time=OLD, status="non-permissioned", area="1"):
    return {
        "record_id": entity,
        "source_id": "gb_planning_data",
        "dataset_id": "brownfield-land",
        "region": "north_west_england",
        "record_type": "brownfield_land",
        "source_url": f"https://www.planning.data.gov.uk/entity/{entity}",
        "source_observed_at": time,
        "planning_permission_status": status,
        "site_area_hectares": area,
    }


def snap(*records):
    return build_construction_preview(list(records), observed_at=NOW)


def compare(before, after):
    return assess_construction_changes(before, after, assessed_at=NOW)


def test_changed_permission_produces_evidence_rich_but_internal_event():
    before = snap(raw())
    after = snap(raw(time=NEW, status="permissioned"))
    result = compare(before, after)
    assert result["assessment_status"] == "INTERNAL_CHANGE_REVIEW_ONLY"
    assert result["observed_change_count"] == 1
    event = result["observed_changes"][0]
    assert event["source_changes"]["planning_permission_status"] == {
        "previous": "non-permissioned", "current": "permissioned",
    }
    assert event["priority"] == "REVIEW"
    assert event["buyer_intent_verified"] is False
    assert event["commercial_outcome_verified"] is False
    assert len(event["event_id"]) == 64
    assert event["source_url"] == "https://www.planning.data.gov.uk/entity/1739547"
    assert result["customer_delivery_enabled"] is False
    assert result["data_resale_authorized"] is False
    assert result["execution_authority"] == "NONE"


def test_area_change_only_is_context_not_sales_opportunity():
    result = compare(snap(raw()), snap(raw(time=NEW, area="2.1")))
    assert len(result["observed_changes"]) == 1
    event = result["observed_changes"][0]
    assert event["source_changes"] == {
        "site_area_hectares": {"previous": "1", "current": "2.1"},
    }
    assert event["priority"] == "CONTEXT"


def test_observation_timestamp_alone_never_causes_opportunity_event():
    result = compare(snap(raw()), snap(raw(time=NEW)))
    assert result["observed_changes"] == []
    assert result["observed_change_count"] == 0


def test_missing_records_are_coverage_not_demolished_sites():
    before = snap(raw(), raw(entity="1739516"))
    after = snap(raw(time=NEW), raw(entity="1722645", time=NEW))
    result = compare(before, after)
    assert result["observed_changes"] == []
    assert result["newly_observed_in_sample"] == ["1722645"]
    assert result["not_in_later_sample"] == ["1739516"]
    assert "not new or deleted projects" in result["coverage_warning"]


def test_disjoint_samples_are_hold_not_new_projects():
    result = compare(snap(raw()), snap(raw(entity="1722645", time=NEW)))
    assert result["assessment_status"] == "HOLD"
    assert "NO_SHARED_OBSERVED_ENTITIES" in result["holds"]
    assert result["observed_changes"] == []


def test_no_baseline_is_not_new_project():
    result = compare(snap(), snap(raw(time=NEW)))
    assert result["assessment_status"] == "HOLD"
    assert "INSUFFICIENT_COMPARABLE_SAMPLES" in result["holds"]


def test_stale_or_replayed_observation_is_hold():
    before = snap(raw(time=OLD))
    for moment in (OLD, "2026-10-12T00:00:00+00:00"):
        later = snap(raw(time=moment, status="permissioned"))
        result = compare(before, later)
        assert result["assessment_status"] == "HOLD"
        assert result["observed_changes"] == []


def test_unmodified_source_replay_is_stable():
    left = snap(raw())
    right = snap(raw(time=NEW, status="permissioned", area="2.2"))
    assert compare(left, right) == compare(left, right)
    event = compare(left, right)["observed_changes"][0]
    assert len(event["source_changes"]) == 2


@pytest.mark.parametrize("mutation", [
    lambda x: x.update({"customer_delivery_enabled": True}),
    lambda x: x.update({"data_resale_authorized": True}),
    lambda x: x.update({"execution_authority": "EXECUTE"}),
    lambda x: x.update({"data_source": "gb_recc_solar"}),
    lambda x: x.update({"schema_version": "unknown"}),
    lambda x: x.update({"dataset_record_count": 99}),
    lambda x: x["records"][0].update({"contact_email": "private@example.com"}),
    lambda x: x["records"][0].update({"source_url": "https://attacker.test/entity/1739547"}),
    lambda x: x["records"][0].update({"planning_permission_status": "won-contract"}),
])
def test_rejects_tampered_or_unapproved_snapshot(mutation):
    before = snap(raw())
    after = deepcopy(snap(raw(time=NEW, status="permissioned")))
    mutation(after)
    with pytest.raises(ValueError):
        compare(before, after)


def test_timestamp_inversion_of_one_shared_entity_holds_all():
    baseline = snap(raw(), raw(entity="1739516", time=NEW))
    later = snap(raw(time=NEW), raw(entity="1739516", time=OLD))
    result = compare(baseline, later)
    assert result["assessment_status"] == "HOLD"
    assert "REPLAY_OR_BACKDATED_ENTITY" in result["holds"]


def test_naive_assessed_timestamp_rejected():
    with pytest.raises(ValueError, match="timezone"):
        assess_construction_changes({}, {}, assessed_at=datetime(2026, 10, 14))


def test_event_identity_includes_observation_window():
    first = snap(raw(time="2026-10-12T09:00:00+00:00"))
    second = snap(raw(time=OLD, status="permissioned"))
    later = snap(raw(time=NEW, status="permissioned"))
    a = compare(first, second)["observed_changes"][0]
    b = compare(first, later)["observed_changes"][0]
    assert a["event_id"] != b["event_id"]


def test_entry_date_change_does_not_become_buyer_intent():
    old = raw()
    new = raw(time=NEW)
    old["source_entry_date"] = "2018-05-22"
    new["source_entry_date"] = "2024-11-29"
    result = compare(snap(old), snap(new))
    assert result["observed_change_count"] == 0
    assert result["execution_authority"] == "NONE"


def test_snapshot_cli_rejects_untrusted_non_object(tmp_path):
    from scripts.compare_construction_snapshots import read_snapshot

    f = tmp_path / "invalid.json"
    f.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="object"):
        read_snapshot(f)


def test_snapshot_cli_rejects_large_file(tmp_path):
    from scripts.compare_construction_snapshots import read_snapshot

    f = tmp_path / "large.json"
    f.write_bytes(b" " * (2 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="large"):
        read_snapshot(f)
