"""Fail-closed founder deadline triage for ORIGINAL EmpireOS official tender intake.

Reads the existing private Find a Tender / Contracts Finder observation only.
Never checks supplier eligibility by implication, submits a bid, sends contact,
changes canonical data, or turns a tender into a verified client.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any
from urllib.parse import urlsplit

from empire_os.gtm_procurement_research_source import (
    REPORT, SCHEMA, HOLDS, assess_procurement,
)

DEFAULT_ROOT = Path("/srv/empire_os")
OUTPUT = Path("runtime/acquisition_research/official_tender_founder_deadline_triage_latest.json")
HOLD_STATUS = "HELD_OFFICIAL_TENDER_RESEARCH_UNVERIFIED"
READY_STATUS = "DEADLINES_TRIAGED_REVIEW_ONLY"
NO_PAID = frozenset({
    "NO_PAID_TRAFFIC_POLICY_HOLD",
    "DIGITAL_MARKETING_PAID_SCOPE_NOT_EXCLUDED_HOLD",
})
NO_FIT = frozenset({
    "CUSTOM_SCOPE_NO_VERIFIED_PRODUCT_FIT",
    "SERVICE_SCOPE_NEEDS_INDEPENDENT_FIT_REVIEW",
    "CATALOG_PRODUCT_NOT_READY",
    "PRODUCT_HYPOTHESIS_REQUIRES_SCOPE_REVIEW",
})
OCDS_FTS = re.compile(r"/Notice/\d{6}-20\d{2}$")
OCDS_CF = re.compile(r"/Notice/[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$", re.I)


def _utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("SOURCE_DATE_REQUIRED")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("SOURCE_DATE_NOT_TIMEZONE_AWARE")
    return dt.astimezone(timezone.utc)


def _notice_url_verified(item: dict[str, Any]) -> bool:
    value = item.get("notice_url")
    if not isinstance(value, str) or len(value) > 350:
        return False
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.port not in (None, 443)
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        return False
    return (
        (item.get("source") == "find_a_tender"
         and parsed.hostname == "www.find-tender.service.gov.uk"
         and bool(OCDS_FTS.fullmatch(parsed.path)))
        or
        (item.get("source") == "contracts_finder"
         and parsed.hostname == "www.contractsfinder.service.gov.uk"
         and bool(OCDS_CF.fullmatch(parsed.path)))
    )


def triage(packet: Any, *, now: datetime) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": "empire.official_tender_founder_deadline_triage.v1",
        "status": HOLD_STATUS,
        "source_qualified_customer_count": 0,
        "bid_ready_count": 0,
        "contact_permission_verified_count": 0,
        "bid_submissions": 0,
        "outbound_sent": False,
        "crm_writes": False,
        "payment_actions": False,
        "auto_bid_enabled": False,
        "external_bids_authorized": False,
        "new_services": False,
    }
    if now.tzinfo is None or now.utcoffset() is None:
        return result
    current = now.astimezone(timezone.utc)
    if (assess_procurement(packet, now=current).get("current_research_receipt")
            is not True):
        return result
    try:
        snapshot_at = _utc(packet["observed_at"])
        if not 0 <= (current - snapshot_at).total_seconds() <= 24 * 3600:
            raise ValueError("STALE_SOURCE")
        items = packet["records"]
        if not isinstance(items, list) or len(items) > 600:
            raise ValueError("BAD_SOURCE_RECORDS")
        listed = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            if not isinstance(item, dict) or not _notice_url_verified(item):
                raise ValueError("SOURCE_NOTICE_NOT_VERIFIED")
            if (item.get("review_status") not in HOLDS
                    or item.get("external_purchasing_requirement_evidence") is not True
                    or item.get("bid_eligibility_verified") is not False
                    or item.get("tender_documents_reviewed") is not False
                    or item.get("product_fit_verified") is not False
                    or item.get("contact_permission_cleared") is not False
                    or item.get("suppression_checked") is not False
                    or item.get("outbound_authorized") is not False
                    or item.get("buyer_interest_in_empire_ai_verified") is not False
                    or item.get("request_status") != "PUBLIC_TENDER_OPEN_AS_OF_OBSERVATION"
                    or not isinstance(item.get("buyer_organisation"), str)
                    or not item["buyer_organisation"]
                    or not isinstance(item.get("ocid"), str)
                    or not item["ocid"]):
                raise ValueError("UNVERIFIED_COMMERCIAL_GATES")
            key = (item["source"], item["ocid"])
            if key in seen:
                raise ValueError("DUPLICATE_PROCUREMENT_PROCESS")
            seen.add(key)
            release_at = _utc(item["notice_release_at"])
            close = _utc(item["tender_closes_at"])
            if release_at > snapshot_at or close <= snapshot_at:
                raise ValueError("INCONSISTENT_NOTICE_TIMELINE")
            remaining = close - current
            if remaining.total_seconds() <= 0:
                urgency = "CLOSED_AFTER_LAST_SOURCE_OBSERVATION"
            elif remaining <= timedelta(hours=72):
                urgency = "DUE_WITHIN_72_HOURS"
            elif remaining <= timedelta(days=7):
                urgency = "DUE_WITHIN_7_DAYS"
            else:
                urgency = "FUTURE_DEADLINE"
            review = item["review_status"]
            if review in NO_PAID:
                decision = "HOLD_PAID_TRAFFIC_OR_UNCLEAR_PAID_SCOPE"
            elif review in NO_FIT:
                decision = "HOLD_CUSTOM_SCOPE_OR_SUPPLIER_FIT"
            else:
                raise ValueError("UNKNOWN_HOLD")
            listed.append({
                "source": item["source"],
                "ocid": item["ocid"],
                "title": item["title"],
                "buyer_organisation": item["buyer_organisation"],
                "official_notice_url": item["notice_url"],
                "tender_closes_at_utc": close.isoformat(),
                "published_estimated_value_gbp": item.get("published_estimated_value_gbp"),
                "published_value_source": item.get("published_value_source"),
                "published_sme_suitable": item.get("published_sme_suitable"),
                "published_contract_start_at": item.get("published_contract_start_at"),
                "published_contract_end_at": item.get("published_contract_end_at"),
                "deadline_urgency": urgency,
                "deadline_last_confirmed_by_aggregated_feed_at_utc": snapshot_at.isoformat(),
                "individual_document_and_amendment_recheck_required": True,
                "policy_or_supplier_hold": decision,
                "original_review_status": review,
                "buyer_verified_for_empire_ai": False,
                "document_reviewed": False,
                "bid_eligible": False,
                "bid_authorized": False,
                "contact_authorized": False,
                "required_next_action": (
                    "RECONFIRM_LATEST_OFFICIAL_NOTICE_AND_DOCUMENTS_WITH_ORIGINAL_OWNER"
                    if urgency != "CLOSED_AFTER_LAST_SOURCE_OBSERVATION"
                    else "DO_NOT_BID_CLOSED_NOTICE"
                ),
            })
        listed.sort(key=lambda x: (x["tender_closes_at_utc"], x["source"], x["ocid"]))
        result.update({
            "status": READY_STATUS,
            "original_feed_observed_at_utc": snapshot_at.isoformat(),
            "triaged_at_utc": current.isoformat(),
            "releases_inspected_in_original_feed": packet["releases_inspected"],
            "notice_count": len(listed),
            "due_within_72_hours_count": sum(x["deadline_urgency"] == "DUE_WITHIN_72_HOURS" for x in listed),
            "due_within_7_days_count": sum(x["deadline_urgency"] == "DUE_WITHIN_7_DAYS" for x in listed),
            "closed_after_snapshot_count": sum(x["deadline_urgency"] == "CLOSED_AFTER_LAST_SOURCE_OBSERVATION" for x in listed),
            "paid_traffic_or_scope_hold_count": sum(x["policy_or_supplier_hold"] == "HOLD_PAID_TRAFFIC_OR_UNCLEAR_PAID_SCOPE" for x in listed),
            "supplier_or_custom_scope_hold_count": sum(x["policy_or_supplier_hold"] == "HOLD_CUSTOM_SCOPE_OR_SUPPLIER_FIT" for x in listed),
            "items": listed,
        })
    except (ValueError, KeyError, TypeError, OverflowError):
        return result
    return result


def review_existing_report(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    failed = triage(None, now=now or datetime.now(timezone.utc))
    path = root / REPORT
    try:
        if path.is_symlink() or path.parent.is_symlink():
            return failed
        st = path.stat()
        if (not stat.S_ISREG(st.st_mode)
                or st.st_size <= 0 or st.st_size > 200_000
                or st.st_mode & 0o077
                or st.st_uid not in (os.geteuid(), 0)):
            return failed
        data = json.loads(path.read_text(encoding="utf-8"))
        return triage(data, now=now or datetime.now(timezone.utc))
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        return failed


def save_private_result(root: Path, review: dict[str, Any]) -> None:
    if review["status"] != READY_STATUS:
        raise ValueError("HELD_REVIEW_NOT_PERSISTED")
    target = root / OUTPUT
    folder = target.parent
    if (folder.is_symlink() or not folder.is_dir()
            or target.is_symlink() or
            (target.exists() and
             (not target.is_file() or target.stat().st_mode & 0o077))):
        raise ValueError("UNSAFE_PRIVATE_OUTPUT")
    fd, temp = tempfile.mkstemp(prefix=".tender-deadlines-", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            os.fchmod(file.fileno(), 0o600)
            json.dump(review, file, sort_keys=True, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Existing EmpireOS official tender deadline desk (read-only)")
    parser.add_argument("--repo-root", default=str(DEFAULT_ROOT))
    parser.add_argument("--write-private", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    report = review_existing_report(root)
    if report["status"] == READY_STATUS and args.write_private:
        try:
            save_private_result(root, report)
        except (OSError, ValueError):
            report = triage(None, now=datetime.now(timezone.utc))
    summary = {k: v for k, v in report.items() if k not in ("items",)}
    summary["private_review_written"] = report["status"] == READY_STATUS and args.write_private
    print(json.dumps(summary, sort_keys=True))
    return 0 if report["status"] == READY_STATUS else 2


if __name__ == "__main__":
    raise SystemExit(main())
