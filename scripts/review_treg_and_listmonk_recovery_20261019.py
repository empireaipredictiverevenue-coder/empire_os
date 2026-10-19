"""Private EmpireOS TREG/Listmonk integration preflight (no remote calls).

Does not install TREG, query billed tools, read/reuse old credentials, start
Listmonk, scan mailing lists, or invoke SMTP. Only checks local legacy code
evidence and evaluates zero-spend optional-tool contracts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from empire_os.listmonk_recovery_boundary import inspect_legacy_listmonk
from empire_os.treg_source_policy import review_treg_for_empire

ROOT = Path("/srv/empire_os")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only", action="store_true", required=True)
    p.add_argument("--repo-root", type=Path, default=ROOT)
    args = p.parse_args(argv)
    try:
        report = {
            "schema_version": "empire.treg_listmonk_recovery_review.v1",
            "mode": "READ_ONLY",
            "listmonk": inspect_legacy_listmonk(args.repo_root),
            "treg": review_treg_for_empire(),
            "paid_external_api_calls": 0,
            "mailing_campaigns_sent": 0,
            "canonical_empiredb_writes": False,
            "execution_authority": "none",
        }
    except (ValueError, OSError, TypeError) as exc:
        report = {
            "schema_version": "empire.treg_listmonk_recovery_review.v1",
            "mode": "READ_ONLY",
            "state": "HOLD", "reason_class": type(exc).__name__,
            "paid_external_api_calls": 0,
            "mailing_campaigns_sent": 0,
            "canonical_empiredb_writes": False,
            "execution_authority": "none",
        }
    print(json.dumps(report, sort_keys=True))
    return 0 if "listmonk" in report else 2


if __name__ == "__main__":
    raise SystemExit(main())
