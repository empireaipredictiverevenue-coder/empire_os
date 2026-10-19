"""No-write command for reviewed business source -> existing Empire Sniper.

All files must be locally available and separately source/rights reviewed.
Does not call any web service, query EmpireDB, enqueue tasks or send email.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.scrapling_sniper_handoff import build_scrapling_sniper_review_handoff
from empire_os.waterfall_source_bridge import EvidenceReview, VERTICAL_TARGETS

MAX_SOURCE_BYTES = 2_000_000
MAX_HTML_BYTES = 512_000
MAX_SNAPSHOT_BYTES = 6_000_000


def _read_bounded(path: Path, cap: int) -> str:
    if not path.is_file() or path.stat().st_size > cap:
        raise ValueError("missing_or_unbounded_review_input")
    return path.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only", action="store_true", required=True)
    p.add_argument("--source-report", type=Path, required=True)
    p.add_argument("--canonical-snapshot", type=Path, required=True)
    p.add_argument("--source-html", type=Path, required=True)
    p.add_argument("--site-url", required=True)
    p.add_argument("--verified-site", required=True)
    p.add_argument("--site-evidence-ref", required=True)
    p.add_argument("--record-index", type=int, default=0)
    p.add_argument("--vertical", choices=sorted(VERTICAL_TARGETS), required=True)
    p.add_argument("--target-kind", required=True)
    p.add_argument("--jurisdiction", required=True)
    p.add_argument("--company-identity-ref", required=True)
    p.add_argument("--jurisdiction-policy-ref", default="")
    p.add_argument("--snapshot-ref", required=True)
    p.add_argument("--complete-snapshot", action="store_true")
    p.add_argument("--independent-canonical-id", required=True)
    p.add_argument("--canonical-identity-receipt", required=True)
    p.add_argument("--source-rights-receipt", required=True)
    p.add_argument("--territory-receipt", required=True)
    p.add_argument("--research-score", type=float, default=0.6)
    opts = p.parse_args(argv)
    try:
        result = build_scrapling_sniper_review_handoff(
            source_report=json.loads(
                _read_bounded(opts.source_report, MAX_SOURCE_BYTES)
            ),
            review=EvidenceReview(
                vertical=opts.vertical,
                target_kind=opts.target_kind,
                jurisdiction=opts.jurisdiction,
                company_identity_ref=opts.company_identity_ref,
                jurisdiction_policy_ref=opts.jurisdiction_policy_ref,
                verified_first_party_website=opts.verified_site,
                website_verification_ref=opts.site_evidence_ref,
            ),
            canonical_rows=json.loads(_read_bounded(
                opts.canonical_snapshot, MAX_SNAPSHOT_BYTES
            )),
            canonical_snapshot_complete=opts.complete_snapshot,
            canonical_snapshot_ref=opts.snapshot_ref,
            independent_canonical_id=opts.independent_canonical_id,
            canonical_identity_receipt_ref=opts.canonical_identity_receipt,
            source_rights_receipt_ref=opts.source_rights_receipt,
            territory_receipt_ref=opts.territory_receipt,
            company_site_html=_read_bounded(opts.source_html, MAX_HTML_BYTES),
            company_page_url=opts.site_url,
            record_index=opts.record_index,
            research_score=opts.research_score,
        )
    except (TypeError, ValueError, KeyError, RuntimeError, OSError, UnicodeError) as exc:
        result = {
            "schema_version": "empire.scrapling_sniper_handoff.v1",
            "state": "HOLD", "error_class": type(exc).__name__,
            "review_task_proposal": None,
            "outbound_authorized": False,
            "canonical_database_writes": False,
            "execution_authority": "none",
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "SNIPER_REVIEW_PACKET_PREPARED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
