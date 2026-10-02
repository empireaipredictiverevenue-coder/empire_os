"""Official public-license identity seeds for evidence recovery.

These records are not buyer-authority claims. They provide named professionals
associated with a company so first-party evidence can be searched more precisely.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import fcntl
import io
import json
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from typing import Any

TEXAS_RMP_CSV = "https://tsbpe.texas.gov/download-csv/RMP/"
TEXAS_RMP_SOURCE = "https://tsbpe.texas.gov/free-licensee-list/"
TEXAS_TDLR_API = "https://data.texas.gov/resource/7358-krk7.json"
TEXAS_TDLR_SOURCE = (
    "https://data.texas.gov/dataset/TDLR-All-Licenses/7358-krk7/about_data"
)
TEXAS_TDLR_AC_CACHE = Path(
    "/srv/empire_os/runtime/license_identity/texas_tdlr_ac_contractors.json"
)
_CACHE_TTL_SECONDS = 6 * 60 * 60
_cache: tuple[float, str] | None = None


@dataclass(frozen=True)
class LicensePrincipalSeed:
    company_name: str
    person_name: str
    role: str
    state: str
    source: str
    source_url: str
    confidence: float
    license_status: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalise_company(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    tokens = [
        token for token in text.split()
        if token not in {
            "llc", "ltd", "inc", "incorporated", "corp", "corporation",
            "company", "co", "pllc", "lp", "llp",
        }
    ]
    return " ".join(tokens)


def _company_match_score(left: str, right: str) -> float:
    a = _normalise_company(left)
    b = _normalise_company(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    at, bt = set(a.split()), set(b.split())
    shorter_tokens, longer_tokens = (
        (at, bt) if len(at) <= len(bt) else (bt, at)
    )
    if (
        len(shorter_tokens) >= 2
        and shorter_tokens <= longer_tokens
    ):
        return 0.96
    overlap = len(at & bt) / max(1, min(len(at), len(bt)))
    seq = SequenceMatcher(None, a, b).ratio()
    if overlap == 1.0 and min(len(at), len(bt)) >= 2:
        return max(0.94, seq)
    return max(seq, overlap * 0.92)


def _fetch_texas_rmp_csv(timeout: float = 12.0) -> str:
    global _cache
    now = time.time()
    if _cache and now - _cache[0] < _CACHE_TTL_SECONDS:
        return _cache[1]
    req = urllib.request.Request(
        TEXAS_RMP_CSV,
        headers={"User-Agent": "Mozilla/5.0 EmpireOS/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8-sig", errors="replace")
    _cache = (now, text)
    return text




def _parse_tdlr_owner(value: Any) -> str:
    raw = " ".join(str(value or "").strip().split())
    if not raw:
        return ""
    if "," in raw:
        last, rest = [part.strip() for part in raw.split(",", 1)]
        pieces = [part for part in rest.split() if part]
        if not last or not pieces:
            return ""
        suffixes = {"II", "III", "IV", "JR", "SR"}
        given = [
            token.upper() if token.upper().rstrip(".") in suffixes
            else token.title()
            for token in pieces
        ]
        candidate = " ".join([*given, last.title()])
    else:
        candidate = " ".join(
            token.upper()
            if token.upper().rstrip(".") in {"II", "III", "IV", "JR", "SR"}
            else token.title()
            for token in raw.split()
        )

    words = [
        token.strip(".,()[]{}")
        for token in candidate.split()
        if token.strip(".,()[]{}")
    ]
    if not 2 <= len(words) <= 6:
        return ""
    if any(any(ch.isdigit() for ch in token) for token in words):
        return ""
    return " ".join(words)


def _parse_mmddyyyy(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%m/%d/%Y").date()
    except ValueError:
        return None


def texas_tdlr_ac_seeds_from_rows(
    company_name: str,
    records: list[dict[str, Any]],
    *,
    as_of: date | None = None,
    minimum_match: float = 0.90,
) -> list[LicensePrincipalSeed]:
    current = as_of or datetime.now(timezone.utc).date()
    rows: list[LicensePrincipalSeed] = []
    for raw in records or []:
        if str(raw.get("license_type") or "").strip() != "A/C Contractor":
            continue
        expiry = _parse_mmddyyyy(
            raw.get("license_expiration_date_mmddccyy")
        )
        if expiry is None or expiry < current:
            continue
        listed_company = str(raw.get("business_name") or "").strip()
        score = _company_match_score(company_name, listed_company)
        if score < minimum_match:
            continue
        owner = _parse_tdlr_owner(raw.get("owner_name"))
        if not owner:
            continue
        if _normalise_company(owner) == _normalise_company(listed_company):
            continue
        rows.append(LicensePrincipalSeed(
            company_name=listed_company,
            person_name=owner,
            role="Licensed A/C Contractor",
            state="TX",
            source="texas_tdlr_ac_contractor",
            source_url=TEXAS_TDLR_SOURCE,
            confidence=round(min(0.99, max(0.90, score)), 4),
            license_status="current_by_expiration",
        ))
    rows.sort(key=lambda row: (-row.confidence, row.person_name.casefold()))
    return rows[:3]


def _tdlr_query_url() -> str:
    params = urllib.parse.urlencode({
        "$select": (
            "license_type,license_number,business_county,business_name,"
            "license_expiration_date_mmddccyy,owner_name,license_subtype"
        ),
        "$where": "license_type='A/C Contractor'",
        "$limit": "30000",
    })
    return TEXAS_TDLR_API + "?" + params


def refresh_texas_tdlr_ac_cache(
    *,
    cache_path: str | Path = TEXAS_TDLR_AC_CACHE,
    timeout: float = 30.0,
) -> dict[str, Any]:
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.touch(exist_ok=True)

    with lock_path.open("r+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            req = urllib.request.Request(
                _tdlr_query_url(),
                headers={"User-Agent": "Mozilla/5.0 EmpireOS/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(
                    resp.read().decode("utf-8", errors="replace")
                )
            if not isinstance(payload, list):
                raise ValueError("TDLR response must be a list")
            records = [
                dict(row)
                for row in payload
                if isinstance(row, dict)
                and str(row.get("license_type") or "").strip()
                == "A/C Contractor"
            ]
            company_index: dict[str, list[int]] = {}
            token_index: dict[str, list[int]] = {}
            for index, row in enumerate(records):
                company = _normalise_company(row.get("business_name") or "")
                if not company:
                    continue
                company_index.setdefault(company, []).append(index)
                for token in set(company.split()):
                    if len(token) >= 3:
                        token_index.setdefault(token, []).append(index)

            snapshot = {
                "schema_version": "empire.official-license-cache.v2",
                "source": "texas_tdlr_ac_contractor",
                "source_url": TEXAS_TDLR_SOURCE,
                "refreshed_at": datetime.now(timezone.utc).isoformat(),
                "record_count": len(records),
                "records": records,
                "company_index": company_index,
                "token_index": token_index,
                "database_write_performed": False,
                "outbound_sent": False,
                "execution_authority": "none",
            }
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(snapshot, separators=(",", ":")),
                encoding="utf-8",
            )
            tmp.replace(path)
            return {
                "ok": True,
                "record_count": len(records),
                "cache_path": str(path),
                "outbound_sent": False,
                "execution_authority": "none",
            }
        except Exception as exc:
            stale_count = 0
            try:
                stale = json.loads(path.read_text(encoding="utf-8"))
                stale_count = len(stale.get("records") or [])
            except (OSError, json.JSONDecodeError, AttributeError):
                pass
            return {
                "ok": False,
                "error": f"{type(exc).__name__}:{str(exc)[:240]}",
                "stale_record_count": stale_count,
                "cache_path": str(path),
                "outbound_sent": False,
                "execution_authority": "none",
            }


def _load_tdlr_cache_payload(
    cache_path: str | Path = TEXAS_TDLR_AC_CACHE,
) -> dict[str, Any]:
    try:
        payload = json.loads(
            Path(cache_path).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_tdlr_cache(
    cache_path: str | Path = TEXAS_TDLR_AC_CACHE,
) -> list[dict[str, Any]]:
    payload = _load_tdlr_cache_payload(cache_path)
    return [
        dict(row)
        for row in (payload.get("records") or [])
        if isinstance(row, dict)
    ]


def _tdlr_candidate_rows(
    company_name: str,
    *,
    cache_path: str | Path = TEXAS_TDLR_AC_CACHE,
) -> list[dict[str, Any]]:
    payload = _load_tdlr_cache_payload(cache_path)
    records = payload.get("records") or []
    if not isinstance(records, list):
        return []
    target = _normalise_company(company_name)
    if not target:
        return []

    exact = payload.get("company_index")
    if isinstance(exact, dict):
        indexes = exact.get(target) or []
        if indexes:
            return [
                dict(records[index])
                for index in indexes
                if isinstance(index, int)
                and 0 <= index < len(records)
                and isinstance(records[index], dict)
            ]

    token_index = payload.get("token_index")
    if not isinstance(token_index, dict):
        return [
            dict(row) for row in records if isinstance(row, dict)
        ]

    tokens = [token for token in target.split() if len(token) >= 3]
    sets = [
        set(index for index in (token_index.get(token) or [])
            if isinstance(index, int))
        for token in tokens
        if token_index.get(token)
    ]
    if not sets:
        return []
    candidate_indexes = (
        set.intersection(*sets)
        if len(sets) > 1 and set.intersection(*sets)
        else set.union(*sets)
    )
    # Bound fuzzy matching work. Exact company matches were already handled.
    ranked = sorted(candidate_indexes)[:500]
    return [
        dict(records[index])
        for index in ranked
        if 0 <= index < len(records)
        and isinstance(records[index], dict)
    ]



def texas_rmp_seeds_from_csv(
    company_name: str,
    csv_text: str,
    *,
    minimum_match: float = 0.90,
) -> list[LicensePrincipalSeed]:
    rows: list[LicensePrincipalSeed] = []
    for raw in csv.DictReader(io.StringIO(csv_text or "")):
        if str(raw.get("LIC_STATUS") or "").strip().lower() != "current":
            continue
        listed_company = str(raw.get("PLUMB_COMPANY") or "").strip()
        score = _company_match_score(company_name, listed_company)
        if score < minimum_match:
            continue
        first = str(raw.get("FIRST_NAME") or "").strip().title()
        middle = str(raw.get("MIDDLE_NAME") or "").strip().title()
        last = str(raw.get("LAST_NAME") or "").strip().title()
        suffix = str(raw.get("SUFFIX") or "").strip()
        name = " ".join(x for x in (first, middle, last, suffix) if x)
        if not first or not last:
            continue
        rows.append(LicensePrincipalSeed(
            company_name=listed_company,
            person_name=name,
            role="Responsible Master Plumber",
            state="TX",
            source="texas_tsbpe_rmp",
            source_url=TEXAS_RMP_SOURCE,
            confidence=round(min(0.99, max(0.90, score)), 4),
            license_status="current",
        ))
    rows.sort(key=lambda row: (-row.confidence, row.person_name.casefold()))
    return rows[:3]


def find_official_license_principals(
    *,
    company_name: str,
    state: str,
    timeout: float = 12.0,
) -> list[dict[str, Any]]:
    state = str(state or "").strip().upper()
    if state != "TX" or not str(company_name or "").strip():
        return []
    seeds: list[LicensePrincipalSeed] = []
    tdlr_rows = _tdlr_candidate_rows(company_name)
    if tdlr_rows:
        seeds.extend(
            texas_tdlr_ac_seeds_from_rows(
                company_name,
                tdlr_rows,
            )
        )

    try:
        text = _fetch_texas_rmp_csv(timeout=timeout)
    except Exception:
        text = ""
    if text:
        seeds.extend(
            texas_rmp_seeds_from_csv(company_name, text)
        )

    dedup: dict[tuple[str, str], LicensePrincipalSeed] = {}
    for seed in seeds:
        key = (
            seed.person_name.casefold(),
            _normalise_company(seed.company_name),
        )
        current = dedup.get(key)
        if current is None or seed.confidence > current.confidence:
            dedup[key] = seed
    ordered = sorted(
        dedup.values(),
        key=lambda row: (
            -row.confidence,
            row.person_name.casefold(),
            row.source,
        ),
    )
    return [row.as_dict() for row in ordered[:5]]
