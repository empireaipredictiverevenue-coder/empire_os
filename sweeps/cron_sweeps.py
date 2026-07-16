#!/usr/bin/env python3
"""
Cron wrapper for Empire OS Market Sweep.
Runs daily at 5am UTC — sweeps all niche × metro combinations.

This version is optimized for speed: no website enrichment, parallel sweeps.
Full enrichment is handled by a separate pipeline.

Usage:
    python3 /root/empire_os/sweeps/cron_sweeps.py
"""

import json
import subprocess
import sys
import threading
import time
from datetime import datetime

NICHES = ["roofing", "construction", "trucking"]
METROS = ["Phoenix, AZ", "Dallas, TX", "Houston, TX", "Atlanta, GA", "Denver, CO"]
LIMIT = 5
TIMEOUT_PER_SWEEP = 45  # seconds

SWEEPER = "/root/empire_os/sweeps/market_sweep.py"


def run_sweep(niche, metro, limit):
    """Run a single sweep and return parsed result."""
    cmd = [
        "python3", SWEEPER,
        "--niche", niche,
        "--metro", metro,
        "--limit", str(limit),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_PER_SWEEP)
        if result.returncode != 0:
            return {"niche": niche, "metro": metro, "error": result.stderr.strip()[-200:]}

        # Parse the last JSON line from stdout
        for line in reversed(result.stdout.strip().split("\n")):
            line = line.strip()
            try:
                return json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
        return {"niche": niche, "metro": metro, "error": "no JSON output"}
    except subprocess.TimeoutExpired:
        return {"niche": niche, "metro": metro, "error": "timed out"}
    except Exception as e:
        return {"niche": niche, "metro": metro, "error": str(e)}


def main():
    print(f"MARKET SWEEP CRON — {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Niches: {', '.join(NICHES)}")
    print(f"Metros: {', '.join(METROS)}")
    print(f"Limit per sweep: {LIMIT}")
    print(f"Total sweeps: {len(NICHES) * len(METROS)}")
    print()

    # Run all sweeps in parallel (batch by niche for DDG rate limiting)
    all_results = []
    threads = []
    lock = threading.Lock()

    def worker(niche, metro):
        res = run_sweep(niche, metro, LIMIT)
        with lock:
            all_results.append(res)
            print(f"  [{res.get('niche','?')} / {res.get('metro','?')}] "
                  f"new={res.get('new_leads', '?')} "
                  f"dupes={res.get('duplicates_skipped', 0)} "
                  f"err={res.get('error', '')}", flush=True)

    for niche in NICHES:
        for metro in METROS:
            t = threading.Thread(target=worker, args=(niche, metro))
            threads.append(t)
            t.start()
            time.sleep(0.2)  # Stagger to avoid DDG rate limiting

    for t in threads:
        t.join()

    # Summary
    total_new = sum(r.get("new_leads", 0) for r in all_results)
    total_dupes = sum(r.get("duplicates_skipped", 0) for r in all_results)
    errors = [r for r in all_results if r.get("error")]

    print(f"\n{'='*60}")
    print(f"  CRON SWEEP COMPLETE")
    print(f"  Total new leads: {total_new}")
    print(f"  Total duplicates skipped: {total_dupes}")
    print(f"  Errors: {len(errors)}")
    if errors:
        for e in errors:
            print(f"    - {e.get('niche','?')} / {e.get('metro','?')}: {e.get('error','')}")
    for r in all_results:
        if not r.get("error"):
            print(f"    {r.get('niche','?')} / {r.get('metro','?')}: "
                  f"{r.get('new_leads',0)} new, {r.get('duplicates_skipped',0)} dupes")
    print(f"{'='*60}")

    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    main()
