"""Read-only, bounded public brownfield-entity probe; stdout only.

No prospect creation, automatic outreach, rights approval, commercial export,
customer fulfilment, production writes or payment action.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler, Request, build_opener,
)

from empire_os.data_exchange_construction import (
    build_construction_preview, normalise_official_brownfield_entities,
)

MAX_RESPONSE_BYTES = 200_000


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_official_json(url: str) -> dict:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.planning.data.gov.uk"
        or parsed.port not in (None, 443)
        or not parsed.path.startswith("/entity/")
        or not parsed.path.endswith(".json")
        or parsed.query or parsed.fragment
    ):
        raise ValueError("non-official URL rejected")
    opener = build_opener(NoRedirect)
    req = Request(url, headers={"User-Agent": "EmpireAI-DataExchange-Observe/1.0"})
    with opener.open(req, timeout=8) as response:
        if response.status != 200:
            raise ValueError("official source HTTP not 200")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("official source response size exceeded")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("official source not a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entity", type=int, nargs="+", required=True)
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    try:
        rows = normalise_official_brownfield_entities(
            args.entity, fetch_json=fetch_official_json, observed_at=now,
        )
        result = build_construction_preview(rows, observed_at=now)
    except (ValueError, URLError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "status": "HOLD", "error_type": type(exc).__name__,
            "customer_delivery_enabled": False,
            "execution_authority": "NONE",
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
