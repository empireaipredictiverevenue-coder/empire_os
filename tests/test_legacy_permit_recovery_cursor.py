import json

from empire_os.legacy_permit_recovery import (
    SCAN_EPOCH,
    SCAN_ORDER,
    _previous_next_offset,
)


def test_cursor_resets_when_scan_order_changes(tmp_path):
    path = tmp_path / "latest.json"
    path.write_text(
        json.dumps({
            "next_offset": 1250,
            "scan_order": "created_at.asc,id.asc",
        })
    )

    assert _previous_next_offset(path) == 0


def test_cursor_reuses_offset_for_current_scan_order(tmp_path):
    path = tmp_path / "latest.json"
    path.write_text(
        json.dumps({
            "next_offset": 1250,
            "scan_order": SCAN_ORDER,
            "scan_epoch": SCAN_EPOCH,
        })
    )

    assert _previous_next_offset(path) == 1250


def test_cursor_resets_when_scan_epoch_changes(tmp_path):
    path = tmp_path / "latest.json"
    path.write_text(
        json.dumps({
            "next_offset": 1250,
            "scan_order": SCAN_ORDER,
            "scan_epoch": "old-epoch",
        })
    )

    assert _previous_next_offset(path) == 0
