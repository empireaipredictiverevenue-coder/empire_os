"""Bounded, read-only streaming audit of an EmpireOS PostgreSQL COPY dump.

This is not a database connection or a sales-list exporter. The existing
migration-only COPY decoder is reused; raw personal/contact fields are never
decoded, printed, returned, persisted or sent to a model.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from stat import S_ISREG
from time import perf_counter
from typing import Any, Mapping
import re

from empire_os.data_cloud_shadow_dump_import import (
    _COPY_HEADER, _decode_copy_text, _digest_strings,
)

SCHEMA="empire.jev.large_prospect_copy_stream.v1"
MAX_FILE_BYTES=16 * 1024**3
MAX_COPY_ROW_BYTES=128 * 1024
MAX_HEADER_BYTES=16 * 1024
MAX_ROWS=5_000_000
MAX_TRACKED_IDS=250_000
MAX_MONTHS=250
MAX_METRO_KEYS=2048

KNOWN_NICHES=frozenset({
    "roofing","solar","hvac","dental","legal","property","plumbing",
    "general_contractor","construction","landscaping","insurance",
    "electrical","home_services","other",
    "restoration","commercial_roofing","commercial_solar",
    "water_mitigation","emergency_services",
    "managed_it","merchant_services","hr_staffing","staffing",
    "auto_insurance","debt_relief","debt_consolidation",
    "business_loan_broker","medical_claims","mental_health_clinic",
    "addiction_treatment_center","home_health_agency","assisted_living",
    "medicare_advantage_agent","nursing_school",
})
MONTH=re.compile(r"^20\d\d-(?:0[1-9]|1[0-2])$")
SAFE_METRO=re.compile(r"^[a-z0-9][a-z0-9 .,/-]{0,70}$")
EXPECTED_COLUMNS=frozenset({"id","niche","metro","status","created_at"})


def _decode_brief(raw:bytes, *, limit:int)->str:
    if len(raw)>limit:
        return ""
    try:
        value=_decode_copy_text(raw)
    except (ValueError, UnicodeError):
        return ""
    return value.strip() if isinstance(value,str) else ""


def _coarse_niche(raw:bytes)->str:
    label=_decode_brief(raw,limit=96).lower().replace(" ","_").replace("-","_")
    return label if label in KNOWN_NICHES else "other_or_unmapped"


def _coarse_metro(raw:bytes)->str:
    label=" ".join(_decode_brief(raw,limit=128).lower().split())
    return label if SAFE_METRO.fullmatch(label) else "unknown_or_invalid"


def _validate_expected(historical:Mapping[str,Any]|None)->tuple[int|None,str|None]:
    if historical is None:
        return None,None
    if not isinstance(historical,Mapping):
        raise ValueError("historical evidence contract invalid")
    if (historical.get("verified") is not True
        or type(historical.get("source_rows")) is not int
        or not 0<historical["source_rows"]<=MAX_ROWS
        or historical.get("source_rows")!=historical.get("target_rows")
        or not isinstance(historical.get("source_pk_sha256"),str)
        or historical["source_pk_sha256"]!=historical.get("target_pk_sha256")
        or not re.fullmatch("[0-9a-f]{64}",historical["source_pk_sha256"])):
        raise ValueError("untrusted independent historical verification")
    return historical["source_rows"],historical["source_pk_sha256"]


def scan_prospect_copy_stream(
    path:Path, *, historical:Mapping[str,Any]|None=None,
    max_rows:int=MAX_ROWS, tracked_id_limit:int=MAX_TRACKED_IDS,
)->dict[str,Any]:
    if (type(max_rows) is not int or not 1<=max_rows<=MAX_ROWS
        or type(tracked_id_limit) is not int
        or not 1<=tracked_id_limit<=MAX_TRACKED_IDS):
        raise ValueError("unsafe streaming reader limits")
    source=Path(path)
    stat=source.lstat()
    if (source.is_symlink() or not S_ISREG(stat.st_mode)
        or not 0<stat.st_size<=MAX_FILE_BYTES):
        raise ValueError("original dump is not a bounded regular file")
    expected_count,expected_digest=_validate_expected(historical)
    source_sha=sha256()
    total_bytes=0
    rows=0
    found=0
    inside_copy=False
    wanted=False
    indexes={}
    identifiers=[]
    digest_tracked=True
    status_counter=Counter()
    niche_counter=Counter()
    metro_counter=Counter()
    month_counter=Counter()
    invalid_months=0
    max_row_seen=0
    started=perf_counter()

    # Binary readline(MAX_COPY_ROW_BYTES+1) prevents a single oversized row
    # from making an enormous Python allocation. The full 233MB dump is never
    # loaded as a JSON object, DataFrame or list of business/contact records.
    with source.open("rb",buffering=1024*1024) as reader:
        while True:
            line=reader.readline(MAX_COPY_ROW_BYTES+1)
            if not line:
                break
            if len(line)>MAX_COPY_ROW_BYTES or not line.endswith(b"\n"):
                raise ValueError("oversized or unterminated pg_dump line")
            source_sha.update(line)
            total_bytes+=len(line)
            if total_bytes>stat.st_size:
                raise ValueError("dump changed during original-source scan")
            if not inside_copy:
                if not line.startswith(b"COPY "):
                    continue
                if len(line)>MAX_HEADER_BYTES:
                    raise ValueError("oversized PostgreSQL COPY header")
                match=_COPY_HEADER.match(line)
                if match is None:
                    # Other pg_dump schemas (auth, storage, etc.) are valid
                    # COPY blocks but must never be decoded or exported.
                    if not line.rstrip(b"\r\n").endswith(b" FROM stdin;"):
                        raise ValueError("unsupported or unsafe PostgreSQL COPY header")
                    inside_copy=True
                    wanted=False
                    continue
                table=match.group("table").decode("ascii")
                columns=tuple(
                    part.strip().decode("ascii").strip('"')
                    for part in match.group("columns").split(b",")
                )
                inside_copy=True
                wanted=table=="prospects"
                if wanted:
                    found+=1
                    if found!=1 or len(set(columns))!=len(columns) or not EXPECTED_COLUMNS.issubset(columns):
                        raise ValueError("duplicate or incompatible prospects COPY block")
                    indexes={name:columns.index(name) for name in EXPECTED_COLUMNS}
                    num_columns=len(columns)
                continue
            if line in (b"\\.\n",b"\\.\r\n"):
                inside_copy=False
                wanted=False
                continue
            if not wanted:
                continue
            max_row_seen=max(max_row_seen,len(line))
            cells=line.rstrip(b"\r\n").split(b"\t")
            if len(cells)!=num_columns:
                raise ValueError("malformed prospect COPY column count")
            rows+=1
            if rows>max_rows:
                raise ValueError("COPY prospect row budget exceeded")
            # Only the canonical primary key is decoded for *local* digest
            # comparison; no raw ID is ever written or returned.
            if digest_tracked:
                if rows<=tracked_id_limit:
                    pk=_decode_brief(cells[indexes["id"]],limit=96)
                    if not pk:
                        raise ValueError("missing or invalid COPY primary key")
                    identifiers.append(pk)
                else:
                    identifiers=[]
                    digest_tracked=False
            niche_counter[_coarse_niche(cells[indexes["niche"]])]+=1
            metro=_coarse_metro(cells[indexes["metro"]])
            if metro not in metro_counter and len(metro_counter)>=MAX_METRO_KEYS:
                metro="overflow_or_other"
            metro_counter[metro]+=1
            raw_status=_decode_brief(cells[indexes["status"]],limit=40).lower()
            if raw_status=="converted":
                status_counter["converted_status_unverified"]+=1
            elif not raw_status:
                status_counter["status_missing"]+=1
            else:
                status_counter["other_status_unverified"]+=1
            month=_decode_brief(cells[indexes["created_at"]],limit=64)[:7]
            if MONTH.fullmatch(month) and (month in month_counter or len(month_counter)<MAX_MONTHS):
                month_counter[month]+=1
            else:
                invalid_months+=1

    if inside_copy or found!=1 or rows==0 or total_bytes!=stat.st_size:
        raise ValueError("missing, incomplete, or changing prospects dump")
    if sum(niche_counter.values())!=rows or sum(status_counter.values())!=rows:
        raise ValueError("incomplete aggregate coverage")

    raw_digest=_digest_strings(identifiers) if digest_tracked else None
    count_match=(expected_count is not None and rows==expected_count)
    digest_match=(expected_digest is not None and raw_digest==expected_digest)
    if historical is not None and not (count_match and digest_match):
        raise ValueError("historic source ID set does not match pinned evidence")

    def public_categories(counts:Counter[str],minimum:int=20,max_groups:int=40)->dict[str,int]:
        # Suppress small sparse geography and niche buckets; no rare property
        # or client-specific metro names leak in the aggregate report.
        exposed={
            key:n for key,n in counts.most_common(max_groups)
            if n>=minimum and key not in ("unknown_or_invalid",)
        }
        hidden=rows-sum(exposed.values())
        if hidden:
            exposed["other_or_suppressed"]=hidden
        return dict(sorted(exposed.items()))

    return {
        "schema_version":SCHEMA,
        "status":("HISTORIC_PROSPECT_COPY_IDENTITY_MATCH_REVIEW_ONLY"
                  if count_match and digest_match else "UNVERIFIED_COPY_AGGREGATES_ONLY"),
        "source_kind":"OFFLINE_POSTGRESQL_COPY_DATA_DUMP",
        "source_size_bytes":stat.st_size,
        "source_file_sha256":source_sha.hexdigest(),
        "source_counted_copy_rows":rows,
        "historical_independent_id_set_match":count_match and digest_match,
        "historical_digest_track_limit_reached":not digest_tracked,
        "monthly_cohort_counts":dict(sorted(month_counter.items())),
        "unknown_or_invalid_created_month_rows":invalid_months,
        "niche_aggregate_counts":public_categories(niche_counter),
        "metro_aggregate_counts":public_categories(metro_counter,minimum=25),
        "status_counts_unverified":dict(sorted(status_counter.items())),
        "largest_prospect_copy_row_bytes":max_row_seen,
        "scan_elapsed_ms":round((perf_counter()-started)*1000,3),
        "all_source_rows_in_memory":False,
        "all_original_personal_fields_discarded":True,
        "source_contacts_or_names_exported":False,
        "deduplicated_person_or_business_count_verified":False,
        "source_read_is_not_current_live_database_count":True,
        "source_rights_and_individual_consent_verified":False,
        "model_records_processed":0,
        "commercial_leads_authorized":0,
        "outreach_sent":0,
        "database_writes":False,
        "execution_authority":"none",
    }
