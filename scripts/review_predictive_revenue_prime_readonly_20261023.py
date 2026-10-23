"""Private aggregate-only read of existing Predictive Cloud PRIME sources.

Use from the isolated worktree with PYTHONPATH pointed at this checkout.
Never connects to CRM/payment credentials or alters production state.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from empire_os.predictive_revenue_prime_status import read_prime_founder_status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", default="/srv/empire_os")
    # No arbitrary tenant selection: the only supported runtime source review
    # is the internal OBSERVE source. End-user access must be authenticated by
    # the canonical Revenue CRM API, not this tool.
    args = parser.parse_args()
    report = read_prime_founder_status(
        repo_root=Path(args.source_root),
        tenant_id="empire-internal",
        as_of=datetime.now(timezone.utc),
    )
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
