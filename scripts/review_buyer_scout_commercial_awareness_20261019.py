"""Read-only cross-snapshot Buyer Scout business awareness and duplicate guard."""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from empire_os.buyer_scout_commercial_awareness import review_buyer_scout_awareness

ROOT = Path("/srv/empire_os/runtime")
SCOUT = "buyer_acquisition/scout_latest.json"
ACTIONS = "buyer_network_intelligence/founder_qualification_actions_latest.json"
RELATIONSHIPS = "buyer_network_intelligence/commercial_relationship_registry_latest.json"

def _load(root: Path, relative: str) -> dict:
    path = root / relative
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_500_000:
        raise ValueError("untrusted_local_snapshot")
    with path.open("r", encoding="utf-8") as stream:
        source = json.load(stream)
    if not isinstance(source, dict):
        raise ValueError("invalid_source")
    return source

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only", action="store_true", required=True)
    p.add_argument("--runtime-root", type=Path, default=ROOT)
    p.add_argument("--prior-scout", type=Path,
                   help="Optional previous OBSERVE scout snapshot for cooldown review")
    args = p.parse_args(argv)
    try:
        previous = None
        if args.prior_scout:
            if (args.prior_scout.is_symlink()
                    or not args.prior_scout.is_file()
                    or args.prior_scout.stat().st_size > 2_500_000):
                raise ValueError("untrusted_prior_snapshot")
            previous = json.loads(args.prior_scout.read_text(encoding="utf-8"))
        summary = review_buyer_scout_awareness(
            _load(args.runtime_root, SCOUT),
            _load(args.runtime_root, ACTIONS),
            _load(args.runtime_root, RELATIONSHIPS),
            as_of=datetime.now(timezone.utc),
            prior_scout=previous,
        )
        print(json.dumps(summary, sort_keys=True))
        return 0
    except (ValueError, TypeError, OSError, json.JSONDecodeError):
        print(json.dumps({
            "schema_version": "empire.buyer_scout_commercial_awareness.v1",
            "state": "HOLD_SOURCE_CONTRACT_OR_STALENESS",
            "emails_sent": False, "canonical_crm_writes": False,
            "outbound_authorized": False, "execution_authority": "none",
        }, sort_keys=True))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
