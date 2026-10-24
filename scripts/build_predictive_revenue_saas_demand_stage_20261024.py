#!/usr/bin/env python3
"""Run existing Predictive Revenue SaaS BUILD STAGE; never publish or send."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.predictive_revenue_saas_build_stage import (
    OUTPUT_REL, SOURCE_REL, SourceHold, _read_source, build, write_private,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-private", action="store_true",
                        help="Update only the existing private GTM research read model")
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args(argv)
    root = Path(args.repo_root)
    try:
        if not root.is_dir() or root.is_symlink():
            raise SourceHold("EXISTING_EMPIREOS_ROOT_NOT_AVAILABLE")
        report = build(root, _read_source(root / SOURCE_REL),
                       suppression_fresh=False)
        if args.write_private:
            write_private(root / OUTPUT_REL, report)
        print(json.dumps({
            "status": "SAAS_DEMAND_PRIVATE_BUILD_STAGE_PASS",
            "existing_catalog_product_code": report["existing_catalog_product_code"],
            "public_signal_count": report["public_signal_count"],
            "external_service_requests_observed":
                report["external_service_requests_observed"],
            "company_hiring_fit_hypotheses":
                report["company_hiring_fit_hypotheses"],
            "private_public_evidence_samples_built":
                report["private_public_evidence_samples_built"],
            "active_verified_buyers": report["real_buyer_conversations_verified"],
            "outbound_send_authorized": False, "emails_sent": 0,
            "private_read_model_written": args.write_private,
            "customer_rows_written": 0, "site_mutated": False,
        }, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "SAAS_DEMAND_BUILD_HELD",
                          "reason_code": str(exc) if isinstance(exc, SourceHold)
                          else type(exc).__name__,
                          "private_read_model_written": False,
                          "emails_sent": 0, "customer_rows_written": 0,
                          "outbound_send_authorized": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
