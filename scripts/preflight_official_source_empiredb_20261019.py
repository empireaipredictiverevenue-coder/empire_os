"""No-write source-to-existing EmpireDB canonical acquisition preflight.

Shows independent official source rights/quality and optional, strictly
bounded canonical read-only identity lookup. NEVER inserts prospects or
emails anyone. No source network requests.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.official_source_canonical_preflight import (
    LEDGER_FIELDS, preflight_official_source_ledgers,
)
from empire_os.crawler_data_repository import CrawlerProspectRepository

PATHS = {
    "gb_recc_solar": "/srv/empire_os/runtime/lead_supply/private_recc_sweeps/internal_observations.json",
    "us_cms_nppes_dental_npi2": "/srv/empire_os/runtime/lead_supply/private_us_dental_orgs/organizations.json",
    "us_nyc_dcwp_home_improvement_companies": "/srv/empire_os/runtime/lead_supply/private_nyc_contractors/private_business_observations.json",
}
MAX_BYTES = 200_000


def _load(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("source_ledger_missing_or_too_large")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("source_ledger_not_mapping")
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", required=True, action="store_true")
    parser.add_argument("--probe-canonical-reader", action="store_true")
    parser.add_argument("--max-lookups", type=int, default=4)
    parser.add_argument("--recc", type=Path, default=Path(PATHS["gb_recc_solar"]))
    parser.add_argument("--nppes", type=Path, default=Path(PATHS["us_cms_nppes_dental_npi2"]))
    parser.add_argument("--nyc", type=Path, default=Path(PATHS["us_nyc_dcwp_home_improvement_companies"]))
    args = parser.parse_args(argv)
    try:
        inputs = {
            "gb_recc_solar": _load(args.recc),
            "us_cms_nppes_dental_npi2": _load(args.nppes),
            "us_nyc_dcwp_home_improvement_companies": _load(args.nyc),
        }
        reader = None
        if args.probe_canonical_reader:
            reader = CrawlerProspectRepository.from_environment()
            if reader.backend_name != "empiredb":
                raise ValueError("canonical_reader_not_empiredb")
        result = preflight_official_source_ledgers(
            inputs, reader=reader, max_canonical_lookups=args.max_lookups,
        )
    except (OSError, TypeError, ValueError, UnicodeError, RuntimeError) as exc:
        result = {
            "schema_version": "empire.official_source_canonical_preflight.v1",
            "mode": "OFFICIAL_TO_CANONICAL_REVIEW_ONLY",
            "state": "HOLD",
            "reason_class": type(exc).__name__,
            "canonical_empiredb_writes": False,
            "exchange_inventory_added": 0,
            "outbound_authorized": False,
            "execution_authority": "none",
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if "source_rows_observed" in result else 2


if __name__ == "__main__":
    raise SystemExit(main())
