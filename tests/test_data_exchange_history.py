"""History tests: all records are synthetic test fixtures, not source claims."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.data_exchange_construction import build_construction_preview
from empire_os.data_exchange_history import build_construction_history

NOW = datetime(2026, 10, 14, 17, tzinfo=timezone.utc)
DAYS = [NOW - timedelta(days=3), NOW - timedelta(days=2),
        NOW - timedelta(days=1), NOW]


def data(i, *, entity="1739547", status="non-permissioned", area="1"):
    return {
        "record_id": entity, "source_id": "gb_planning_data",
        "dataset_id": "brownfield-land", "region": "north_west_england",
        "record_type": "brownfield_land",
        "source_url": f"https://www.planning.data.gov.uk/entity/{entity}",
        "source_observed_at": DAYS[i].isoformat(),
        "planning_permission_status": status,
        "site_area_hectares": area,
    }


def snapshot(i, **kwargs):
    return build_construction_preview([data(i, **kwargs)],
                                      observed_at=DAYS[i])


def history(*snapshots):
    return build_construction_history(snapshots, assessed_at=NOW)


def test_real_observation_history_without_deltas_is_zero_not_new_projects():
    result = history(snapshot(0), snapshot(1), snapshot(2))
    assert result["snapshot_count"] == 3
    assert result["window_count"] == 2
    assert result["observed_change_count"] == 0
    assert result["held_window_count"] == 0
    assert result["latest_chain_sha256"] == result["snapshot_manifest"][-1]["chain_sha256"]
    assert result["chain_authenticity"] == "NOT_EXTERNALLY_ANCHORED"
    assert result["customer_delivery_enabled"] is False
    assert result["execution_authority"] == "NONE"


def test_permission_change_emits_only_one_event_on_true_value_transition():
    before = snapshot(0)
    transition = snapshot(1, status="permissioned")
    later = snapshot(2, status="permissioned")
    result = history(before, transition, later)
    assert result["observed_change_count"] == 1
    event = result["observed_changes"][0]
    assert event["priority"] == "REVIEW"
    assert event["buyer_intent_verified"] is False
    assert event["commercial_outcome_verified"] is False
    assert len(event["event_id"]) == 64
    assert history(before, transition, later) == result


def test_area_only_change_is_context():
    result = history(snapshot(0), snapshot(1, area="3"))
    assert result["observed_changes"][0]["priority"] == "CONTEXT"


def test_chain_commitments_include_sequence_and_historical_differences():
    a = history(snapshot(0), snapshot(1))
    b = history(snapshot(0), snapshot(1, area="3"))
    assert a["latest_chain_sha256"] != b["latest_chain_sha256"]
    assert a["snapshot_manifest"][1]["previous_sha256"] == a["snapshot_manifest"][0]["chain_sha256"]
    assert a["snapshot_manifest"][0]["previous_sha256"] == "0" * 64


def test_newly_sampled_id_not_fake_create_or_delete():
    result = history(snapshot(0), snapshot(1, entity="1722645"))
    assert result["held_window_count"] == 1
    assert result["observed_change_count"] == 0
    assert "NO_SHARED_OBSERVED_ENTITIES" in result["comparison_windows"][0]["holds"]


def test_older_capture_order_is_not_accepted():
    with pytest.raises(ValueError, match="chronology"):
        history(snapshot(1), snapshot(0))
    with pytest.raises(ValueError, match="chronology"):
        history(snapshot(1), snapshot(1))


def test_time_spread_inside_snapshot_is_bounded():
    rows = [data(0), data(1, entity="1722645")]
    result = build_construction_preview(rows, observed_at=DAYS[1])
    with pytest.raises(ValueError, match="chronology"):
        history(result, snapshot(2))


def test_mutation_to_commercial_execution_flag_is_rejected():
    untrusted = deepcopy(snapshot(1))
    untrusted["customer_delivery_enabled"] = True
    with pytest.raises(ValueError, match="authority"):
        history(snapshot(0), untrusted)


def test_private_contact_field_is_rejected():
    untrusted = deepcopy(snapshot(1))
    untrusted["records"][0]["email"] = "nobody@example.com"
    with pytest.raises(ValueError, match="unreviewed"):
        history(snapshot(0), untrusted)


def test_cannot_introduce_a_future_source_observation():
    tomorrow = NOW + timedelta(days=1)
    forged = build_construction_preview(
        [{**data(2), "source_observed_at": tomorrow.isoformat()}],
        observed_at=tomorrow,
    )
    with pytest.raises(ValueError, match="chronology"):
        history(snapshot(0), forged)


@pytest.mark.parametrize("input_value", [None, {}, [], [None], [1, 2], [{}] * 2])
def test_invalid_history_fails_closed(input_value):
    with pytest.raises(ValueError):
        build_construction_history(input_value, assessed_at=NOW)


def test_rejects_unbounded_history_and_naive_time():
    with pytest.raises(ValueError, match="bounded"):
        history(*[snapshot(0)] * 17)
    with pytest.raises(ValueError, match="timezone"):
        build_construction_history(
            [snapshot(0), snapshot(1)], assessed_at=datetime(2026, 10, 14),
        )


def test_history_rejects_unparseable_time_and_non_dictionary_rows():
    broken = deepcopy(snapshot(1))
    broken["records"][0]["source_observed_at"] = "not-a-date"
    with pytest.raises(ValueError, match="observation invalid"):
        history(snapshot(0), broken)
    broken["records"] = ["untrusted"]
    with pytest.raises(ValueError, match="row shape"):
        history(snapshot(0), broken)


def test_history_cli_checks_mismatch_and_never_prints_private_content(tmp_path, capsys):
    import json
    from scripts.review_construction_history import main

    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps(snapshot(0)), encoding="utf-8")
    b.write_text(json.dumps(snapshot(1, status="permissioned")), encoding="utf-8")
    code = main(["--snapshots", str(a), str(b)])
    assert code == 0
    outcome = json.loads(capsys.readouterr().out)
    assert outcome["observed_change_count"] == 1
    assert outcome["execution_authority"] == "NONE"
    assert main([
        "--snapshots", str(a), str(b),
        "--expected-chain-sha256", "0" * 64,
    ]) == 2
    held = json.loads(capsys.readouterr().out)
    assert held["assessment_status"] == "HOLD"
    assert "private" not in str(held)


def test_history_cli_disallows_symlink_input(tmp_path):
    from scripts.review_construction_history import read_bounded_snapshot

    original = tmp_path / "original.json"
    link = tmp_path / "alias.json"
    original.write_text("{}", encoding="utf-8")
    link.symlink_to(original)
    with pytest.raises(ValueError, match="symbolic link"):
        read_bounded_snapshot(link)


def test_empty_cli_history_refuses_success(capsys):
    from scripts.review_construction_history import main

    assert main(["--snapshots", "/tmp/missing-empire-snapshot"]) == 2
    result = __import__("json").loads(capsys.readouterr().out)
    assert result["assessment_status"] == "HOLD"
