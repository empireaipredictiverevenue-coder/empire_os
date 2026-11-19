"""Original Search Fabric SEC Form D source-quality refresh (evidence-only).

Uses the SEC's publicly available EDGAR daily index; federal index metadata
is reusable. This is a bounded owner-side discovery path, not a stock feed,
investment advice, investor network or verified startup funding product.

Designed for the ORIGINAL five-minute Search Fabric service. It self-gates
to no more than one successful new fetch per six hours, reads the latest
available business-day index, and writes only its pre-existing private
Search Fabric runtime directory. Never creates another scheduler.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone, date
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.request import urlopen, Request
import fcntl
import json
import os
import re
import stat

from empire_os.supply_quality_twin import (
    SupplyQualityObservation, build_supply_quality_twin,
)

SCHEMA = "empire.search_fabric.sec_formd_source_quality.v1"
STATE_SCHEMA = "empire.search_fabric.sec_formd_owner_cursor.v1"
SEC_ROOT = "https://www.sec.gov/Archives/"
FETCH_GAP = timedelta(hours=6)
MAX_BYTES = 2_500_000
MAX_FILINGS = 750
HISTORY_MAX = 10_000
# SEC requires meaningful organisation/contact identification. Never invent a
# provider key; this is the existing founder's real Workspace contact.
USER_AGENT = "Empire AI research phil@empire-ai.co.uk"
FORM_TYPES = {"D", "D/A"}
CIK = re.compile(r"^[1-9][0-9]{0,9}$")
INDEX_PATH = re.compile(r"^edgar/data/([1-9][0-9]{0,9})/([0-9]{10}-[0-9]{2}-[0-9]{6})\.txt$")
FIELD_DATE = re.compile(r"^20[0-9]{6}$")
ID_SHA = re.compile(r"^[a-f0-9]{64}$")


def digest(value: Mapping[str, Any]) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone_required")
    return dt.astimezone(timezone.utc)


def official_daily_url(day: date) -> str:
    if not isinstance(day, date):
        raise ValueError("date_required")
    return f"https://www.sec.gov/Archives/edgar/daily-index/{day.year}/QTR{((day.month-1)//3)+1}/master.{day:%Y%m%d}.idx"


def candidate_index_dates(now: datetime) -> list[date]:
    if now.tzinfo is None:
        raise ValueError("timezone_required")
    utc_now = now.astimezone(timezone.utc)
    today = utc_now.date()
    first = today if utc_now.hour >= 23 else today-timedelta(days=1)
    result: list[date] = []
    for i in range(8):
        day = first-timedelta(days=i)
        if day.weekday() < 5:
            result.append(day)
        if len(result) == 3:
            break
    return result


def fetch_index(day: date, *, timeout: float = 7.0) -> bytes:
    """One fixed-host SEC GET, never arbitrary URL or user-supplied company ID."""
    req = Request(official_daily_url(day), method="GET", headers={
        "User-Agent": USER_AGENT, "Accept": "text/plain",
    })
    with urlopen(req, timeout=max(1.0, min(8.0, timeout))) as resp:
        if resp.status != 200:
            raise OSError("sec_index_non_200")
        raw = resp.read(MAX_BYTES+1)
    if not 200 < len(raw) <= MAX_BYTES:
        raise ValueError("invalid_sec_index_size")
    return raw


def parse_index(raw: bytes, *, date_requested: date) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(raw, bytes) or not 200 < len(raw) <= MAX_BYTES:
        raise ValueError("sec_index_untrusted_bytes")
    # EDGAR master index is 7-bit-safe ASCII with a structured pipe-delimited
    # row layout. Ignore optional private individual names/contacts.
    try:
        text = raw.decode("latin-1")
    except UnicodeError:
        raise ValueError("sec_index_decode_invalid") from None
    if "CIK|Company Name|Form Type|Date Filed|File Name" not in text[:1500]:
        raise ValueError("sec_master_index_missing_header")
    rows: list[dict[str, Any]] = []
    status = Counter()
    seen = set()
    for line in text.splitlines():
        if not line or "|" not in line or line.startswith("CIK|"):
            continue
        bits = line.split("|")
        if len(bits) != 5:
            status["malformed_index_row"] += 1
            continue
        cik, company, form, filed, accession = [v.strip() for v in bits]
        if form not in FORM_TYPES:
            continue
        status["formd_rows_seen"] += 1
        if not CIK.fullmatch(cik):
            status["invalid_filer_cik"] += 1
            continue
        p = INDEX_PATH.fullmatch(accession)
        if not p or p.group(1) != cik or not FIELD_DATE.fullmatch(filed):
            status["invalid_filer_accession"] += 1
            continue
        try:
            filed_day = datetime.strptime(filed, "%Y%m%d").date()
        except ValueError:
            status["invalid_filed_date"] += 1
            continue
        if filed_day != date_requested or not 2 <= len(company) <= 180:
            status["source_date_or_company_name_invalid"] += 1
            continue
        if any(ord(c) < 32 for c in company):
            status["untrusted_company_name"] += 1
            continue
        evidence_id = sha256(f"sec_formd|{cik}|{accession}".encode()).hexdigest()
        if evidence_id in seen:
            status["duplicate_filing_index_row"] += 1
            continue
        seen.add(evidence_id)
        rows.append({
            "evidence_id": evidence_id,
            "cik": cik,
            "company_filer_name": company,
            "form_type": form,
            "filed_date": filed_day.isoformat(),
            "evidence_url": SEC_ROOT + accession,
            "identity_basis": "SEC_INDEXED_FILER_CIK_AND_COMPANY_NAME",
            "sec_filing_record_verified": True,
            "independent_legal_entity_identity_verified": False,
            "startup_stage_verified": False,
            "financing_closed_verified": False,
            "investor_relationship_verified": False,
            "buyer_purchase_intent_verified": False,
            "data_rights": "US_GOV_PUBLIC_INDEX_METADATA_RESEARCH_ONLY",
        })
        if len(rows) > MAX_FILINGS:
            raise ValueError("SEC_FORMD_ROWS_EXCEED_SAFETY_CAP")
    if status["formd_rows_seen"] == 0:
        raise ValueError("SEC_INDEX_HAS_NO_FORMD_EVIDENCE")
    return rows, {
        "form_d": sum(x["form_type"] == "D" for x in rows),
        "form_d_amendment": sum(x["form_type"] == "D/A" for x in rows),
        "held_counts": dict(sorted(status.items())),
        "all_unique_sec_filing_ids": len(rows),
    }


def load_private_state(path: Path) -> Mapping[str, Any] | None:
    if path.is_symlink():
        raise ValueError("unsafe_source_cursor_link")
    if not path.exists():
        return None
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > 900_000 or (st.st_mode & 0o077):
            raise ValueError("unsafe_source_cursor")
        with os.fdopen(fd, "rb") as file:
            fd = -1
            state = json.load(file)
    finally:
        if fd >= 0:
            os.close(fd)
    if not isinstance(state, dict) or state.get("schema_version") != STATE_SCHEMA:
        raise ValueError("untrusted_source_cursor")
    expected = state.get("integrity_sha256")
    content = dict(state)
    content.pop("integrity_sha256", None)
    if expected != digest(content):
        raise ValueError("tampered_source_cursor")
    seen = state.get("seen")
    if (not isinstance(seen, list) or len(seen) > HISTORY_MAX or
            any(not isinstance(i, str) or not ID_SHA.fullmatch(i) for i in seen)):
        raise ValueError("invalid_source_cursor_seen_history")
    try:
        attempted_at = _utc(state.get("last_success_at"))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("invalid_source_cursor_clock")
    if not isinstance(state.get("last_index_date"), str) or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", state["last_index_date"]):
        raise ValueError("invalid_source_cursor_index")
    return state


def atomic_private(path: Path, value: Mapping[str, Any]) -> None:
    if path.is_symlink() or path.parent.is_symlink() or not path.parent.is_dir():
        raise ValueError("unsafe_private_source_output_path")
    output = (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)+chr(10)).encode()
    if len(output) > 900_000:
        raise ValueError("source_report_exceeds_limit")
    temporary = path.with_name(path.name + ".staged")
    if temporary.exists() or temporary.is_symlink():
        raise ValueError("source_output_pending_competing_writer")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(output)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def review_once(*, root: Path, now: datetime | None = None,
                fetch: Callable[[date], bytes] = fetch_index,
                no_network: bool = False) -> dict[str, Any]:
    """Bounded original owner call: MAX 3 SEC requests only when due."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("unsafe_original_owner_runtime")
    state_file = root/"sec_formd_source_owner_cursor_v1.json"
    report_file = root/"sec_formd_source_quality_latest.json"
    lock_file = root/"sec_formd_source_owner.lock"
    fd = os.open(lock_file, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w") as lock:
            fd = -1
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {
                    "status": "SEC_FORMD_ORIGINAL_OWNER_ALREADY_RUNNING",
                    "new_filing_records": 0, "network_requests": 0,
                    "tenant_db_writes": False, "commercial_release": False,
                }
            prior = load_private_state(state_file)
            if no_network:
                return {
                    "status": "SEC_FORMD_OWNER_NO_WEB_POLICY_HOLD",
                    "new_filing_records": 0, "network_requests": 0,
                    "tenant_db_writes": False, "commercial_release": False,
                }
            if prior is not None:
                prior_at = _utc(prior["last_success_at"])
                if prior_at > now + timedelta(minutes=5):
                    raise ValueError("future_previous_source_receipt")
                if now - prior_at < FETCH_GAP:
                    return {
                        "status": "SEC_FORMD_ORIGINAL_OWNER_ALREADY_FRESH",
                        "latest_index_date": prior["last_index_date"],
                        "source_success_age_hours": round((now - prior_at).total_seconds()/3600, 2),
                        "new_filing_records": 0, "network_requests": 0,
                        "tenant_db_writes": False, "commercial_release": False,
                    }
            attempted = 0
            last_error = "NO_AVAILABLE_SEC_DAILY_INDEX"
            for day in candidate_index_dates(now):
                attempted += 1
                try:
                    raw = fetch(day)
                    filings, summary = parse_index(raw, date_requested=day)
                    break
                except (OSError, TimeoutError, ValueError, UnicodeError):
                    continue
            else:
                return {
                    "status": "SEC_FORMD_ORIGINAL_PUBLIC_SOURCE_UNAVAILABLE",
                    "new_filing_records": 0,
                    "network_requests": attempted, "error_class": last_error,
                    "tenant_db_writes": False, "commercial_release": False,
                }
            old_ids = set(prior["seen"]) if prior else set()
            new = [row for row in filings if row["evidence_id"] not in old_ids]
            # Original SOURCE QUALITY TWIN observes a verified SEC index
            # issuer identity (CIK + filing), not a verified startup stage.
            observations = [
                SupplyQualityObservation(
                    observation_key=f"sec_formd:{r['evidence_id']}",
                    supply_id=f"sec_issuer_filing:{r['cik']}:{r['evidence_id']}",
                    source_keys=("sec_edgar_formd_index",),
                    product_key="startup_intelligence",
                    market_key="us_exempt_offerings",
                    evidence_refs=(r["evidence_url"],),
                    source_healthy=True,
                    identity_accepted=True,
                    delivered=None, buyer_accepted=None,
                    recognized_revenue_cents=None,
                ) for r in filings
            ]
            twin = build_supply_quality_twin(
                observations, source_key="sec_edgar_formd_index",
                product_key="startup_intelligence", market_key="us_exempt_offerings",
            )
            if (twin.source_policy_mutation or twin.canonical_writes
                    or twin.execution_authority != "none"
                    or twin.attributed_commercial_outcome_count != 0):
                raise ValueError("SEC_OWNER_SUPPLY_TWIN_AUTHORITY_INVALID")
            new_ids = sorted(old_ids.union(r["evidence_id"] for r in filings))
            new_ids = new_ids[-HISTORY_MAX:]
            report = {
                "schema_version": SCHEMA,
                "status": "SEC_FORMD_OFFICIAL_INDEX_REFRESH_VERIFIED",
                "as_of": now.isoformat(),
                "index_date": day.isoformat(),
                "index_url": official_daily_url(day),
                "index_content_sha256": sha256(raw).hexdigest(),
                "official_sec_index_filer_records": len(filings),
                "new_unique_filing_records_vs_previous": len(new),
                "unique_sec_cik_filers": len({r["cik"] for r in filings}),
                "filing_counts": summary,
                "source_candidate_preview": new[:30],
                "source_candidate_index": filings,
                "source_records_complete_in_private_receipt": True,
                "source_last_success_at": now.isoformat(),
                "original_supply_quality_twin": {
                    "source": twin.source_key,
                    "source_health_observed_count": twin.source_health_observed_count,
                    "sec_index_issuer_identity_accepted_count": twin.identity_accepted_count,
                    "independent_startup_legal_identity_accepted_count": 0,
                    "startup_stage_confirmed_count": 0,
                    "buyer_accepted_count": twin.buyer_accepted_count,
                    "commercial_outcomes_count": twin.attributed_commercial_outcome_count,
                    "mode": twin.mode,
                    "blockers": list(twin.blockers),
                },
                "individual_startups_independently_verified": 0,
                "funding_rounds_independently_verified": 0,
                "source_reuse_rights": "US_GOV_SEC_INDEX_METADATA_PUBLIC",
                "filing_metadata_only_no_filing_republication": True,
                "customer_data_distribution_enabled": False,
                "original_search_provider_replaced": False,
                "sender_or_user_contact_activated": False,
                "tenant_db_writes": False, "commercial_release": False,
                "network_requests": attempted,
            }
            report["integrity_sha256"] = digest(report)
            next_state = {
                "schema_version": STATE_SCHEMA,
                "last_success_at": now.isoformat(),
                "last_index_date": day.isoformat(),
                "seen": new_ids,
                "last_report_sha256": report["integrity_sha256"],
            }
            next_state["integrity_sha256"] = digest(next_state)
            # Always persist private report first, then cursor so an
            # interrupted process merely retries instead of losing evidence.
            atomic_private(report_file, report)
            atomic_private(state_file, next_state)
            return {
                "status": report["status"],
                "index_date": day.isoformat(),
                "official_sec_index_filer_records": len(filings),
                "new_filing_records": len(new),
                "unique_sec_cik_filers": report["unique_sec_cik_filers"],
                "source_twin_sec_filer_identity_accepted": twin.identity_accepted_count,
                "startup_stage_verified": 0,
                "report_sha256": report["integrity_sha256"],
                "network_requests": attempted,
                "tenant_db_writes": False, "commercial_release": False,
            }
    finally:
        if fd >= 0: os.close(fd)


# Original Search Fabric service retains its sole existing five-minute timer.
# This additive qualifier runs only under the ORIGINAL owner's canonical
# private runtime and never within offline fixture or --no-web runs. Six-hour
# self-gating happens in the existing private company-review cursor.
_ORIGINAL_REVIEW_ONCE = review_once


def review_once(*, root: Path, now: datetime | None = None,
                fetch: Callable[[date], bytes] = fetch_index,
                no_network: bool = False) -> dict[str, Any]:
    result = _ORIGINAL_REVIEW_ONCE(
        root=root, now=now, fetch=fetch, no_network=no_network,
    )
    if (root != Path("/srv/empire_os/runtime/search_fabric_evidence")
            or no_network or fetch is not fetch_index):
        return result
    try:
        # Imported here to preserve single source ownership and to keep
        # original source reads working even if the qualification layer fails.
        from empire_os.agents.brokerage_formd_company_qualification_v1 import (
            run_original_owner_company_review,
        )
        # Six documents plus their matching official SEC submissions:
        # maximum 12 additional first-party GETs per six hours.
        review = run_original_owner_company_review(root=root, limit=6)
        result["issuer_company_qualification"] = review
    except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
        result["issuer_company_qualification"] = {
            "status": "SEC_ISSUER_COMPANY_QUALIFICATION_HELD",
            "error_class": type(exc).__name__,
            "independently_verified_startups": 0,
            "outbound_sent": False,
            "db_writes": False,
            "commercial_release": False,
        }
    try:
        # Product-to-human research is part of the existing Data Brokerage
        # owner. This reuses Search Fabric first-party people and the original
        # cross-mailbox contact-history gate. Twelve-hour private refresh; no
        # new scheduler, promotion, recipient guess or outbound.
        from empire_os.agents.brokerage_named_buyer_contact_review_v1 import (
            run_existing_owner_named_buyer_research,
        )
        result["issuer_named_buyer_research"] = run_existing_owner_named_buyer_research(
            root=root.parents[1],
        )
    except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
        result["issuer_named_buyer_research"] = {
            "status": "NAMED_BUYER_RESEARCH_HELD",
            "error_class": type(exc).__name__,
            "outbound_sent": False,
            "crm_writes": False,
        }
    return result
