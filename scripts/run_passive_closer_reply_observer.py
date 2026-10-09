#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from empire_os.closer_role_transport import (
    PostgresCloserRpc,
    ROLE_FUNCTIONS,
)
from empire_os.passive_reply_detection_tap import (
    safe_observe_reply_mapping,
)

ROOT = Path("/srv/empire_os")
OUT = (
    ROOT
    / "runtime/conversations_replies_control/"
      "passive_closer_reply_observer_latest.json"
)

ROLE = "empire_closer_planner"

MESSAGE_KEYS = (
    "message_id",
    "provider_message_id",
    "gmail_message_id",
    "inbound_message_id",
    "reply_message_id",
    "reply_id",
)

THREAD_KEYS = (
    "thread_id",
    "provider_thread_id",
    "gmail_thread_id",
    "conversation_id",
)

IDENTITY_KEYS = (
    "canonical_id",
    "person_id",
    "contact_id",
    "lead_id",
    "sender_email",
    "from_email",
    "email",
)

CLASS_KEYS = (
    "classification",
    "reply_classification",
    "reply_type",
    "intent",
    "sentiment",
    "disposition",
    "outcome",
)

TIME_KEYS = (
    "received_at",
    "sent_at",
    "created_at",
    "occurred_at",
    "timestamp",
)


def atomic(payload: dict[str, Any]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(OUT)


def flatten(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    if isinstance(value, Mapping):
        row = dict(value)
        rows.append(row)

        for v in row.values():
            if isinstance(v, (Mapping, list, tuple)):
                rows.extend(flatten(v))

    elif isinstance(value, (list, tuple)):
        for item in value:
            rows.extend(flatten(item))

    return rows


def lookup(mapping: Mapping[str, Any], names) -> Any:
    folded = {
        str(k).casefold(): v
        for k, v in mapping.items()
    }

    for name in names:
        value = folded.get(name.casefold())
        if value not in (None, "", [], {}):
            return value

    return None


def read_only_rpc(name: str) -> tuple[str, tuple[str, ...]]:
    sql_text, keys = ROLE_FUNCTIONS[ROLE][name]

    low = str(sql_text).strip().casefold()

    if not low.startswith("select"):
        raise RuntimeError(
            f"{name} is not SELECT-only"
        )

    forbidden = (
        " insert ",
        " update ",
        " delete ",
        " truncate ",
        " alter ",
        " create ",
        " drop ",
    )

    padded = " " + low + " "

    if any(x in padded for x in forbidden):
        raise RuntimeError(
            f"{name} contains mutating SQL"
        )

    return str(sql_text), tuple(keys)


def list_params(keys: tuple[str, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    for key in keys:
        low = key.casefold()

        if "limit" in low:
            out[key] = 100
        elif "offset" in low:
            out[key] = 0
        elif any(x in low for x in ("status", "state")):
            out[key] = None
        else:
            raise RuntimeError(
                f"unresolved safe list parameter: {key}"
            )

    return out


def context_params(
    keys: tuple[str, ...],
    row: Mapping[str, Any],
) -> dict[str, Any] | None:

    aliases = {
        "case_id": (
            "case_id",
            "closer_case_id",
        ),
        "conversation_id": (
            "conversation_id",
            "thread_id",
        ),
        "thread_id": (
            "thread_id",
            "conversation_id",
        ),
        "message_id": (
            "message_id",
            "reply_message_id",
            "inbound_message_id",
        ),
        "reply_id": (
            "reply_id",
            "inbound_reply_id",
        ),
    }

    result: dict[str, Any] = {}

    for key in keys:
        low = key.casefold()
        semantic = low[2:] if low.startswith("p_") else low

        names = aliases.get(
            semantic,
            (semantic,),
        )

        value = lookup(row, names)

        if value is None:
            return None

        result[key] = value

    return result


def main() -> int:
    base = {
        "schema_version":
            "empire-passive-closer-reply-observer-v1",

        "generated_at":
            datetime.now(timezone.utc).isoformat(),

        "mode":
            "OBSERVE",

        "mailbox_invoked":
            False,

        "provider_invoked":
            False,

        "db_write":
            False,

        "outbound":
            False,

        "action_authority_granted":
            False,
    }

    dsn = os.getenv(
        "EMPIRE_CLOSER_PLANNER_DSN",
        "",
    ).strip()

    if not dsn:
        base.update(
            status="NO_CLOSER_DSN",
            observed=0,
        )
        atomic(base)
        print("STATUS: NO_CLOSER_DSN")
        return 0

    try:
        _, list_keys = read_only_rpc(
            "list_closer_work"
        )

        _, context_keys = read_only_rpc(
            "get_closer_reply_context"
        )

        rpc = PostgresCloserRpc(
            dsn,
            ROLE,
        )

        work = rpc(
            "list_closer_work",
            list_params(list_keys),
        )

        initial_rows = flatten(work)

        observed = 0
        context_reads = 0
        complete_candidates = 0
        sampled_key_sets = []

        for original in initial_rows[:200]:
            row = dict(original)

            if len(sampled_key_sets) < 12:
                sampled_key_sets.append(
                    sorted(
                        str(x)
                        for x in row.keys()
                    )
                )

            params = context_params(
                context_keys,
                row,
            )

            if params is not None:
                try:
                    context = rpc(
                        "get_closer_reply_context",
                        params,
                    )
                    context_reads += 1

                    contexts = flatten(context)

                    for part in contexts:
                        row.update(part)

                except Exception:
                    # Read enrichment is optional;
                    # never break observer execution.
                    pass

            message = lookup(
                row,
                MESSAGE_KEYS,
            )

            thread = lookup(
                row,
                THREAD_KEYS,
            )

            identity = lookup(
                row,
                IDENTITY_KEYS,
            )

            if not (
                message
                and thread
                and identity
            ):
                continue

            complete_candidates += 1

            mapping = {
                "message_id":
                    str(message),

                "thread_id":
                    str(thread),

                "canonical_id":
                    str(identity),

                "direction":
                    "inbound",
            }

            classification = lookup(
                row,
                CLASS_KEYS,
            )

            timestamp = lookup(
                row,
                TIME_KEYS,
            )

            if classification is not None:
                mapping[
                    "classification"
                ] = str(classification)

            if timestamp is not None:
                mapping[
                    "received_at"
                ] = str(timestamp)

            result = safe_observe_reply_mapping(
                mapping,
                direction="inbound",
                source=(
                    "closer_rpc:"
                    "get_closer_reply_context"
                ),
            )

            if result.get("observed"):
                observed += 1

        status = (
            "VERIFIED_RUNTIME"
            if observed
            else "NO_COMPLETE_REPLY_IDENTITY"
        )

        base.update(
            {
                "status":
                    status,

                "list_closer_work_rows":
                    len(initial_rows),

                "context_reads":
                    context_reads,

                "complete_candidates":
                    complete_candidates,

                "observed":
                    observed,

                # Only field names, never values.
                "sampled_key_sets":
                    sampled_key_sets,
            }
        )

        atomic(base)

        print("STATUS:", status)
        print(
            "WORK_ROWS:",
            len(initial_rows),
        )
        print(
            "CONTEXT_READS:",
            context_reads,
        )
        print(
            "COMPLETE_CANDIDATES:",
            complete_candidates,
        )
        print(
            "OBSERVED:",
            observed,
        )

        return 0

    except Exception as exc:
        base.update(
            {
                "status":
                    "OBSERVER_ERROR",

                "observed":
                    0,

                "error_type":
                    type(exc).__name__,
            }
        )

        atomic(base)

        print(
            "STATUS: OBSERVER_ERROR"
        )
        print(
            "ERROR_TYPE:",
            type(exc).__name__,
        )

        return 0


if __name__ == "__main__":
    raise SystemExit(main())
