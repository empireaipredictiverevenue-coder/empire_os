import json
from pathlib import Path

import scripts.run_acquisition_guarded as guard


def test_soak_active_before_expiry(tmp_path):
    expiry = tmp_path / "expires"
    expiry.write_text("200")
    assert guard.soak_active(now_epoch=100, expiry_path=expiry) == (True, 200)


def test_soak_inactive_at_or_after_expiry(tmp_path):
    expiry = tmp_path / "expires"
    expiry.write_text("200")
    assert guard.soak_active(now_epoch=200, expiry_path=expiry) == (False, 200)
    assert guard.soak_active(now_epoch=201, expiry_path=expiry) == (False, 200)


def test_missing_or_invalid_expiry_does_not_block_normal_acquisition(tmp_path):
    missing = tmp_path / "missing"
    assert guard.soak_active(now_epoch=100, expiry_path=missing) == (False, None)

    invalid = tmp_path / "invalid"
    invalid.write_text("not-an-epoch")
    assert guard.soak_active(now_epoch=100, expiry_path=invalid) == (False, None)
