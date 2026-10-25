#!/usr/bin/env python3
"""Run existing Predictive Revenue SaaS BUILD STAGE; never publish or send."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.predictive_revenue_saas_build_stage import (
    OUTPUT_REL, SOURCE_REL, SourceHold, _read_source, build, write_private,
    verify_clueso_official_sources, FOUNDER_CLUESO_REPORT_REL,
    load_founder_clueso_first_touch, apply_founder_clueso_first_touch,
)


def _existing_readonly_snapshot(root: Path, relative: str) -> dict | None:
    """Optional bounded owner snapshot; never read customer rows or tokens."""
    path = root / relative
    try:
        if (path.is_symlink() or not path.is_file()
                or path.stat().st_size > 500_000):
            return None
        payload = json.loads(path.read_text(encoding="utf8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, UnicodeError, ValueError, TypeError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-private", action="store_true",
                        help="Update only the existing private GTM research read model")
    parser.add_argument("--verify-clueso-official", action="store_true",
                        help="GET two exact official Clueso pages; no message, login or tracking")
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args(argv)
    root = Path(args.repo_root)
    try:
        if not root.is_dir() or root.is_symlink():
            raise SourceHold("EXISTING_EMPIREOS_ROOT_NOT_AVAILABLE")
        report = build(
            root, _read_source(root / SOURCE_REL),
            suppression_fresh=False,
            intake_observer=_existing_readonly_snapshot(
                root, "runtime/gtm_pipeline/integration_observer_latest.json"),
            buyer_queue=_existing_readonly_snapshot(
                root, "runtime/buyer_network_intelligence/candidate_queue_latest.json"),
        )
        source_check = (verify_clueso_official_sources()
                        if args.verify_clueso_official else None)
        report["clueso_first_party_get_evidence"] = source_check
        for action in report["next_review_actions"]:
            if action["source_id"] == "clueso_founding_ae_20261024":
                action["first_party_source_status"] = (
                    source_check["status"] if source_check is not None
                    else "NO_FRESH_FIRST_PARTY_GET_THIS_RUN")
                action["contact_channel_authorized"] = False
        founder_report = load_founder_clueso_first_touch(
            root / FOUNDER_CLUESO_REPORT_REL)
        if founder_report is not None:
            report = apply_founder_clueso_first_touch(report, founder_report)
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
            "founder_reported_linkedin_manual_first_touches": report.get(
                "founder_reported_linkedin_manual_first_touch_count", 0),
            "clueso_first_touch_status": (
                "FOUNDER_REPORTED_SENT_PLATFORM_UNVERIFIED"
                if founder_report is not None else "NO_FOUNDER_SEND_REPORT"),
            "commercial_observation": report["original_commercial_truth"]["status"],
            "canonical_count_if_verified": report[
                "original_commercial_truth"]["canonical_sales_acquisitions_if_verified"],
            "server_gmail_evidence_fresh": report[
                "original_commercial_truth"]["original_buyer_network_gmail_snapshot_fresh"],
            "top_review_action": report["next_review_actions"][0]["action"],
            "top_review_source_id": report["next_review_actions"][0]["source_id"],
            "clueso_official_source_status": (
                source_check["status"] if source_check is not None
                else "NO_FRESH_FIRST_PARTY_GET_THIS_RUN"),
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
