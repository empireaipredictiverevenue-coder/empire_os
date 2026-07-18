#!/usr/bin/env python3
"""
Empire OS — AEO Citation Monitor (recurring SaaS product).

Wraps aeo_checker (one-shot snapshot) into a time-series monitor:
- tracks citation_rate per vertical over time
- appends timestamped samples to /root/feedback/aeo_citations.json
  (preserving history; aeo_checker.py overwrites, this APPENDS)

SKU: aeo_monitor  (MRR T1 $29 / T2 $99 / T3 $299 / T4 $999, USDC)
Settlement out-of-band (TS-5) — this module is the monitoring layer only.

Run:
  python3 aeo_monitor.py run logistics        # single check
  python3 aeo_monitor.py --loop               # check all known verticals, sleep 3600
"""
import json, os, time, sys, argparse

FEEDBACK = "/root/feedback"
STORE = f"{FEEDBACK}/aeo_citations.json"
CHECK_INTERVAL = 3600  # 1h loop

# reuse aeo_checker's vertical->query map + probe engine
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aeo_checker as ac


def _load_store():
    """Load history store; tolerant of aeo_checker's one-shot snapshot format."""
    if not os.path.exists(STORE):
        return {"history": {}}
    try:
        d = json.load(open(STORE))
    except Exception:
        return {"history": {}}
    # normalize: aeo_checker writes a flat snapshot; we keep a history key
    if "history" not in d:
        # first migration: wrap any prior snapshot
        d = {"history": {}}
    return d


def _save_store(d):
    os.makedirs(FEEDBACK, exist_ok=True)
    json.dump(d, open(STORE, "w"), indent=2)


def run_check(vertical):
    """
    Run an AEO citation check for a single vertical and append the result
    (timestamped) to the JSON history store.

    Returns:
        dict: {vertical, citation_rate (float 0..1), cited, cited_urls,
               query, results_seen, checked_at, history_len}
    """
    query = ac.VERTICAL_QUERIES.get(vertical)
    if not query:
        return {"vertical": vertical, "error": "no query mapped for vertical",
                "citation_rate": 0.0}
    chk = ac.check_vertical(vertical, query)
    cited = bool(chk.get("cited"))
    # per-vertical citation_rate: 1.0 if cited this probe, else 0.0
    citation_rate = 1.0 if cited else 0.0
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    store = _load_store()
    hist = store.setdefault("history", {})
    samples = hist.setdefault(vertical, [])
    sample = {
        "checked_at": ts,
        "query": query,
        "cited": cited,
        "cited_urls": chk.get("cited_urls", []),
        "results_seen": chk.get("results_seen", 0),
        "citation_rate": citation_rate,
    }
    samples.append(sample)
    _save_store(store)
    return {
        "vertical": vertical,
        "citation_rate": citation_rate,
        "cited": cited,
        "cited_urls": chk.get("cited_urls", []),
        "query": query,
        "results_seen": chk.get("results_seen", 0),
        "checked_at": ts,
        "history_len": len(samples),
    }


def history(vertical=None):
    """Return the timestamped history (all verticals or one)."""
    store = _load_store()
    hist = store.get("history", {})
    if vertical:
        return {vertical: hist.get(vertical, [])}
    return hist


def _loop():
    verticals = list(ac.VERTICAL_QUERIES.keys())
    print(f"[aeo_monitor] loop start | verticals={verticals} | "
          f"interval={CHECK_INTERVAL}s", flush=True)
    while True:
        for v in verticals:
            try:
                r = run_check(v)
                print(f"[aeo_monitor] {v} rate={r.get('citation_rate')} "
                      f"cited={r.get('cited')} hist={r.get('history_len')}",
                      flush=True)
            except Exception as e:
                print(f"[aeo_monitor] {v} error: {e}", flush=True)
        time.sleep(CHECK_INTERVAL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="--loop",
                    help="run <vertical> | --loop")
    ap.add_argument("--loop", action="store_true", help="monitor all verticals, sleep 3600")
    args = ap.parse_args()
    if args.cmd == "--loop" or args.loop:
        _loop()
    else:
        r = run_check(args.cmd)
        print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
