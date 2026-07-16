#!/usr/bin/env python3
"""Empire OS v3 — Idle-Asset / Waste / Logistics Sniper.

Detects business opportunities from idle assets, waste leakage, and
logistics wastage. Data-feed driven (NO satellite imagery needed, NO LLM).
Mirrors lead_sniper's guard-rail pattern.

Scope (what it hunts):
  - idle trucks / equipment (parking lots, freight downtime)
  - waste leakage (dumping, spill, illegal disposal signals)
  - logistics wastage (empty warehouses, disused distribution centers,
    abandoned cold storage)

Guard rails (same as lead_sniper — operator-review mode):
  - FIND ONLY. Never auto-emails. Finds -> empire_tasks
    (task_type='idle_asset_review') for human promotion.
  - NO si_outbox writes. NO spam.
  - Rule-based scoring from idle_asset_rules.md (no Ollama/MiniMax).
  - Dedup + per-cycle cap + KILL alert at high score.

Runs as a daemon via supervisor_daemon.py (empire-agent-idle_asset).
"""
import os, json, time, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone

# ── paths / config ────────────────────────────────────────────────────────
AGENT_HOME = Path(os.environ.get("AGENT_HOME", "/root/empire_os/empire_os/agents"))
ROLE_DIR = AGENT_HOME / "feedback" / "idle_asset"
ROLE_DIR.mkdir(parents=True, exist_ok=True)
SHOTS_LOG = ROLE_DIR / "shots.jsonl"
TICK_INTERVAL = int(os.environ.get("IDLE_TICK", "180"))  # 3 min

# Guard rails
MAX_PER_CYCLE = int(os.environ.get("IDLE_MAX_PER_CYCLE", "5"))
DEDUP_HOURS = int(os.environ.get("IDLE_DEDUP_HOURS", "24"))
REVIEW_TABLE = "empire_tasks"   # Supabase; task_type='idle_asset_review'
_seen_urls = set()

# Scoring weights
W_INTENT = 0.5
W_FIT = 0.3
W_RECENCY = 0.2
KILL_THRESHOLD = 0.8

# Signal keywords -> opportunity type
SIGNAL_KEYWORDS = {
    "idle_truck": ["idle truck", "parked truck", "truck depot empty", "fleet idle",
                   "equipment idle", "machinery unused", "idle equipment"],
    "waste_leakage": ["waste leak", "illegal dumping", "spill", "leakage",
                      "contaminated", "hazardous waste", "dump site"],
    "logistics_waste": ["empty warehouse", "vacant warehouse", "abandoned storage",
                        "disused logistics", "idle distribution", "cold storage empty",
                        "abandoned cold storage", "vacant industrial"],
}

# Data-feed sources (public RSS — free, no API key)
FEEDS = [
    ("travis_county_permits", "https://www.traviscountytx.gov/news/rss.xml"),
    ("austin_permits", "https://www.austintexas.gov/feed/permits"),
    ("logistics_rss", "https://www.freightwaves.com/news/feed"),
]


def _load_rules(path=None):
    """Parse idle_asset_rules.md (optional, human-editable). Falls back inline."""
    path = path or os.environ.get(
        "IDLE_RULES", str(AGENT_HOME / "idle_asset_rules.md"))
    rules = {"max_per_cycle": MAX_PER_CYCLE, "dedup_hours": DEDUP_HOURS,
             "kill_threshold": KILL_THRESHOLD}
    try:
        for line in Path(path).read_text().splitlines():
            s = line.strip()
            if s.startswith("#") or ":" not in s:
                continue
            k, v = s.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            if k == "max_per_cycle":
                rules["max_per_cycle"] = int(v)
            elif k == "dedup_hours":
                rules["dedup_hours"] = int(v)
            elif k == "kill_threshold":
                rules["kill_threshold"] = float(v)
    except Exception:
        pass
    return rules


RULES = _load_rules()

# ── Supabase (PostgREST) ────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL",
    "https://owbeinlfcfdtwcwrttjy.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
_HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"}


def _sb_insert(table, row):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}", data=json.dumps(row).encode(),
        headers=_HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _already_reviewed(url):
    if not url or url in _seen_urls:
        return True
    try:
        q = (f"{SUPABASE_URL}/rest/v1/{REVIEW_TABLE}?"
             f"task_type=eq.idle_asset_review&status=eq.pending"
             f"&payload->>url=eq.{urllib.parse.quote(url, safe='')}")
        req = urllib.request.Request(q, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            return len(json.loads(r.read())) > 0
    except Exception:
        return False


def _queue_review(asset, asset_type, score):
    """Route an idle-asset find to the human-review queue. Never emails."""
    url = asset.get("url", "")
    if _already_reviewed(url):
        return {"status": "dup"}
    try:
        row = {
            "task_type": "idle_asset_review",
            "status": "pending",
            "payload": {
                "asset_type": asset_type,
                "title": asset.get("title", "")[:200],
                "url": url,
                "source": asset.get("source", ""),
                "score": round(score, 3),
                "detected_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        _sb_insert(REVIEW_TABLE, row)
        _seen_urls.add(url)
        return {"status": "review_queued"}
    except Exception as e:
        return {"status": "error", "error": str(e)[:160]}


def _score(asset):
    """Rule-based opportunity score 0..1 (no LLM)."""
    text = (asset.get("title", "") + " " + asset.get("source", "")).lower()
    intent = 0.0
    hit_type = None
    for atype, kws in SIGNAL_KEYWORDS.items():
        hits = sum(1 for k in kws if k in text)
        if hits:
            intent = max(intent, min(1.0, hits / 3.0))
            hit_type = atype
    # generic idle/waste words also signal opportunity
    generic = ["abandon", "disus", "idle", "vacant", "empty", "leak",
               "dump", "waste", "unused", "disused"]
    if any(w in text for w in generic):
        intent = max(intent, 0.7)
        if not hit_type:
            hit_type = ("waste_leakage" if any(w in text for w in
                        ["leak", "dump", "waste", "spill"]) else "logistics_waste")
    # recency: RSS items / enriched assets are recent by nature
    recency = 0.7
    # fit: known idle-asset industries score higher
    fit = 0.6 if any(w in text for w in
                     ["warehouse", "storage", "logistics", "industrial",
                      "truck", "freight", "distribution"]) else 0.3
    score = W_INTENT * intent + W_FIT * fit + W_RECENCY * recency
    return score, hit_type or "logistics_waste"


# ── Scopes (data feeds) ─────────────────────────────────────────────────────
def _scan_feed(name, url):
    """Fetch an RSS feed, extract idle/waste/logistics signals."""
    out = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EmpireOS-idle/1.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            xml = r.read()
        root = ET.fromstring(xml)
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title:
                continue
            tl = title.lower()
            if any(k in tl for kws in SIGNAL_KEYWORDS.values() for k in kws) or \
               any(w in tl for w in ["abandon", "disus", "idle", "vacant",
                                     "empty", "leak", "dump", "waste"]):
                out.append({"title": title, "url": link or url,
                            "source": f"feed:{name}"})
    except Exception:
        pass
    return out


# ── Tick ─────────────────────────────────────────────────────────────────────
def tick():
    queued = 0
    kills = 0
    all_assets = []
    for name, url in FEEDS:
        all_assets.extend(_scan_feed(name, url))
    # also pull existing enriched idle assets (real data) as candidates
    try:
        q = (f"{SUPABASE_URL}/rest/v1/idle_asset_enriched?"
             f"select=compound_id,business_name,industry,lead_gen_score"
             f"&lead_gen_score=gte.0.6&limit=20")
        req = urllib.request.Request(q, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=12) as r:
            for row in json.loads(r.read()):
                all_assets.append({
                    "title": f"{row.get('business_name','')} ({row.get('industry','')})",
                    "url": f"enriched:{row.get('compound_id','')}",
                    "source": "idle_asset_enriched",
                })
    except Exception:
        pass

    for asset in all_assets:
        if queued >= RULES["max_per_cycle"]:
            break
        score, atype = _score(asset)
        if score < 0.5:
            continue
        post = _queue_review(asset, atype, score)
        if post.get("status") == "review_queued":
            queued += 1
            if score >= RULES["kill_threshold"]:
                kills += 1
    return {"scanned": len(all_assets), "queued": queued, "kills": kills}


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] idle-asset sniper online — tick {TICK_INTERVAL}s")
    while True:
        try:
            r = tick()
            print(f"[{datetime.now(timezone.utc).isoformat()}] "
                  f"scanned={r['scanned']} queued={r['queued']} kills={r['kills']}")
        except Exception as e:
            print(f"ERROR: {e}")
        time.sleep(TICK_INTERVAL)
