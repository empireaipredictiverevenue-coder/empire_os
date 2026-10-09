# EMPIRE_WAVE_090B
from pathlib import Path
import json
import tempfile

from empire_os.runtime_control_adjudication import (
    adjudicate_control,
)


def test_source_text_cannot_verify_runtime():

    with tempfile.TemporaryDirectory() as tmp:

        root = Path(tmp)

        (
            root
            / "runtime/test"
        ).mkdir(
            parents=True
        )

        path = (
            root
            / "runtime/test/readme.txt"
        )

        path.write_text(
            "canonical_identity output_quality"
        )

        result = adjudicate_control(
            root=root,
            lane="test",
            control="canonical_identity",
            artifact_paths=[
                "runtime/test/readme.txt"
            ],
            active_units=[],
        )

        assert result.status == (
            "UNVERIFIED"
        )


def test_recent_structured_exact_key_verifies():

    with tempfile.TemporaryDirectory() as tmp:

        root = Path(tmp)

        (
            root
            / "runtime/test"
        ).mkdir(
            parents=True
        )

        path = (
            root
            / "runtime/test/latest.json"
        )

        path.write_text(
            json.dumps(
                {
                    "schema_version":
                        "x-v1",

                    "generated_at":
                        "2026-10-07T12:00:00Z",

                    "canonical_identity":
                        "abc",
                }
            )
        )

        result = adjudicate_control(
            root=root,
            lane="test",
            control="canonical_identity",
            artifact_paths=[
                "runtime/test/latest.json"
            ],
            active_units=[],
        )

        assert result.status == (
            "VERIFIED_RUNTIME"
        )


def test_generic_json_does_not_verify_output_quality():

    with tempfile.TemporaryDirectory() as tmp:

        root = Path(tmp)

        (
            root
            / "runtime/test"
        ).mkdir(
            parents=True
        )

        path = (
            root
            / "runtime/test/latest.json"
        )

        path.write_text(
            json.dumps(
                {
                    "schema_version":
                        "x-v1",

                    "generated_at":
                        "now",

                    "status":
                        "PASS",
                }
            )
        )

        result = adjudicate_control(
            root=root,
            lane="test",
            control="output_quality",
            artifact_paths=[
                "runtime/test/latest.json"
            ],
            active_units=[],
        )

        assert result.status == (
            "UNVERIFIED"
        )
