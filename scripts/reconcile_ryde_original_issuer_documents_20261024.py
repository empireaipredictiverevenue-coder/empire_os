"""Hash-pinned Ryde council tender documents: read-only evidence, no bid authority.

Only the four exact public files the issuer itself links from its
Transparency page. Source bytes are checked against independently reviewed
SHA-256 digests; unexpected changes HOLD, never update pins automatically.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from scripts.review_official_tender_founder_deadlines_20261024 import (
    READY_STATUS as DEADLINE_READY, review_existing_report,
)

ROOT = Path("/srv/empire_os")
OUTPUT = Path("runtime/acquisition_research/ryde_gdpr_issuer_requirements_latest.json")
SCHEMA = "empire.ryde_gdpr_public_issuer_requirements.v1"
READY = "ORIGINAL_ISSUER_REQUIREMENTS_VERIFIED_BID_AUTHORITY_HELD"
HELD = "HELD_ORIGINAL_ISSUER_REQUIREMENTS_UNVERIFIED"
URL_BASE = "https://rydetowncouncil.gov.uk/wp-content/uploads/2026/10/"
PAGE = "https://rydetowncouncil.gov.uk/transparency/"
NOTICE = "https://www.contractsfinder.service.gov.uk/Notice/5f4d9841-b30a-42bb-b122-3f7758606443"
OCID = "ocds-b5fd17-4f1d763a-8ba8-4b2c-9b97-6ea1e7ab3a42"
MAX_BYTES = 600_000
FILES: dict[str, tuple[str, str, str]] = {
    "request_to_quote": (
        "Request-to-Quote-Data-Audit-1.pdf", "application/pdf",
        "15a945b4f5201af7382cf66e9320dfb6a4bc02bf00635cf194c7f7e69bac99a9",
    ),
    "due_diligence": (
        "Due-Dilligence-Check-Sheet-Summary-1.pdf", "application/pdf",
        "88eb0a30a0b44e47bc662253da67816905157fd4e6312456ff8b795aa4e20f3f",
    ),
    "pricing_schedule": (
        "Pricing-Shedule-Data-Audit-1.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "4394e43b34263cacd51d717a81776165cacfc6ef3e3aa2b1bea11d9d05879ae9",
    ),
    "references": (
        "References-1.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "42a9bcfc7d5c7474d621f934fb19f488083bb01f50d7f3be687ea53e7f8fdfb3",
    ),
}
REQUIREMENTS = [
    "Named auditor(s) with recognised data-protection qualification (BCS Practitioner, PC.dp, CIPP/E or equivalent)",
    "Evidence of comparable completed public-sector data-protection audits",
    "Independence and conflict-of-interest declaration",
    "ICO registration and own documented data-protection and information-security arrangements",
    "Professional indemnity insurance at least GBP 5,000,000",
    "Public liability insurance at least GBP 5,000,000",
    "Two comparable customer references from last three years",
    "At least some audit fieldwork on site in Ryde",
    "Review data mapping, ROPA, lawful basis, DPIAs, privacy notices, security, retention, rights, data-sharing, breaches, training and CCTV",
    "Editable audit plan, findings with RAG ratings, prioritised action plan, ROPA, information asset/data-flow register, final report and councillor presentation",
    "Supplier financial/accounts evidence and applicable health-and-safety information in published due-diligence form",
]
NO_BID_REASON = "SPECIALIST_SUPPLIER_CREDENTIALS_INSURANCE_REFERENCES_AND_INDEPENDENCE_NOT_VERIFIED"


def _safe_url(url: str) -> bool:
    parsed = urlsplit(url)
    return (parsed.scheme == "https" and parsed.hostname == "rydetowncouncil.gov.uk"
        and parsed.netloc == "rydetowncouncil.gov.uk"
        and parsed.query == "" and parsed.fragment == ""
        and parsed.username is None and parsed.password is None
        and url.startswith(URL_BASE)
        and url in {URL_BASE + entry[0] for entry in FILES.values()})


def _fetch(url: str) -> Mapping[str, Any]:
    import requests
    if not _safe_url(url):
        raise ValueError("OFF_ISSUER_DOCUMENT_REJECTED")
    response = requests.get(
        url, timeout=(4, 12), stream=True, allow_redirects=False,
        headers={"Accept": "application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                 "User-Agent": "EmpireOS-Original-Issuer-Tender-Review/1.0"},
    )
    try:
        body = response.raw.read(MAX_BYTES + 1, decode_content=True)
        return {
            "status": response.status_code,
            "url": response.url,
            "content_type": str(response.headers.get("Content-Type") or "").split(";")[0].strip().lower(),
            "body": body,
        }
    finally:
        response.close()


def _docx_body_contains(body: bytes, phrases: tuple[str, ...]) -> bool:
    try:
        with zipfile.ZipFile(BytesIO(body)) as archive:
            member = archive.getinfo("word/document.xml")
            if member.file_size > 800_000:
                return False
            root = ET.fromstring(archive.read(member))
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        text = " ".join(
            "".join(element.text or "" for element in paragraph.iter(namespace + "t"))
            for paragraph in root.iter(namespace + "p")
        ).casefold()
        return all(value.casefold() in text for value in phrases)
    except (zipfile.BadZipFile, KeyError, ValueError, ET.ParseError, RuntimeError):
        return False


def verify_public_documents(
    *, source_report: Mapping[str, Any],
    fetch: Callable[[str], Mapping[str, Any]] = _fetch,
) -> dict[str, Any]:
    fail = {
        "schema_version": SCHEMA,
        "status": HELD,
        "bid_eligibility_verified": False,
        "buyer_closing_date_authoritatively_reconciled": False,
        "bid_authorized": False,
        "contact_authorized": False,
        "external_bid_submitted": False,
        "crm_writes": False,
        "email_sent": False,
        "payment_actions": False,
        "verified_contract_value_gbp": None,
        "verified_profit_margin": None,
    }
    try:
        if (not isinstance(source_report, Mapping)
            or source_report.get("status") != DEADLINE_READY
            or source_report.get("external_bids_authorized") is not False
            or source_report.get("source_qualified_customer_count") != 0):
            raise ValueError("ORIGINAL_SOURCE_REVIEW_REQUIRED")
        targets=[x for x in source_report.get("items",[])
            if x.get("ocid")==OCID and x.get("official_notice_url")==NOTICE]
        if (len(targets)!=1 or targets[0].get("bid_authorized") is not False
                or targets[0].get("bid_eligible") is not False
                or targets[0].get("policy_or_supplier_hold") != "HOLD_CUSTOM_SCOPE_OR_SUPPLIER_FIT"
                or targets[0].get("tender_closes_at_utc") != "2026-10-26T12:00:00+00:00"):
            raise ValueError("ORIGINAL_OCDS_IDENTITY_OR_DEADLINE_DRIFT")
        checked=[]
        for label,(filename,mime,digest) in FILES.items():
            url=URL_BASE+filename
            reply=fetch(url)
            body=reply.get("body")
            if (reply.get("status")!=200 or reply.get("url")!=url
                or reply.get("content_type")!=mime
                or not isinstance(body,bytes) or not 1000<len(body)<=MAX_BYTES
                or sha256(body).hexdigest()!=digest):
                raise ValueError("PUBLIC_ISSUER_CONTENT_CHANGED_OR_UNAVAILABLE")
            if mime=="application/pdf":
                if not body.startswith(b"%PDF-") or b"%%EOF" not in body[-2048:]:
                    raise ValueError("NOT_AN_INTACT_ISSUER_PDF")
            else:
                required = (
                    ("Pricing schedule", "GRAND TOTAL")
                    if label=="pricing_schedule"
                    else ("References","Reference 1","Reference 2")
                )
                if not _docx_body_contains(body,required):
                    raise ValueError("ISSUER_DOCX_TEMPLATE_STRUCTURE_MISMATCH")
            checked.append({
                "document_type":label,
                "original_publisher_url":url,
                "content_sha256":digest,
                "publisher_bytes_validated":True,
                "not_issuer_sealed_after_download":True,
            })
        return {
            **fail, "status": READY,
            "source_review_verified_at_utc": datetime.now(timezone.utc).isoformat(),
            "issuer_transparency_page": PAGE,
            "official_contracts_finder_notice": NOTICE,
            "ocid":OCID,
            "issuer_document_count":4,
            "documents":checked,
            "reviewed_original_pdf_sha256":FILES["request_to_quote"][2],
            "published_requirements":list(REQUIREMENTS),
            "conditions_supported_by_original_council_document": True,
            "clarification_deadline_from_issuer_document": "2026-10-26",
            "quotation_deadline_from_issuer_document": "2026-11-02T12:00:00+00:00",
            "feed_closing_datetime": "2026-10-26T12:00:00+00:00",
            "source_deadline_conflict": True,
            "action": "EXACT_DEADLINE_MUST_BE_CONFIRMED_BY_ORIGINAL_ISSUER_NO_BID_UNTIL_SUPPLIER_PROOF",
            "supplier_capability": "NOT_VERIFIED",
            "independent_auditor_qualification": "NOT_VERIFIED",
            "public_sector_references": "NOT_VERIFIED",
            "insurance_limits": "NOT_VERIFIED",
            "ico_registration": "NOT_VERIFIED",
            "data_security_terms": "SOURCE_SCOPE_REQUIRES_SUPPLIER_REVIEW",
            "minimum_onsite_fieldwork": "REQUIRED_BY_ORIGINAL_ISSUER",
            "ownership_of_deliverables": "RYDE_TOWN_COUNCIL",
            "payment_terms_as_stated_percent": [20,20,30,30],
            "payment_method_as_stated": "BANK_TRANSFER",
            "contract_value_in_issuer_pricing_template": None,
            "pricing_template_prepopulated": False,
            "bid_eligibility_hold_reason": NO_BID_REASON,
        }
    except Exception:
        # Remote HTTPS, decompression and untrusted source failures must remain
        # a private HELD receipt, never a permission to submit a tender.
        return fail


def review_live(root: Path) -> dict[str, Any]:
    source = review_existing_report(root,now=datetime.now(timezone.utc))
    return verify_public_documents(source_report=source)


def write_private(root: Path, report: Mapping[str, Any]) -> Path:
    if report.get("status") != READY:
        raise ValueError("HELD_REPORT_CANNOT_BE_PUBLISHED")
    root=Path(root).resolve(strict=True)
    path=root/OUTPUT
    folder=path.parent
    if (folder.is_symlink() or not folder.is_dir()
        or stat.S_IMODE(folder.stat().st_mode)!=0o700
        or path.is_symlink()
        or (path.exists() and (not path.is_file()
            or stat.S_IMODE(path.stat().st_mode)!=0o600))):
        raise ValueError("PRIVATE_OUTPUT_INVALID")
    fd,tmp=tempfile.mkstemp(prefix=".ryde-issuer-",suffix=".json",dir=folder)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            os.fchmod(f.fileno(),0o600)
            json.dump(report,f,indent=2,sort_keys=True)
            f.write("\n")
            f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return path


def main() -> int:
    import argparse
    parser=argparse.ArgumentParser(description="Issuer-owned Ryde tender sources, no supplier bid")
    parser.add_argument("--repo-root",default=str(ROOT))
    parser.add_argument("--write-private",action="store_true")
    args=parser.parse_args()
    try:
        result=review_live(Path(args.repo_root))
        saved=False
        if result["status"]==READY and args.write_private:
            write_private(Path(args.repo_root),result)
            saved=True
    except (OSError,ValueError):
        result=verify_public_documents(source_report={})
        saved=False
    summary={k:v for k,v in result.items() if k not in ("documents","published_requirements")}
    summary["private_record_written"]=saved
    print(json.dumps(summary,sort_keys=True))
    return 0 if result["status"]==READY else 2

if __name__=="__main__":
    raise SystemExit(main())
