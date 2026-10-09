# EMPIRE_WAVE_090C_C
from pathlib import Path
import tempfile

from empire_os.consent_suppression_governor_shadow import (
    python_paths_from_execstart,
    suppression_signals,
)


def test_exact_suppression_table_detected():

    with tempfile.TemporaryDirectory() as tmp:

        path = Path(tmp) / "x.py"

        path.write_text(
            'TABLE = "outbound_suppressions"\n'
        )

        signals = suppression_signals(
            path
        )

        assert (
            "outbound_suppressions"
            in signals
        )


def test_execstart_python_path_parser():

    value = (
        "/srv/empire_os/.venv/bin/python "
        "/srv/empire_os/scripts/"
        "outbound_governor_worker.py"
    )

    paths = (
        python_paths_from_execstart(
            value
        )
    )

    assert any(
        str(path).endswith(
            "scripts/outbound_governor_worker.py"
        )
        for path in paths
    )
