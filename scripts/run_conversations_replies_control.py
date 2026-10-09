# EMPIRE_WAVE_092B
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from empire_os.conversations_replies_control import (
    adjudicate_records,
)
from empire_os.conversation_source_admission import (
    CONVERSATION_DB_TABLES, admit_candidate_rows,
)


ROOT = Path("/srv/empire_os")

DISCOVERY = (
    ROOT
    / "runtime/control_plane/"
      "conversations_replies_binding_truth_latest.json"
)

OUT = (
    ROOT
    / "runtime/conversations_replies_control/"
      "latest.json"
)

MAX_TABLES = 12
MAX_ROWS_PER_TABLE = 750

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


def query_table(
    table,
):
    """Read only approved original event metadata; fail closed on IO errors."""
    from empire_os.conversation_evidence_db_reader import (
        read_reply_evidence,
    )
    return read_reply_evidence(
        table,
        max_rows=MAX_ROWS_PER_TABLE,
    )


def useful_db_candidate(
    item,
):

    # Only explicit, reviewed conversation/reply tables are admissible.
    # An outbound event with message_id is still delivery telemetry.
    if item.get("table") not in CONVERSATION_DB_TABLES:
        return False

    columns = {
        str(
            x.get(
                "column",
                ""
            )
        ).casefold()
        for x in item.get(
            "columns",
            []
        )
    }

    has_message = any(
        token in column
        for column in columns
        for token in (
            "message_id",
            "provider_message",
            "external_message",
            "provider_event_id",
        )
    )

    has_thread = any(
        token in column
        for column in columns
        for token in (
            "thread_id",
            "conversation_id",
            "in_reply_to",
            "parent_message",
        )
    )

    return (
        has_message
        or has_thread
    )


def runtime_records(
    discovery,
):

    records = []

    for item in discovery.get(
        "runtime_candidates",
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

        if relative.startswith(
            "runtime/control_plane/"
        ):
            continue

        if relative.startswith(
            "runtime/conversations_replies_control/"
        ):
            continue

        path = (
            ROOT
            / relative
        )

        try:

            resolved = path.resolve()
            runtime_root = (
                ROOT / "runtime"
            ).resolve()

            if runtime_root not in (
                resolved,
                *resolved.parents,
            ):
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

        stack = [value]

        seen = 0

        while stack and seen < 3000:

            current = stack.pop()

            if isinstance(
                current,
                dict,
            ):

                seen += 1

                records.append(
                    (
                        relative,
                        current,
                    )
                )

                for child in current.values():

                    if isinstance(
                        child,
                        (
                            dict,
                            list,
                        ),
                    ):
                        stack.append(child)

            elif isinstance(
                current,
                list,
            ):

                stack.extend(
                    current[:1000]
                )

    return records


def main():

    discovery = json.loads(
        DISCOVERY.read_text()
    )

    records = []

    selected_tables = []

    for item in discovery.get(
        "database_candidates",
        [],
    ):

        table = item.get(
            "table"
        )

        if not table:
            continue

        if not useful_db_candidate(
            item
        ):
            continue

        rows = query_table(
            table
        )

        # A successful empty query is still a completed source read.
        # Distinguish it from a failed or never-attempted DB read.
        selected_tables.append(
            table
        )

        if not rows:
            continue

        records.extend(
            (
                table,
                row,
            )
            for row in rows
        )

        if len(
            selected_tables
        ) >= MAX_TABLES:
            break

    if not selected_tables:
        from empire_os.conversation_evidence_db_reader import EvidenceReadUnavailable
        raise EvidenceReadUnavailable("NO_APPROVED_DATABASE_SOURCES")

    runtime = runtime_records(
        discovery
    )

    records.extend(runtime)

    eligible, admission = admit_candidate_rows(records)
    payload = adjudicate_records(
        eligible
    )
    payload["source_admission"] = admission

    payload[
        "source_summary"
    ] = {
        "database_tables":
            selected_tables,

        "database_table_count":
            len(
                selected_tables
            ),

        "runtime_record_sources":
            len(
                {
                    source
                    for source, _
                    in runtime
                }
            ),

        "records_examined":
            len(
                records
            ),
        "message_candidate_rows_admitted": len(eligible),
        "nonmessage_rows_excluded": admission["excluded_nonmessage_rows"],
    }

    atomic_write(
        OUT,
        payload,
    )
    atomic_write(
        OUT.with_name("collector_health_latest.json"),
        {
            "schema": "empire.conversation_collector_health.v1",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "status": (
                "READ_SUCCESS" if selected_tables else "NO_DATABASE_SOURCES_SELECTED"
            ),
            "source_query_completed": bool(selected_tables),
            "database_table_count": len(selected_tables),
            "records_examined": len(records),
            "candidate_records_admitted": len(eligible),
            "canonical_messages": payload["semantic_effectiveness"]["canonical_message_count"],
            "authenticated_buyers_proved": False,
            "execution_authority": "none",
        },
    )

    sem = payload[
        "semantic_effectiveness"
    ]

    print(
        json.dumps(
            {
                "status":
                    (
                        "PASS"
                        if sem[
                            "effective"
                        ]
                        else "HOLD"
                    ),

                "database_tables":
                    len(
                        selected_tables
                    ),

                "records_examined":
                    len(
                        records
                    ),

                "canonical_messages":
                    sem[
                        "canonical_message_count"
                    ],

                "classified":
                    sem[
                        "classified_count"
                    ],

                "inbound_replies":
                    sem[
                        "inbound_reply_count"
                    ],

                "outcome_links":
                    sem[
                        "outcome_link_count"
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

                "mailbox_write":
                    False,

                "outbound":
                    False,

                "mode":
                    "OBSERVE",
            },
            indent=2,
        )
    )


def run_cli() -> int:
    """Never mislabel a failed database read as a zero-reply observation."""
    from empire_os.conversation_evidence_db_reader import EvidenceReadUnavailable
    try:
        main()
        return 0
    except EvidenceReadUnavailable as exc:
        atomic_write(
            OUT.with_name("collector_health_latest.json"),
            {
                "schema": "empire.conversation_collector_health.v1",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "status": "DATABASE_SOURCE_READ_FAILED",
                "reason_code": str(exc),
                "source_query_completed": False,
                "canonical_snapshot_preserved": True,
                "authenticated_buyers_proved": False,
                "execution_authority": "none",
            },
        )
        print(json.dumps({
            "status": "DATABASE_SOURCE_READ_FAILED",
            "execution_authority": "none",
        }))
        return 3


if __name__ == "__main__":
    raise SystemExit(run_cli())
