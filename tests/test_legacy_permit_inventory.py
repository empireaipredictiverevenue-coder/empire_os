from empire_os.legacy_permit_inventory import update_cumulative_inventory


def _payload(*, record_id, state, mode, classification="REUSE", next_offset=10):
    return {
        "mode": "OBSERVE",
        "scan_epoch": "test-epoch",
        "scan_order": "prospect_id.asc,created_at.asc,id.asc",
        "scan_offset": 0,
        "next_offset": next_offset,
        "generated_at": "2026-09-24T19:00:00+00:00",
        "database_write_performed": False,
        "canonical_promotion_performed": False,
        "outbound_sent": False,
        "actual_revenue": False,
        "records": [{
            "legacy_prospect_id": record_id,
            "recovery_classification": classification,
            "recovery_state": state,
            "inventory_identity_mode": mode,
            "source_owner_identity_state": (
                "MATCHED" if mode == "OWNER_IDENTIFIED" else "PLACEHOLDER"
            ),
            "source_freshness": "SOURCE_REVALIDATED_CURRENT",
            "canonical_prospect_id": None,
            "original_evidence": {
                "niche": "plumbing",
                "metro": "NYC",
            },
            "recovered_fields": {
                "metro": "NYC",
                "permit_number": "123",
                "business_name": "Example",
                "address": "1 TEST STREET, Queens",
            },
        }],
    }


def test_cumulative_inventory_counts_unique_records(tmp_path):
    first = update_cumulative_inventory(
        tmp_path,
        _payload(
            record_id="p1",
            state="VERIFIED_CURRENT",
            mode="OWNER_IDENTIFIED",
        ),
    )
    second = update_cumulative_inventory(
        tmp_path,
        _payload(
            record_id="p2",
            state="VERIFIED_CURRENT_PROJECT_ONLY",
            mode="PROJECT_ONLY",
            next_offset=0,
        ),
    )

    assert first["unique_inventory_records"] == 1
    assert second["unique_inventory_records"] == 2
    assert second["verified_current_inventory"] == 2
    assert second["verified_current_owner_identified"] == 1
    assert second["verified_current_project_only"] == 1
    assert second["borough_counts"]["Queens"] == 2
    assert second["full_scan_complete"] is True
    assert second["full_scan_completions"] == 1
    assert second["canonical_database_write_performed"] is False

    third = update_cumulative_inventory(
        tmp_path,
        _payload(
            record_id="p3",
            state="VERIFIED_CURRENT",
            mode="OWNER_IDENTIFIED",
            next_offset=50,
        ),
    )
    assert third["full_scan_complete"] is True
    assert third["latest_cycle_completed_scan"] is False
    assert third["full_scan_completions"] == 1


def test_cumulative_inventory_is_idempotent_by_legacy_id(tmp_path):
    payload = _payload(
        record_id="p1",
        state="VERIFIED_CURRENT",
        mode="OWNER_IDENTIFIED",
    )
    update_cumulative_inventory(tmp_path, payload)
    again = update_cumulative_inventory(tmp_path, payload)

    assert again["unique_inventory_records"] == 1
    assert again["verified_current_inventory"] == 1


def test_cumulative_inventory_resets_on_epoch_change(tmp_path):
    update_cumulative_inventory(
        tmp_path,
        _payload(
            record_id="old",
            state="VERIFIED_CURRENT",
            mode="OWNER_IDENTIFIED",
        ),
    )
    new_payload = _payload(
        record_id="new",
        state="VERIFIED_CURRENT_PROJECT_ONLY",
        mode="PROJECT_ONLY",
    )
    new_payload["scan_epoch"] = "new-epoch"

    result = update_cumulative_inventory(tmp_path, new_payload)

    assert result["unique_inventory_records"] == 1
    assert result["verified_current_owner_identified"] == 0
    assert result["verified_current_project_only"] == 1
