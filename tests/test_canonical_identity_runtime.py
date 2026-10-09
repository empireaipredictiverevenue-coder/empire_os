from pathlib import Path


RUNNER = Path(
    "scripts/run_canonical_identity_resolution.py"
)

OVERLAY = Path(
    "scripts/apply_canonical_identity_overlay.py"
)


def test_runtime_exists():

    assert RUNNER.exists()
    assert OVERLAY.exists()


def test_manual_do_not_merge_exists():

    text = RUNNER.read_text()

    assert (
        "buyer_identity_overrides.json"
        in text
    )


def test_identity_output_exists_in_contract():

    text = RUNNER.read_text()

    assert (
        "buyer_identity_latest.json"
        in text
    )


def test_overlay_supports_backlog_and_queue():

    text = OVERLAY.read_text()

    assert '"backlog"' in text
    assert '"queue"' in text


def test_overlay_preserves_aliases():

    text = OVERLAY.read_text()

    assert (
        "identity_aliases"
        in text
    )

    assert (
        "identity_canonical"
        in text
    )
