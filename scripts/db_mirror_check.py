#!/usr/bin/env python3
"""
Empire OS DB Mirror — host mirror via HTTP API
Since the host's empire_os.db diverged from the container's (different schemas,
1.7GB bloat in container), we DON'T sync the SQLite file. Instead:
  - Host scripts read container data via empire_os.db_adapter (which proxies
    to the container's DB via incus exec)
  - All WRITES go through the hub at http://10.118.155.218:8081
  - The host's empire_os.db remains a thin local mirror of legacy data only

Run as a periodic cron to verify both sides are healthy.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")

LOG = "/root/feedback/db_mirror.log"


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def main() -> int:
    try:
        from empire_os.db_adapter import (
            get_lane_leads_count_by_niche,
            get_si_tenant_count,
            get_si_subscription_count,
            get_si_charges_pending,
            get_empty_lanes,
        )
    except Exception as e:
        log(f"ERR import: {e}")
        return 1

    # Sanity check: container DB reachable
    try:
        niches = get_lane_leads_count_by_niche()
        log(f"OK container reachable: {len(niches)} niches, "
            f"top={niches[0] if niches else 'none'}")
    except Exception as e:
        log(f"ERR container unreachable: {e}")
        return 1

    # Sanity check: hub reachable
    try:
        import urllib.request
        req = urllib.request.Request("http://10.118.155.218:8081/health", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            hub_health = json.loads(resp.read())
        log(f"OK hub reachable: {hub_health}")
    except Exception as e:
        log(f"ERR hub unreachable: {e}")
        return 1

    # Snapshot key counts
    try:
        tenants = get_si_tenant_count()
        subs = get_si_subscription_count()
        pending_n, pending_total = get_si_charges_pending()
        empty = len(get_empty_lanes(limit=200))
        log(f"OK counts: tenants={tenants} subs={subs} "
            f"pending_chgs={pending_n} (${pending_total:,.2f}) empty_lanes={empty}")
    except Exception as e:
        log(f"WARN counts: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())