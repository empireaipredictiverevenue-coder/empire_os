"""First-payer current owner and scope handoff: no private keys on CLI."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

from empire_os.flagship_first_payer_scoped_quant_bridge import (
    review_first_payer_scoped_quant_bridge,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    report = review_first_payer_scoped_quant_bridge(
        args.repo_root, as_of=datetime.now(timezone.utc),
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
