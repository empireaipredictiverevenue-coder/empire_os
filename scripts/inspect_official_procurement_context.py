"""One bounded public OCDS GET; metadata only, no contacts or commercial acts."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, build_opener

from empire_os.data_exchange_procurement_context import inspect_procurement_releases
from scripts.probe_construction_official_entities import NoRedirect

MAX_BYTES = 512_000


def fetch_official_procurement(url: str) -> dict:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.find-tender.service.gov.uk"
        or parsed.port not in (None, 443)
        or parsed.username or parsed.password or parsed.fragment
        or parsed.path != "/api/1.0/ocdsReleasePackages"
    ):
        raise ValueError("procurement transport URL not authorised")
    query = parse_qs(parsed.query, strict_parsing=True)
    if set(query) != {"updatedFrom", "updatedTo", "limit"} or any(
        len(v) != 1 for v in query.values()
    ):
        raise ValueError("procurement query not authorised")
    if query["limit"][0] not in {"1", "2", "3", "4", "5"}:
        raise ValueError("procurement limit not authorised")
    for item in (query["updatedFrom"][0], query["updatedTo"][0]):
        if len(item) != 20 or not item.endswith("T00:00:00Z"):
            raise ValueError("procurement timestamp not authorised")
        date.fromisoformat(item[:10])
    req = Request(url, headers={
        "User-Agent": "EmpireAI-DataExchange-Observe/1.0",
        "Accept": "application/json",
    })
    with build_opener(NoRedirect).open(req, timeout=10) as response:
        if response.status != 200:
            raise ValueError("procurement source returned unexpected HTTP status")
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("procurement source body exceeds permitted limit")
    result = json.loads(data)
    if not isinstance(result, dict):
        raise ValueError("procurement source not a JSON object")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", required=True, type=date.fromisoformat)
    parser.add_argument("--end-date", required=True, type=date.fromisoformat)
    parser.add_argument("--limit", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        result = inspect_procurement_releases(
            start_date=args.start_date,
            end_date=args.end_date,
            limit=args.limit,
            fetch_json=fetch_official_procurement,
            observed_at=datetime.now(timezone.utc),
        )
    except (ValueError, TypeError, OSError, URLError,
            json.JSONDecodeError) as exc:
        print(json.dumps({
            "status": "HOLD", "error_type": type(exc).__name__,
            "execution_authority": "NONE",
            "customer_delivery_enabled": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
