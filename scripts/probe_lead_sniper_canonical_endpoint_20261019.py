"""Read-only canonical EmpireDB Lead Sniper review endpoint preflight.

Usage:
 /srv/empire_os/.venv/bin/python -m scripts.probe_lead_sniper_canonical_endpoint_20261019 --read-only

Expects approved canonical EmpireDB reader credentials in existing runtime.
No write attempt, no queue activation, no HTTP fetch, no outgoing messages.
"""
from __future__ import annotations

import argparse
import json

from empire_os.lead_sniper_repository import LeadSniperRepository

# Deterministic non-sensitive, non-existent test URL used only for read lookup.
PROBE_URL = "https://example.invalid/empire-sniper-readonly-probe"


def run(*, repository: LeadSniperRepository | None = None) -> dict:
    # Even if operator enabled writes in environment, probe does not call insert.
    try:
        store = repository or LeadSniperRepository.from_environment()
        match = store.pending_review_exists(PROBE_URL)
        return {
            "schema_version": "empire.lead_sniper_canonical_endpoint_preflight.v1",
            "status": "READ_ONLY_REVIEW_QUERY_PASS",
            "canonical_empiredb_read_contract_verified": True,
            "existing_probe_task_observed": match,
            "queue_write_authorized_by_probe": False,
            "outbound_authorized": False,
            "execution_authority": "read_only",
        }
    except Exception as exc:
        return {
            "schema_version": "empire.lead_sniper_canonical_endpoint_preflight.v1",
            "status": "HOLD_CANONICAL_READER_UNAVAILABLE",
            "reason": type(exc).__name__,
            "canonical_empiredb_read_contract_verified": False,
            "queue_write_authorized_by_probe": False,
            "outbound_authorized": False,
            "execution_authority": "none",
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    result = run()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "READ_ONLY_REVIEW_QUERY_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
