"""Fault-injected private proof of exact eight-asset, two-route rollback."""
from __future__ import annotations

from pathlib import Path
import pytest

from empire_os.earned_media_saas700_reconciliation import LIVE, DESTINATION
from empire_os.earned_media_saas_rebased_release import read_index, index_digest
from empire_os.earned_media_saas708_atomic_private_trial import (
    PrivateTrialHeld, private_rehearsal_copy, release_scope,
    run_private_trial, CANDIDATE_PIN,
)
from empire_os.earned_media_saas700_reconciliation import LIVE_700_PIN


def prepare(tmp_path):
    target, before = private_rehearsal_copy(tmp_path / "live-disposable")
    assert len(before) == 700
    assert index_digest(before) == LIVE_700_PIN
    return target, before


def trial(copy, **options):
    pins = {"source_pin": LIVE_700_PIN, "candidate_pin": CANDIDATE_PIN}
    pins.update(options)
    return run_private_trial(copy, DESTINATION, **pins)


def test_full_two_route_eight_asset_success_preserves_source(tmp_path):
    copy, before = prepare(tmp_path)
    previous_candidate = read_index(DESTINATION)
    result = trial(copy)
    assert result["status"] == "EXACT_EIGHT_ASSETS_TWO_ROUTES_PRIVATE_COPY_APPLIED"
    assert result["changed_existing_routes"] == 2
    assert result["added_immutable_assets"] == 8
    assert result["result_inventory_sha256"] == CANDIDATE_PIN
    assert result["root_publisher_exercised"] is False
    assert result["production_site_modified"] is False
    assert read_index(copy) == previous_candidate
    assert index_digest(read_index(LIVE)) == LIVE_700_PIN
    assert read_index(DESTINATION) == previous_candidate


@pytest.mark.parametrize("stage", [
    "before", "after_assets", "after_first_route", "after_all",
])
def test_injected_failures_exactly_restore_all_700_originals(stage, tmp_path):
    copy, before = prepare(tmp_path)
    with pytest.raises(PrivateTrialHeld, match="INJECTED_FAILURE"):
        trial(copy, fail_at=stage)
    assert read_index(copy) == before
    assert len(read_index(copy)) == 700


def test_postapply_hook_failure_also_recovers_all_files(tmp_path):
    copy, before = prepare(tmp_path)
    def fail():
        raise RuntimeError("INJECTED_POST_APPLY_HOOK_ERROR")
    with pytest.raises(RuntimeError, match="INJECTED_POST_APPLY"):
        trial(copy, post_apply=fail)
    assert read_index(copy) == before


def test_cannot_invoke_private_trial_against_public_live_site():
    with pytest.raises(PrivateTrialHeld, match="LIVE_OR_STAGED_SOURCE"):
        trial(LIVE)


def test_candidate_cannot_be_the_transaction_destination():
    with pytest.raises(PrivateTrialHeld, match="LIVE_OR_STAGED_SOURCE"):
        trial(DESTINATION)


def test_stage_and_live_source_must_be_exact_pins(tmp_path):
    copy, before = prepare(tmp_path)
    with pytest.raises(PrivateTrialHeld, match="EXACT_708_REVIEW_PINS_ONLY"):
        trial(copy, source_pin="0"*64)
    assert read_index(copy) == before


def test_preexisting_immutable_asset_collision_blocks_before_writes(tmp_path):
    copy, before = prepare(tmp_path)
    # A foreign asset appears in the disposable copy before preflight.
    stage=read_index(DESTINATION)
    new_asset=next(name for name in stage if name not in before)
    (copy/new_asset).parent.mkdir(parents=True, exist_ok=True)
    (copy/new_asset).write_bytes(b"CONCURRENT_OTHER_OWNER_PAYLOAD")
    modified=read_index(copy)
    with pytest.raises(PrivateTrialHeld, match="PINNED_SOURCE"):
        trial(copy)
    assert read_index(copy) == modified


def test_bad_or_missing_eight_asset_inventory_not_accepted():
    original=read_index(LIVE)
    proposed=read_index(DESTINATION)
    addition=next(name for name in proposed if name not in original)
    incomplete=dict(proposed)
    incomplete.pop(addition)
    with pytest.raises(PrivateTrialHeld, match="PINNED_SOURCE"):
        release_scope(original,incomplete,
            source_pin=LIVE_700_PIN,candidate_pin=CANDIDATE_PIN)
