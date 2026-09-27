from pathlib import Path


def test_hermes_resident_uses_governed_current_branch():
    root = Path(__file__).resolve().parents[1]
    text = (
        root / "scripts/run_hermes_resident_latest.sh"
    ).read_text(encoding="utf-8")

    assert 'CURRENT_BRANCH="$(git -C "$REPO" branch --show-current)"' in text
    assert 'EMPIRE_HERMES_WORKER_CODE_BRANCH' in text
    assert 'feature/revenue-intelligence-v2|agent/data-cloud-wave4' in text
    assert 'BRANCH=feature/revenue-intelligence-v2' not in text
