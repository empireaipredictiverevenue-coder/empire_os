# EMPIRE_WAVE_090B
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json
import time


CONTROL_KEYS = {
    "entity_classification": {
        "entity_type",
        "entity_classification",
        "classification",
        "record_type",
    },

    "canonical_identity": {
        "canonical_identity",
        "canonical_id",
        "canonical_domain",
        "canonical_person_id",
        "identity_fingerprint",
    },

    "duplicate_detection": {
        "duplicate_count",
        "duplicates",
        "dedupe_status",
        "deduplicated",
        "idempotency_key",
        "work_fingerprint",
        "identity_fingerprint",
        "canonical_event_id",
    },

    "input_quality": {
        "input_quality",
        "input_verdict",
        "input_validation",
        "input_valid",
        "validation_errors",
    },

    "output_quality": {
        "output_quality",
        "output_verdict",
        "output_validation",
        "output_valid",
    },

    "evidence_lineage": {
        "source_lineage",
        "provenance",
        "source_ids",
        "source_id",
        "evidence",
        "evidence_ids",
    },

    "conflict_detection": {
        "conflict_count",
        "conflicts",
        "contradictions",
        "reconciliation_status",
        "state_conflict",
    },

    "freshness": {
        "generated_at",
        "updated_at",
        "as_of",
        "observed_at",
        "timestamp",
    },

    "quarantine": {
        "quarantine",
        "quarantined",
        "quarantine_count",
        "hold_reason",
        "held_count",
        "reject_reason",
        "rejected_reason",
    },

    "action_authority": {
        "execution_authority",
        "action_allowed",
        "founder_gate",
        "send_authority",
    },

    "outcome_linkage": {
        "outcome",
        "outcome_id",
        "conversion_id",
        "realised_revenue",
        "realized_revenue",
        "order_id",
        "payment_id",
        "fulfilment_id",
        "fulfillment_id",
    },
}


META_KEYS = {
    "schema_version",
    "generated_at",
    "updated_at",
    "as_of",
    "timestamp",
}


MAX_AGE_SECONDS = (
    7
    * 24
    * 60
    * 60
)


@dataclass(frozen=True)
class AdjudicatedControl:
    lane: str
    control: str
    status: str
    confidence: float
    artifact_paths: tuple[str, ...]
    matched_keys: tuple[str, ...]
    active_units: tuple[str, ...]
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def recursive_keys(
    value: Any,
    *,
    depth: int = 0,
    max_depth: int = 5,
) -> set[str]:

    if depth > max_depth:
        return set()

    found = set()

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

        for child in value[:50]:

            found.update(
                recursive_keys(
                    child,
                    depth=depth + 1,
                    max_depth=max_depth,
                )
            )

    return found


def load_structured_runtime_artifact(
    root: Path,
    relative: str,
):

    path = (
        root
        / relative
    )

    try:
        resolved = path.resolve()
        runtime_root = (
            root
            / "runtime"
        ).resolve()

        if runtime_root not in (
            resolved,
            *resolved.parents,
        ):
            return None

        # Never use the control fabric's own conclusions
        # to prove another business lane.
        if "runtime/control_plane/" in (
            relative.replace("\\", "/")
        ):
            return None

        if (
            not path.is_file()
            or path.suffix.lower()
            != ".json"
        ):
            return None

        age = max(
            0,
            int(
                time.time()
                - path.stat().st_mtime
            ),
        )

        if age > MAX_AGE_SECONDS:
            return None

        value = json.loads(
            path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        )

        keys = recursive_keys(
            value
        )

        return {
            "path":
                relative,

            "age_seconds":
                age,

            "keys":
                keys,

            "has_contract_metadata":
                bool(
                    keys
                    & META_KEYS
                ),

            # EMPIRE_WAVE_091B_EFFECTIVENESS_GATE
            #
            # Optional semantic gate. A detector may exist
            # at runtime yet have zero useful production
            # coverage. When a control explicitly declares
            # itself ineffective, presence alone cannot
            # verify that control.
            "control_effectiveness":
                (
                    value.get(
                        "control_effectiveness"
                    )
                    if isinstance(
                        value,
                        dict,
                    )
                    else None
                ),
        }

    except Exception:
        return None


def adjudicate_control(
    *,
    root: Path,
    lane: str,
    control: str,
    artifact_paths: list[str],
    active_units: list[str],
) -> AdjudicatedControl:

    expected = CONTROL_KEYS[
        control
    ]

    proven = []
    matched = set()

    for relative in sorted(
        set(
            artifact_paths
        )
    ):

        item = (
            load_structured_runtime_artifact(
                root,
                relative,
            )
        )

        if not item:
            continue

        hits = (
            item[
                "keys"
            ]
            & expected
        )

        if not hits:
            continue

        if not item[
            "has_contract_metadata"
        ]:
            continue

        effectiveness = item.get(
            "control_effectiveness"
        )

        if isinstance(
            effectiveness,
            dict,
        ):

            declared = effectiveness.get(
                control
            )

            if declared is False:
                continue

        proven.append(
            relative
        )

        matched.update(
            hits
        )

    active_units = sorted(
        set(
            active_units
        )
    )

    if proven:

        confidence = (
            0.99
            if active_units
            else 0.96
        )

        return AdjudicatedControl(
            lane=lane,
            control=control,
            status="VERIFIED_RUNTIME",
            confidence=confidence,
            artifact_paths=tuple(
                proven
            ),
            matched_keys=tuple(
                sorted(
                    matched
                )
            ),
            active_units=tuple(
                active_units
            ),
            reason=(
                "recent_structured_runtime_artifact_"
                "with_exact_control_signature"
            ),
        )

    return AdjudicatedControl(
        lane=lane,
        control=control,
        status="UNVERIFIED",
        confidence=0.0,
        artifact_paths=(),
        matched_keys=(),
        active_units=tuple(
            active_units
        ),
        reason=(
            "no_recent_structured_runtime_artifact_"
            "with_exact_control_signature"
        ),
    )
