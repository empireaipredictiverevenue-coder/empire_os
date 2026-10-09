# EMPIRE_WAVE_090C_B
from pathlib import Path
import json
import tempfile

from empire_os.runtime_control_adjudication import (
    adjudicate_control,
)


def test_generic_observe_authority_does_not_verify_action_authority():

    with tempfile.TemporaryDirectory() as tmp:

        root = Path(tmp)

        path = (
            root
            / "runtime"
            / "test"
            / "latest.json"
        )

        path.parent.mkdir(
            parents=True
        )

        path.write_text(
            json.dumps(
                {
                    "schema_version":
                        "test-v1",

                    "generated_at":
                        "2026-10-07T12:00:00Z",

                    "authority":
                        "OBSERVE",
                }
            )
        )

        result = adjudicate_control(
            root=root,
            lane="test",
            control="action_authority",
            artifact_paths=[
                "runtime/test/latest.json"
            ],
            active_units=[],
        )

        assert result.status == "UNVERIFIED"
