#!/usr/bin/env python3
"""CLI for the Empire Coder foundation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.coder import EmpireCoder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EmpireOS governed developer intelligence"
    )
    parser.add_argument(
        "--workspace",
        default="/srv/empire_os",
    )
    parser.add_argument(
        "--runtime-root",
        default=None,
    )
    subs = parser.add_subparsers(dest="command", required=True)

    create = subs.add_parser("create")
    create.add_argument("objective")

    show = subs.add_parser("show")
    show.add_argument("task_id")

    search = subs.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=25)

    context = subs.add_parser("context")
    context.add_argument("task_id")
    context.add_argument("--term", action="append", default=[])
    context.add_argument("--symbol", action="append", default=[])

    route = subs.add_parser("route")
    route.add_argument("task_id")

    subs.add_parser("doctor")
    subs.add_parser("garden")

    memory = subs.add_parser("memory")
    memory.add_argument("task_id")

    report = subs.add_parser("report")
    report.add_argument("task_id")

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    coder = EmpireCoder(
        Path(args.workspace),
        runtime_root=args.runtime_root,
    )

    if args.command == "create":
        print(json.dumps(
            coder.create_task(args.objective).as_dict(),
            indent=2,
            sort_keys=True,
        ))
        return 0
    if args.command == "show":
        print(json.dumps(
            coder.load_task(args.task_id).as_dict(),
            indent=2,
            sort_keys=True,
        ))
        return 0
    if args.command == "search":
        rows = coder.repo.search(args.query, limit=args.limit)
        print(json.dumps(
            [row.__dict__ for row in rows],
            indent=2,
            sort_keys=True,
        ))
        return 0
    if args.command == "context":
        pack = coder.build_context(
            args.task_id,
            terms=args.term,
            symbols=args.symbol,
        )
        print(json.dumps(pack.as_dict(), indent=2, sort_keys=True))
        return 0
    if args.command == "route":
        print(json.dumps(
            coder.model_route(args.task_id).__dict__,
            indent=2,
            sort_keys=True,
        ))
        return 0
    if args.command == "doctor":
        print(json.dumps(coder.doctor(), indent=2, sort_keys=True))
        return 0
    if args.command == "garden":
        summary = coder.refresh_knowledge()
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "memory":
        snapshot = coder.memory.load(args.task_id)
        if snapshot is None:
            raise SystemExit("task context memory not found")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 0
    if args.command == "report":
        print(json.dumps(
            coder.candidate_report(args.task_id),
            indent=2,
            sort_keys=True,
        ))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
