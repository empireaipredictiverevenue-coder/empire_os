"""Review COO / Business Development / Chief of Staff evidence, stdout only.

No email, HTTP, DB access, agent queue writes, production service changes, or
new scheduling. Input is a bounded, human-reviewed JSON evidence packet.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

from empire_os.executive_commercial_roles import review_executive_commercial_roles
from empire_os.executive_commercial_observer import observe_executive_commercial_roles


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--input", type=Path)
    target.add_argument("--live-observe", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=Path("/srv/empire_os"))
    args = parser.parse_args(argv)

    if args.live_observe:
        # No job dispatch or backend writes: this uses the same read-only
        # source resolver as the existing Astra executive refresh.
        result = observe_executive_commercial_roles(args.repo_root)
    else:
        assert args.input is not None
        if (args.input.is_symlink() or not args.input.is_file()
                or args.input.stat().st_size > 250_000):
            raise SystemExit("Invalid or unbounded input file")
        packet = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(packet, dict) or set(packet) != {"as_of", "partners", "operations"}:
            raise SystemExit("Invalid evidence packet shape")
        as_of = datetime.fromisoformat(packet["as_of"].replace("Z", "+00:00"))
        result = review_executive_commercial_roles(
            packet["partners"], packet["operations"], as_of=as_of,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
