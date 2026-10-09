# EMPIRE_WAVE_090C_D1
from __future__ import annotations

from hashlib import sha256
from typing import Any
import json
import re


TRACE_COLUMNS = (
    "message_id",
    "thread_id",
    "send_id",
    "outbound_id",
)


EVENT_MAP = (
    (
        "UNSUBSCRIBE_OPT_OUT",
        (
            "unsubscribe",
            "unsubscribed",
            "opt_out",
            "optout",
            "opted_out",
            "do_not_contact",
            "do_not_call",
            "dnc",
        ),
    ),
    (
        "BOUNCE",
        (
            "hard_bounce",
            "soft_bounce",
            "bounced",
            "bounce",
        ),
    ),
    (
        "COMPLAINT",
        (
            "spam_complaint",
            "complaint",
            "reported_spam",
        ),
    ),
    (
        "REPLY",
        (
            "inbound_reply",
            "replied",
            "reply",
        ),
    ),
    (
        "DELIVERY",
        (
            "delivered",
            "delivery",
        ),
    ),
)


def stable_hash(
    value: str,
) -> str:

    return sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()


def normalize_token(
    value: Any,
) -> str:

    return re.sub(
        r"[^a-z0-9]+",
        "_",
        str(
            value
        ).strip().casefold(),
    ).strip("_")


def truthy(
    value: Any,
) -> bool:

    if value is True:
        return True

    if value is False:
        return False

    text = normalize_token(
        value
    )

    return text in {
        "1",
        "true",
        "yes",
        "y",
        "active",
    }


def classify_outcome(
    row: dict[str, Any],
) -> str | None:

    # First, explicit value semantics.
    for key, value in row.items():

        if value is None:
            continue

        key_token = normalize_token(
            key
        )

        value_token = normalize_token(
            value
        )

        combined = (
            key_token
            + "_"
            + value_token
        )

        for outcome, tokens in EVENT_MAP:

            for token in tokens:

                token = normalize_token(
                    token
                )

                if (
                    value_token == token
                    or combined.endswith(
                        "_" + token
                    )
                    or (
                        token in key_token
                        and truthy(value)
                    )
                ):
                    return outcome

    return None


def trace_values(
    row: dict[str, Any],
):

    result = []

    lower = {
        str(key).casefold():
            value
        for key, value in row.items()
    }

    for name in TRACE_COLUMNS:

        value = lower.get(
            name
        )

        if value in (
            None,
            "",
        ):
            continue

        result.append(
            (
                name,
                str(value),
            )
        )

    return result


def source_event_fingerprint(
    *,
    table: str,
    row: dict[str, Any],
) -> str:

    explicit = None

    lower = {
        str(key).casefold():
            value
        for key, value in row.items()
    }

    for key in (
        "event_id",
        "id",
        "message_id",
        "provider_event_id",
        "webhook_event_id",
    ):

        value = lower.get(
            key
        )

        if value not in (
            None,
            "",
        ):
            explicit = (
                key
                + ":"
                + str(value)
            )
            break

    if explicit is None:

        explicit = json.dumps(
            row,
            sort_keys=True,
            default=str,
            separators=(
                ",",
                ":",
            ),
        )

    return stable_hash(
        table
        + ":"
        + explicit
    )
