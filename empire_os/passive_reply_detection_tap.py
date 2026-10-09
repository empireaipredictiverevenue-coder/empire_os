from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from empire_os.conversations_replies_control import (
    adjudicate_records,
)


ROOT = Path("/srv/empire_os")

OUT = (
    ROOT
    / "runtime/conversations_replies_control/"
      "passive_reply_tap_latest.json"
)


def _atomic_write(payload: dict[str, Any]) -> None:
    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = OUT.with_suffix(".tmp")

    tmp.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    tmp.replace(OUT)


def observe_reply(
    *,
    message_id: str,
    thread_id: str,
    identity: str,
    classification: str | None = None,
    received_at: str | None = None,
    direction: str = "inbound",
    source: str = "production-reply-runtime",
) -> dict[str, Any]:
    """
    Passive observation only.

    The raw identifiers exist only for this function
    call. Existing conversations/replies control
    canonicalises/hashes them.

    No mailbox call.
    No provider call.
    No DB write.
    No outbound.
    No action authority.
    """

    if not message_id:
        raise ValueError(
            "message_id required"
        )

    if not thread_id:
        raise ValueError(
            "thread_id required"
        )

    if not identity:
        raise ValueError(
            "identity required"
        )

    row: dict[str, Any] = {
        "message_id":
            str(message_id),

        "thread_id":
            str(thread_id),

        "canonical_id":
            str(identity),

        "direction":
            str(direction),
    }

    if classification:
        row[
            "classification"
        ] = str(
            classification
        )

    if received_at:
        row[
            "received_at"
        ] = str(
            received_at
        )

    result = adjudicate_records(
        [
            (
                str(source),
                row,
            )
        ]
    )

    result[
        "passive_tap"
    ] = {
        "schema_version":
            "empire-passive-reply-tap-v1",

        "observed_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "source":
            str(source),

        "live_event_observed":
            True,

        "provider_invoked":
            False,

        "mailbox_invoked":
            False,

        "action_authority_granted":
            False,
    }

    result.setdefault(
        "governance",
        {}
    ).update(
        {
            "authority":
                "OBSERVE",

            "action_authority_granted":
                False,

            "provider_invoked":
                False,

            "mailbox_invoked":
                False,

            "mailbox_write":
                False,

            "db_write":
                False,

            "outbound":
                False,

            "raw_message_id_persisted":
                False,

            "raw_thread_id_persisted":
                False,

            "raw_identity_persisted":
                False,

            "raw_message_content_persisted":
                False,
        }
    )

    serialized = json.dumps(
        result,
        sort_keys=True,
    )

    # Fail closed if the existing control ever starts
    # leaking raw values into its persistent result.
    for raw in (
        str(message_id),
        str(thread_id),
        str(identity),
    ):
        if (
            len(raw) >= 6
            and raw in serialized
        ):
            raise RuntimeError(
                "passive tap raw identifier persistence detected"
            )

    _atomic_write(
        result
    )

    return result

# EMPIRE_PASSIVE_MAPPING_OBSERVER_092D4

_DIAGNOSTIC_OUT = (
    ROOT
    / "runtime/conversations_replies_control/"
      "passive_reply_tap_diagnostic_latest.json"
)


def _mapping_value(
    mapping: dict[str, Any],
    names: tuple[str, ...],
):
    folded = {
        str(k).casefold(): v
        for k, v in mapping.items()
    }

    for name in names:
        value = folded.get(
            name.casefold()
        )

        if value not in (
            None,
            "",
            [],
            {},
        ):
            if isinstance(
                value,
                (
                    str,
                    int,
                    float,
                ),
            ):
                return str(value)

    return None


def observe_reply_mapping(
    mapping: dict[str, Any],
    *,
    classification: str | None = None,
    direction: str = "inbound",
    source: str = "gmail-reply-runtime",
) -> dict[str, Any]:
    """
    Accept the existing correlated production object.

    No provider read is performed here. The mapping
    must already exist in the normal reply runtime.
    """

    if not isinstance(
        mapping,
        dict,
    ):
        raise ValueError(
            "correlated reply mapping required"
        )

    message_id = _mapping_value(
        mapping,
        (
            "message_id",
            "provider_message_id",
            "gmail_message_id",
            "external_message_id",
            "inbound_message_id",
        ),
    )

    thread_id = _mapping_value(
        mapping,
        (
            "thread_id",
            "provider_thread_id",
            "gmail_thread_id",
            "conversation_id",
        ),
    )

    identity = _mapping_value(
        mapping,
        (
            "canonical_id",
            "person_id",
            "contact_id",
            "lead_id",
            "sender_email",
            "from_email",
            "email",
        ),
    )

    mapped_classification = _mapping_value(
        mapping,
        (
            "classification",
            "reply_classification",
            "reply_type",
            "intent",
            "sentiment",
            "disposition",
            "outcome",
        ),
    )

    received_at = _mapping_value(
        mapping,
        (
            "received_at",
            "sent_at",
            "created_at",
            "timestamp",
        ),
    )

    if not (
        message_id
        and thread_id
        and identity
    ):
        raise ValueError(
            "correlated mapping lacks complete "
            "message/thread/identity tuple"
        )

    return observe_reply(
        message_id=message_id,
        thread_id=thread_id,
        identity=identity,
        classification=(
            classification
            or mapped_classification
        ),
        received_at=received_at,
        direction=direction,
        source=source,
    )


def safe_observe_reply_mapping(
    mapping: dict[str, Any],
    *,
    classification: str | None = None,
    direction: str = "inbound",
    source: str = "gmail-reply-runtime",
) -> dict[str, Any]:
    """
    Passive observer failures must never alter the
    production reply-processing result.
    """

    try:
        result = observe_reply_mapping(
            mapping,
            classification=classification,
            direction=direction,
            source=source,
        )

        return {
            "observed": True,
            "error_type": None,
            "canonical_message_count":
                result.get(
                    "semantic_effectiveness",
                    {},
                ).get(
                    "canonical_message_count",
                    0,
                ),
        }

    except Exception as exc:
        diagnostic = {
            "schema_version":
                "empire-passive-reply-tap-diagnostic-v1",

            "observed_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "mode":
                "OBSERVE",

            # Exception TYPE only.
            # Never persist provider data or exception
            # text that might contain PII.
            "observed":
                False,

            "error_type":
                type(exc).__name__,

            "source":
                str(source),

            "governance": {
                "provider_invoked":
                    False,

                "mailbox_invoked":
                    False,

                "mailbox_write":
                    False,

                "db_write":
                    False,

                "outbound":
                    False,

                "action_authority_granted":
                    False,
            },
        }

        _DIAGNOSTIC_OUT.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        tmp = _DIAGNOSTIC_OUT.with_suffix(
            ".tmp"
        )

        tmp.write_text(
            json.dumps(
                diagnostic,
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )

        tmp.replace(
            _DIAGNOSTIC_OUT
        )

        return {
            "observed": False,
            "error_type":
                type(exc).__name__,
        }
