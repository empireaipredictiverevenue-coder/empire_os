"""Owner acceptance evidence report; pure read-only, one original website reader."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.microsite_owner_handoff_v11 import check_live_original_owner


def main() -> None:
    parser = argparse.ArgumentParser(description="Original five-site owner + V10 read-only release review")
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("/srv/empire_os"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    packet = check_live_original_owner(args.stage, args.root)
    output = json.dumps(packet, indent=2, sort_keys=True) + "\n"
    if args.output:
        # Write only to the dedicated private release review stage; never site/repo.
        permitted = Path("/home/ubuntu/empire_releases").resolve()
        target = args.output.resolve()
        if target.is_relative_to(Path("/srv/empire_os").resolve()) or not target.is_relative_to(permitted):
            raise SystemExit("Refusing output outside private EmpireOS release stage")
        if target.is_symlink():
            raise SystemExit("Refusing symlink output")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output)
    print(output, end="")


if __name__ == "__main__":
    main()
