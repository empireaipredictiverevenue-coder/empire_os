"""Read-only bounded LPA brownfield discovery; stdout-only internal review.

No API keys, user contacts, database migrations or customer distribution.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from urllib.error import URLError
from urllib.parse import parse_qsl, urlsplit
from urllib.request import Request, build_opener

from empire_os.data_exchange_discovery import (
    AUTHORITY, discover_official_brownfield_sample,
)
from scripts.probe_construction_official_entities import (
    MAX_RESPONSE_BYTES, NoRedirect, fetch_official_json,
)


def fetch_discovery_listing(url: str) -> dict:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "www.planning.data.gov.uk":
        raise ValueError("listing host not authorised")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("listing authority not authorised")
    if parsed.path != "/entity.json" or parsed.fragment:
        raise ValueError("listing path not authorised")
    parameters = parse_qsl(parsed.query, keep_blank_values=True)
    if len(parameters) != 7 or set(parameters[-2:]) != {
        ("field", "entity"), ("field", "dataset"),
    }:
        raise ValueError("listing fields not authorised")
    param = dict(parameters[:5])
    if (
        set(param) != {"dataset", "geometry_entity", "geometry_relation", "limit", "offset"}
        or param["dataset"] != "brownfield-land"
        or param["geometry_entity"] not in {"626027", "626048"}
        or param["geometry_relation"] != "within"
        or param["limit"] not in {"1", "2", "3", "4", "5"}
        or param["offset"] not in {str(i) for i in range(1001)}
    ):
        raise ValueError("listing filters not authorised")
    opener = build_opener(NoRedirect)
    req = Request(url, headers={"User-Agent": "EmpireAI-DataExchange-Observe/1.0"})
    with opener.open(req, timeout=10) as response:
        if response.status != 200:
            raise ValueError("official listing HTTP not 200")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("official listing response size exceeded")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("official listing response must be object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority", required=True, choices=sorted(AUTHORITY))
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        review = discover_official_brownfield_sample(
            authority=args.authority, limit=args.limit, offset=args.offset,
            fetch_listing=fetch_discovery_listing,
            fetch_entity=fetch_official_json,
            observed_at=datetime.now(timezone.utc),
        )
    except (OSError, URLError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "assessment_status": "HOLD", "error_type": type(exc).__name__,
            "customer_delivery_enabled": False,
            "execution_authority": "NONE",
        }, sort_keys=True))
        return 2
    print(json.dumps(review, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
