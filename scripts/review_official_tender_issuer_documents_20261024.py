"""Original EmpireOS UK tender issuer-document index, not document verification.

Read only public official OCDS release packages for current held service
notices. Records issuer document references, amendment chronology and gaps.
Never download attachments, infer legal eligibility, submit or send anything.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Mapping
from urllib.parse import urlsplit

from empire_os.acquisition_official_tender_intake import retrieve_bounded_notices
from empire_os.data_exchange_procurement_context import OGL_V3
from scripts.review_official_tender_founder_deadlines_20261024 import (
    READY_STATUS as DEADLINE_READY, review_existing_report,
)

ROOT = Path("/srv/empire_os")
OUT = Path("runtime/acquisition_research/official_tender_issuer_document_index_latest.json")
SCHEMA = "empire.official_tender_issuer_document_index.v1"
READY = "ORIGINAL_ISSUER_DOCUMENT_REFERENCES_OBSERVED_NOT_VERIFIED"
HELD = "HELD_ORIGINAL_ISSUER_DOCUMENT_INVENTORY"
UUID = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",re.I)
GOOD_TYPES = frozenset({
    "tenderNotice", "biddingDocuments", "clarifications",
    "technicalSpecifications", "evaluationReports",
    "contractNotice", "contractSchedule",
})


def _date(raw: Any) -> datetime:
    if not isinstance(raw,str):
        raise ValueError("MISSING_DATETIME")
    value=datetime.fromisoformat(raw.replace("Z","+00:00"))
    if value.tzinfo is None:
        raise ValueError("NAIVE_DATETIME")
    return value.astimezone(timezone.utc)


def _url_is_original_document(url: Any, doc_type: str) -> bool:
    if not isinstance(url,str) or len(url)>450:
        return False
    urlparts=urlsplit(url)
    if (urlparts.scheme!="https" or urlparts.hostname!="www.contractsfinder.service.gov.uk"
            or urlparts.netloc!="www.contractsfinder.service.gov.uk"
            or urlparts.query or urlparts.fragment):
        return False
    path=urlparts.path
    if doc_type=="tenderNotice":
        return path.startswith("/Notice/") and bool(UUID.fullmatch(path.removeprefix("/Notice/")))
    return path.startswith("/Notice/Attachment/") and bool(
        UUID.fullmatch(path.removeprefix("/Notice/Attachment/"))
    )


def enumerate_issuer_references(
    packages: list[Mapping[str, Any]], targets: list[Mapping[str, Any]], *,
    observed_at: datetime
) -> dict[str, Any]:
    held = {
        "schema_version": SCHEMA, "status": HELD,
        "document_content_verified_count": 0,
        "individually_amendment_verified_count": 0,
        "buyer_permission_verified": False,
        "supplier_eligible_count": 0,
        "bid_ready_count": 0,
        "external_bid_sent": False,
        "outbound_sent": False,
        "crm_writes": False,
        "payment_mutations": False,
    }
    if observed_at.tzinfo is None or len(packages)>3 or not 1<=len(targets)<=8:
        return held
    try:
        roots={}
        for row in targets:
            if (row.get("source")!="contracts_finder"
                or row.get("policy_or_supplier_hold")!="HOLD_CUSTOM_SCOPE_OR_SUPPLIER_FIT"
                or row.get("deadline_urgency")=="CLOSED_AFTER_LAST_SOURCE_OBSERVATION"
                or not isinstance(row.get("ocid"),str)
                or not row.get("official_notice_url")):
                raise ValueError("SOURCE_TARGET_NOT_APPROVED_FOR_RESEARCH")
            key=row["ocid"]
            if key in roots:
                raise ValueError("DUPLICATE_TARGET")
            roots[key]=row
        releases={key:[] for key in roots}
        for package in packages:
            if (not isinstance(package,Mapping)
                or package.get("license")!=OGL_V3
                or (package.get("publisher") or {}).get("name")!="Cabinet Office"
                or not isinstance(package.get("releases"),list)
                or len(package["releases"])>100):
                raise ValueError("UNTRUSTED_OR_OVERSIZED_ISSUER_PACKAGE")
            for item in package["releases"]:
                if not isinstance(item,Mapping) or item.get("ocid") not in roots:
                    continue
                tender=item.get("tender")
                if not isinstance(tender,Mapping) or tender.get("status")!="active":
                    continue
                if not {"tender","tenderAmendment"}.intersection(item.get("tag") or []):
                    continue
                stamp=_date(item.get("date"))
                if stamp>observed_at:
                    raise ValueError("FUTURE_AMENDMENT")
                releases[item["ocid"]].append((stamp,item))
        items=[]
        for key,target in roots.items():
            options=releases[key]
            if not options:
                raise ValueError("TARGET_NOT_PRESENT_IN_FRESH_OFFICIAL_SOURCE")
            options.sort(key=lambda pair:pair[0],reverse=True)
            stamp,latest=options[0]
            tender=latest["tender"]
            if tender.get("title")!=target["title"]:
                raise ValueError("INCONSISTENT_LATEST_TITLE")
            if _date((tender.get("tenderPeriod") or {}).get("endDate")).isoformat()!=target["tender_closes_at_utc"]:
                raise ValueError("LATEST_ISSUER_DEADLINE_CHANGED_REQUIRES_NEW_TRIAGE")
            raw=tender.get("documents")
            if not isinstance(raw,list) or not 1<=len(raw)<=40:
                raise ValueError("ISSUER_DOCUMENT_REFERENCES_MISSING")
            docs=[]
            seen=set()
            for document in raw:
                if not isinstance(document,Mapping):
                    raise ValueError("INVALID_ISSUER_DOCUMENT")
                t=document.get("documentType")
                url=document.get("url")
                if t not in GOOD_TYPES or not _url_is_original_document(url,t) or url in seen:
                    raise ValueError("UNTRUSTED_DOCUMENT_REFERENCE")
                seen.add(url)
                docs.append({
                    "document_type":t,
                    "url":url,
                    "declared_format":document.get("format"),
                    "publisher_description":str(document.get("description") or "")[:240],
                    "content_retrieved":False,
                    "content_hash_verified":False,
                    "eligibility_requirement_read":False,
                })
            if not any(d["document_type"]=="tenderNotice" for d in docs):
                raise ValueError("OFFICIAL_NOTICE_LINK_MISSING")
            items.append({
                "ocid":key,
                "title":target["title"],
                "issuer_notice_url":target["official_notice_url"],
                "published_amendment_count_in_scan":sum(
                    "tenderAmendment" in (part.get("tag") or [])
                    for _,part in options
                ),
                "release_versions_seen":len(options),
                "latest_release_at_utc":stamp.isoformat(),
                "last_retrieved_from_original_feed_at_utc":observed_at.isoformat(),
                "document_references_count":len(docs),
                "document_access": "REFERENCES_ONLY_CONTENT_NOT_VERIFIED",
                "original_attachments_restricted_or_unread": True,
                "bid_eligibility_verified":False,
                "all_clarifications_reviewed":False,
                "issuer_documents":docs,
            })
        items.sort(key=lambda obj:obj["title"])
        return {
            **held,"status":READY,
            "target_notices":len(items),
            "document_references":sum(len(x["issuer_documents"]) for x in items),
            "issuer_amendment_references":sum(x["published_amendment_count_in_scan"] for x in items),
            "items":items,
        }
    except (ValueError, KeyError, TypeError, OverflowError):
        return held


def observe(root: Path, *, now: datetime | None = None, fetch=None) -> dict[str, Any]:
    current=now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return enumerate_issuer_references([],[],observed_at=current)
    deadline=review_existing_report(root,now=current)
    if deadline.get("status")!=DEADLINE_READY:
        return enumerate_issuer_references([],[],observed_at=current)
    targets=[
        x for x in deadline["items"]
        if x.get("source")=="contracts_finder"
        and x.get("policy_or_supplier_hold")=="HOLD_CUSTOM_SCOPE_OR_SUPPLIER_FIT"
        and x.get("deadline_urgency")!="CLOSED_AFTER_LAST_SOURCE_OBSERVATION"
    ]
    if not targets:
        return enumerate_issuer_references([],[],observed_at=current)
    start=current-timedelta(days=21)
    try:
        kw=dict(source="contracts_finder",from_iso=start.isoformat(),to_iso=current.isoformat())
        packages=retrieve_bounded_notices(**kw) if fetch is None else retrieve_bounded_notices(**kw,fetch=fetch)
        return enumerate_issuer_references(packages,targets,observed_at=current)
    except (ValueError,OSError,TimeoutError,KeyError,TypeError):
        return enumerate_issuer_references([],[],observed_at=current)


def write_private(root: Path, packet: Mapping[str, Any]) -> Path:
    if packet.get("status")!=READY:
        raise ValueError("NO_WRITE_ON_HOLD")
    root=Path(root).resolve(strict=True)
    target=root/OUT
    folder=target.parent
    if (folder.is_symlink() or not folder.is_dir()
        or stat.S_IMODE(folder.stat().st_mode)!=0o700
        or target.is_symlink()
        or (target.exists() and
            (not target.is_file() or stat.S_IMODE(target.stat().st_mode)!=0o600))):
        raise ValueError("UNSAFE_PRIVATE_ISSUER_DOCUMENT_INDEX")
    fd,temp=tempfile.mkstemp(prefix=".issuer-docs-",suffix=".json",dir=folder)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as file:
            os.fchmod(file.fileno(),0o600)
            json.dump(packet,file,sort_keys=True,indent=2)
            file.write("\n")
            file.flush();os.fsync(file.fileno())
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return target


def main() -> int:
    import argparse
    parser=argparse.ArgumentParser(description="Original issuer OCDS attachment inventory, read-only")
    parser.add_argument("--repo-root",default=str(ROOT))
    parser.add_argument("--write-private",action="store_true")
    args=parser.parse_args()
    data=observe(Path(args.repo_root))
    written=False
    if data.get("status")==READY and args.write_private:
        try:
            write_private(Path(args.repo_root),data)
            written=True
        except (ValueError,OSError):
            data=enumerate_issuer_references([],[],observed_at=datetime.now(timezone.utc))
    summary={key:value for key,value in data.items() if key!="items"}
    summary["private_index_written"]=written
    print(json.dumps(summary,sort_keys=True))
    return 0 if data["status"]==READY else 2


if __name__=="__main__":
    raise SystemExit(main())
