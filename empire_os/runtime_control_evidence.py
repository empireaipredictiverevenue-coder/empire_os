# EMPIRE_WAVE_090A
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json
import time


@dataclass(frozen=True)
class RuntimeArtifactEvidence:
    lane: str
    path: str
    size_bytes: int
    age_seconds: int
    controls: tuple[str, ...]
    schema_version: str | None
    generated_at: str | None
    authority: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeUnitEvidence:
    lane: str
    unit: str
    active_state: str
    sub_state: str
    unit_file_state: str
    exec_main_status: str
    controls: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def recursive_keys(
    value: Any,
    *,
    depth: int = 0,
    max_depth: int = 4,
) -> set[str]:

    if depth > max_depth:
        return set()

    found: set[str] = set()

    if isinstance(value, dict):

        for key, child in value.items():

            found.add(
                str(key).lower()
            )

            found.update(
                recursive_keys(
                    child,
                    depth=depth + 1,
                    max_depth=max_depth,
                )
            )

    elif isinstance(value, list):

        for child in value[:30]:

            found.update(
                recursive_keys(
                    child,
                    depth=depth + 1,
                    max_depth=max_depth,
                )
            )

    return found


def json_metadata(
    path: Path,
):

    try:
        value = json.loads(
            path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        )

    except Exception:
        return (
            set(),
            None,
            None,
            None,
        )

    keys = recursive_keys(
        value
    )

    if isinstance(
        value,
        dict,
    ):

        schema = value.get(
            "schema_version"
        )

        generated = (
            value.get(
                "generated_at"
            )
            or value.get(
                "updated_at"
            )
            or value.get(
                "timestamp"
            )
        )

        authority = value.get(
            "authority"
        )

    else:

        schema = None
        generated = None
        authority = None

    return (
        keys,
        str(schema)
        if schema is not None
        else None,
        str(generated)
        if generated is not None
        else None,
        str(authority)
        if authority is not None
        else None,
    )


def artifact_age_seconds(
    path: Path,
) -> int:

    try:
        return max(
            0,
            int(
                time.time()
                - path.stat().st_mtime
            ),
        )

    except Exception:
        return 10**12


def runtime_candidate_strength(
    *,
    artifact_count: int,
    active_unit_count: int,
    recent_artifact_count: int,
    control_candidate_count: int,
) -> str:

    if (
        artifact_count > 0
        and active_unit_count > 0
        and recent_artifact_count > 0
        and control_candidate_count >= 4
    ):
        return "STRONG_RUNTIME_CANDIDATE"

    if (
        artifact_count > 0
        and (
            active_unit_count > 0
            or recent_artifact_count > 0
        )
    ):
        return "PARTIAL_RUNTIME_CANDIDATE"

    if artifact_count > 0:
        return "ARTIFACT_ONLY"

    return "NO_RUNTIME_EVIDENCE"
