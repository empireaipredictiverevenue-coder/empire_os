#!/usr/bin/env python3
"""Private National Storm Hub Revenue Pulse alert preview (NO sending).

Runs without database access or credentials. Production canonical Revenue
Pulse is only an organisation-wide diagnostic; no false NSH attribution.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from empire_os.national_storm_hub_revenue_alerts import review_nsh_revenue_alerts

PULSE_PATH = Path("/srv/empire_os/runtime/revenue_pulse/latest.json")
HOME = "https://nationalstormhub.com/"
WEATHER = "https://nationalstormhub.com/api/alerts?state=TX"


def _http_code(url: str) -> int | None:
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "NationalStormHubRevenuePulse/1.0 (internal-site-probe)"}
        )
        with urllib.request.urlopen(request, timeout=9) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (OSError, TimeoutError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", required=True, action="store_true")
    parser.add_argument("--probe-live", action="store_true",
                        help="Check only the fixed, public NSH HTTPS endpoints.")
    parser.add_argument("--pulse-snapshot", type=Path, default=PULSE_PATH)
    args = parser.parse_args()

    try:
        company = json.loads(args.pulse_snapshot.read_text())
    except (OSError, json.JSONDecodeError):
        company = None
    if not isinstance(company, dict):
        company = None

    probes = None
    if args.probe_live:
        probes = {"homepage_http": _http_code(HOME), "weather_api_http": _http_code(WEATHER)}
    review = review_nsh_revenue_alerts(
        now=datetime.now(timezone.utc),
        site_probe=probes,
        current_revenue_pulse=company,
        tenant_events=None,  # No verified tenant-scoped commercial feed connected.
    )
    print(json.dumps(review, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
