"""
Lead Sniper Agent — precision over volume. Finds HIGH-INTENT prospects.

agi-scout = broad net. lead-sniper = rifle scope.

Sniper differs from scout in 3 ways:
  1. **Intent signals only.** Looks for "need a contractor TODAY",
     "looking for emergency plumber", "who do you recommend for..."
     NOT generic posts. Scorer requires urgency keyword + niche fit.
  2. **Faster cycle.** 2 min vs scout's 5 min. Snipers move fast.
  3. **EmpireDB B2B review only.** No outbox or messaging route. Existing
     scoring is a research heuristic, not purchase intent or verified leads.

Data sources (free, public):
  - Legacy Reddit RSS urgency research (explicitly disabled by default)
  - Legacy permit RSS monitoring (explicitly disabled by default)
  - Approved B2B source evidence must be corroborated by Empire Source Intelligence

Scoring (per lead):
  intent_score     = urgency-keyword matches (0..1)
  niche_fit        = synthetic_intelligence.score_niche_fit()
  recency_bonus    = 1.0 if filed in 24h, else 0.5
  sniper_score     = (0.5*intent + 0.3*fit + 0.2*recency)
  Only eligible independently evidenced B2B firms may enter a held review
  proposal at sniper_score >= 0.6; score alone never proves a buyer.

Output:
  /srv/empire_os/runtime/sniper/ — diagnostic log when process runs
  Canonical EmpireDB gateway   — gated human B2B review tasks only
  No outbox, SMTP, customer promotion, or unapproved alert
"""
from __future__ import annotations
import json
import os
import re
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

from empire_os.synthetic_agents import SyntheticAgent
from empire_os.synthetic_intelligence import score_niche_fit
from empire_os.lead_sniper_repository import (
    LeadSniperRepository, review_b2b_sniper_candidate,
)

ROLE_DIR = Path(os.environ.get(
    "SNIPER_FEEDBACK_DIR", "/srv/empire_os/runtime/sniper"
))
SHOTS_LOG = ROLE_DIR / "shots.jsonl"
TICK_INTERVAL = 120  # 2 min — snipers move fast

# High-intent urgency keywords — these are the "buying now" signals
URGENCY_KEYWORDS = [
    "need a", "need an", "need someone", "looking for",
    "emergency", "urgent", "asap", "today", "right now",
    "this weekend", "tomorrow", "quickly", "fast",
    "recommend", "who do you use", "who do you recommend",
    "any good", "anyone know", "hire", "hiring",
    "broken", "leaking", "flooding", "no heat", "no ac",
    "fire damage", "storm damage", "hail damage",
]
# Scoring weights
W_INTENT = 0.5
W_FIT = 0.3
W_RECENCY = 0.2
SNIPER_THRESHOLD = 0.6   # below this, don't queue
KILL_THRESHOLD = 0.8     # above this, alert operator

# ── Guard rails (operator-review mode) ──────────────────────────────────
# Sniper scans research sources only. B2B company evidence must independently
# pass review before EmpireDB can queue any task. Queue disabled by default.
# No si_outbox writes, no auto-email, no founder spam, no consumer targeting.
MAX_PER_CYCLE = int(os.environ.get("SNIPER_MAX_PER_CYCLE", "5"))
DEDUP_HOURS = int(os.environ.get("SNIPER_DEDUP_HOURS", "24"))
REVIEW_TABLE = "empire_tasks"   # Canonical EmpireDB via LeadSniperRepository
_seen_urls = set()              # process-local secondary dedup

def _already_reviewed(url: str, *, repository=None) -> bool:
    """Fail closed if the primary EmpireDB review dedup is unavailable."""
    if not url or url in _seen_urls:
        return True
    try:
        store = repository or LeadSniperRepository.from_environment()
        return store.pending_review_exists(url, dedup_hours=DEDUP_HOURS)
    except Exception:
        return True

RULES_PATH = os.environ.get("SNIPER_RULES", str(Path(__file__).with_name("sniper_rules.md")))

def _load_rules(path: str = RULES_PATH) -> dict:
    """Parse sniper_rules.md into a dict. Falls back to built-ins if missing.
    No LLM. Human-editable. Keys: niches, urgency_keywords, weights,
    thresholds, max_per_cycle, dedup_hours, sources, mode."""
    rules = {
        "niches": ["roofing", "hvac", "plumbing", "electrical",
                   "pest_control", "landscaping", "solar"],
        "urgency_keywords": list(URGENCY_KEYWORDS),
        "w_intent": W_INTENT, "w_fit": W_FIT, "w_recency": W_RECENCY,
        "sniper_threshold": SNIPER_THRESHOLD, "kill_threshold": KILL_THRESHOLD,
        "max_per_cycle": MAX_PER_CYCLE, "dedup_hours": DEDUP_HOURS,
        "sources": {"reddit_urgent": True, "county_permits_urgent": True},
        "mode": "review_only",
    }
    try:
        txt = Path(path).read_text()
        section = None
        for line in txt.splitlines():
            s = line.strip()
            if s.startswith("## "):
                section = s[3:].strip().lower()
                continue
            if not s or s.startswith("#") or ":" not in s:
                continue
            k, v = s.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            if section == "niches to hunt" and k not in ("niches to hunt",):
                pass
            if k == "niches to hunt":
                rules["niches"] = [x.strip() for x in v.split(",") if x.strip()]
            elif k == "urgency keywords":
                rules["urgency_keywords"] = [x.strip() for x in v.split(",") if x.strip()]
            elif k in ("w_intent", "w_fit", "w_recency"):
                rules[k] = float(v)
            elif k in ("sniper_threshold", "kill_threshold"):
                rules[k] = float(v)
            elif k == "max_per_cycle":
                rules["max_per_cycle"] = int(v); globals()["MAX_PER_CYCLE"] = int(v)
            elif k == "dedup_hours":
                rules["dedup_hours"] = int(v); globals()["DEDUP_HOURS"] = int(v)
            elif k in rules["sources"] or k.endswith("_urgent"):
                rules["sources"][k] = (v.lower() in ("on", "true", "1", "yes"))
            elif k == "mode":
                rules["mode"] = v
    except Exception:
        pass  # keep built-ins
    return rules

RULES = _load_rules()

def _queue_review(lead: dict, niche: str, score: float, *, repository=None) -> dict:
    """Canonical EmpireDB review adapter. Never emails or promotes contacts."""
    proposed = review_b2b_sniper_candidate(lead, niche, score)
    if proposed["decision"] != "B2B_REVIEW_PROPOSAL":
        return {"ok": False, "status": "held", "reasons": proposed["reasons"]}
    try:
        store = repository or LeadSniperRepository.from_environment()
        result = store.queue_review(proposed)
        if result.get("status") == "review_queued":
            _seen_urls.add(proposed["url"])
        return result
    except Exception as exc:
        return {"ok": False, "status": "held", "reason": type(exc).__name__}

HERMES_GATEWAY_URL = os.environ.get(
    "HERMES_GATEWAY_URL", "http://10.118.155.156:9100")

# ──────────────────────────────────────────────────────────────────────
# Sniper scopes — one per source
# ──────────────────────────────────────────────────────────────────────

class _BaseScope:
    name = "base"

    def __init__(self):
        self._stats = {"scanned": 0, "hits": 0, "kills": 0,
                       "last_scan_at": None, "last_error": None}

    def scan(self, niche: str) -> list[dict]:
        """Return list of high-intent leads for this niche."""
        raise NotImplementedError

    def _ok(self, scanned: int, hits: int):
        self._stats["scanned"] += scanned
        self._stats["hits"] += hits
        self._stats["last_scan_at"] = datetime.now(timezone.utc).isoformat()

    def _fail(self, err: str):
        self._stats["last_error"] = str(err)[:200]

    @property
    def stats(self) -> dict:
        return dict(self._stats)


class RedditUrgentScope(_BaseScope):
    """Reddit RSS feeds - hunt for 'urgent' posts in niche subs."""
    name = "reddit_urgent"

    SUBREDDITS = {
        "roofing": ["Roofing", "HomeImprovement"],
        "hvac":    ["HVAC", "HomeImprovement"],
        "plumbing":["plumbing", "HomeImprovement"],
        "electrical":["electricians", "HomeImprovement"],
        "pest_control":["pestcontrol", "HomeImprovement"],
        "landscaping":["landscaping", "lawncare"],
    }

    def scan(self, niche: str) -> list[dict]:
        if os.environ.get("EMPIRE_SNIPER_LEGACY_PUBLIC_FETCH_APPROVED") != "1":
            self._fail("legacy_public_source_not_approved")
            return []
        import xml.etree.ElementTree as ET
        from email.utils import parsedate_to_datetime as parse_dt

        subs = self.SUBREDDITS.get(niche, ["HomeImprovement"])
        out = []
        try:
            for sub in subs[:2]:
                url = f"https://old.reddit.com/r/{sub}/new/.rss"
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = resp.read().decode(errors="ignore")
                root = ET.fromstring(body)
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                entries = root.findall("atom:entry", ns) or []
                for entry in entries:
                    title_el = entry.find("atom:title", ns)
                    title = (title_el.text or "").strip() if title_el is not None else ""
                    author_el = entry.find("atom:author/atom:name", ns)
                    author = author_el.text.strip() if author_el is not None and author_el.text else ""
                    link_el = entry.find("atom:link", ns)
                    url_perma = link_el.get("href", "") if link_el is not None else ""
                    updated_el = entry.find("atom:updated", ns)
                    updated = updated_el.text.strip() if updated_el is not None and updated_el.text else ""
                    content_el = entry.find("atom:content", ns)
                    content_text = ""
                    if content_el is not None and content_el.text:
                        content_text = re.sub(r"<[^>]+>", " ", content_el.text)

                    # Check urgency keywords in title+content
                    blob = (title + " " + content_text).lower()
                    hits = [k for k in URGENCY_KEYWORDS if k in blob]
                    if not hits:
                        continue

                    # Recency
                    age_h = 999
                    if updated:
                        try:
                            dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                            age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                        except Exception:
                            try:
                                dt = parse_dt(updated)
                                age_h = (datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc)).total_seconds() / 3600
                            except Exception:
                                pass
                    if age_h > 72:
                        continue

                    out.append({
                        "source": f"reddit:r/{sub}",
                        "niche": niche,
                        "name": author,
                        "phone": "",
                        "details": {
                            "title": title[:200],
                            "url": url_perma,
                            "intent_keywords_hit": hits[:5],
                            "age_hours": round(age_h, 1),
                            "score": 0,
                        },
                    })
            self._ok(scanned=len(entries), hits=len(out))
        except Exception as e:
            self._fail(str(e))
        return out


class CountyPermitsUrgentScope(_BaseScope):
    """County permit RSS — high recency = high intent."""
    name = "county_permits_urgent"

    FEEDS = [
        "https://www.maricopa.gov/5739/RSS-Feeds",
        "https://www.traviscountytx.gov/news/rss.xml",
    ]
    NICHE_KW = {
        "roofing":    ["roof", "reroof", "shingle"],
        "hvac":       ["hvac", "furnace", "ac unit", "air condition"],
        "plumbing":   ["plumb", "water heater", "drain"],
        "electrical": ["electric", "panel", "wiring"],
        "solar":      ["solar", "pv"],
    }

    def scan(self, niche: str) -> list[dict]:
        if os.environ.get("EMPIRE_SNIPER_LEGACY_PUBLIC_FETCH_APPROVED") != "1":
            self._fail("legacy_public_source_not_approved")
            return []
        kws = self.NICHE_KW.get(niche, [niche])
        out = []
        try:
            for feed_url in self.FEEDS[:2]:
                try:
                    req = urllib.request.Request(
                        feed_url, headers={"User-Agent": "EmpireOS-sniper/1.0"})
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        body = resp.read().decode(errors="ignore")
                except Exception:
                    continue
                # Cheap RSS parse: <item> chunks
                for chunk in body.split("<item")[1:]:
                    title = ""
                    pub = ""
                    i = chunk.find("<title>")
                    if i >= 0:
                        j = chunk.find("</title>", i)
                        if j > i:
                            title = chunk[i + 7:j].strip()
                    p = chunk.find("<pubDate>")
                    if p >= 0:
                        pj = chunk.find("</pubDate>", p)
                        if pj > p:
                            pub = chunk[p + 9:pj].strip()
                    if not title or not any(k in title.lower() for k in kws):
                        continue
                    # Recency
                    age_h = 999
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(pub)
                        age_h = (datetime.now(timezone.utc)
                                 - dt.replace(tzinfo=timezone.utc)
                                 ).total_seconds() / 3600
                    except Exception:
                        pass
                    if age_h > 72:
                        continue
                    out.append({
                        "source": f"permits:{feed_url.split('/')[2]}",
                        "niche": niche,
                        "name": title[:80],
                        "phone": "",
                        "details": {
                            "title": title,
                            "feed": feed_url,
                            "age_hours": round(age_h, 1),
                            "published": pub,
                        },
                    })
                if out:
                    break
            self._ok(scanned=1, hits=len(out))
        except Exception as e:
            self._fail(str(e))
        return out


# ──────────────────────────────────────────────────────────────────────
# Lead Sniper Agent
# ──────────────────────────────────────────────────────────────────────

class LeadSniperAgent(SyntheticAgent):
    """Rule-based scanner with gated canonical B2B human-review endpoint."""

    NICHES = ["roofing", "hvac", "plumbing", "electrical",
              "pest_control", "landscaping", "solar"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.scopes = {
            "reddit_urgent": RedditUrgentScope(),
            "county_permits_urgent": CountyPermitsUrgentScope(),
        }
        self._cycle_kills = 0

    def _score(self, lead: dict, niche: str) -> float:
        """Compute sniper score (0..1) for one lead."""
        details = lead.get("details", {})
        text = json.dumps(details).lower()
        # Intent score
        hits = sum(1 for kw in URGENCY_KEYWORDS if kw in text)
        intent = min(1.0, hits / 3.0)
        # Niche fit
        fit = score_niche_fit(lead, niche)
        # Recency bonus
        age = details.get("age_hours", 999)
        if age <= 24:
            recency = 1.0
        elif age <= 48:
            recency = 0.7
        elif age <= 72:
            recency = 0.5
        else:
            recency = 0.2
        return W_INTENT * intent + W_FIT * fit + W_RECENCY * recency

    def _emit_kill_alert(self, lead: dict, niche: str, score: float):
        try:
            import requests
            requests.post(
                f"{HERMES_GATEWAY_URL}/v1/notify/alert",
                json={
                    "title": f"🔫 Sniper KILL [{score:.2f}] {niche}",
                    "body": (f"source={lead['source']}\n"
                             f"details={json.dumps(lead.get('details',{}), default=str)[:600]}"),
                    "severity": "high",
                    "source": "lead-sniper-agent",
                },
                timeout=5)
        except Exception:
            pass

    def observe(self) -> dict:
        # What scopes are healthy? Pick which niche to scan next.
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "scope_health": {n: s.stats for n, s in self.scopes.items()},
            "niches": self.NICHES,
            "cycle_kills": self._cycle_kills,
        }

    def reason(self, state: dict) -> str:
        # Pick the niche with the least fresh activity (heuristic —
        # sniper rewards freshness, so starved niches deserve the shot)
        niche = self.NICHES[self.context.cycle % len(self.NICHES)]
        return json.dumps({
            "action": "snipe",
            "niche": niche,
            "reasoning": f"cycle {self.context.cycle}: scanning {niche}",
        })

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except Exception:
            return {"summary": "decision parse failed"}
        if d.get("action") != "snipe":
            return {"summary": "idle"}
        niche = d.get("niche", self.NICHES[0])

        # Fire all scopes at this niche
        all_leads = []
        for scope in self.scopes.values():
            try:
                all_leads.extend(scope.scan(niche))
            except Exception:
                continue

        # Score + route (review-only — no auto-email)
        shots = []
        kills = []
        self._cycle_kills = 0
        queued_this_cycle = 0
        for lead in all_leads:
            score = self._score(lead, niche)
            shot = {"niche": niche, "source": lead["source"],
                    "score": round(score, 3),
                    "title": lead.get("details", {}).get("title", "")[:80]}
            if score < SNIPER_THRESHOLD:
                shots.append({**shot, "decision": "skip"})
                continue
            # A high score is only a research heuristic, not a successful
            # commercial outcome, so track accepted review queues separately.
            # guard rail: cap reviews per cycle
            if queued_this_cycle >= MAX_PER_CYCLE:
                shots.append({**shot, "decision": "cap_reached"})
                continue
            post = _queue_review(lead, niche, score)
            shots.append({**shot, "decision": post.get("status", "queue"), "post": post})
            if post.get("status") == "review_queued":
                queued_this_cycle += 1
                if score >= KILL_THRESHOLD:
                    kills.append(shot)
                    self._cycle_kills += 1
            if (post.get("status") == "review_queued"
                    and score >= KILL_THRESHOLD
                    and os.environ.get("EMPIRE_SNIPER_ALERTS_APPROVED") == "1"):
                self._emit_kill_alert(lead, niche, score)

        # Log
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "cycle": self.context.cycle,
            "niche": niche,
            "n_scanned": len(all_leads),
            "n_queued": sum(1 for s in shots if s.get("decision") == "review_queued"),
            "n_kills": len(kills),
            "shots": shots,
            "scope_health": {n: s.stats for n, s in self.scopes.items()},
        }
        try:
            SHOTS_LOG.parent.mkdir(parents=True, exist_ok=True)
            with SHOTS_LOG.open("a") as f:
                f.write(json.dumps(record) + "\n")
        except OSError:
            # Diagnostics may fail without granting a network or DB fallback.
            pass
        return {
            "summary": (f"{niche}: {len(all_leads)} targets, "
                        f"{record['n_queued']} queued, "
                        f"{record['n_kills']} KILLS"),
            "n_queued": record["n_queued"],
            "n_kills": record["n_kills"],
        }

    def tick(self) -> dict:
        """Ollama-free tick: observe -> reason -> act only.
        Base SyntheticAgent.tick() also runs an LLM 'learn' step that
        503s now Ollama is removed; override to skip it."""
        self.context.cycle += 1
        state = self.observe()
        decision = self.reason(state)
        return self.act(decision)


if __name__ == "__main__":
    agent = LeadSniperAgent(
        name="lead-sniper-agent",
        role="lead_sniper",
        health_url="http://localhost:9109/health",
    )
    print(f"[{datetime.now(timezone.utc).isoformat()}] "
          f"lead-sniper online — tick {TICK_INTERVAL}s", flush=True)
    failures = 0
    while True:
        try:
            r = agent.tick()
            failures = 0
            print(json.dumps({"cycle": r.get("cycle"),
                              "summary": r.get("result", {}).get(
                                  "summary", "")}))
        except Exception as e:
            failures += 1
            backoff = min(20 * failures, 120)
            print(json.dumps({"error": str(e)[:200], "backoff": backoff}))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)
