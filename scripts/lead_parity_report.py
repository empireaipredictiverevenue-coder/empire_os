#!/usr/bin/env python3
"""Generate a read-only canonical-vs-legacy lead parity report."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from empire_os.lead_intelligence_transport import (
    PostgresLeadIntelligenceReader,
)
from empire_os.lead_parity import (
    build_parity_report,
    fetch_canonical_parity_inputs,
)


def read_legacy_rows(
    db_path: str | Path,
    *,
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not 1 <= int(limit) <= 10000:
        raise ValueError("limit must be between 1 and 10000")

    path = Path(db_path).expanduser().resolve()
    uri = f"file:{path}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row

    try:
        crm = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                  lead_uid,
                  business_name,
                  niche,
                  metro,
                  phone
                FROM crm_leads
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        ]

        lane_rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT *
                FROM lane_leads
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        ]
    finally:
        connection.close()

    lane: list[dict[str, Any]] = []
    for row in lane_rows:
        normalized = dict(row)
        if "business_name" not in normalized:
            normalized["business_name"] = normalized.get("name")
        lane.append(normalized)

    return crm, lane


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Compare canonical Supabase prospects with legacy "
            "crm_leads/lane_leads without mutating either source."
        )
    )
    p.add_argument(
        "--db-path",
        default=os.getenv(
            "EMPIRE_DB_PATH",
            "/srv/empire_os/empire_os.db",
        ),
    )
    p.add_argument(
        "--limit",
        type=int,
        default=5000,
    )
    p.add_argument(
        "--output",
        default="",
        help="Optional JSON output path; stdout when omitted.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    reader = PostgresLeadIntelligenceReader.from_env()

    prospects, acquisitions = fetch_canonical_parity_inputs(
        reader,
        limit=args.limit,
    )
    crm_leads, lane_leads = read_legacy_rows(
        args.db_path,
        limit=args.limit,
    )

    report = build_parity_report(
        prospects=prospects,
        acquisitions=acquisitions,
        crm_leads=crm_leads,
        lane_leads=lane_leads,
    )
    rendered = json.dumps(
        report,
        indent=2,
        sort_keys=True,
    ) + "\n"

    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        tmp = output.with_suffix(output.suffix + ".tmp")
        tmp.write_text(rendered, encoding="utf-8")
        tmp.replace(output)
    else:
        print(rendered, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
