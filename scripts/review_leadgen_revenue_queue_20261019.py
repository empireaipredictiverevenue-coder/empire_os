"""Inspect existing real B2B buyer research against canonical Exchange selected stock.

Offline upstream read-only. Optionally writes one PRIVATE derived report when
--write-private is specified. Includes optional source preparation summary;
NO network fetch, buyer message, task insertion, CRM/EmpireDB mutation,
or financial authority. Niche overlap is not territory or buyer-capacity fit.

python -m scripts.review_leadgen_revenue_queue_20261019 --read-only
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from empire_os.recc_supply_sweep import _atomic_private_json
from empire_os.leadgen_revenue_activation_queue import build_leadgen_revenue_queue
from empire_os.official_source_canonical_preflight import preflight_official_source_ledgers
from scripts.preflight_official_source_empiredb_20261019 import PATHS

EXCHANGE = Path("/srv/empire_os/runtime/commercial_exchange/latest.json")
BUYER_ACTIONS = Path("/srv/empire_os/runtime/buyer_network_intelligence/founder_qualification_actions_latest.json")
RELATIONSHIPS = Path("/srv/empire_os/runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json")
MAX_BYTES = 5_000_000
PRIVATE_DIR = Path("/srv/empire_os/runtime/lead_supply/private_leadgen")
PRIVATE_REPORT = PRIVATE_DIR / "research_queue_latest.json"


def _read(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("missing_or_unsafe_leadgen_snapshot")
    d = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(d, dict):
        raise ValueError("invalid_leadgen_snapshot_type")
    return d


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--exchange", type=Path, default=EXCHANGE)
    parser.add_argument("--buyer-actions", type=Path, default=BUYER_ACTIONS)
    parser.add_argument("--include-source-readiness", action="store_true")
    parser.add_argument("--include-contact-history", action="store_true")
    parser.add_argument("--relationships", type=Path, default=RELATIONSHIPS)
    parser.add_argument("--write-private", action="store_true")
    parser.add_argument("--max-visible", type=int, default=15)
    opts = parser.parse_args(argv)
    try:
        source = None
        if opts.include_source_readiness:
            source = preflight_official_source_ledgers({
                key: _read(Path(path)) for key, path in PATHS.items()
            })
        result = build_leadgen_revenue_queue(
            exchange=_read(opts.exchange),
            buyer_actions=_read(opts.buyer_actions),
            source_preflight=source,
            relationship_history=(_read(opts.relationships)
                                  if opts.include_contact_history else None),
            max_visible=opts.max_visible,
        )
        if opts.write_private and result["state"] == "FOUNDER_RESEARCH_QUEUE_READY":
            if PRIVATE_DIR.is_symlink() or PRIVATE_REPORT.is_symlink():
                raise ValueError("unsafe_private_report_path")
            PRIVATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
            PRIVATE_DIR.chmod(0o700)
            _atomic_private_json(PRIVATE_REPORT, result)
    except (ValueError, TypeError, OSError, UnicodeError, RuntimeError) as exc:
        result = {
            "schema_version": "empire.leadgen_revenue_activation_queue.v1",
            "mode": "READ_ONLY_PRIVATE_LEADGEN",
            "state": "HOLD", "reason_class": type(exc).__name__,
            "qualified_buyers": 0, "verified_buyer_capacity": 0,
            "ready_for_outbound": 0, "canonical_empiredb_writes": False,
            "execution_authority": "none",
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("state") == "FOUNDER_RESEARCH_QUEUE_READY" else 2

if __name__ == "__main__":
    raise SystemExit(main())
