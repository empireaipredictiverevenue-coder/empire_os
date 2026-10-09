# EMPIRE_WAVE_090A
from pathlib import Path
import json
import tempfile

from empire_os.runtime_control_evidence import (
    artifact_age_seconds,
    json_metadata,
    runtime_candidate_strength,
)


def test_json_metadata_extracts_runtime_contract():

    with tempfile.TemporaryDirectory() as tmp:

        path = Path(tmp) / "latest.json"

        path.write_text(
            json.dumps(
                {
                    "schema_version":
                        "test-v1",

                    "generated_at":
                        "2026-10-07T12:00:00Z",

                    "authority":
                        "OBSERVE",

                    "canonical_identity":
                        "abc",

                    "evidence":
                        [],
                }
            )
        )

        (
            keys,
            schema,
            generated,
            authority,
        ) = json_metadata(
            path
        )

        assert (
            "canonical_identity"
            in keys
        )

        assert schema == "test-v1"
        assert authority == "OBSERVE"
        assert generated


def test_strong_candidate_requires_runtime_shape():

    result = runtime_candidate_strength(
        artifact_count=3,
        active_unit_count=1,
        recent_artifact_count=2,
        control_candidate_count=6,
    )

    assert result == (
        "STRONG_RUNTIME_CANDIDATE"
    )


def test_artifact_only_is_not_verified():

    result = runtime_candidate_strength(
        artifact_count=3,
        active_unit_count=0,
        recent_artifact_count=0,
        control_candidate_count=8,
    )

    assert result == "ARTIFACT_ONLY"


def test_age_is_non_negative():

    with tempfile.TemporaryDirectory() as tmp:

        path = Path(tmp) / "x.json"

        path.write_text("{}")

        assert (
            artifact_age_seconds(
                path
            )
            >= 0
        )
