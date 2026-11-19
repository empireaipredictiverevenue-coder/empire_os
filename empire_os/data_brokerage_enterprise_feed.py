"""Continuous bounded enterprise research feed inside original Data Brokerage owner.

No independent timer, raw personal contacts, public publication, entitlement,
client delivery or paid source access. Called under original brokerage lock.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import tempfile
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path("/home/ubuntu/empire_research/enterprise_data_packs_20261118")
STATE = Path("runtime/data_brokerage/enterprise_professional_feed_latest.json")
SCHEMA = "empire.data_brokerage.enterprise_professional_feed.v1"
USER_AGENT = "EmpireAI-ProfessionalData-SourceQuality/1.0"
# Independent cadence, one due source per existing owner invocation.
SOURCES = {
    "us_disaster_declaration_activity": (12, 500, 2000, "FEMA"),
    "global_legal_entity_identity_gb": (24, 100, 500, "GLEIF"),
    "uk_renewable_development_projects": (168, 10000, 50000, "DESNZ"),
    "uk_cqc_corporate_care_locations": (168, 30000, 100000, "CQC"),
    "us_fda_regulatory_enforcement_sample": (24, 1100, 1300, "openFDA"),
}
HEADERS = {
    "global_legal_entity_identity_gb": (
        "lei", "entity_name", "registration_authority_id", "company_registration_number",
        "country", "city", "entity_status", "lei_status", "lei_last_updated",
        "lei_next_renewal", "source_url", "observed_at",
    ),
    "us_disaster_declaration_activity": (
        "disaster_number", "declaration_id", "state", "county_designated_area",
        "fips_state", "fips_county", "event_type", "declaration_type",
        "declaration_date", "incident_begin_date", "source_last_refresh",
        "source_url", "observed_at",
    ),
    "uk_cqc_corporate_care_locations": (
        "location_id", "provider_id", "provider_name", "service_name",
        "service_type", "postcode_district", "local_authority", "region",
        "last_check_date", "source_url", "observed_at",
    ),
    "uk_renewable_development_projects": (
        "project_ref", "site_name", "technology", "capacity_mw",
        "development_status", "county", "region", "country",
        "planning_authority", "planning_application_ref", "record_last_updated",
        "source_url", "observed_at",
    ),
    "us_fda_regulatory_enforcement_sample": (
        "record_id", "sector", "recall_number", "event_id", "report_date",
        "reported_classification", "recall_initiation_date", "state", "country",
        "published_corporate_name_candidate", "company_identity_verified",
        "product_type", "published_product_summary", "publisher_reported_reason",
        "source_url", "source_legal_terms", "observed_at",
    ),
}

def _sha(buf: bytes) -> str:
    return hashlib.sha256(buf).hexdigest()

def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".enterprise-refresh-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as h:
            h.write(data)
            h.flush()
            os.fsync(h.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def _get(url: str, *, limit: int = 35_000_000) -> bytes:
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=22) as r:
        buf = r.read(limit + 1)
        if len(buf) > limit:
            raise ValueError("SOURCE_BYTE_CAP_EXCEEDED")
        return buf

def _download_json(url: str):
    return json.loads(_get(url, limit=4_000_000))

class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.href = None
        self.text = []
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.text = []
    def handle_data(self, value):
        if self.href is not None:
            self.text.append(value)
    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            self.links.append((" ".join(self.text).strip(), self.href))
            self.href = None
            self.text = []

def _latest_official_csv(index_url: str, host: str, pattern: str) -> str:
    links = _Links()
    links.feed(_get(index_url, limit=2_000_000).decode("utf-8", errors="replace"))
    for text, url in links.links:
        parsed = urlparse(url)
        if (parsed.scheme == "https" and parsed.hostname == host
                and not parsed.username and not parsed.password
                and re.search(pattern, parsed.path, re.IGNORECASE)
                and ("csv" in text.lower() or "csv" in url.lower())):
            return url.split("?", 1)[0]
    raise ValueError("NO_VERIFIED_CURRENT_PUBLISHER_CSV_LINK")

def _fetch_gleif(stamp: str):
    rows = []
    seen = set()
    for page in range(1, 4):
        url = "https://api.gleif.org/api/v1/lei-records?" + urlencode({
            "filter[entity.legalAddress.country]": "GB",
            "page[size]": "100", "page[number]": page,
        })
        data = _download_json(url)
        for item in data.get("data", []):
            attrs = item.get("attributes") or {}
            ent = attrs.get("entity") or {}
            reg = attrs.get("registration") or {}
            lei = attrs.get("lei") or ""
            name = (ent.get("legalName") or {}).get("name") or ""
            if (not re.fullmatch(r"[A-Z0-9]{20}", lei) or not name or lei in seen
                or ent.get("status") != "ACTIVE" or ent.get("category") != "GENERAL"
                or reg.get("status") != "ISSUED"):
                continue
            seen.add(lei)
            address = ent.get("legalAddress") or {}
            rows.append(dict(lei=lei, entity_name=name,
                registration_authority_id=(ent.get("registeredAt") or {}).get("id") or "",
                company_registration_number=ent.get("registeredAs") or "",
                country=address.get("country") or "", city=address.get("city") or "",
                entity_status="ACTIVE", lei_status="ISSUED",
                lei_last_updated=reg.get("lastUpdateDate") or "",
                lei_next_renewal=reg.get("nextRenewalDate") or "",
                source_url="https://api.gleif.org/api/v1/lei-records/" + lei,
                observed_at=stamp))
    return rows, "https://api.gleif.org/api/v1/lei-records"

def _fetch_fema(stamp: str):
    url = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries?" + urlencode({
        "$orderby": "declarationDate desc", "$top": "1000",
    })
    data = _download_json(url)
    rows, seen = [], set()
    for x in data.get("DisasterDeclarationsSummaries", []):
        identity = (x.get("disasterNumber"), x.get("state"),
                    x.get("fipsCountyCode"), x.get("designatedArea"))
        if identity in seen:
            continue
        seen.add(identity)
        rows.append(dict(disaster_number=x.get("disasterNumber"),
          declaration_id=x.get("femaDeclarationString"), state=x.get("state"),
          county_designated_area=x.get("designatedArea"),
          fips_state=x.get("fipsStateCode"), fips_county=x.get("fipsCountyCode"),
          event_type=x.get("incidentType"), declaration_type=x.get("declarationType"),
          declaration_date=x.get("declarationDate"),
          incident_begin_date=x.get("incidentBeginDate"),
          source_last_refresh=x.get("lastRefresh"),
          source_url="https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries",
          observed_at=stamp))
    return rows, "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"

def _fetch_cqc(stamp: str):
    url = _latest_official_csv(
        "https://www.cqc.org.uk/about-us/transparency/using-cqc-data",
        "www.cqc.org.uk", r"/system/files/\d{4}-\d{2}/\d+_.*CQC_directory\.csv$",
    )
    src = io.StringIO(_get(url).decode("utf-8-sig", errors="replace"))
    for _ in range(4):
        next(src)
    rows, seen = [], set()
    for x in csv.DictReader(src):
        name = (x.get("Provider name") or "").strip()
        loc = (x.get("Name") or "").strip()
        ident = (x.get("CQC Location ID (for office use only)") or "").strip()
        # Corporate/organisation records only; no personal contacts or street addresses.
        if not (name and loc and ident and re.search(
            r"\b(ltd|limited|llp|plc|nhs|trust|foundation|cic|c\.i\.c\.|community interest company|corporation)\b", name, re.I
        )) or ident in seen:
            continue
        seen.add(ident)
        rows.append(dict(location_id=ident,
          provider_id=(x.get("CQC Provider ID (for office use only)") or "").strip(),
          provider_name=name, service_name=loc,
          service_type=(x.get("Service types") or "").strip(),
          postcode_district=(x.get("Postcode") or "").strip().upper().split(" ")[0],
          local_authority=(x.get("Local authority") or "").strip(),
          region=(x.get("Region") or "").strip(),
          last_check_date=(x.get("Date of latest check") or "").strip(),
          source_url=(x.get("Location URL") or "").strip(), observed_at=stamp))
    return rows, url

def _parse_repd_raw(buf: bytes, stamp: str) -> tuple[list[dict], dict]:
    """Strict UTF-8 or publisher CP1252; never silently corrupt names/refs."""
    try:
        decoded = buf.decode("utf-8-sig")
        encoding = "utf-8-sig"
    except UnicodeDecodeError:
        decoded = buf.decode("cp1252")  # DESNZ November 2026 official CSV
        encoding = "cp1252"
    parser = csv.DictReader(io.StringIO(decoded, newline=""))
    if not {"Ref ID", "Development Status", "Technology Type",
            "Record Last Updated (dd/mm/yyyy)"}.issubset(parser.fieldnames or ()):
        raise ValueError("REPD_OFFICIAL_PUBLISHER_SCHEMA_INVALID")
    rows, seen, exact_duplicates = [], {}, []
    for x in parser:
        ident = (x.get("Ref ID") or "").strip()
        if not ident:
            raise ValueError("REPD_PUBLISHER_MISSING_PROJECT_REFERENCE")
        if ident in seen:
            if seen[ident] != x:
                raise ValueError("REPD_PUBLISHER_CONFLICTING_DUPLICATE_ID")
            exact_duplicates.append(ident)
            continue
        seen[ident] = x
        rows.append(dict(project_ref=ident, site_name=(x.get("Site Name") or "").strip(),
          technology=(x.get("Technology Type") or "").strip(),
          capacity_mw=(x.get("Installed Capacity (MWelec)") or "").strip(),
          development_status=(x.get("Development Status") or "").strip(),
          county=(x.get("County") or "").strip(), region=(x.get("Region") or "").strip(),
          country=(x.get("Country") or "").strip(),
          planning_authority=(x.get("Planning Authority") or "").strip(),
          planning_application_ref=(x.get("Planning Application Reference") or "").strip(),
          record_last_updated=(x.get("Record Last Updated (dd/mm/yyyy)") or "").strip(),
          source_url="https://www.gov.uk/government/publications/renewable-energy-planning-database-quarterly-extract",
          observed_at=stamp))
    if not 10_000 <= len(rows) <= 50_000 or len(exact_duplicates) > 100:
        raise ValueError("REPD_PUBLISHER_ROW_COUNT_OR_DUPLICATE_BOUND")
    return rows, {"raw_publisher_encoding": encoding,
                  "raw_publisher_row_count": len(rows) + len(exact_duplicates),
                  "exact_duplicate_public_ref_rows": len(exact_duplicates),
                  "conflicting_duplicate_public_ref_rows": 0}


def _fetch_repd(stamp: str):
    url = _latest_official_csv(
        "https://www.gov.uk/government/publications/renewable-energy-planning-database-quarterly-extract",
        "assets.publishing.service.gov.uk", r"\.csv$",
    )
    parsed = urlparse(url)
    match = re.fullmatch(
        r"/media/[a-zA-Z0-9]+/(REPD_[Pp]ublication_Q[1-4]_20[0-9]{2}\.csv)",
        parsed.path,
    )
    if (not match or parsed.scheme != "https"
            or parsed.netloc != "assets.publishing.service.gov.uk"
            or parsed.query or parsed.fragment):
        raise ValueError("REPD_UNEXPECTED_PUBLISHER_ASSET_URL")
    # Preserve original publisher bytes; never trust redirected historical URLs.
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=22) as response:
        if response.url != url or response.status != 200:
            raise ValueError("REPD_PUBLISHER_RAW_ASSET_REDIRECT_HOLD")
        buf = response.read(9_000_001)
    if not buf or len(buf) > 9_000_000:
        raise ValueError("REPD_PUBLISHER_RAW_ASSET_SIZE_LIMIT")
    rows, quality = _parse_repd_raw(buf, stamp)
    digest = _sha(buf)
    relative = (Path("runtime/predictive_cloud/brokerage_research_private/"
                     "forecast_pilot/source_archives")
                / ("source_" + match.group(1).removesuffix(".csv")
                   + "_" + digest + ".csv"))
    archive = Path("/srv/empire_os") / relative
    if archive.parent.is_symlink():
        raise ValueError("REPD_SOURCE_ARCHIVE_PATH_SYMLINK")
    archive.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if archive.parent.stat().st_mode & 0o077:
        raise ValueError("REPD_SOURCE_ARCHIVE_DIRECTORY_NOT_PRIVATE")
    if archive.exists() or archive.is_symlink():
        if (archive.is_symlink() or not archive.is_file()
                or archive.stat().st_mode & 0o077
                or _sha(archive.read_bytes()) != digest):
            raise ValueError("REPD_RAW_SOURCE_ARCHIVE_DRIFT")
    else:
        _atomic(archive, buf)
    quality.update({
        "publisher_original_raw_sha256": digest,
        "publisher_original_raw_bytes": len(buf),
        "publisher_original_raw_archive_relative": str(relative),
        "publisher_original_source_url": url,
        "publisher_source_content_addressed": True,
        "publisher_raw_redistribution_authorized": False,
    })
    return rows, url, quality

def _fetch_fda(stamp: str):
    # Lazy import respects the existing bounded network/parse helper owner.
    from empire_os.data_brokerage_fda_regulatory_research import fetch_research_sample
    return fetch_research_sample(stamp)

FETCHERS = {
    "us_disaster_declaration_activity": _fetch_fema,
    "global_legal_entity_identity_gb": _fetch_gleif,
    "uk_renewable_development_projects": _fetch_repd,
    "uk_cqc_corporate_care_locations": _fetch_cqc,
    "us_fda_regulatory_enforcement_sample": _fetch_fda,
}

def _entity_key(name: str, row: dict) -> str:
    if name == "global_legal_entity_identity_gb":
        return row["lei"]
    if name == "us_disaster_declaration_activity":
        return "|".join(str(row.get(k) or "") for k in (
            "disaster_number", "state", "fips_county", "county_designated_area"))
    if name == "uk_cqc_corporate_care_locations":
        return row["location_id"]
    if name == "us_fda_regulatory_enforcement_sample":
        return row["record_id"]
    return row["project_ref"]

def _fingerprint(row: dict) -> str:
    return _sha(json.dumps({k: "" if v is None else str(v)
                           for k, v in row.items()
                           if k not in ("observed_at", "source_url")},
                           sort_keys=True, ensure_ascii=True).encode())

def _stable_map(name: str, rows: list[dict]):
    result = {}
    for row in rows:
        key = _entity_key(name, row)
        if not key or key in result:
            raise ValueError("MISSING_OR_DUPLICATE_SOURCE_ENTITY_ID")
        result[key] = _fingerprint(row)
    return result

def _csv_bytes(name: str, rows: list[dict]) -> bytes:
    dest = io.StringIO(newline="")
    writer = csv.DictWriter(dest, fieldnames=HEADERS[name], extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return dest.getvalue().encode("utf-8")

def _read_rows(name: str):
    p = ROOT / (name + ".csv")
    if not p.is_file():
        return []
    with p.open(encoding="utf-8", newline="") as h:
        reader = csv.DictReader(h)
        if tuple(reader.fieldnames or ()) != HEADERS[name]:
            raise ValueError("EXISTING_DATASET_SCHEMA_MISMATCH")
        return list(reader)

def _load_state(path: Path):
    if not path.exists():
        return {"schema": SCHEMA, "datasets": {}, "execution_authority": "research_only"}
    obj = json.loads(path.read_text())
    if obj.get("schema") != SCHEMA or not isinstance(obj.get("datasets"), dict):
        raise ValueError("EXISTING_PROFESSIONAL_FEED_STATE_INVALID")
    return obj

def _nowtime(value: str):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError):
        return None

def run_due(root: Path, *, now: datetime | None = None,
            fetchers: dict[str, Callable] | None = None,
            state_path: Path | None = None,
            dataset_root: Path | None = None,
            allow_noncanonical: bool = False) -> dict:
    """Perform at most one due source update per heartbeat. Safe on cooldown."""
    root = Path(root).resolve()
    if root != Path("/srv/empire_os") and not allow_noncanonical:
        return {"status": "NONCANONICAL_ROOT_HELD", "network_requests": 0}
    instant = now or datetime.now(timezone.utc)
    if instant.utcoffset() is None:
        raise ValueError("UTC_REQUIRED")
    state_path = state_path or root / STATE
    target = dataset_root or ROOT
    state = _load_state(state_path)
    saved = state["datasets"]
    due = []
    for name, (hours, _, _, _) in SOURCES.items():
        previous = saved.get(name) or {}
        last = _nowtime(previous.get("last_checked_at"))
        # Failed upstream calls retry hourly, never wait the full 7-day
        # publisher cadence after a transient outage or failed validation.
        wait_hours = 1 if previous.get("source_status") in (
            "SOURCE_REFRESH_HELD", "SOURCE_RECHECK_REQUIRED",
        ) else hours
        if last is None or instant - last >= timedelta(hours=wait_hours):
            due.append(name)
    if not due:
        return {"status": "PROFESSIONAL_FEED_ALL_SOURCES_WITHIN_CADENCE",
                "network_requests": 0, "next_due_at": min(
                    (_nowtime(saved[n]["last_checked_at"]) + timedelta(hours=(
                        1 if saved[n].get("source_status") in (
                            "SOURCE_REFRESH_HELD", "SOURCE_RECHECK_REQUIRED")
                        else SOURCES[n][0])) for n in SOURCES),
                ).isoformat()}
    name = due[0]  # One source per original heartbeat, not an extra scheduler.
    hours, minimum, maximum, publisher = SOURCES[name]
    old = saved.get(name) or {}
    stamp = instant.isoformat(timespec="seconds")
    receipt = {
        "publisher": publisher, "last_checked_at": stamp,
        "refresh_hours": hours, "licence_release_approved": False,
        "customer_delivery_authorized": False, "commercial_sales_authorized": False,
        "source_status": "SOURCE_REFRESH_HELD", "error_class": None,
        "sample_not_full_population": name in (
            "global_legal_entity_identity_gb", "us_disaster_declaration_activity",
            "us_fda_regulatory_enforcement_sample"),
    }
    requests = 3 if name == "us_fda_regulatory_enforcement_sample" else 1
    try:
        fetched = (fetchers or FETCHERS)[name](stamp)
        if not isinstance(fetched, tuple) or len(fetched) not in (2, 3):
            raise ValueError("SOURCE_FETCH_RESULT_SCHEMA_INVALID")
        rows, source_url = fetched[:2]
        metadata = fetched[2] if len(fetched) == 3 else {}
        if not isinstance(metadata, dict):
            raise ValueError("SOURCE_PUBLICATION_METADATA_INVALID")
        if not minimum <= len(rows) <= maximum:
            raise ValueError("SOURCE_ROW_COUNT_OUTSIDE_VERIFIED_BOUNDS")
        if not all(isinstance(row, dict) for row in rows):
            raise ValueError("INVALID_SOURCE_ROWS")
        current = _stable_map(name, rows)
        # Preserve old file if corrupted. Source network errors do not erase the last good snapshot.
        path = target / (name + ".csv")
        before = _stable_map(name, _read_rows_from_path(name, path))
        new = set(current) - set(before)
        changed = {k for k in current.keys() & before.keys() if current[k] != before[k]}
        absent = set(before) - set(current)
        if name in ("global_legal_entity_identity_gb", "us_disaster_declaration_activity",
                    "us_fda_regulatory_enforcement_sample"):
            event_kind = "SAMPLE_MEMBERSHIP_CHANGE_NOT_NEW_WORLD_EVENT"
        else:
            event_kind = "PUBLISHER_SNAPSHOT_CHANGE_NOT_INDEPENDENTLY_VERIFIED_EVENT"
        if new or changed or absent:
            output = _csv_bytes(name, rows)
            if path.exists():
                # Keep last verified snapshot by content digest; no destructive deletion.
                archive = target / "history" / (name + "_" + _sha(path.read_bytes())[:20] + ".csv")
                if not archive.exists():
                    _atomic(archive, path.read_bytes())
            _atomic(path, output)
        else:
            output = path.read_bytes()
        receipt.update({
            "source_status": "VERIFIED_CHANGED" if (new or changed or absent) else "VERIFIED_UNCHANGED",
            "source_url": source_url,
            "publisher_publication_metadata": metadata,
            "row_count": len(rows),
            "source_snapshot_sha256": _sha(output),
            "previous_verified_sha256": old.get("source_snapshot_sha256"),
            "source_window_new_ids": len(new),
            "source_window_changed_ids": len(changed),
            "source_window_absent_ids": len(absent),
            "change_definition": event_kind,
            "last_success_at": stamp,
            "network_requests": requests,
            "quality_pass": True,
            "new_ids_sample": sorted(new)[:12] if name != "uk_cqc_corporate_care_locations" else [],
        })
    except Exception as e:
        receipt["error_class"] = type(e).__name__
        receipt["source_status"] = "SOURCE_REFRESH_HELD"
        receipt["network_requests"] = requests
        # Preserve last successful source evidence despite failed refresh.
        for key in ("row_count", "source_snapshot_sha256", "last_success_at", "source_url",
                    "publisher_publication_metadata"):
            if key in old:
                receipt[key] = old[key]
        receipt["quality_pass"] = False
    saved[name] = receipt
    state.update({
        "schema": SCHEMA, "datasets": saved, "updated_at": stamp,
        "owner": "ORIGINAL_DATA_BROKERAGE_HEARTBEAT",
        "outbound_sent": False, "customer_delivery_authorized": False,
        "commercial_sales_authorized": False, "source_redistribution_approved": False,
        "execution_authority": "research_only",
    })
    _atomic(state_path, (json.dumps(state, sort_keys=True, indent=2) + "\n").encode())
    return {"status": receipt["source_status"], "source": name,
            "records": receipt.get("row_count"),
            "new": receipt.get("source_window_new_ids"),
            "changed": receipt.get("source_window_changed_ids"),
            "absent": receipt.get("source_window_absent_ids"),
            "last_checked_at": stamp, "network_requests": requests,
            "customer_delivery_authorized": False}

def _read_rows_from_path(name: str, path: Path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as h:
        reader = csv.DictReader(h)
        if tuple(reader.fieldnames or ()) != HEADERS[name]:
            raise ValueError("EXISTING_SOURCE_HEADER_INVALID")
        return list(reader)


def record_scheduled_owner_observation(
    root: Path, source: dict, views: dict,
    *, now: datetime | None = None,
    cloud_research: dict | None = None,
    fabric_research: dict | None = None,
    temporal_research: dict | None = None,
    frozen_research: dict | None = None,
    future_outcome: dict | None = None,
) -> dict:
    """Attest a genuine systemd-origin owner invocation without fabricating new data.

    A manual operator bootstrap or a test invocation does not create a timer receipt.
    Invoked only inside the original owner lock.
    """
    root = Path(root).resolve()
    invocation = os.environ.get("INVOCATION_ID", "")
    if root != Path("/srv/empire_os") or not re.fullmatch(r"[a-fA-F0-9]{32}", invocation):
        return {"status": "NOT_SYSTEMD_OWNER_INVOCATION", "timer_receipt_written": False}
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    receipt = {
        "schema": "empire.data_brokerage.systemd_owner_observation.v1",
        "observed_at": stamp.isoformat(timespec="seconds"),
        "owner": "empire-department-cycle.service",
        "invocation_id_sha256": _sha(invocation.lower().encode()),
        "professional_source_status": source.get("status"),
        "professional_product_view_status": views.get("status"),
        "source_requests_this_invocation": source.get("network_requests", 0),
        "product_view_writes_this_invocation": views.get("view_writes", 0),
        "predictive_cloud_research_status": (cloud_research or {}).get("status"),
        "predictive_fabric_research_feature_status": (fabric_research or {}).get("status"),
        "predictive_fabric_research_feature_segments": (
            (fabric_research or {}).get("feature_segments", 0)
        ),
        "predictive_fabric_production_training_authorized": False,
        "temporal_research_pilot_status": (temporal_research or {}).get("status"),
        "temporal_publisher_label_rows": (temporal_research or {}).get("private_label_rows", 0),
        "temporal_publisher_forecast_predictions_produced": 0,
        "prospective_research_freeze_status": (frozen_research or {}).get("status"),
        "prospective_research_frozen_at": (frozen_research or {}).get("frozen_at"),
        "prospective_research_asof": (frozen_research or {}).get("publisher_asof_date"),
        "prospective_research_cohort_rows": (frozen_research or {}).get("research_scored_projects", 0),
        "prospective_research_score_sha256": (frozen_research or {}).get("score_object_sha256"),
        "prospective_production_predictions_produced": 0,
        "prospective_model_training_authorized": False,
        "next_publisher_evaluation_status": (future_outcome or {}).get("status"),
        "next_publisher_evaluation_writes": (future_outcome or {}).get("evaluation_writes", 0),
        "next_publisher_future_outcome_rows": (future_outcome or {}).get("matched_outcomes", 0),
        "next_publisher_customer_prediction_authorized": False,
        "customer_delivery_authorized": False,
        "new_timer_created": False,
        "outreach_sent": False,
        "sales_authorized": False,
    }
    target = root / "runtime/data_brokerage/enterprise_feed_scheduler_last_seen.json"
    _atomic(target, (json.dumps(receipt, indent=2, sort_keys=True)+"\n").encode())
    return {"status": "SYSTEMD_BROKERAGE_OWNER_OBSERVED", "timer_receipt_written": True,
            "observed_at": receipt["observed_at"]}
