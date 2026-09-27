#!/usr/bin/env python3
"""Materialize one canonical prospect into the Intelligence Fabric."""
from __future__ import annotations

import argparse
import json

from empire_os.intelligence_materializer_transport import (
    PostgresIntelligenceMaterializer,
)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description=(
            "Project one canonical prospect plus its active identity "
            "and v1 qualification into the Intelligence Fabric."
        )
    )
    command.add_argument(
        "--prospect-id",
        required=True,
        help="Canonical prospect UUID.",
    )
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    writer = PostgresIntelligenceMaterializer.from_env()
    result = writer.materialize(args.prospect_id)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
