"""Actual authorized NVIDIA viewer ask_question through native MCP.

Use OpenCode's existing approved Viewer OAuth grant; never print or persist it.
Call NVIDIA's pinned read-only synthetic question tool only once, retain an
immutable private receipt with real SQL and executed DB answer evidence.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import os
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from scripts.verify_nvidia_viewer_real_mcp_tools_20261117 import load_existing_grant

ROOT = Path("/srv/empire_os/runtime/nvidia_ontology_eval")
OUT = ROOT / "nvidia_viewer_mcp_real_question_20261117.json"
MCP = "http://127.0.0.1:33013/mcp"
QUESTION = (
    "Using the synthetic empire_graph database, count ontology_edges where "
    "relation is BUYER_DEMANDS_LANE. Execute SQL and report the actual database "
    "count, not a guess."
)

def parse_single_count(rows) -> int | None:
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        return None
    if len(rows[0]) != 1:
        return None
    value = next(iter(rows[0].values()))
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None

async def main():
    if OUT.exists():
        raise RuntimeError("existing acceptance receipt; do not overwrite")
    approved = ROOT / "nvidia_viewer_real_mcp_tools_20261117.json"
    previous = json.loads(approved.read_text())
    if previous.get("viewer_readonly_mcp_acceptance") is not True:
        raise RuntimeError("precondition: viewer identity and read tools not verified")
    token = load_existing_grant()
    report = {
        "scope": "EXISTING_AUTHORIZED_OPENCODE_VIEWER_VIA_NATIVE_MCP",
        "synthetic_only": True,
        "customer_data_sent": False,
        "actual_mcp_tool": "ask_question",
        "user_token_disclosed": False,
        "administrator_not_used": True,
        "expected_count": 2,
        "actual_count": None,
        "generated_sql_present": False,
        "actual_database_rows_present": False,
        "semantic_filter_preserved": False,
        "tool_error": None,
        "verified": False
    }
    try:
        async with streamablehttp_client(
            MCP, headers={"Authorization": "Bearer " + token},
            timeout=25, sse_read_timeout=155
        ) as (reader, writer, _):
            async with ClientSession(
                reader, writer,
                read_timeout_seconds=datetime.timedelta(seconds=145)
            ) as client:
                await client.initialize()
                response = await client.call_tool(
                    "ask_question", {"question": QUESTION},
                    read_timeout_seconds=datetime.timedelta(seconds=145),
                )
                report["is_error"] = bool(response.isError)
                structured = getattr(response, "structuredContent", None)
                if isinstance(structured, dict):
                    answer = structured
                    if "result" in answer and isinstance(answer["result"], dict):
                        answer = answer["result"]
                else:
                    answer = {}
                sql = str(answer.get("sql") or "")
                rows = answer.get("rows")
                report["generated_sql_present"] = bool(sql.strip())
                report["sql_count_aggregate"] = "COUNT(" in sql.upper().replace(" ", "")
                report["semantic_filter_preserved"] = (
                    "ontology_edges" in sql.lower()
                    and "BUYER_DEMANDS_LANE" in sql
                )
                report["actual_database_rows_present"] = isinstance(rows, list) and bool(rows)
                report["actual_count"] = parse_single_count(rows)
                report["rows_reported"] = answer.get("row_count")
                report["reasoning_present"] = bool(answer.get("reasoning"))
                report["answer_present"] = bool(answer.get("answer"))
                report["structured_response_keys"] = sorted(answer)
                if response.isError:
                    report["tool_error"] = "NVIDIA_TOOL_REPORTED_ERROR"
    except Exception as exc:
        report["tool_error"] = type(exc).__name__
    report["verified"] = all((
        report.get("is_error") is False,
        report["generated_sql_present"],
        report.get("sql_count_aggregate"),
        report["semantic_filter_preserved"],
        report["actual_database_rows_present"],
        report["actual_count"] == report["expected_count"],
        report["tool_error"] is None,
    ))
    fd = os.open(OUT, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["verified"]:
        raise SystemExit(2)

if __name__ == "__main__":
    asyncio.run(main())
