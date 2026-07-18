"""
buyer_hunter_agent — SEPARATE buyer-acquisition engine.

Distinct from lead_sniper (which finds HOMEOWNERS / leads to sell).
This agent FINDS BUSINESSES that BUY leads, scores them for USDC-settlement
fit, and registers them as cold prospects in the outreach pipeline
(si_buyer_outreach via hub /v1/outreach/prospect/register).

Sources (no paid API required, proxy-bypassed):
  - Curated industry directory pages (association member lists, niche
    business directories) per lane vertical + metro.
  - Public web search for "<vertical> contractors <metro>" via a search
    endpoint (DuckDuckGo HTML, proxy-bypassed).
  - Repurpose existing permit/license data to find CONTRACTOR businesses.

It does NOT send email — outreach_runner does that (repitched to USDC).
It only DISCOVERS + REGISTERS. Idempotent: skips known prospect_ids.
"""
from __future__ import annotations
import os, re, time, json, requests
from datetime import datetime, timezone
from pathlib import Path

# Sovereign topology: bypass dead Privoxy/Tor proxy for all outbound.
_http = requests.Session()
_http.trust_env = False

HUB_URL = os.environ.get("HUB_URL", "http://127.0.0.1:8000")
LOG_PATH = Path("/root/feedback/buyer_hunter.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# Lane verticals we sell into (buyers of these leads)
VERTICALS = ["roofing", "solar", "mortgage", "insurance", "debt_relief",
             "tax_prep", "investing", "hvac", "fencing", "bathroom_remodel"]
METROS = ["NYC", "LAX", "CHI", "DFW", "SEA", "BOS", "WDC", "PHX", "ATL", "MIA"]
# Crypto-native fit bonus (verticals whose buyers often hold USDC)
CRYPTO_FRIENDLY = {"solar", "investing", "debt_relief", "tax_prep", "crypto"}

# B2B product hunting: businesses that buy our SOFTWARE/SaaS SKUs (not leads)
# Each target type maps to the SKUs it should be pitched.
B2B_TARGETS = [
    {"type": "logistics", "skus": ["satellite_idle_watch", "warehouse_asset"],
     "queries": ["logistics company {m}", "freight broker {m}", "fleet management {m}"]},
    {"type": "warehouse", "skus": ["warehouse_asset", "satellite_idle_watch"],
     "queries": ["warehouse 3pl {m}", "fulfillment center {m}", "cold storage {m}"]},
    {"type": "ai_team", "skus": ["skillspector_audit", "hermes_framework"],
     "queries": ["ai automation agency {m}", "llm consulting {m}", "ml ops company {m}"]},
    {"type": "marketing_agency", "skus": ["opencut_studio", "marketingskills", "empire_templates"],
     "queries": ["video production agency {m}", "marketing agency {m}", "content studio {m}"]},
    {"type": "agency", "skus": ["empire_leads_engine", "empire_templates"],
     "queries": ["digital agency {m}", "lead generation company {m}", "growth agency {m}"]},
]
B2B_METROS = ["NYC", "LAX", "DFW", "CHI", "ATL", "SEA", "PHX", "MIA"]
INTERVAL_SECONDS = int(os.environ.get("HUNTER_INTERVAL", "1800"))
CYCLE_LIMIT = int(os.environ.get("HUNTER_LIMIT", "40"))


def hunt_b2b_internal(limit: int = 20) -> int:
    """Fallback: mine existing si_buyer_outreach for B2B-fit businesses
    (agencies / logistics / warehouse in name) and tag SKU interests.
    Real data already in our DB — no external dependency."""
    import sqlite3
    _log("INFO", "hunt_b2b_internal_start")
    found = 0
    try:
        db = os.environ.get("EMPIRE_DB_PATH", "/root/empire_os/empire_os.db")
        cnx = sqlite3.connect(db, timeout=10)
        # keyword -> skus mapping
        kw_map = [
            ("logistics", ["satellite_idle_watch", "warehouse_asset"]),
            ("freight", ["satellite_idle_watch", "warehouse_asset"]),
            ("warehouse", ["warehouse_asset", "satellite_idle_watch"]),
            ("fulfillment", ["warehouse_asset"]),
            ("3pl", ["warehouse_asset", "satellite_idle_watch"]),
            ("agency", ["empire_leads_engine", "empire_templates", "opencut_studio"]),
            ("marketing", ["opencut_studio", "marketingskills", "empire_templates"]),
            ("ai ", ["skillspector_audit", "hermes_framework"]),
            ("automation", ["skillspector_audit", "hermes_framework"]),
            ("video", ["opencut_studio", "marketingskills"]),
        ]
        for kw, skus in kw_map:
            if found >= limit:
                break
            rows = cnx.execute(
                "SELECT prospect_id, business_name, metro, niche FROM si_buyer_outreach "
                "WHERE (lower(business_name) LIKE ? OR lower(niche) LIKE ?) "
                "AND source != 'buyer_hunter_b2b' LIMIT ?",
                (f"%{kw}%", f"%{kw}%", limit - found)).fetchall()
            for pid, name, metro, niche in rows:
                np_ = f"b2b_int_{pid}"
                p = {
                    "prospect_id": np_,
                    "business_name": name or pid,
                    "email": "",
                    "metro": metro or "",
                    "niche": "b2b",
                    "phone": "",
                    "url": "skus:" + ",".join(skus),
                    "source": "buyer_hunter_b2b",
                    "score": 80,
                    "usdc_fit": True,
                }
                if register_prospect(p):
                    found += 1
        cnx.close()
    except Exception as e:
        _log("ERROR", "b2b_internal_fail", error=str(e)[:160])
    _log("INFO", "hunt_b2b_internal_done", registered=found)
    return found


def hunt_b2b_external(limit: int = None) -> int:
    """External web discovery of B2B buyers per B2B_TARGETS (logistics,
    warehouse, ai_team, marketing_agency, agency) across metros."""
    _log("INFO", "hunt_b2b_external_start")
    found = 0
    cap = limit or CYCLE_LIMIT
    for tgt in B2B_TARGETS:
        if found >= cap:
            break
        for metro in B2B_METROS:
            if found >= cap:
                break
            for q_tmpl in tgt["queries"]:
                if found >= cap:
                    break
                q = q_tmpl.format(m=metro)
                hits = search_businesses(q, limit=3)
                for h in hits:
                    dom = re.sub(r"[^a-z0-9]", "", h["domain"].lower())
                    pid = f"b2b_{tgt['type']}_{metro}_{dom}"
                    p = {
                        "prospect_id": pid,
                        "business_name": h["title"] or h["domain"],
                        "email": "",
                        "metro": metro,
                        "niche": "b2b",
                        "phone": "",
                        "url": "skus:" + ",".join(tgt["skus"]),
                        "source": "buyer_hunter_b2b",
                        "score": 86,
                        "usdc_fit": True,
                    }
                    if register_prospect(p):
                        found += 1
                        _log("FOUND_B2B", "prospect", pid=pid, type=tgt["type"],
                             metro=metro, skus=tgt["skus"])
                time.sleep(1.0)
    _log("INFO", "hunt_b2b_external_done", registered=found)
    return found


def hunt_b2b_cycle(limit: int = None) -> int:
    """Discover B2B buyers for the software/MRR SKU suite.
    Tries external search first; falls back to mining existing pipeline."""
    cap = limit or CYCLE_LIMIT
    ext = 0
    try:
        ext = hunt_b2b_external(cap)
    except Exception as e:
        _log("ERROR", "b2b_external_fail", error=str(e)[:160])
    if ext < cap:
        try:
            hunt_b2b_internal(cap - ext)
        except Exception as e:
            _log("ERROR", "b2b_internal_wrap", error=str(e)[:160])
    return ext


def _log(level, msg, **fields):
    ev = {"ts": datetime.now(timezone.utc).isoformat(), "level": level,
          "msg": msg, **fields}
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(ev) + "\n")
    print(json.dumps(ev), flush=True)


def register_prospect(p: dict) -> bool:
    try:
        r = _http.post(f"{HUB_URL}/v1/outreach/prospect/register", json=p,
                       timeout=10)
        return r.status_code < 300 and r.json().get("ok", False)
    except Exception as e:
        _log("ERROR", "register_failed", error=str(e)[:160])
        return False


def search_businesses(query: str, limit: int = 8) -> list[dict]:
    """Cheap public discovery via a reachable search engine (Bing HTML)."""
    out = []
    engines = [
        ("https://www.google.com/search", {"q": query, "num": str(limit)}),
        ("https://www.bing.com/search", {"q": query}),
    ]
    for url, params in engines:
        try:
            r = _http.get(url, params=params, timeout=12,
                          headers={"User-Agent": "Mozilla/5.0 (compatible; EmpireOS/1.0)"})
            if r.status_code != 200:
                continue
            # Bing: <h2><a href="url">title</a>  |  Google: /url?q= redirect or direct
            for m in re.finditer(
                r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', r.text, re.S):
                href, title = m.group(1), re.sub("<.*?>", "", m.group(2))
                # decode google redirect wrapper
                gm = re.search(r"[?&]q=(https?://[^&]+)", href)
                if gm:
                    href = requests.utils.unquote(gm.group(1))
                if not href.startswith("http"):
                    continue
                dom = re.sub(r"https?://", "", href).split("/")[0]
                if any(x in dom for x in ("bing", "microsoft", "wikipedia",
                                          "youtube", "facebook", "instagram",
                                          "yelp", "linkedin", "google", "gstatic")):
                    continue
                title_clean = title.strip()[:60]
                if not title_clean:
                    continue
                out.append({"title": title_clean, "url": href, "domain": dom})
                if len(out) >= limit:
                    return out
            if out:
                return out
        except Exception as e:
            _log("ERROR", "search_fail", engine=url, q=query, error=str(e)[:120])
    return out


# Backwards-compatible alias (old name still referenced by hunt_cycle)
ddg_businesses = search_businesses


def hunt_cycle():
    _log("INFO", "hunt_start")
    found = 0
    for vertical in VERTICALS:
        if found >= CYCLE_LIMIT:
            break
        crypto_fit = vertical in CRYPTO_FRIENDLY
        for metro in METROS:
            if found >= CYCLE_LIMIT:
                break
            q = f"{vertical} contractors {metro} leads"
            hits = ddg_businesses(q, limit=4)
            for h in hits:
                pid = f"hunt_{vertical}_{metro}_{re.sub(r'[^a-z0-9]', '', h['domain'].lower())}"
                p = {
                    "prospect_id": pid,
                    "business_name": h["title"] or h["domain"],
                    "email": "",
                    "metro": metro,
                    "niche": vertical,
                    "phone": "",
                    "url": h["url"],
                    "source": "buyer_hunter",
                    "score": 82 if crypto_fit else 70,
                    "usdc_fit": crypto_fit,
                }
                if register_prospect(p):
                    found += 1
                    _log("FOUND", "prospect", pid=pid, vertical=vertical,
                         metro=metro, crypto_fit=crypto_fit)
            time.sleep(1.5)
    _log("INFO", "hunt_done", registered=found)
    return found


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] buyer_hunter starting "
          f"- interval {INTERVAL_SECONDS}s, limit {CYCLE_LIMIT}", flush=True)
    while True:
        try:
            hunt_cycle()           # lead-lane buyers (contractors)
            hunt_b2b_cycle()       # B2B software/MRR SKU buyers
        except Exception as e:
            _log("ERROR", "cycle_exception", error=str(e)[:200])
        time.sleep(INTERVAL_SECONDS)
