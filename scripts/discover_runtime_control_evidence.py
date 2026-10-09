# EMPIRE_WAVE_090A
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from empire_os.detection_fabric import (
    CONTROL_NAMES,
    CONTROL_TERMS,
    LANES,
    runtime_matches_lane,
    systemd_matches_lane,
)
from empire_os.runtime_control_evidence import (
    RuntimeArtifactEvidence,
    RuntimeUnitEvidence,
    artifact_age_seconds,
    json_metadata,
    runtime_candidate_strength,
)
from empire_os.truth_quality_control import (
    now_iso,
)


ROOT = Path("/srv/empire_os")
RUNTIME = ROOT / "runtime"

OUT = (
    RUNTIME
    / "control_plane"
    / "runtime_evidence_candidates_latest.json"
)

MAX_FILES = 4000
MAX_FILE_BYTES = 2_000_000

RECENT_SECONDS = 7 * 24 * 60 * 60


def atomic_write(
    path: Path,
    payload,
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = path.with_suffix(
        ".tmp"
    )

    tmp.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    tmp.replace(path)


def runtime_files():

    if not RUNTIME.exists():
        return []

    files = []

    for path in RUNTIME.rglob("*"):

        if len(files) >= MAX_FILES:
            break

        if not path.is_file():
            continue

        try:
            size = path.stat().st_size

        except Exception:
            continue

        if (
            size <= 0
            or size > MAX_FILE_BYTES
        ):
            continue

        if path.suffix.lower() not in {
            ".json",
            ".jsonl",
            ".md",
            ".txt",
        }:
            continue

        files.append(path)

    return sorted(files)


def text_controls(
    path: Path,
):

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )[:200_000].lower()

    except Exception:
        return set()

    found = set()

    for control, terms in (
        CONTROL_TERMS.items()
    ):

        if any(
            term in text
            for term in terms
        ):
            found.add(control)

    return found


def artifact_evidence(
    lane,
    path: Path,
):

    # EMPIRE_WAVE_090C_D1R3
    #
    # runtime/ is concurrently mutated by workers.
    # A file may legitimately be moved/deleted after
    # enumeration but before inspection. That is a
    # snapshot race, not a control-plane failure.
    try:
        stat = path.stat()
    except OSError:
        return None

    keys = set()

    schema = None
    generated = None
    authority = None

    if path.suffix.lower() == ".json":

        (
            keys,
            schema,
            generated,
            authority,
        ) = json_metadata(path)

    controls = text_controls(
        path
    )

    for control, terms in (
        CONTROL_TERMS.items()
    ):

        if any(
            term in keys
            for term in terms
        ):
            controls.add(
                control
            )

    return RuntimeArtifactEvidence(
        lane=lane.lane,
        path=str(
            path.relative_to(ROOT)
        ),
        size_bytes=stat.st_size,
        age_seconds=artifact_age_seconds(
            path
        ),
        controls=tuple(
            sorted(
                controls
            )
        ),
        schema_version=schema,
        generated_at=generated,
        authority=authority,
    )


def systemd_units():

    command = [
        "systemctl",
        "list-unit-files",
        "--type=service",
        "--type=timer",
        "--no-legend",
        "--no-pager",
    ]

    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )

    units = []

    for line in result.stdout.splitlines():

        parts = line.split()

        if not parts:
            continue

        name = parts[0]

        if name.startswith(
            "empire-"
        ):
            units.append(name)

    return sorted(
        set(units)
    )


def unit_properties(
    unit: str,
):

    result = subprocess.run(
        [
            "systemctl",
            "show",
            unit,
            "--property=ActiveState",
            "--property=SubState",
            "--property=UnitFileState",
            "--property=ExecMainStatus",
            "--property=ExecStart",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    props = {}

    for line in result.stdout.splitlines():

        if "=" not in line:
            continue

        key, value = line.split(
            "=",
            1,
        )

        props[key] = value

    return props


def unit_controls(
    props,
):

    text = " ".join(
        str(value)
        for value in props.values()
    ).lower()

    found = set()

    for control, terms in (
        CONTROL_TERMS.items()
    ):

        if any(
            term in text
            for term in terms
        ):
            found.add(control)

    return found


def main():

    files = runtime_files()
    units = systemd_units()

    lanes = []

    for lane in LANES:

        lane_files = [
            path
            for path in files
            if runtime_matches_lane(
                path.relative_to(
                    ROOT
                ),
                lane,
            )
        ]

        artifacts = []

        for path in lane_files:

            item = artifact_evidence(
                lane,
                path,
            )

            if item is None:
                continue

            artifacts.append(
                item
            )

        lane_units = [
            unit
            for unit in units
            if systemd_matches_lane(
                unit,
                lane,
            )
        ]

        unit_evidence = []

        for unit in lane_units:

            props = unit_properties(
                unit
            )

            unit_evidence.append(
                RuntimeUnitEvidence(
                    lane=lane.lane,
                    unit=unit,
                    active_state=props.get(
                        "ActiveState",
                        "unknown",
                    ),
                    sub_state=props.get(
                        "SubState",
                        "unknown",
                    ),
                    unit_file_state=props.get(
                        "UnitFileState",
                        "unknown",
                    ),
                    exec_main_status=props.get(
                        "ExecMainStatus",
                        "unknown",
                    ),
                    controls=tuple(
                        sorted(
                            unit_controls(
                                props
                            )
                        )
                    ),
                )
            )

        active_units = [
            item
            for item in unit_evidence
            if item.active_state
            in {
                "active",
                "activating",
            }
        ]

        recent = [
            item
            for item in artifacts
            if item.age_seconds
            <= RECENT_SECONDS
        ]

        control_candidates = {
            control: {
                "artifact_paths": [],
                "unit_names": [],
            }
            for control in CONTROL_NAMES
        }

        for item in artifacts:

            for control in item.controls:

                if control in control_candidates:

                    control_candidates[
                        control
                    ][
                        "artifact_paths"
                    ].append(
                        item.path
                    )

        for item in unit_evidence:

            for control in item.controls:

                if control in control_candidates:

                    control_candidates[
                        control
                    ][
                        "unit_names"
                    ].append(
                        item.unit
                    )

        candidate_controls = [
            control
            for control, evidence
            in control_candidates.items()
            if (
                evidence[
                    "artifact_paths"
                ]
                or evidence[
                    "unit_names"
                ]
            )
        ]

        strength = (
            runtime_candidate_strength(
                artifact_count=len(
                    artifacts
                ),
                active_unit_count=len(
                    active_units
                ),
                recent_artifact_count=len(
                    recent
                ),
                control_candidate_count=len(
                    candidate_controls
                ),
            )
        )

        lanes.append(
            {
                "lane":
                    lane.lane,

                "candidate_strength":
                    strength,

                "artifact_count":
                    len(
                        artifacts
                    ),

                "recent_artifact_count":
                    len(
                        recent
                    ),

                "unit_count":
                    len(
                        unit_evidence
                    ),

                "active_unit_count":
                    len(
                        active_units
                    ),

                "candidate_control_count":
                    len(
                        candidate_controls
                    ),

                "candidate_controls":
                    candidate_controls,

                "control_candidates":
                    control_candidates,

                "artifacts":
                    [
                        item.as_dict()
                        for item
                        in sorted(
                            artifacts,
                            key=lambda x:
                                (
                                    x.age_seconds,
                                    x.path,
                                ),
                        )[:60]
                    ],

                "units":
                    [
                        item.as_dict()
                        for item
                        in unit_evidence
                    ],
            }
        )

    payload = {
        "schema_version":
            "empire-runtime-control-evidence-v1",

        "generated_at":
            now_iso(),

        "authority":
            "OBSERVE",

        "important":
            (
                "Candidate runtime evidence is not "
                "automatic control verification."
            ),

        "lanes":
            lanes,

        "governance": {
            "db_write":
                False,

            "outbound":
                False,

            "traffic":
                False,

            "funds":
                False,

            "automatic_verification":
                False,
        },
    }

    atomic_write(
        OUT,
        payload,
    )

    summary = []

    for lane in lanes:

        summary.append(
            {
                "lane":
                    lane[
                        "lane"
                    ],

                "strength":
                    lane[
                        "candidate_strength"
                    ],

                "artifacts":
                    lane[
                        "artifact_count"
                    ],

                "recent":
                    lane[
                        "recent_artifact_count"
                    ],

                "units":
                    lane[
                        "unit_count"
                    ],

                "active_units":
                    lane[
                        "active_unit_count"
                    ],

                "candidate_controls":
                    lane[
                        "candidate_control_count"
                    ],

                "controls":
                    lane[
                        "candidate_controls"
                    ],
            }
        )

    print(
        json.dumps(
            {
                "status":
                    "PASS",

                "summary":
                    summary,

                "authority":
                    "OBSERVE",

                "automatic_verification":
                    False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
