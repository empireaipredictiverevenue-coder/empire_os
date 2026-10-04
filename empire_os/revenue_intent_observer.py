"""Community Intent -> governed Revenue Actor boundary.

The actor router consumes a mapping:

    signal_id -> {
        source: "*_intent",
        status: "unresolved" | "needs_review",
        raw: {
            community_intent: {...}
        }
    }

This module adapts Community Intent observations to that existing
transport contract. It does not grant commercial authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


_ROW_KEYS = {
    "signal_id",
    "observation_id",
    "source_id",
    "id",
    "title",
    "text",
    "body",
    "content",
    "snippet",
    "description",
    "source_url",
    "url",
    "source",
    "platform",
    "niche",
    "observed_at",
}


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _canonical_hash(
    row: Mapping[str, Any],
) -> str:
    raw = json.dumps(
        dict(row),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")

    return hashlib.sha256(
        raw
    ).hexdigest()


def _row_score(
    row: Mapping[str, Any],
) -> int:
    return sum(
        1
        for key in _ROW_KEYS
        if key in row
        and row.get(key) not in (
            None,
            "",
            [],
            {},
        )
    )


def _candidate_lists(
    value: Any,
    path: str = "$",
) -> list[
    tuple[
        str,
        list[dict[str, Any]],
    ]
]:
    found = []

    if isinstance(value, Mapping):
        for key, child in value.items():
            found.extend(
                _candidate_lists(
                    child,
                    f"{path}.{key}",
                )
            )

    elif isinstance(value, list):
        rows = [
            dict(item)
            for item in value
            if isinstance(
                item,
                Mapping,
            )
        ]

        if rows:
            found.append(
                (
                    path,
                    rows,
                )
            )

        for index, child in enumerate(
            value
        ):
            found.extend(
                _candidate_lists(
                    child,
                    f"{path}[{index}]",
                )
            )

    return found


def extract_observations(
    payload: Mapping[str, Any],
) -> tuple[
    list[dict[str, Any]],
    str,
]:
    candidates = _candidate_lists(
        payload
    )

    if not candidates:
        return [], ""

    expected = payload.get(
        "observations"
    )

    expected_count = (
        expected
        if isinstance(
            expected,
            int,
        )
        and expected >= 0
        else None
    )

    ranked = []

    for path, rows in candidates:
        useful = [
            row
            for row in rows
            if _row_score(row) >= 2
        ]

        if not useful:
            continue

        exact_count = (
            1
            if (
                expected_count is not None
                and len(useful)
                == expected_count
            )
            else 0
        )

        average_score = (
            sum(
                _row_score(row)
                for row in useful
            )
            / len(useful)
        )

        ranked.append(
            (
                exact_count,
                len(useful),
                average_score,
                path,
                useful,
            )
        )

    if not ranked:
        return [], ""

    ranked.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
            item[3],
        ),
        reverse=True,
    )

    best = ranked[0]

    return (
        best[4],
        best[3],
    )


def _signal_id(
    row: Mapping[str, Any],
) -> str:
    observed = (
        row.get("signal_id")
        or row.get("observation_id")
        or row.get("source_id")
        or row.get("id")
    )

    if observed:
        return str(observed)

    return (
        "community:"
        + _canonical_hash(row)[:24]
    )


def _signal_source(
    row: Mapping[str, Any],
) -> str:
    source = _clean(
        row.get("source")
        or row.get("platform")
    ).lower()

    if source.endswith("_intent"):
        return source

    # Transport source only. The Intent Brain still decides
    # whether the content represents real buyer intent.
    return "community_intent"


def _community_payload(
    original: Mapping[str, Any],
    signal_id: str,
) -> dict[str, Any]:
    row = dict(original)

    row["signal_id"] = signal_id

    if not _clean(
        row.get("text")
    ):
        text = (
            row.get("body")
            or row.get("content")
            or row.get("snippet")
            or row.get("description")
            or row.get("title")
        )

        if text:
            row["text"] = str(text)

    if not _clean(
        row.get("url")
    ):
        url = row.get(
            "source_url"
        )

        if url:
            row["url"] = str(url)

    evidence_urls = row.get(
        "evidence_urls"
    )

    if not isinstance(
        evidence_urls,
        list,
    ):
        evidence_urls = []

    url = _clean(
        row.get("url")
    )

    if (
        url
        and url not in evidence_urls
    ):
        evidence_urls.append(
            url
        )

    row[
        "evidence_urls"
    ] = evidence_urls

    return row


def normalize_community_intent(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    rows, source_path = (
        extract_observations(
            payload
        )
    )

    signals: dict[
        str,
        dict[str, Any],
    ] = {}

    for original in rows:
        signal_id = _signal_id(
            original
        )

        if signal_id in signals:
            continue

        community = _community_payload(
            original,
            signal_id,
        )

        source = _signal_source(
            original
        )

        status = _clean(
            original.get("status")
        ).lower()

        if status not in {
            "unresolved",
            "needs_review",
        }:
            status = "unresolved"

        url = _clean(
            community.get("url")
        )

        niche = (
            community.get("niche")
        )

        observed_at = (
            original.get(
                "observed_at"
            )
            or original.get(
                "last_seen_at"
            )
            or original.get(
                "created_at"
            )
        )

        envelope = {
            "signal_id":
                signal_id,
            "source":
                source,
            "status":
                status,
            "niche":
                niche,
            "url":
                url or None,
            "created_at":
                observed_at,
            "last_seen_at":
                observed_at,
            "raw": {
                "community_intent":
                    community,
                "evidence_urls":
                    list(
                        community.get(
                            "evidence_urls",
                            [],
                        )
                    ),
            },
        }

        signals[
            signal_id
        ] = envelope

    return {
        "schema_version":
            "empire.revenue_intent_normalization.v2",
        "source_schema_version":
            payload.get(
                "schema_version"
            ),
        "source_collection_path":
            source_path,
        "observation_count":
            len(signals),
        "mode":
            "OBSERVE",
        "execution_authority":
            "none",
        "signals":
            signals,
    }


def normalize_file(
    source: Path,
    destination: Path,
) -> dict[str, Any]:
    payload = json.loads(
        source.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        payload,
        Mapping,
    ):
        raise ValueError(
            "Community Intent payload must be an object"
        )

    report = normalize_community_intent(
        payload
    )

    signals = report[
        "signals"
    ]

    if not signals:
        raise ValueError(
            "No Community Intent observations discovered"
        )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = (
        destination.parent
        / (
            destination.name
            + ".tmp"
        )
    )

    # IMPORTANT:
    # run_intent_actor_cycle expects the file itself
    # to be signal_id -> signal envelope.
    temporary.write_text(
        json.dumps(
            signals,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary.replace(
        destination
    )

    return report
