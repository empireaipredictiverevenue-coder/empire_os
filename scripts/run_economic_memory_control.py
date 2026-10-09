# EMPIRE_WAVE_091B
from __future__ import annotations

import json
from pathlib import Path

from empire_os.economic_memory_control import (
    build_control,
)


ROOT = Path("/srv/empire_os")

BINDING = (
    ROOT
    / "runtime/control_plane/"
      "economic_memory_binding_truth_latest.json"
)

OUT = (
    ROOT
    / "runtime/economic_memory_control/"
      "latest.json"
)


def atomic_write(
    path,
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
        )
        + "\n",
        encoding="utf-8",
    )

    tmp.replace(path)


def main():

    truth = json.loads(
        BINDING.read_text()
    )

    sources = []

    seen = set()

    for item in truth.get(
        "existing_runtime_candidates",
        [],
    ):

        relative = item.get(
            "path"
        )

        if not relative:
            continue

        relative = relative.replace(
            "\\",
            "/",
        )

        # Never let the control plane prove itself.
        if relative.startswith(
            "runtime/control_plane/"
        ):
            continue

        if relative.startswith(
            "runtime/economic_memory_control/"
        ):
            continue

        if relative in seen:
            continue

        seen.add(relative)

        path = (
            ROOT
            / relative
        )

        try:

            resolved = path.resolve()

            runtime_root = (
                ROOT
                / "runtime"
            ).resolve()

            if runtime_root not in (
                resolved,
                *resolved.parents,
            ):
                continue

            if not path.is_file():
                continue

            if path.suffix.casefold() != ".json":
                continue

            value = json.loads(
                path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            )

        except (
            OSError,
            json.JSONDecodeError,
        ):
            continue

        sources.append(
            (
                relative,
                value,
            )
        )

    payload = build_control(
        sources
    )

    payload[
        "source_runtime_artifact_count"
    ] = len(
        sources
    )

    atomic_write(
        OUT,
        payload,
    )

    print(
        json.dumps(
            {
                "status":
                    (
                        "PASS"
                        if payload[
                            "semantic_effectiveness"
                        ][
                            "effective"
                        ]
                        else "HOLD"
                    ),

                "runtime_sources":
                    len(
                        sources
                    ),

                "candidate_events":
                    payload[
                        "semantic_effectiveness"
                    ][
                        "candidate_event_count"
                    ],

                "canonical_events":
                    payload[
                        "semantic_effectiveness"
                    ][
                        "canonical_event_count"
                    ],

                "duplicates":
                    payload[
                        "duplicate_detection"
                    ][
                        "duplicate_count"
                    ],

                "conflicts":
                    payload[
                        "conflict_detection"
                    ][
                        "conflict_count"
                    ],

                "quarantine":
                    payload[
                        "quarantine"
                    ][
                        "quarantine_count"
                    ],

                "outcome_links":
                    payload[
                        "semantic_effectiveness"
                    ][
                        "outcome_link_count"
                    ],

                "memory_write":
                    False,

                "mode":
                    "OBSERVE",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
