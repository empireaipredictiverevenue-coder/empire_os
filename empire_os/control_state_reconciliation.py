from __future__ import annotations

from hashlib import sha256
from typing import Any, Iterable


SYSTEM_ENTITIES = {
    "__system__",
    "__unknown__",
    "",
}


def normalize_entity(
    value: Any,
) -> str:

    return str(
        value
        or ""
    ).strip().lower()


def active_entity_set(
    entity_type_payload: dict[str, Any],
) -> set[str]:

    result = set()

    for item in entity_type_payload.get(
        "decisions",
        [],
    ):

        identity = normalize_entity(
            item.get(
                "canonical"
            )
            or item.get(
                "raw"
            )
        )

        if identity:
            result.add(
                identity
            )

    return result


def entity_generation_id(
    entity_type_payload: dict[str, Any],
) -> str:

    rows = []

    for item in entity_type_payload.get(
        "decisions",
        [],
    ):

        canonical = normalize_entity(
            item.get(
                "canonical"
            )
            or item.get(
                "raw"
            )
        )

        if not canonical:
            continue

        rows.append(
            "|".join(
                (
                    canonical,
                    str(
                        item.get(
                            "entity_type"
                        )
                        or ""
                    ),
                    str(
                        bool(
                            item.get(
                                "lane_allowed"
                            )
                        )
                    ),
                    str(
                        bool(
                            item.get(
                                "quarantine"
                            )
                        )
                    ),
                )
            )
        )

    raw = "\n".join(
        sorted(
            rows
        )
    )

    return sha256(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()[:24]


def partition_control_signals(
    signals: Iterable[Any],
    active_entities: set[str],
):

    current = []
    historical = []

    for signal in signals:

        entity = normalize_entity(
            getattr(
                signal,
                "entity",
                "",
            )
        )

        if (
            entity in SYSTEM_ENTITIES
            or entity in active_entities
        ):
            current.append(
                signal
            )

        else:
            historical.append(
                signal
            )

    return (
        current,
        historical,
    )


def stale_entity_counts(
    signals: Iterable[Any],
    active_entities: set[str],
) -> dict[str, int]:

    counts: dict[
        str,
        int,
    ] = {}

    for signal in signals:

        entity = normalize_entity(
            getattr(
                signal,
                "entity",
                "",
            )
        )

        if (
            not entity
            or entity in SYSTEM_ENTITIES
            or entity in active_entities
        ):
            continue

        counts[
            entity
        ] = (
            counts.get(
                entity,
                0,
            )
            + 1
        )

    return dict(
        sorted(
            counts.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        )
    )
