"""Reconcile the original £25k Dublin–Belfast tender with a public government notice.

No MultiQuote authentication, registration, buyer contact or bid submission.
This is a second public official notice mirror of the same CA18567 process;
its differing summary deadline is preserved as a conflict, not resolved away.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import unescape
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Callable, Mapping, Any
from urllib.parse import urlsplit

from scripts.review_official_tender_founder_deadlines_20261024 import (
    READY_STATUS as DEADLINES_READY, review_existing_report,
)

ROOT=Path("/srv/empire_os")
OUTPUT=Path("runtime/acquisition_research/land_guide_official_quality_weights_latest.json")
SCHEMA="empire.land_guide_original_public_notice_quality.v1"
READY="SECOND_GOVERNMENT_NOTICE_VERIFIED_RFQ_STILL_RESTRICTED"
HELD="HELD_PUBLIC_LAND_GUIDE_REQUIREMENTS_UNVERIFIED"
SOURCE_URL="https://www.sell2wales.gov.wales/search/show/search_view.aspx?ID=OCT667975&catID="
REF="CA18567"
CF_OCID="ocds-b5fd17-4321ebe7-2ddb-47fa-81f9-fa095553b41b"
FTS_OCID="ocds-h6vhtk-0787b9"
CF_NOTICE="https://www.contractsfinder.service.gov.uk/Notice/cab39ee0-c192-4fb2-9253-472214e58ca7"
EXPECTED_TITLE="RFQ 2026/43 - Development of a Dublin Belfast Economic Corridor Investment Land Guide"
EXACT_QUALITY=80
EXACT_PRICE=20


def _fetch_public(url: str) -> Mapping[str, Any]:
    import requests
    if url!=SOURCE_URL:
        raise ValueError("UNAPPROVED_SOURCE_URL")
    r=requests.get(
        url,timeout=(5,12),stream=True,allow_redirects=False,
        headers={"User-Agent":"EmpireOS-OriginalTender-OfficialNotice-Observe/1.0",
                 "Accept":"text/html"},
    )
    try:
        raw=r.raw.read(160_001,decode_content=True)
        return {"status":r.status_code, "url":r.url,
                "mime":str(r.headers.get("Content-Type","")).split(";")[0].strip().lower(),
                "raw":raw}
    finally:
        r.close()


def verify_primary_notices(
    *, deadline_review: Mapping[str, Any], fetch: Callable[[str],Mapping[str,Any]]=_fetch_public,
    observed_at: datetime,
) -> dict[str, Any]:
    held={
        "schema_version":SCHEMA,"status":HELD,
        "bid_ready":False,"supplier_eligibility_verified":False,
        "full_supplier_rfq_verified":False,
        "original_portal_registration_performed":False,
        "bid_submitted":False,"buyer_contacted":False,
        "outbound_sent":False,"crm_writes":False,"payment_actions":False,
        "customer_revenue_verified":False,
    }
    try:
        if observed_at.tzinfo is None or not isinstance(deadline_review,Mapping):
            raise ValueError("UNTRUSTED_REVIEW")
        if (deadline_review.get("status")!=DEADLINES_READY
            or deadline_review.get("external_bids_authorized") is not False
            or deadline_review.get("source_qualified_customer_count")!=0):
            raise ValueError("ORIGINAL_GOVERNOR_HELD_SOURCE_REQUIRED")
        matches=[row for row in deadline_review.get("items",[])
                 if row.get("ocid")==CF_OCID]
        if len(matches)!=1:
            raise ValueError("CANONICAL_PROCUREMENT_RECORD_MISSING")
        row=matches[0]
        if (row.get("official_notice_url")!=CF_NOTICE
            or row.get("title")!="CA18567 - "+EXPECTED_TITLE
            or row.get("policy_or_supplier_hold")!="HOLD_CUSTOM_SCOPE_OR_SUPPLIER_FIT"
            or row.get("tender_closes_at_utc")!="2026-10-30T12:00:00+00:00"
            or row.get("published_estimated_value_gbp")!="25000.00"
            or row.get("published_value_source")!="OFFICIAL_OCDS_TENDER_VALUE_NOT_BINDING"
            or row.get("published_sme_suitable") is not True
            or row.get("bid_authorized") is not False
            or row.get("bid_eligible") is not False
            or row.get("contact_authorized") is not False):
            raise ValueError("ORIGINAL_SOURCE_TERMS_MISMATCH")
        response=fetch(SOURCE_URL)
        raw=response.get("raw")
        parsed=urlsplit(str(response.get("url") or ""))
        if (response.get("status")!=200 or parsed.scheme!="https"
            or response.get("url")!=SOURCE_URL or parsed.hostname!="www.sell2wales.gov.wales"
            or response.get("mime")!="text/html"
            or not isinstance(raw,bytes) or not 800<len(raw)<160000):
            raise ValueError("GOVERNMENT_NOTICE_TRANSPORT_HELD")
        from bs4 import BeautifulSoup
        text=" ".join(BeautifulSoup(raw,"html.parser").get_text(" ",strip=True).split())
        title_marker=EXPECTED_TITLE
        if not all(token in text for token in (
            title_marker, REF, FTS_OCID,
            "Newry, Mourne and Down District Council (NMD)",
            "Below threshold - open competition",
            "25000.00 GBP",
            "30 November 2026",
            "31 March 2027",
            "26 October 2026, 12:00PM",
            "30 October 2026, 12:00PM",
            "https://suppliers.multiquote.com",
            "As per RFQ Documentation",
            "Has documents: No",
        )):
            raise ValueError("REQUIRED_PUBLIC_NOTICE_FIELDS_MISSING")
        # Do not parse loose unrelated numbers or copy a computed ranking from
        # an aggregator. The official notice's own award criteria are bound.
        m=re.search(r"\bAward criteria\b(.*?)\bSubmission\b",text,re.S|re.I)
        if not m:
            raise ValueError("NO_PUBLIC_AWARD_CRITERIA")
        award=m.group(1)
        price=re.search(r"Type:\s*price\b.*?Weighting:\s*([0-9.]+)\b",award,re.I|re.S)
        quality=re.search(r"Type:\s*quality\b.*?Weighting:\s*([0-9.]+)\b",award,re.I|re.S)
        if not price or not quality or float(price.group(1))!=20.0 or float(quality.group(1))!=80.0:
            raise ValueError("PUBLISHED_WEIGHTINGS_CHANGED")
        if "Tender submission deadline 30 October 2026, 12:00PM" not in text:
            raise ValueError("FULL_NOTICE_DEADLINE_MISMATCH")
        if "Enquiry deadline 26 October 2026, 12:00PM" not in text:
            raise ValueError("ENQUIRY_DATE_MISMATCH")
        if "Deadline date: 31 October 2026" not in text:
            raise ValueError("SUMMARY_DEADLINE_CHANGED_DO_NOT_ASSUME")
        if "Has documents: No" not in text or "As per RFQ Documentation" not in award:
            raise ValueError("PORTAL_REQUIRED_RFQ_NOT_ACCESSIBLE")
        return {
            **held,"status":READY,
            "issuer_reviewed_at_utc":observed_at.astimezone(timezone.utc).isoformat(),
            "primary_sell2wales_notice_url":SOURCE_URL,
            "primary_sell2wales_public_page_sha256":sha256(raw).hexdigest(),
            "public_sell2wales_ocid":FTS_OCID,
            "contracts_finder_ocid":CF_OCID,
            "contracts_finder_notice_url":CF_NOTICE,
            "procurement_reference":REF,
            "procurement_title":EXPECTED_TITLE,
            "purchaser":"Newry, Mourne and Down District Council (NMD)",
            "published_value_estimate_gbp":"25000.00",
            "published_quality_weight_pct":80,
            "published_price_weight_pct":20,
            "scoring_subcriteria_from_full_rfq_verified":False,
            "official_full_notice_submit_at_utc":"2026-10-30T12:00:00+00:00",
            "official_full_notice_questions_until_utc":"2026-10-26T12:00:00+00:00",
            "public_summary_displays_different_deadline":"2026-10-31",
            "summary_and_full_notice_deadline_disagree":True,
            "submit_date_authoritatively_reconciled_with_portal":False,
            "public_notice_has_supplier_documents":False,
            "supplier_document_access_status":"MULTIQUOTE_ACCOUNT_AND_RFQ_DOCUMENTS_NOT_READ",
            "public_procurement_sme_suitable":True,
            "original_rfq_supplier_qualification":"NOT_VERIFIED",
            "pricing_and_cost_basis_verified":False,
            "bid_or_price_authorised":False,
            "next_review":"OWNER_REVIEW_MULTIQUOTE_RFQ_SCORING_SUPPLIER_ELIGIBILITY_AND_DEADLINE",
        }
    except Exception:
        return held


def observe(root: Path) -> dict[str,Any]:
    now=datetime.now(timezone.utc)
    research=review_existing_report(root,now=now)
    return verify_primary_notices(deadline_review=research,observed_at=now)


def write_private(root: Path, report: Mapping[str,Any]) -> Path:
    if report.get("status")!=READY:
        raise ValueError("HELD_EVIDENCE_NOT_WRITTEN")
    root=Path(root).resolve(strict=True)
    path=root/OUTPUT;folder=path.parent
    if (folder.is_symlink() or not folder.is_dir()
        or stat.S_IMODE(folder.stat().st_mode)!=0o700
        or path.is_symlink()
        or (path.exists() and (not path.is_file()
            or stat.S_IMODE(path.stat().st_mode)!=0o600))):
        raise ValueError("PRIVATE_EVIDENCE_LOCATION_UNSAFE")
    fd,temporary=tempfile.mkstemp(prefix=".land-guide-government-",suffix=".json",dir=folder)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            os.fchmod(f.fileno(),0o600)
            json.dump(report,f,sort_keys=True,indent=2)
            f.write("\n");f.flush();os.fsync(f.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
    return path


def main() -> int:
    import argparse
    parser=argparse.ArgumentParser(description="Original public UK tender official notice reconciliation, no bid")
    parser.add_argument("--repo-root",default=str(ROOT))
    parser.add_argument("--write-private",action="store_true")
    args=parser.parse_args()
    report=observe(Path(args.repo_root))
    saved=False
    if report["status"]==READY and args.write_private:
        try:
            write_private(Path(args.repo_root),report); saved=True
        except (OSError,ValueError):
            report=verify_primary_notices(deadline_review={},observed_at=datetime.now(timezone.utc))
    summary={k:v for k,v in report.items() if k not in ("primary_sell2wales_public_page_sha256",)}
    summary["private_source_record_written"]=saved
    print(json.dumps(summary,sort_keys=True))
    return 0 if report["status"]==READY else 2


if __name__=="__main__":
    raise SystemExit(main())
