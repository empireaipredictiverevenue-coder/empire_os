"""Regression tests for the read-only owner release vs master tracker audit."""
from pathlib import Path
import csv

import pytest

from scripts.master_execution_status import audit_commercial_register


FIELDS = ["id", "priority", "title", "audit_status", "owner", "evidence_next_action", "source"]


def _register(tmp_path: Path, statuses: tuple[str, str]) -> Path:
    path = tmp_path / "register.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for key, state in zip(("P1-03", "P1-04"), statuses):
            writer.writerow(dict(id=key, priority="P1", title=key,
                                 audit_status=state, owner="original_website",
                                 evidence_next_action="owner receipt", source="release register"))
    return path


def _release(tmp_path: Path, *, confirmed: bool = True) -> Path:
    path = tmp_path / "release.md"
    path.write_text(
        ("Original 707→746 website release is LIVE.\n"
         "Scoped public HTTPS verification PASS 49/49\n"
         "746/746\n") if confirmed else "Older candidate not deployed.\n",
        encoding="utf-8",
    )
    return path


def test_live_owner_claim_and_current_tracker_are_consistent(tmp_path):
    report = audit_commercial_register(
        _register(tmp_path, ("LIVE", "LIVE")), _release(tmp_path)
    )
    assert report["row_count"] == 2
    assert report["tracker_conflicts"] == []
    assert report["owner_release_claim_present"] is True
    assert report["owner_release_claim_independently_verified_by_this_command"] is False
    assert report["execution_authority"] == "none"
    assert report["commercial_execution_performed"] is False


def test_stale_tracker_reports_exact_task_without_mutation(tmp_path):
    path = _register(tmp_path, ("OPEN", "LIVE"))
    before = path.read_bytes()
    report = audit_commercial_register(path, _release(tmp_path))
    assert report["tracker_conflicts"] == [
        {"task_id": "P1-03", "reason": "recorded_live_release_still_open"}
    ]
    assert path.read_bytes() == before


def test_no_live_owner_proof_never_auto_marks_done(tmp_path):
    report = audit_commercial_register(
        _register(tmp_path, ("OPEN", "OPEN")), _release(tmp_path, confirmed=False)
    )
    assert report["owner_release_claim_present"] is False
    assert report["tracker_conflicts"] == []


def test_duplicate_task_ids_fail_closed(tmp_path):
    path = _register(tmp_path, ("LIVE", "LIVE"))
    content = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(content + [content[1]]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate_task_id"):
        audit_commercial_register(path, _release(tmp_path))


def test_incomplete_row_fails_closed(tmp_path):
    path = _register(tmp_path, ("LIVE", "LIVE"))
    path.write_text(path.read_text(encoding="utf-8").replace(
        "original_website", "", 1
    ), encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete_row"):
        audit_commercial_register(path, _release(tmp_path))
