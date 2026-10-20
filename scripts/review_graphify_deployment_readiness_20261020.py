"""Real Graphify deployment sign-off, separate from Coder implementation authority.

Examples:
  PYTHONPATH=/srv/empire_os /srv/empire_os/.venv/bin/python -B \
    -m scripts.review_graphify_deployment_readiness_20261020 --read-only

No dispatch, restart, contract promotion, worker creation or database change.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.graphify_deployment_gate import review_deployment_readiness


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/srv/empire_os"))
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args()
    print(json.dumps(review_deployment_readiness(args.root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
