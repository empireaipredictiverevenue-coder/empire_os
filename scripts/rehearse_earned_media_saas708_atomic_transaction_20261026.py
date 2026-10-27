"""Prove exact atomic 700->708 overlay and fault rollback on temporary copies."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json

from empire_os.earned_media_saas700_reconciliation import (
    DESTINATION, LIVE, verify,
)
from empire_os.earned_media_saas_rebased_release import read_index, index_digest
from empire_os.earned_media_saas708_atomic_private_trial import (
    private_rehearsal_copy, run_private_trial, PrivateTrialHeld,
    CANDIDATE_PIN,
)
from empire_os.earned_media_saas700_reconciliation import LIVE_700_PIN


def rehearse() -> dict:
    assert verify()["status"] == "PRIVATE_708_FILE_REBASE_INTEGRITY_PASS_REVIEW_ONLY"
    assert index_digest(read_index(LIVE)) == LIVE_700_PIN
    assert index_digest(read_index(DESTINATION)) == CANDIDATE_PIN
    result = {}
    tests = ("success", "before", "after_assets", "after_first_route", "after_all", "post_apply")
    for name in tests:
        with TemporaryDirectory(prefix="empire-saas708-transaction-") as scratch:
            copy, before = private_rehearsal_copy(Path(scratch) / "site")
            try:
                def fail():
                    raise RuntimeError("INJECTED_POST_APPLY_FAILURE")
                detail = run_private_trial(
                    copy, DESTINATION,
                    source_pin=LIVE_700_PIN,
                    candidate_pin=CANDIDATE_PIN,
                    fail_at=name if name not in ("success", "post_apply") else None,
                    post_apply=fail if name == "post_apply" else None,
                )
                if name != "success":
                    raise AssertionError("EXPECTED_PRIVATE_FAILURE_NOT_RAISED")
                if read_index(copy) != read_index(DESTINATION):
                    raise AssertionError("FINAL_PRIVATE_INVENTORY_MISMATCH")
                result[name] = detail["status"]
            except (PrivateTrialHeld, RuntimeError) as exc:
                if name == "success" or read_index(copy) != before:
                    raise
                result[name] = "EXACT_700_FILE_ROLLBACK_CONFIRMED"
    if (index_digest(read_index(LIVE)) != LIVE_700_PIN or
            index_digest(read_index(DESTINATION)) != CANDIDATE_PIN):
        raise AssertionError("PUBLIC_SOURCE_OR_APPROVED_STAGE_CHANGED_DURING_TEST")
    return {
        "schema_version":"empire.website.saas708_private_fault_transaction_proof.v1",
        "status":"PRIVATE_ATOMIC_TRANSACTION_ALL_SIX_SCENARIOS_PASS",
        "source_live_file_count":700,
        "candidate_file_count":708,
        "two_existing_routes_replaced":2,
        "eight_new_assets_added":8,
        "source_inventory_sha256":LIVE_700_PIN,
        "candidate_inventory_sha256":CANDIDATE_PIN,
        "scenarios":result,
        "scenarios_passed":len(result),
        "uses_disposable_temporary_copies_only":True,
        "protected_root_archive_directly_read":False,
        "independent_original_astra_website_owner_approved":False,
        "production_publisher_invoked":False,
        "production_site_modified":False,
        "buyer_or_payment_action":False,
    }


if __name__ == "__main__":
    print(json.dumps(rehearse(), sort_keys=True))
