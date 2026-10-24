"""Private tender RFQ drop and documentary chain of custody for EmpireOS.

This is an *internal evidence inventory*, not an interpretation of supplier
RFQ clauses or proof that a tender issuer authored the supplied bytes.
Only explicitly staged PDFs/DOCX under one fixed root are accepted.
No network, LLM, email, supplier portal access, tender submission, DB write,
credential validation, external action or commercial authority is granted.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from io import BytesIO
import os
from pathlib import Path
import re
import stat
import tempfile
import zipfile
from typing import Any

BASE = Path("runtime/acquisition_research")
DROP = BASE / "tender_supplier_documents" / "CA18567"
RECEIPT = BASE / "land_guide_supplier_documents_inventory_latest.json"
SCHEMA = "empire.tender_supplier_document_inventory.v1"
AWAIT = "AWAIT_AUTHORISED_MULTIQUOTE_RFQ_FILES"
OBSERVED = "SUPPLIER_FILES_OBSERVED_NOT_AUTHENTICATED_OR_REVIEWED"
HELD = "HELD_UNSAFE_OR_UNSUPPORTED_SUPPLIER_DOCUMENTS"
NAMES = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,58}\.(?:pdf|docx)", re.I)
MAX_SINGLE = 12_000_000
MAX_TOTAL = 28_000_000
MAX_FILES = 8
MAX_XML = 2_000_000
EXPECTED = {
    "reference": "CA18567",
    "ocid": "ocds-b5fd17-4321ebe7-2ddb-47fa-81f9-fa095553b41b",
    "public_document_evidence": "RFQ_CONTENT_NOT_YET_AVAILABLE_FROM_ORIGINAL_MULTIQUOTE_PORTAL",
}
REQUIREMENTS = (
    "Current RFQ and any amendments, published supplier notices and closing deadline",
    "Detailed quality evaluation subcriteria, scored answer templates and minimum thresholds",
    "Full investment land-guide technical specification, mapping/geography and scope",
    "Required supplier experience, references, company registration, insurance and conflicts",
    "Data licences, land-ownership source rights and cross-border research restrictions",
    "Expected delivery milestones, stakeholder work, design and acceptance requirements",
    "Pricing structure, VAT/tax treatment, financial standing and contract conditions",
    "Genuine eligible specialist delivery-team evidence and available time/cost quotations",
)


def _baseline(status: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA, "status": status,
        "procurement_reference": EXPECTED["reference"],
        "original_tender_ocid": EXPECTED["ocid"],
        "document_count": 0,
        "documents": [],
        "provenance_status": "NOT_AUTHENTICATED_BY_ISSUER",
        "file_contents_professionally_reviewed": False,
        "full_rfq_reviewed": False,
        "supplier_eligibility_verified": False,
        "scored_quality_criteria_verified": False,
        "price_approved": False,
        "bid_ready": False,
        "bid_authorized": False,
        "external_bid_submitted": False,
        "buyer_contacted": False,
        "crm_writes": False,
        "payment_actions": False,
        "revenue_verified": False,
        "required_supplier_and_rfq_evidence": list(REQUIREMENTS),
        "next_action": "OBTAIN_GENUINE_CA18567_RFQ_WITH_LAWFUL_SUPPLIER_PORTAL_ACCESS_AND_HUMAN_REVIEW",
    }


def _dir_safe(path: Path) -> bool:
    if path.is_symlink() or not path.is_dir():
        return False
    st=path.stat()
    return (
        stat.S_IMODE(st.st_mode)==0o700
        and st.st_uid==os.geteuid()
    )


def ensure_private_drop(root: Path) -> Path:
    """Explicit internal-only write to the existing private acquisition tree."""
    base = root / BASE
    if not _dir_safe(base):
        raise ValueError("ORIGINAL_PRIVATE_RESEARCH_FOLDER_REQUIRED")
    parent=base / "tender_supplier_documents"
    if parent.exists():
        if not _dir_safe(parent):
            raise ValueError("DOCUMENT_PARENT_NOT_PRIVATE")
    else:
        parent.mkdir(mode=0o700)
    drop=parent / "CA18567"
    if drop.exists():
        if not _dir_safe(drop):
            raise ValueError("DOCUMENT_DROP_NOT_PRIVATE")
    else:
        drop.mkdir(mode=0o700)
    return drop


def _read_pdf(data: bytes) -> bool:
    return data.startswith(b"%PDF-") and b"%%EOF" in data[-2048:]


def _docx_archive_valid(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names=archive.namelist()
            if (not names or len(names)>250 or len(names)!=len(set(names))
                or "word/document.xml" not in names
                or "[Content_Types].xml" not in names):
                return False
            total=0
            for member in archive.infolist():
                total+=member.file_size
                if (member.file_size>MAX_XML if member.filename=="word/document.xml"
                    else member.file_size>10_000_000):
                    return False
                if total > MAX_TOTAL:
                    return False
                if member.filename.startswith("/") or ".." in Path(member.filename).parts:
                    return False
            # Validates OOXML structure minimally. No extraction or parsing
            # of untrusted prose as agent instructions.
            return True
    except (OSError,ValueError,zipfile.BadZipFile,RuntimeError):
        return False


def inventory(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    moment=now or datetime.now(timezone.utc)
    held=_baseline(HELD)
    if moment.tzinfo is None:
        return held
    original=root/BASE
    parent=original/"tender_supplier_documents"
    folder=root/DROP
    try:
        if not _dir_safe(original):
            return held
        if not parent.exists() or not folder.exists():
            return _baseline(AWAIT)
        if not _dir_safe(parent) or not _dir_safe(folder):
            return held
        contents=sorted(folder.iterdir(),key=lambda p:p.name)
        if not contents:
            return _baseline(AWAIT)
        if len(contents)>MAX_FILES:
            return held
        observed=[]
        total_bytes=0
        for path in contents:
            st=path.lstat()
            if (not NAMES.fullmatch(path.name)
                or not stat.S_ISREG(st.st_mode)
                or stat.S_IMODE(st.st_mode)!=0o600
                or st.st_uid!=os.geteuid() or st.st_nlink!=1
                or st.st_size<100 or st.st_size>MAX_SINGLE):
                return held
            total_bytes+=st.st_size
            if total_bytes>MAX_TOTAL:
                return held
            # Fixed MAX_TOTAL and fixed root; reject source magic mismatches.
            if st.st_mtime > moment.timestamp() + 60:
                return held
            fd=os.open(path,os.O_RDONLY | getattr(os,"O_NOFOLLOW",0))
            try:
                opened=os.fstat(fd)
                if (not stat.S_ISREG(opened.st_mode) or opened.st_ino!=st.st_ino
                    or opened.st_dev!=st.st_dev or opened.st_size!=st.st_size):
                    return held
                with os.fdopen(fd,"rb",closefd=False) as file:
                    data=file.read(MAX_SINGLE+1)
            finally:
                os.close(fd)
            if len(data)!=st.st_size:
                return held
            suffix=path.suffix.lower()
            if (suffix==".pdf" and not _read_pdf(data)) or (
                suffix==".docx" and not _docx_archive_valid(data)):
                return held
            observed.append({
                "file_name":path.name,
                "source_document_sha256":sha256(data).hexdigest(),
                "bytes":len(data),
                "content_format":suffix[1:].upper(),
                "observed_mtime_utc":datetime.fromtimestamp(
                    st.st_mtime,tz=timezone.utc).isoformat(),
                "document_upload_origin":"UNATTESTED_LOCAL_PRIVATE_DROP",
                "issuer_authenticity_verified":False,
                "latest_amendment_verified":False,
                "human_specialist_reviewed":False,
                "parsed_as_supplier_authority":False,
            })
        return {
            **_baseline(OBSERVED),
            "document_count":len(observed),
            "documents":observed,
            "observed_at_utc":moment.astimezone(timezone.utc).isoformat(),
            "total_source_bytes":total_bytes,
            "next_action":"ORIGINAL_OWNER_VERIFY_MULTIQUOTE_DOWNLOAD_PROVENANCE_DOCUMENT_SCOPE_AND_SPECIALIST_REVIEW",
        }
    except (OSError,UnicodeError,ValueError):
        return held


def save_private(root: Path, report: dict[str, Any]) -> Path:
    if report["status"]==HELD:
        raise ValueError("UNSAFE_SOURCE_NEVER_SAVED_AS_TRUSTED")
    base=root/BASE
    if not _dir_safe(base):
        raise ValueError("ORIGINAL_PRIVATE_RESEARCH_REQUIRED")
    dest=root/RECEIPT
    if dest.is_symlink() or (dest.exists() and (
        not dest.is_file() or stat.S_IMODE(dest.stat().st_mode)!=0o600)):
        raise ValueError("UNSAFE_RECEIPT_TARGET")
    fd,tmp=tempfile.mkstemp(prefix=".supplier-docs-",suffix=".json",dir=base)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            os.fchmod(f.fileno(),0o600)
            json.dump(report,f,indent=2,sort_keys=True)
            f.write("\n");f.flush();os.fsync(f.fileno())
        os.replace(tmp,dest)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return dest
