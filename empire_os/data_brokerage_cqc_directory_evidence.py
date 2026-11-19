"""CQC official care-location directory in existing EmpireOS Data Brokerage owner.

One official OGL CSV, located through CQC's own data page. No people,
phones, address, emails, registration manager or care recipient fields.
A private, source-linked full directory and a small signed control manifest
are refreshed at most weekly through the original broker source owner.

This is an INTERNAL evidence dataset, not a customer-export, outreach list
or verified company registry. A vanished listing is not a closed business.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit
import csv
import json
import os
import re
import tempfile

CANONICAL=Path("/srv/empire_os")
SCHEMA="empire.brokerage.cqc_organisation_directory.v1"
SOURCE_PAGE="https://www.cqc.org.uk/about-us/transparency/using-cqc-data"
SOURCE_RX=re.compile(r"https://www\.cqc\.org\.uk/system/files/20\d{2}-\d{2}/\d{1,2}_[A-Za-z]+_20\d{2}_CQC_directory\.csv$")
DATE_TEXT_RX=re.compile(r"^This data was produced on (\d{1,2} [A-Za-z]+ 20\d{2})$")
LOC_RX=re.compile(r"(?:1-[0-9]{4,18}|[A-Z][A-Z0-9]{2,10})$")  # Includes NHS RA7, RP1 identifiers
MAX_PAGE_BYTES=280_000
MAX_CSV_BYTES=26_000_000
MAX_ROWS=145_000
MIN_ROWS_FOR_ORIGINAL_FULL_EXPORT=15_000
REFRESH_AFTER=timedelta(days=7)
BASE=Path("runtime/data_brokerage")
MANIFEST=BASE/"cqc_provider_directory_manifest_latest.json"
OGL_URL="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
CSV_HEADERS=(
    "Name","Provider name","Service types","Date of latest check",
    "Local authority","Region","Location URL",
    "CQC Location ID (for office use only)",
    "CQC Provider ID (for office use only)",
)
FORBIDDEN_FIELDS=(
    "Phone number","Address","Postcode","Also known as",
    "Service's website (if available)","Specialisms/services",
)
NO_SEND={"customer_distribution_authorized":False,
         "sales_outreach_authorized":False,"contact_enrichment_authorized":False,
         "crm_writes":False,"payments_authorized":False,
         "personal_information_export_authorized":False}


def signature(doc):
    return sha256(json.dumps(doc,sort_keys=True,ensure_ascii=False,
                            separators=(",",":"),allow_nan=False).encode()).hexdigest()


def _aware(now):
    now=now or datetime.now(timezone.utc)
    if not isinstance(now,datetime) or not now.tzinfo or now.utcoffset() is None:
        raise ValueError("cqc_requires_aware_observation_time")
    return now.astimezone(timezone.utc)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _SourceAnchor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.href=None
        self.label=[]
        self.matched=[]

    def handle_starttag(self,tag,attrs):
        if tag=="a":
            self.href=dict(attrs).get("href")
            self.label=[]

    def handle_data(self,data):
        if self.href is not None:
            self.label.append(data)

    def handle_endtag(self,tag):
        if tag=="a" and self.href is not None:
            if " ".join("".join(self.label).split()).casefold()=="cqc care directory - csv":
                self.matched.append(self.href)
            self.href=None


def find_official_csv_link(html):
    if not isinstance(html,str) or len(html)>MAX_PAGE_BYTES:
        raise ValueError("cqc_official_directory_page_invalid")
    parser=_SourceAnchor()
    parser.feed(html)
    links=set(parser.matched)
    if len(links)!=1:
        raise ValueError("cqc_directory_anchor_missing_or_ambiguous")
    url=next(iter(links))
    if not SOURCE_RX.fullmatch(url):
        raise ValueError("cqc_directory_url_wrong_issuer")
    return url


def _download(url,max_bytes,accept):
    if url!=SOURCE_PAGE and not SOURCE_RX.fullmatch(url):
        raise ValueError("cqc_unapproved_source_destination")
    req=Request(url,headers={"User-Agent":"EmpireAI-Data-Brokerage-Evidence/1.0 (empire-ai.co.uk)",
                             "Accept":accept},method="GET")
    with build_opener(_NoRedirect).open(req,timeout=20) as response:
        if response.status!=200 or response.geturl()!=url:
            raise ValueError("cqc_unverified_download_status_or_redirect")
        media=response.headers.get("Content-Type","").lower()
        expected="text/html" if url==SOURCE_PAGE else "text/csv"
        if not media.startswith(expected):
            raise ValueError("cqc_original_media_type_unverified")
        blob=response.read(max_bytes+1)
    if len(blob)>max_bytes or not blob:
        raise ValueError("cqc_official_source_size_invalid")
    return blob


def _clean(value,max_len):
    if not isinstance(value,str):
        return None
    value=" ".join(value.split()).strip()
    if not value or len(value)>max_len or any(ord(c)<32 for c in value):
        return None
    return value


def _segment(service):
    s=(service or "").lower()
    if "dentist" in s:return "dentistry"
    if "homecare" in s:return "homecare"
    if "nursing homes" in s:return "nursing_care"
    if "residential homes" in s:return "residential_care"
    if "hospital" in s:return "hospital"
    if "doctors/gps" in s:return "primary_care"
    if "mental health" in s:return "mental_health"
    if "ambulance" in s:return "ambulance"
    return "other_regulated_care"


def normalize_cqc_csv(csv_content,*,source_url):
    """Pure deterministic conversion; only nine selected organisation fields."""
    if not SOURCE_RX.fullmatch(source_url) or not isinstance(csv_content,bytes):
        raise ValueError("cqc_unverified_official_csv")
    if len(csv_content)>MAX_CSV_BYTES or len(csv_content)<120:
        raise ValueError("cqc_csv_size_invalid")
    try:
        text=csv_content.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("cqc_csv_encoding_failure") from exc
    reader=csv.reader(StringIO(text,newline=""))
    try:
        title=next(reader)
        next(reader)
        dated=next(reader)
        next(reader)
        headers=next(reader)
    except StopIteration as exc:
        raise ValueError("cqc_csv_required_metadata_missing") from exc
    if title[0]!="CQC Locations data" or not dated or not DATE_TEXT_RX.fullmatch(dated[0]):
        raise ValueError("cqc_publication_date_missing")
    published=datetime.strptime(DATE_TEXT_RX.fullmatch(dated[0]).group(1),"%d %B %Y").date()
    file_name=source_url.rsplit("/",1)[-1]
    if not file_name.lower().startswith(
        f"{published.day:02d}_{published.strftime('%B')}_{published.year}".lower()
    ) and not file_name.lower().startswith(
        f"{published.day}_{published.strftime('%B')}_{published.year}".lower()
    ):
        raise ValueError("cqc_filename_source_date_mismatch")
    if len(headers)!=len(set(headers)) or not set(CSV_HEADERS).issubset(headers):
        raise ValueError("cqc_source_column_schema_mismatch")
    items=[]
    loc_ids=set()
    provider_ids=set()
    segments=Counter()
    memberships=Counter()
    missing=Counter()
    for idx,values in enumerate(reader,start=1):
        if len(items)>=MAX_ROWS:
            raise ValueError("cqc_source_row_limit")
        if len(values)!=len(headers):
            raise ValueError("cqc_source_row_wrong_column_count")
        row=dict(zip(headers,values))
        location=row["CQC Location ID (for office use only)"].strip()
        provider=row["CQC Provider ID (for office use only)"].strip()
        url=row["Location URL"].strip()
        if not LOC_RX.fullmatch(location) or not LOC_RX.fullmatch(provider):
            raise ValueError("cqc_official_location_or_provider_id_invalid")
        if url!=f"https://www.cqc.org.uk/location/{location}":
            raise ValueError("cqc_location_source_link_wrong_id")
        if location in loc_ids:
            raise ValueError("cqc_duplicate_location_id_not_safely_deduplicated")
        loc_ids.add(location)
        provider_ids.add(provider)
        service=_clean(row["Service types"],900)  # NHS multi-specialty locations can exceed 500 chars
        name=_clean(row["Name"],200)
        organisation=_clean(row["Provider name"],200)
        if not name or not organisation or not service:
            raise ValueError("cqc_required_organisation_field_missing")
        local=_clean(row["Local authority"],100)
        region=_clean(row["Region"],100)
        if not local:missing["local_authority"]+=1
        if not region:missing["region"]+=1
        segment=_segment(service)
        per_service=sorted({_segment(x) for x in service.split("|") if x.strip()})
        segments[segment]+=1
        memberships.update(per_service)
        item={
            "source_id":"gb_cqc_care_provider_organisations",
            "entity_kind":"regulated_care_location",
            "entity_id":"cqc_location:"+location,
            "location_id":location,
            "provider_id":provider,
            "location_name":name,
            "registered_provider_name":organisation,
            "service_types_as_published":service,
            "service_segment":segment,
            "service_market_memberships":per_service,
            "local_authority":local,
            "region":region,
            "latest_check_as_published":_clean(row["Date of latest check"],42),
            "official_location_url":url,
        }
        assert not (set(item)&set(FORBIDDEN_FIELDS))
        items.append(item)
    if not items:
        raise ValueError("cqc_original_no_organisations")
    items.sort(key=lambda x:x["location_id"])
    return {
        "publication_date":published.isoformat(),
        "records":items,
        "provider_ids":len(provider_ids),
        "location_count":len(items),
        "segment_counts":dict(sorted(segments.items())),
        "overlapping_market_membership_counts":dict(sorted(memberships.items())),
        "missing_geographic_fields":dict(sorted(missing.items())),
    }


def _private_write(path,data):
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("cqc_unsafe_receipt_or_data_path")
    path.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
    path.parent.chmod(0o700)
    fd,stage=tempfile.mkstemp(prefix=".cqc_stage_",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(stage,0o600)
        os.replace(stage,path)
    finally:
        if os.path.exists(stage):os.unlink(stage)


def _read_manifest(path):
    if path.is_symlink():raise ValueError("cqc_manifest_symlink")
    if not path.exists():return None
    if not path.is_file() or not 0<path.stat().st_size<30_000:
        raise ValueError("cqc_manifest_size_invalid")
    x=json.loads(path.read_text())
    if x.get("schema_version")!=SCHEMA:
        raise ValueError("cqc_manifest_schema_changed")
    unsigned=dict(x)
    expected=unsigned.pop("integrity_sha256",None)
    if signature(unsigned)!=expected:
        raise ValueError("cqc_manifest_signature_invalid")
    return x


def _load_records(root,manifest):
    """Read a signed immutable internal data file. Never trust arbitrary paths."""
    hex_sha=manifest["csv_sha256"]
    if not re.fullmatch(r"[0-9a-f]{64}",hex_sha):
        raise ValueError("cqc_source_digest_invalid")
    p=root/BASE/f"cqc_locations_{hex_sha[:24]}.jsonl"
    if p.is_symlink() or not p.is_file() or p.stat().st_size>37_000_000:
        raise ValueError("cqc_private_data_missing")
    raw=p.read_bytes()
    if sha256(raw).hexdigest()!=manifest["records_sha256"]:
        raise ValueError("cqc_private_data_integrity_failure")
    entries=[json.loads(line) for line in raw.splitlines()]
    if len(entries)!=manifest["locations"]:
        raise ValueError("cqc_record_count_mismatch")
    return entries


def _changes(old,now):
    prior={x["entity_id"]:x for x in old}
    next_={x["entity_id"]:x for x in now}
    shared=prior.keys() & next_.keys()
    attributes=("provider_id","location_name","registered_provider_name",
                "service_types_as_published","service_segment","local_authority",
                "region","latest_check_as_published")
    changed=[]
    for key in sorted(shared):
        delta={a:{"from":prior[key][a],"to":next_[key][a]}
               for a in attributes if prior[key][a]!=next_[key][a]}
        if delta:
            if len(changed)<12:
                changed.append({"entity_id":key,
                                "official_source_url":next_[key]["official_location_url"],
                                "source_reported_field_changes":delta,
                                "actual_care_service_or_ownership_event_verified":False})
    return {
        "unchanged_or_unmeasured_not_customer_change_feed":False,
        "source_newly_listed_not_confirmed_new_openings":len(next_.keys()-prior.keys()),
        "source_absent_not_confirmed_closures":len(prior.keys()-next_.keys()),
        "source_reported_changed_locations":sum(
            any(prior[k][a]!=next_[k][a] for a in attributes) for k in shared),
        "illustrative_source_changes":changed,
        "independently_verified_business_events":0,
        "customer_delivery_authorized":False,
    }


def run_existing_broker_cqc_directory(root,*,now=None,fetch=_download,persist=True):
    root=Path(root).resolve()
    if root!=CANONICAL:
        return {"status":"NONCANONICAL_CQC_NO_NETWORK",
                "external_requests":0,"customer_distribution_authorized":False}
    when=_aware(now)
    path=root/MANIFEST
    previous=_read_manifest(path)
    if not persist:
        return {"status":"READ_ONLY_CQC_EVIDENCE",
                "previous":previous["last_checked_at"] if previous else None,
                "external_requests":0,"customer_distribution_authorized":False}
    if previous:
        last=_aware(datetime.fromisoformat(previous["last_checked_at"]))
        if last>when+timedelta(minutes=5):
            raise ValueError("cqc_future_manifest_timestamp")
        if when-last<REFRESH_AFTER:
            return {"status":"ORIGINAL_CQC_DIRECTORY_FRESH",
                    "locations":previous["locations"],
                    "provider_ids":previous["provider_ids"],
                    "source_publication_date":previous["publication_date"],
                    "external_requests":0,"customer_distribution_authorized":False}
    page=fetch(SOURCE_PAGE,MAX_PAGE_BYTES,"text/html")
    url=find_official_csv_link(page.decode("utf-8"))
    csv_blob=fetch(url,MAX_CSV_BYTES,"text/csv")
    sha=sha256(csv_blob).hexdigest()
    if previous and previous["csv_sha256"]==sha:
        result=dict(previous)
        result["last_checked_at"]=when.isoformat()
        result["status"]="CQC_ORIGINAL_SOURCE_EXPORT_UNCHANGED"
        result.pop("integrity_sha256",None)
        result["integrity_sha256"]=signature(result)
        _private_write(path,json.dumps(result,sort_keys=True).encode())
        return {"status":result["status"],
                "locations":result["locations"],
                "provider_ids":result["provider_ids"],
                "external_requests":2,"customer_distribution_authorized":False}
    parsed=normalize_cqc_csv(csv_blob,source_url=url)
    if len(parsed["records"])<MIN_ROWS_FOR_ORIGINAL_FULL_EXPORT:
        raise ValueError("cqc_full_directory_unexpectedly_incomplete")
    prior_entries=_load_records(root,previous) if previous else None
    changed=_changes(prior_entries,parsed["records"]) if prior_entries is not None else {
        "status":"FIRST_OBSERVATION_IS_NOT_A_CHANGE_EVENT",
        "source_newly_listed_not_confirmed_new_openings":0,
        "source_absent_not_confirmed_closures":0,
        "source_reported_changed_locations":0,
        "illustrative_source_changes":[],
        "independently_verified_business_events":0,
        "customer_delivery_authorized":False,
    }
    lines=b"".join(
        (json.dumps(row,sort_keys=True,ensure_ascii=False,
                    separators=(",",":"),allow_nan=False)+"\n").encode()
        for row in parsed["records"]
    )
    if len(lines)>37_000_000:
        raise ValueError("cqc_private_directory_output_too_large")
    data_path=root/BASE/f"cqc_locations_{sha[:24]}.jsonl"
    if data_path.exists():
        if data_path.is_symlink() or sha256(data_path.read_bytes()).hexdigest()!=sha256(lines).hexdigest():
            raise ValueError("cqc_immutable_snapshot_collision")
    else:
        _private_write(data_path,lines)
    manifest={
        "schema_version":SCHEMA,
        "status":"CQC_OFFICIAL_FULL_ORGANISATION_DIRECTORY_SAMPLED",
        "last_checked_at":when.isoformat(),
        "publication_date":parsed["publication_date"],
        "days_since_official_publication":(
            when.date()-datetime.fromisoformat(parsed["publication_date"]).date()
        ).days,
        "publication_lag_or_update_warning":True,
        "source_web_page":SOURCE_PAGE,
        "original_csv_url":url,
        "original_cqc_attribution":"Contains public sector information licensed under the Open Government Licence v3.0",
        "licence_url":OGL_URL,
        "csv_sha256":sha,
        "records_sha256":sha256(lines).hexdigest(),
        "locations":parsed["location_count"],
        "provider_ids":parsed["provider_ids"],
        "segment_counts":parsed["segment_counts"],
        "overlapping_market_membership_counts":parsed["overlapping_market_membership_counts"],
        "missing_geographic_fields":parsed["missing_geographic_fields"],
        "record_schema_fields":list(parsed["records"][0]),
        "excluded_source_fields":list(FORBIDDEN_FIELDS),
        "source_provider_ids_are_not_independently_verified_company_registration":True,
        "sole_trader_public_names_may_require_privacy_review":True,
        "source_review_claims":changed,
        "signed_first_party_export":False,
        "official_url_and_field_integrity_verified":True,
        "data_release_state":"INTERNAL_RESEARCH_ONLY_NOT_CUSTOMER_CLEARED",
        **NO_SEND,
    }
    manifest["integrity_sha256"]=signature(manifest)
    _private_write(path,json.dumps(manifest,sort_keys=True,ensure_ascii=False).encode())
    return {"status":manifest["status"],"locations":manifest["locations"],
            "provider_ids":manifest["provider_ids"],
            "segment_counts":manifest["segment_counts"],
            "publication_date":manifest["publication_date"],
            "days_since_publication":manifest["days_since_official_publication"],
            "metadata_change_count":changed["source_reported_changed_locations"],
            "integrity_sha256":manifest["integrity_sha256"],
            "external_requests":2,
            "customer_distribution_authorized":False,"outbound_sent":False}
