"""Bounded rights-reviewed RECC Solar business-identity supply sweeps.

One lawful UK B2B acquisition source, no consumer/claims scraping, no outgoing
contact, no canonical prospect writes, no customer resale, no payment/trading.

Source observations are a PRIVATE INTERNAL evidence pool, never an Exchange
inventory or verified buyer seat. The existing canonical crawler remains the
only candidate->EmpireDB prospect ingest path.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import time
from typing import Any
import urllib.parse
import urllib.request
import urllib.robotparser

from empire_os.candidate_quality import assess_candidate
from empire_os.lead_sources import recc_solar
from empire_os.source_intelligence import SOURCES

SCHEMA = "empire.recc_solar_supply_sweep.v1"
STATE_SCHEMA = "empire.recc_solar_supply_sweep_state.v1"
BASE = "https://www.recc.org.uk"
UA = recc_solar.USER_AGENT
MAX_LINKS = 40
DEFAULT_BATCH = 8
MAX_BATCH = 8
MAX_DETAILS_PER_UTC_DAY = 32
MAX_PRIVATE_OBSERVATIONS = 40
MAX_BYTES = 600_000
REQUEST_TIMEOUT = 20
MIN_REQUEST_SPACING_SEC = 0.7


def _fetch(url: str, *, opener=None) -> str:
    opener = opener or urllib.request.urlopen
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "www.recc.org.uk"
            or parsed.port is not None or parsed.username or parsed.password):
        raise ValueError("source_host_not_authorized")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with opener(req, timeout=REQUEST_TIMEOUT) as response:
        if response.status != 200:
            raise ValueError("source_http_not_success")
        content = response.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise ValueError("source_response_oversize")
        return content.decode("utf-8", errors="replace")


def _robots_allowed(*, fetch: Callable[[str], str]) -> bool:
    contents = fetch(BASE + "/robots.txt")
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(contents.splitlines())
    example = BASE + "/scheme/members/example-member"
    directory = BASE + "/scheme/members?technology=Solar%20PV"
    return parser.can_fetch(UA, directory) and parser.can_fetch(UA, example)


def _read_json(path: Path, *, limit: int) -> dict:
    if not path.exists():
        return {}
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError("private_sweep_file_invalid_or_oversize")
    val = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(val, dict):
        raise ValueError("private_sweep_json_not_a_mapping")
    return val


def _atomic_private_json(path: Path, value: dict) -> None:
    import secrets
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + secrets.token_hex(5) + ".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(temp, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def sweep_recc_members(
    root: Path,
    *,
    now: datetime | None = None,
    fetch: Callable[[str], str] = _fetch,
    detail: Callable[[str, str], Any] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    batch_size: int = DEFAULT_BATCH,
) -> dict[str, Any]:
    """One bounded rotating sweep, with cross-run duplicate protection.

    Uses a filesystem mutex around entire sequence to prevent concurrent
    cron/manual scans and daily cap overrun. No unregistered sources.
    """
    if type(batch_size) is not int or not 1 <= batch_size <= MAX_BATCH:
        raise ValueError("batch_size_out_of_bounds")
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        raise ValueError("current_time_must_include_timezone")
    rights = SOURCES.get("gb_recc_solar")
    if (not rights or rights.production_status != "verified"
            or "internal_acquisition" not in rights.allowed_uses
            or rights.raw_resale_allowed is not False):
        raise ValueError("source_rights_contract_hold")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Work only in a private directory and do not publish company rows.
    root.chmod(0o700)
    with (root / ".sweep.lock").open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"schema_version": SCHEMA, "state": "ALREADY_RUNNING",
                    "canonical_empiredb_writes": False, "outbound_authorized": False}
        state_path = root / "state.json"
        ledger_path = root / "internal_observations.json"
        last_path = root / "latest.json"
        state = _read_json(state_path, limit=20000)
        ledger = _read_json(ledger_path, limit=150000)
        if state and state.get("schema_version") != STATE_SCHEMA:
            raise ValueError("previous_state_schema_untrusted")
        if ledger and ledger.get("schema_version") != SCHEMA:
            raise ValueError("previous_ledger_schema_untrusted")
        prior = ledger.get("observations", [])
        if not isinstance(prior, list) or len(prior) > MAX_PRIVATE_OBSERVATIONS:
            raise ValueError("private_observation_ledger_invalid")
        existing = {
            v["member_url"]: dict(v)
            for v in prior if isinstance(v, dict)
            and isinstance(v.get("member_url"), str)
        }
        if len(existing) != len(prior):
            raise ValueError("private_observation_ledger_duplicate_or_malformed")
        day = stamp.astimezone(timezone.utc).date().isoformat()
        spent = state.get("details_today", 0) if state.get("utc_day") == day else 0
        if type(spent) is not int or spent < 0 or spent > MAX_DETAILS_PER_UTC_DAY:
            raise ValueError("daily_source_budget_invalid")
        available = min(batch_size, MAX_DETAILS_PER_UTC_DAY - spent)
        if available <= 0:
            return {
                "schema_version": SCHEMA, "state": "DAILY_SOURCE_BUDGET_EXHAUSTED",
                "utc_day": day, "details_today": spent,
                "existing_unique_research_observations": len(existing),
                "canonical_empiredb_writes": False,
                "outbound_authorized": False,
            }
        # Reserve the full bounded request budget DURABLY before the first
        # public fetch. A crash/timeout may waste allowance but can never
        # reset it and hammer the registered source on the next attempt.
        index = state.get("cursor", 0)
        if type(index) is not int or not 0 <= index < MAX_LINKS:
            raise ValueError("invalid_persisted_cursor")
        _atomic_private_json(state_path, {
            "schema_version": STATE_SCHEMA,
            "utc_day": day,
            "details_today": spent + available,
            "cursor": index,
            "last_reserved_at": stamp.isoformat(),
        })
        if not _robots_allowed(fetch=fetch):
            raise ValueError("source_robots_disallowed")
        search = BASE + "/scheme/members?technology=Solar%20PV&submitbutton=submit"
        html = fetch(search)
        links = recc_solar._member_links(html, limit=MAX_LINKS)
        if not links:
            raise ValueError("source_directory_no_members")
        index = state.get("cursor", 0)
        if type(index) is not int or not 0 <= index < MAX_LINKS:
            raise ValueError("invalid_persisted_cursor")
        cursor = index % len(links)
        observed = []
        attempts = 0
        failures = 0
        for i in range(available):
            url, name = links[(cursor + i) % len(links)]
            if not url.startswith(BASE + "/scheme/members/"):
                raise ValueError("member_url_outside_registered_source")
            # Gentle first-party cadence, without following member web sites.
            sleep(MIN_REQUEST_SPACING_SEC)
            attempts += 1
            try:
                record = (detail or recc_solar._detail)(name, url)
            except Exception:
                failures += 1
                continue
            if record is None:
                continue
            quality = assess_candidate(record)
            if not quality.accepted:
                continue
            observed.append({
                "member_url": url,
                "business_name": record.name[:200],
                "business_website_observed": str(
                    record.raw.get("business_website") or ""
                )[:500],
                "source_id": "gb_recc_solar",
                "niche": "solar",
                "territory": "GB",
                "observed_at": stamp.isoformat(),
                "source_internal_use_only": True,
                "source_raw_resale_allowed": False,
                "verified_canonical_prospect_id": None,
                "outbound_authorized": False,
            })
        for observation in observed:
            existing[observation["member_url"]] = observation
        next_cursor = (cursor + attempts) % len(links)
        new_state = {
            "schema_version": STATE_SCHEMA,
            "utc_day": day,
            "details_today": spent + attempts,
            "cursor": next_cursor,
            "directory_members_available_within_cap": len(links),
            "last_completed_at": stamp.isoformat(),
        }
        safe_summary = {
            "schema_version": SCHEMA,
            "state": "COMPLETED_WITH_SOURCE_ERRORS" if failures else "COMPLETED",
            "source_id": "gb_recc_solar",
            "source_rights": "internal_acquisition_only_no_raw_resale",
            "observed_at": stamp.isoformat(),
            "directory_members_available_within_cap": len(links),
            "source_details_attempted_this_sweep": attempts,
            "source_detail_failures_this_sweep": failures,
            "new_unique_research_observations": sum(
                1 for x in observed if x["member_url"] not in (
                    {v["member_url"] for v in prior}
                )
            ),
            "unique_research_observations": len(existing),
            "details_today": spent + attempts,
            "next_cursor": next_cursor,
            "source_rows_not_yet_canonical_inventory": True,
            "verified_canonical_prospect_additions": 0,
            "commercial_exchange_inventory_added": 0,
            "canonical_empiredb_writes": False,
            "outbound_authorized": False,
            "execution_authority": "none",
        }
        _atomic_private_json(ledger_path, {
            "schema_version": SCHEMA,
            "observations": sorted(
                existing.values(), key=lambda x: x["member_url"]
            ),
        })
        _atomic_private_json(state_path, new_state)
        _atomic_private_json(last_path, safe_summary)
        return safe_summary
