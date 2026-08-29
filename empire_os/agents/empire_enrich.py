#!/usr/bin/env python3
"""
empire_enrich.py — in-house replacement for scrapecreators_enrich.

scrapecreators.com was a paid third-party API that returned Reddit threads,
TikTok posts, Google Maps rows, etc. as "lead-intent" seeds. We moved
off it (no API key, no budget for that subscription anymore). This module
does the same job using our own lead_sources/* stack — same targets, same
niches, same outbox (si_buyer_outreach, source='empire_enrich').

Backed by:
  - lead_sources/permits.py        (NYC DOB permits — Tier: real, free)
  - lead_sources/nyc_hpd.py        (NYC HPD violations — Tier: real, free)
  - lead_sources/chicago_311.py    (Chicago 311 service requests — Tier: real, free)
  - lead_sources/overpass.py       (OpenStreetMap POIs — Tier: real, free)
  - lead_sources/searxng_search.py (search snippets — Tier: real, free)
  - lead_sources/court_listener.py (legal signals — Tier: real, free)
  - lead_sources/solar_intelligence (solar permit signals — Tier: real, free)

Return shape mirrors the old scrapecreators_enrich.run() so callers
(content_engine.py, a2a_buyer_marketplace.py, etc.) don't change.

Key handling: SCRAPECREATORS_API_KEY env was the old third-party key.
This module ignores it — we don't need a paid API. We DO accept an opt-in
EMPIRE_ENRICH_DRY_RUN=1 for testing.
"""
from __future__ import annotations
import os, sys, json, time, sqlite3, logging, traceback

# Make sure /root/empire_os/empire_os/ is on path so we can import
# the sibling lead_sources/* modules.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS_DIR)
sys.path.insert(0, os.path.dirname(_THIS_DIR))

log = logging.getLogger("empire_enrich")

DB = os.getenv("EMPIRE_DB", "/root/empire_os/empire_os.db")
DRY_RUN = bool(int(os.getenv("EMPIRE_ENRICH_DRY_RUN", "0")))
# Cap how many leads any single run can insert.
CAP = int(os.getenv("EMPIRE_ENRICH_CAP", "10"))

# Niches we want to seed via in-house sources. Matches what
# scrapecreators_enrich did, mapped to our actual lane niches.
NICHES = [
    "roofing", "hvac", "plumbing", "solar", "landscaping",
    "pest_control", "electrical", "painting", "windows", "fencing",
]


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _safe_import_source(name: str):
    """Import one of lead_sources/* modules; return None if it's missing/broken."""
    try:
        mod = __import__(f"empire_os.lead_sources.{name}", fromlist=["run"])
        return mod
    except Exception as e:
        log.info("skip %s (%s)", name, str(e)[:120])
        return None


# Mapping: niche -> list of source module names that are likely to fire.
NICHE_SOURCES = {
    "roofing":      ["permits", "nyc_hpd", "chicago_311", "searxng_search"],
    "hvac":         ["permits", "nyc_hpd", "chicago_311", "searxng_search"],
    "plumbing":     ["permits", "nyc_hpd", "chicago_311", "searxng_search"],
    "solar":        ["permits", "solar_intelligence", "searxng_search"],
    "landscaping":  ["permits", "chicago_311", "searxng_search"],
    "pest_control": ["permits", "nyc_hpd", "chicago_311"],
    "electrical":   ["permits", "nyc_hpd", "chicago_311", "searxng_search"],
    "painting":     ["permits", "chicago_311", "searxng_search"],
    "windows":      ["permits", "chicago_311"],
    "fencing":      ["permits", "chicago_311"],
}


def _ingest_one(c: sqlite3.Connection, lc, niche: str, source_tag: str) -> int:
    """Insert a LeadCandidate into si_buyer_outreach. Returns 1 if inserted, 0 if duplicate."""
    if not lc or not getattr(lc, "name", None):
        return 0
    try:
        name = getattr(lc, "name", "")[:120]
        email = getattr(lc, "email", "") or ""
        email = email[:200]
        metro = getattr(lc, "metro", "") or ""
        state = getattr(lc, "state", "") or ""
        details = getattr(lc, "details", "") or ""
        contact = getattr(lc, "url", "") or ""
        if not metro and state:
            metro = state  # fall back so the funnel can route
        # dedupe on (name, source)
        existing = c.execute(
            "SELECT 1 FROM si_buyer_outreach WHERE business_name=? AND source=? LIMIT 1",
            (name, source_tag),
        ).fetchone()
        if existing:
            return 0
        c.execute(
            "INSERT INTO si_buyer_outreach "
            "(business_name, email, metro, niche, score, url, source, "
            "first_touch_at, last_touch_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (name, email, metro, niche, 0.6, contact,
             source_tag, _now(), _now()),
        )
        return 1
    except Exception as e:
        log.warning("ingest err %s: %s", name[:40], str(e)[:120])
        return 0


def pull_one(niche: str) -> int:
    """Pull from the in-house source stack for one niche.

    Returns # of NEW rows inserted into si_buyer_outreach.
    """
    # pull_one is just pull_one_cap with default cap; delegate.
    return pull_one_cap(niche, cap=CAP, dry_run=DRY_RUN)


def run(dry_run: bool = False, cap: int = CAP) -> dict:
    """Pull across all configured niches. Backward-compatible return shape."""
    stats = {
        "queries": 0, "upserted": 0, "errors": 0,
        # The old scrapecreators_enrich used "credits_left". We don't
        # have a credit budget, but surface a freebie indicator so
        # downstream json consumers don't KeyError.
        "credits_left": "unlimited",
        "provider": "empire_enrich (in-house)",
    }
    eff_dry = dry_run or DRY_RUN
    eff_cap = cap if cap != CAP else CAP  # honor caller's cap if they passed one
    for niche in NICHES:
        stats["queries"] += 1
        try:
            # Per-niche cap (smaller) keeps things bounded
            inserted = pull_one_cap(niche, cap=max(2, eff_cap // len(NICHES)), dry_run=eff_dry)
            stats["upserted"] += inserted
        except Exception as e:
            stats["errors"] += 1
            log.warning("niche %s err: %s", niche, str(e)[:160])
    return stats


def pull_one_cap(niche: str, cap: int, dry_run: bool = False) -> int:
    """Same as pull_one but with an explicit per-call cap. Namespaced so
    callers passing their own cap don't mutate module state."""
    sources = NICHE_SOURCES.get(niche, [])
    inserted = 0
    c = _db()
    try:
        for src_name in sources:
            if inserted >= cap:
                break
            mod = _safe_import_source(src_name)
            if mod is None:
                continue
            try:
                run_fn = getattr(mod, "run", None) or getattr(mod, "_run_nyc", None)
                if run_fn is None:
                    continue
                try:
                    yield_iter = run_fn(metro=None, limit=4)
                except TypeError:
                    try:
                        yield_iter = run_fn()
                    except Exception:
                        continue
                for lc in yield_iter:
                    if inserted >= cap:
                        break
                    try:
                        payload = lc.to_intake_payload()
                    except Exception:
                        payload = {
                            "name": getattr(lc, "name", ""),
                            "email": getattr(lc, "email", ""),
                            "phone": getattr(lc, "phone", ""),
                            "niche": getattr(lc, "niche", niche),
                            "metro": getattr(lc, "metro", ""),
                            "state": getattr(lc, "state", ""),
                            "details": getattr(lc, "details", ""),
                            "source": getattr(lc, "source", src_name),
                            "lead_score": getattr(lc, "lead_score", 50),
                        }
                    if not payload.get("niche"):
                        payload["niche"] = niche
                    class _Obj:
                        pass
                    obj = _Obj()
                    for k, v in payload.items():
                        setattr(obj, k, v)
                    tag = f"empire_enrich/{src_name}"
                    if dry_run:
                        log.info("dry: would insert %s", payload.get("name", "")[:40])
                        inserted += 1
                    else:
                        inserted += _ingest_one(c, obj, niche, tag)
            except Exception as e:
                log.info("%s err: %s", src_name, str(e)[:120])
        c.commit()
    finally:
        c.close()
    return inserted


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--cap", type=int, default=CAP)
    a = ap.parse_args()
    print(json.dumps(run(dry_run=a.dry, cap=a.cap), indent=2))
