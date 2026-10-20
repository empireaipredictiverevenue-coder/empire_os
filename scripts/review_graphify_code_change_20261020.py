"""Evidence-only ASTRA code-change impact briefing from current real source.

Example:
  python -B -m scripts.review_graphify_code_change_20261020 \
    --changed-file empire_os/coder/models.py --read-only

No task creation, patch execution, network operations or business records.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.coder.graphify_change_review import GraphifyChangeReviewer


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/srv/empire_os"))
    parser.add_argument(
        "--graph", type=Path,
        default=Path("/srv/empire_os/runtime/graphify/attested_coder_20261020/graphify-out/graph.json"),
    )
    parser.add_argument(
        "--manifest", type=Path,
        default=Path("/srv/empire_os/runtime/graphify/attested_coder_manifest_20261020.json"),
    )
    parser.add_argument("--changed-file", action="append", required=True)
    parser.add_argument("--max-affected", type=int, default=20)
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args()
    review = GraphifyChangeReviewer(
        workspace=args.root, graph_path=args.graph,
        snapshot_path=args.manifest,
    ).review(args.changed_file, max_affected=args.max_affected)
    print(json.dumps(review, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
