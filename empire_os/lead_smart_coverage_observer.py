from __future__ import annotations

import base64
import hashlib
import json
import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urljoin
from urllib.request import Request, urlopen


PUBLIC_COVERAGE_URL = "https://affiliate-bid-coverage.leadsmartinc.com/"
COVERAGE_TABLE = "offer_bids"

COVERAGE_FIELDS = (
    "zip,city,state,offer_key,offer_name,"
    "duration_payout,cpl_payout,top_payout,last_updated"
)

USER_AGENT = "EmpireAI-LeadSmartCoverageObserver/1.0"


@dataclass(frozen=True)
class PublicContract:
    host: str
    public_key: str
    public_key_kind: str
    bundle_url: str
    bundle_sha256: str


def _http_text(url: str, *, timeout: int = 45) -> str:
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT},
        method="GET",
    )

    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)

    return json.loads(
        base64.urlsafe_b64decode(payload.encode()).decode()
    )


def extract_supabase_host(bundle: str) -> str:
    hosts = sorted(set(re.findall(
        r"https://[a-z0-9-]+\.supabase\.co",
        bundle,
        flags=re.I,
    )))

    if len(hosts) != 1:
        raise RuntimeError(
            f"expected one public backend host, found {len(hosts)}"
        )

    return hosts[0]


def extract_public_credential(bundle: str) -> tuple[str, str]:
    """
    Extract ONLY credentials intentionally embedded in the public client.

    Accepted:
      - sb_publishable_* key
      - JWT whose declared role is exactly anon

    Never accepts sb_secret_* or a JWT with any other role.
    """

    publishable = sorted(set(re.findall(
        r"sb_publishable_[A-Za-z0-9._-]+",
        bundle,
    )))

    if publishable:
        if len(publishable) != 1:
            raise RuntimeError(
                "ambiguous public publishable credentials"
            )

        return "publishable", publishable[0]

    jwt_pattern = re.compile(
        r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
    )

    candidates: list[str] = []

    for token in jwt_pattern.findall(bundle):
        try:
            payload = _decode_jwt_payload(token)
        except Exception:
            continue

        if payload.get("role") == "anon":
            candidates.append(token)

    candidates = sorted(set(candidates))

    if len(candidates) != 1:
        raise RuntimeError(
            f"expected one anon public JWT, found {len(candidates)}"
        )

    return "anon_jwt", candidates[0]


def discover_public_contract() -> PublicContract:
    html = _http_text(PUBLIC_COVERAGE_URL)

    matches = re.findall(
        r'<script[^>]+src=["\']([^"\']*/assets/index-[^"\']+\.js)["\']',
        html,
        flags=re.I,
    )

    if len(matches) != 1:
        raise RuntimeError(
            f"expected one main coverage bundle, found {len(matches)}"
        )

    bundle_url = urljoin(PUBLIC_COVERAGE_URL, matches[0])
    bundle = _http_text(bundle_url, timeout=60)

    host = extract_supabase_host(bundle)
    key_kind, public_key = extract_public_credential(bundle)

    return PublicContract(
        host=host,
        public_key=public_key,
        public_key_kind=key_kind,
        bundle_url=bundle_url,
        bundle_sha256=hashlib.sha256(
            bundle.encode()
        ).hexdigest(),
    )


def _auth_headers(contract: PublicContract) -> dict[str, str]:
    headers = {
        "apikey": contract.public_key,
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        "Range-Unit": "items",
    }

    if contract.public_key_kind == "anon_jwt":
        headers["Authorization"] = (
            f"Bearer {contract.public_key}"
        )

    return headers


def public_rest_get(
    contract: PublicContract,
    *,
    table: str,
    params: dict[str, str],
    start: int,
    end: int,
    exact_count: bool = False,
) -> tuple[list[dict[str, Any]], str | None]:
    query = urlencode(
        params,
        safe=",.*()",
    )

    url = (
        f"{contract.host.rstrip('/')}/rest/v1/"
        f"{quote(table, safe='')}?{query}"
    )

    headers = {
        **_auth_headers(contract),
        "Range": f"{start}-{end}",
    }

    if exact_count:
        headers["Prefer"] = "count=exact"

    request = Request(
        url,
        headers=headers,
        method="GET",
    )

    try:
        with urlopen(request, timeout=45) as response:
            body = response.read().decode(
                "utf-8",
                errors="replace",
            )

            data = json.loads(body) if body else []

            if not isinstance(data, list):
                raise RuntimeError(
                    "public read returned non-list payload"
                )

            return data, response.headers.get("Content-Range")

    except HTTPError as exc:
        body = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"public read failed status={exc.code} "
            f"table={table} body={body[:400]}"
        ) from exc


def fetch_verticals(
    contract: PublicContract,
) -> list[dict[str, Any]]:
    rows, _ = public_rest_get(
        contract,
        table="verticals",
        params={
            "select":
                "id,slug,name,enabled,sort_order,"
                "group_label,offer_key,offer_name,"
                "offer_group",
            "order": "sort_order.asc",
        },
        start=0,
        end=199,
        exact_count=True,
    )

    return rows


def select_canonical_roofing_vertical(
    verticals: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Exact campaign selector.

    Avoids the broad 'roof' match that also catches:
      - Roofing CPL
      - Waterproofing
    """

    matches = [
        row
        for row in verticals
        if row.get("enabled") is True
        and str(row.get("slug") or "").casefold() == "roofing"
        and str(row.get("offer_key") or "").casefold() == "roofing"
        and str(row.get("group_label") or "").casefold()
            == "pay-per-call"
    ]

    if len(matches) != 1:
        raise RuntimeError(
            "canonical Roofing Pay-per-Call vertical "
            f"is ambiguous: {len(matches)} matches"
        )

    return matches[0]


def fetch_roofing_coverage(
    contract: PublicContract,
    *,
    offer_key: str,
    page_size: int = 1000,
    max_rows: int = 100_000,
) -> tuple[list[dict[str, Any]], str | None]:
    rows: list[dict[str, Any]] = []
    start = 0
    first_content_range: str | None = None

    while True:
        end = start + page_size - 1

        batch, content_range = public_rest_get(
            contract,
            table=COVERAGE_TABLE,
            params={
                "select": COVERAGE_FIELDS,
                "offer_key": f"eq.{offer_key}",
                "order": "zip.asc",
            },
            start=start,
            end=end,
            exact_count=(start == 0),
        )

        if start == 0:
            first_content_range = content_range

        rows.extend(batch)

        if len(rows) > max_rows:
            raise RuntimeError(
                f"roofing coverage exceeds safety cap {max_rows}"
            )

        if len(batch) < page_size:
            break

        start += page_size

    return rows, first_content_range


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def validate_roofing_rows(
    rows: list[dict[str, Any]],
    *,
    offer_key: str,
) -> None:
    if not rows:
        raise RuntimeError("roofing coverage returned zero rows")

    required = {
        "zip",
        "city",
        "state",
        "offer_key",
        "offer_name",
        "duration_payout",
        "cpl_payout",
        "top_payout",
        "last_updated",
    }

    for index, row in enumerate(rows):
        missing = required - set(row)

        if missing:
            raise RuntimeError(
                f"row {index} missing fields: {sorted(missing)}"
            )

        zip_code = row.get("zip")

        if (
            not isinstance(zip_code, str)
            or re.fullmatch(r"\d{5}", zip_code) is None
        ):
            raise RuntimeError(
                f"invalid ZIP at row {index}: {zip_code!r}"
            )

        if row.get("offer_key") != offer_key:
            raise RuntimeError(
                f"unexpected offer_key at row {index}: "
                f"{row.get('offer_key')!r}"
            )

        for key in (
            "duration_payout",
            "cpl_payout",
            "top_payout",
        ):
            value = row.get(key)

            if value is None:
                continue

            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"invalid {key} at row {index}: {value!r}"
                ) from exc

            if number < 0:
                raise RuntimeError(
                    f"negative {key} at row {index}: {number}"
                )

        updated = row.get("last_updated")

        if not isinstance(updated, str) or not updated:
            raise RuntimeError(
                f"missing last_updated at row {index}"
            )

        _parse_time(updated)


def _numeric_values(
    rows: list[dict[str, Any]],
    key: str,
) -> list[float]:
    result = []

    for row in rows:
        value = row.get(key)

        if value is not None:
            result.append(float(value))

    return result


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "median": None,
            "max": None,
        }

    return {
        "count": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
    }


def build_snapshot(
    *,
    contract: PublicContract,
    vertical: dict[str, Any],
    rows: list[dict[str, Any]],
    content_range: str | None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    observed_at = observed_at or datetime.now(timezone.utc)

    ordered = sorted(
        rows,
        key=lambda row: (
            row["zip"],
            str(row.get("offer_name") or ""),
        ),
    )

    source_hash = hashlib.sha256(
        json.dumps(
            ordered,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()

    updated_times = [
        _parse_time(row["last_updated"])
        for row in ordered
    ]

    newest = max(updated_times)
    oldest = min(updated_times)

    duration_values = _numeric_values(
        ordered,
        "duration_payout",
    )

    cpl_values = _numeric_values(
        ordered,
        "cpl_payout",
    )

    top_values = _numeric_values(
        ordered,
        "top_payout",
    )

    unique_zips = {
        row["zip"]
        for row in ordered
    }

    return {
        "schema_version":
            "empire.lead_smart.coverage_snapshot.v1",
        "mode": "OBSERVE",
        "buyer": "Lead Smart",
        "vertical": "Roofing",
        "observed_at": observed_at.isoformat(),
        "source": {
            "public_url": PUBLIC_COVERAGE_URL,
            "backend_host": contract.host,
            "table": COVERAGE_TABLE,
            "bundle_url": contract.bundle_url,
            "bundle_sha256": contract.bundle_sha256,
            "public_key_persisted": False,
            "content_range": content_range,
            "semantics": "TARGETING_GUIDANCE_ONLY",
            "payout_guaranteed": False,
        },
        "canonical_vertical": {
            "id": vertical.get("id"),
            "slug": vertical.get("slug"),
            "name": vertical.get("name"),
            "group_label": vertical.get("group_label"),
            "offer_key": vertical.get("offer_key"),
            "offer_name": vertical.get("offer_name"),
            "enabled": vertical.get("enabled"),
        },
        "coverage": {
            "row_count": len(ordered),
            "unique_zip_count": len(unique_zips),
            "duplicate_zip_row_count":
                len(ordered) - len(unique_zips),
            "source_oldest_last_updated":
                oldest.isoformat(),
            "source_newest_last_updated":
                newest.isoformat(),
            "oldest_age_seconds": max(
                0,
                int((observed_at - oldest).total_seconds()),
            ),
            "newest_age_seconds": max(
                0,
                int((observed_at - newest).total_seconds()),
            ),
            "duration_payout": _stats(duration_values),
            "cpl_payout": _stats(cpl_values),
            "top_payout": _stats(top_values),
            "rows_with_no_top_payout": sum(
                row.get("top_payout") is None
                for row in ordered
            ),
        },
        "source_hash": source_hash,
        "rows": ordered,
        "authority": {
            "zip_coverage_observed": True,
            "zip_coverage_activation_verified": False,
            "tracking_verified": False,
            "routing_verified": False,
            "routing_enabled": False,
            "traffic_enabled": False,
            "commercial_activation": False,
            "execution_authority": "NONE",
        },
    }


def build_delta(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, Any]:
    if not previous:
        return {
            "baseline": True,
            "previous_source_hash": None,
            "source_changed": None,
            "zip_added_count": None,
            "zip_removed_count": None,
            "top_payout_changed_zip_count": None,
        }

    prev_rows = previous.get("rows") or []
    curr_rows = current.get("rows") or []

    def by_zip(
        rows: list[dict[str, Any]],
    ) -> dict[str, float | None]:
        result: dict[str, float | None] = {}

        for row in rows:
            zip_code = row["zip"]
            value = row.get("top_payout")

            if value is None:
                result.setdefault(zip_code, None)
                continue

            value = float(value)

            existing = result.get(zip_code)

            if existing is None or value > existing:
                result[zip_code] = value

        return result

    previous_map = by_zip(prev_rows)
    current_map = by_zip(curr_rows)

    previous_zips = set(previous_map)
    current_zips = set(current_map)

    common = previous_zips & current_zips

    changed = sum(
        previous_map[zip_code] != current_map[zip_code]
        for zip_code in common
    )

    return {
        "baseline": False,
        "previous_source_hash":
            previous.get("source_hash"),
        "source_changed":
            previous.get("source_hash")
            != current.get("source_hash"),
        "zip_added_count":
            len(current_zips - previous_zips),
        "zip_removed_count":
            len(previous_zips - current_zips),
        "top_payout_changed_zip_count": changed,
    }


def write_snapshot(
    snapshot: dict[str, Any],
    *,
    output_root: Path,
) -> tuple[Path, Path]:
    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    snapshots = output_root / "snapshots"
    snapshots.mkdir(
        parents=True,
        exist_ok=True,
    )

    observed = datetime.fromisoformat(
        snapshot["observed_at"]
    )

    stamp = observed.strftime("%Y%m%dT%H%M%SZ")

    snapshot_path = (
        snapshots
        / f"{stamp}_{snapshot['source_hash'][:12]}.json"
    )

    payload = json.dumps(
        snapshot,
        indent=2,
        sort_keys=True,
    ) + "\n"

    snapshot_path.write_text(payload)

    latest_path = output_root / "latest.json"
    temporary = output_root / ".latest.json.tmp"

    temporary.write_text(payload)
    temporary.replace(latest_path)

    return snapshot_path, latest_path


def observe(
    *,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = discover_public_contract()

    verticals = fetch_verticals(contract)

    vertical = select_canonical_roofing_vertical(
        verticals
    )

    rows, content_range = fetch_roofing_coverage(
        contract,
        offer_key=vertical["offer_key"],
    )

    validate_roofing_rows(
        rows,
        offer_key=vertical["offer_key"],
    )

    snapshot = build_snapshot(
        contract=contract,
        vertical=vertical,
        rows=rows,
        content_range=content_range,
    )

    snapshot["delta"] = build_delta(
        previous,
        snapshot,
    )

    return snapshot
