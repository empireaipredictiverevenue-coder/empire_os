from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any


SEVERITY = {
    "INFO": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


@dataclass
class ControlSignal:
    code: str
    severity: str
    entity: str
    source: str
    reason: str
    evidence: list[str] = field(
        default_factory=list
    )
    recommendation: str = "OBSERVE"
    blocks_entity: bool = False

    def as_dict(self):
        return asdict(self)


def normalize_text(
    value: Any,
) -> str:

    return " ".join(
        str(
            value
            or ""
        )
        .lower()
        .split()
    )


def signal_fingerprint(
    signal: ControlSignal,
) -> str:

    raw = "|".join(
        (
            normalize_text(
                signal.entity
            ),
            normalize_text(
                signal.code
            ),
            normalize_text(
                signal.reason
            ),
        )
    )

    return sha256(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()


def fuse_signals(
    signals: list[ControlSignal],
) -> list[dict[str, Any]]:

    fused: dict[
        str,
        dict[str, Any],
    ] = {}

    for signal in signals:

        key = signal_fingerprint(
            signal
        )

        if key not in fused:

            fused[key] = {
                "fingerprint":
                    key,

                "code":
                    signal.code,

                "severity":
                    signal.severity,

                "entity":
                    signal.entity,

                "reason":
                    signal.reason,

                "sources":
                    set(),

                "evidence":
                    set(),

                "recommendations":
                    set(),

                "blocks_entity":
                    signal.blocks_entity,
            }

        item = fused[key]

        item[
            "sources"
        ].add(
            signal.source
        )

        item[
            "evidence"
        ].update(
            str(value)
            for value
            in signal.evidence
            if value is not None
        )

        item[
            "recommendations"
        ].add(
            signal.recommendation
        )

        item[
            "blocks_entity"
        ] = bool(
            item[
                "blocks_entity"
            ]
            or signal.blocks_entity
        )

        if (
            SEVERITY.get(
                signal.severity,
                0,
            )
            >
            SEVERITY.get(
                item[
                    "severity"
                ],
                0,
            )
        ):
            item[
                "severity"
            ] = signal.severity

    output = []

    for item in fused.values():

        output.append(
            {
                "fingerprint":
                    item[
                        "fingerprint"
                    ],

                "code":
                    item[
                        "code"
                    ],

                "severity":
                    item[
                        "severity"
                    ],

                "entity":
                    item[
                        "entity"
                    ],

                "reason":
                    item[
                        "reason"
                    ],

                "sources":
                    sorted(
                        item[
                            "sources"
                        ]
                    ),

                "source_independence_count":
                    len(
                        item[
                            "sources"
                        ]
                    ),

                "evidence":
                    sorted(
                        item[
                            "evidence"
                        ]
                    ),

                "recommendations":
                    sorted(
                        item[
                            "recommendations"
                        ]
                    ),

                "blocks_entity":
                    item[
                        "blocks_entity"
                    ],
            }
        )

    output.sort(
        key=lambda item: (
            -SEVERITY.get(
                item[
                    "severity"
                ],
                0,
            ),
            item[
                "entity"
            ],
            item[
                "code"
            ],
        )
    )

    return output


def entity_risk(
    fused: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    entities: dict[
        str,
        dict[str, Any],
    ] = {}

    for signal in fused:

        entity = (
            signal.get(
                "entity"
            )
            or "__system__"
        )

        current = entities.setdefault(
            entity,
            {
                "entity":
                    entity,

                "max_severity":
                    "INFO",

                "signal_count":
                    0,

                "blocking_signal_count":
                    0,

                "codes":
                    set(),
            },
        )

        current[
            "signal_count"
        ] += 1

        current[
            "codes"
        ].add(
            signal[
                "code"
            ]
        )

        if signal.get(
            "blocks_entity"
        ):

            current[
                "blocking_signal_count"
            ] += 1

        if (
            SEVERITY.get(
                signal[
                    "severity"
                ],
                0,
            )
            >
            SEVERITY.get(
                current[
                    "max_severity"
                ],
                0,
            )
        ):

            current[
                "max_severity"
            ] = signal[
                "severity"
            ]

    output = []

    for item in entities.values():

        output.append(
            {
                "entity":
                    item[
                        "entity"
                    ],

                "max_severity":
                    item[
                        "max_severity"
                    ],

                "signal_count":
                    item[
                        "signal_count"
                    ],

                "blocking_signal_count":
                    item[
                        "blocking_signal_count"
                    ],

                "codes":
                    sorted(
                        item[
                            "codes"
                        ]
                    ),

                "held":
                    bool(
                        item[
                            "blocking_signal_count"
                        ]
                    ),
            }
        )

    output.sort(
        key=lambda item: (
            -SEVERITY.get(
                item[
                    "max_severity"
                ],
                0,
            ),
            -item[
                "blocking_signal_count"
            ],
            item[
                "entity"
            ],
        )
    )

    return output


def duplicate_keys(
    records: list[dict[str, Any]],
    *,
    key: str,
) -> dict[str, int]:

    counts = {}

    for record in records:

        value = str(
            record.get(
                key
            )
            or ""
        ).strip().lower()

        if not value:
            continue

        counts[
            value
        ] = (
            counts.get(
                value,
                0,
            )
            + 1
        )

    return {
        value:
            count

        for value, count
        in counts.items()

        if count > 1
    }


def task_collisions(
    tasks: list[dict[str, Any]],
) -> dict[str, list[str]]:

    fingerprints = {}

    for task in tasks:

        fingerprint = str(
            task.get(
                "work_fingerprint"
            )
            or task.get(
                "canonical_task_id"
            )
            or ""
        ).strip()

        task_id = str(
            task.get(
                "task_id"
            )
            or ""
        ).strip()

        if (
            not fingerprint
            or not task_id
        ):
            continue

        fingerprints.setdefault(
            fingerprint,
            [],
        ).append(
            task_id
        )

    return {
        fingerprint:
            sorted(
                set(
                    ids
                )
            )

        for fingerprint, ids
        in fingerprints.items()

        if len(
            set(ids)
        ) > 1
    }


def double_counted_events(
    events: list[dict[str, Any]],
) -> dict[str, int]:

    counts = {}

    for event in events:

        identity = str(
            event.get(
                "canonical_event_id"
            )
            or event.get(
                "economic_event_id"
            )
            or ""
        ).strip()

        if not identity:
            continue

        counts[
            identity
        ] = (
            counts.get(
                identity,
                0,
            )
            + 1
        )

    return {
        identity:
            count

        for identity, count
        in counts.items()

        if count > 1
    }


def lane_verdict(
    gaps: list[dict[str, Any]],
) -> str:

    if any(
        item.get(
            "severity"
        )
        == "CRITICAL"

        for item in gaps
    ):
        return "BLOCK"

    if any(
        item.get(
            "severity"
        )
        == "HIGH"

        for item in gaps
    ):
        return "HOLD_FOR_REMEDIATION"

    if gaps:
        return "PASS_WITH_WARNINGS"

    return "PASS"
