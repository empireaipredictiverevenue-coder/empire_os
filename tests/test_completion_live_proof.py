import json
from datetime import datetime, timezone
from pathlib import Path

from empire_os.completion_live_proof import run_completion_live_proof


NOW = datetime(2026, 10, 3, 0, 15, tzinfo=timezone.utc)


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")


def test_exact_rule_writes_line_bound_checkpoint_only_on_all_pass(tmp_path):
    _write(
        tmp_path / "docs/MASTER_REMAINING_CHECKLIST.md",
        "# Demo\n"
        "## Quant Brain / Decision Verification — ACTIVE\n"
        "- [ ] Live EmpireOS verification of Quant endpoints and opportunity Quant Review\n",
    )
    _write(
        tmp_path / "runtime/opportunity_factory/quant_review_latest.json",
        {
            "schema_version": "empire.opportunity_quant_review.v1",
            "execution_authority": "none",
        },
    )

    def http_get(url):
        if url.endswith("/health"):
            return 200, json.dumps({"ok": True})
        return 200, json.dumps({"available": True})

    result = run_completion_live_proof(
        tmp_path,
        now=NOW,
        http_get=http_get,
        systemd_probe=lambda unit, mode: False,
    )

    assert result["live_proof_pass_count"] == 1
    ref = result["checkpoints_written"][0]
    packet = json.loads((tmp_path / ref).read_text())
    assert packet["stage"] == "LIVE_VERIFY_DONE"
    assert packet["checklist_lines"] == [3]
    assert packet["synthetic_evidence_used"] is False


def test_partial_probe_does_not_write_checkpoint(tmp_path):
    _write(
        tmp_path / "docs/MASTER_REMAINING_CHECKLIST.md",
        "# Demo\n"
        "## Autonomous Predictive Cloud / Opportunity Loop — ACTIVE\n"
        "- [ ] Install/enable autonomous Opportunity Loop timer if tests pass\n",
    )
    _write(
        tmp_path / "runtime/opportunity_radar/loop_latest.json",
        {
            "automatic_quant_review": True,
            "execution_authority": "none",
        },
    )

    result = run_completion_live_proof(
        tmp_path,
        now=NOW,
        http_get=lambda url: (0, ""),
        systemd_probe=lambda unit, mode: mode == "enabled",
    )

    assert result["live_proof_pass_count"] == 0
    assert result["live_proof_blocked_count"] == 1
    assert result["checkpoints_written"] == []


def test_unconfigured_items_are_not_guessed(tmp_path):
    _write(
        tmp_path / "docs/MASTER_REMAINING_CHECKLIST.md",
        "# Demo\n## Other\n- [ ] Unknown feature\n",
    )

    result = run_completion_live_proof(
        tmp_path,
        now=NOW,
        http_get=lambda url: (200, "{}"),
        systemd_probe=lambda unit, mode: True,
    )

    assert result["pending_rule_match_count"] == 0
    assert result["checkpoints_written"] == []
