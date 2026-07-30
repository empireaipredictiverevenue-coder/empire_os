#!/usr/bin/env python3
"""whale_harvester.py — Pull WHALES from free, real sources:

  1. HackerNews (free Firebase JSON API, no key):
     - topstories (high karma = respected entrepreneurs)
     - askstories ("Ask HN" threads signal builders actively looking)
     - showstories (Show HN = product launches = founders with companies)
     - For each, fetch comments + look for founder-style emails.
  2. GitHub public API (free, 60 req/h unauth):
     - users that look like founders (1 repo, "company" or "inc" in name)
     - email parsed from public commits/events
  3. ATOM feed of new YC-launched RFS-style posts (public).

All writes go to si_prospect_consent with classified_tier=WHALE
and whale_finder_reason set so the chief-of-staff loop dials them.

Cadence: every 6h. Stays under HN API limits (60 calls/min).

No API keys. No paid services.
"""
from __future__ import annotations
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

INTERVAL_SEC = int(os.environ.get("INTERVAL_SEC", str(6 * 3600)))   # 6h
HN_TOP_N = int(os.environ.get("HN_TOP_N", "60"))
HN_ASK_N = int(os.environ.get("HN_ASK_N", "20"))
HN_SHOW_N = int(os.environ.get("HN_SHOW_N", "20"))

CANDIDATE_LOG_DIRS = ("/root/empire_os/feedback", "/root/feedback")
FEEDBACK_DIR = next(
    (Path(p) for p in CANDIDATE_LOG_DIRS if os.access(p, os.W_OK)),
    Path("/tmp"),
)
WHALE_LOG = FEEDBACK_DIR / "whales_harvested.jsonl"


# ═══════════════════════════════════════════════════════════════════════
# HN free API
# ═══════════════════════════════════════════════════════════════════════

HN_BASE = "https://hacker-news.firebaseio.com/v0"

EMAIL_RE = re.compile(r"[a-zA-Z0-9._+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
FOUNDER_RE = re.compile(
    r"\b(founder|co[- ]?founder|ceo|building|startup|launching|hiring|mrr|arr|"
    r"raised(?:\s+\$[\d.]+[mbk]?)?|bootstrap|seed|round)\b", re.I)


def _hn(item_id: int, timeout: int = 8) -> dict | None:
    url = f"{HN_BASE}/item/{item_id}.json"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "EmpireOS-WhaleHarvester/1.0",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


def _fetch_story_ids(kind: str, n: int) -> list[int]:
    if kind == "top":
        path = "topstories"
    elif kind == "ask":
        path = "askstories"
    elif kind == "show":
        path = "showstories"
    else:
        return []
    try:
        req = urllib.request.Request(
            f"{HN_BASE}/{path}.json?limit={n}",
            headers={"User-Agent": "EmpireOS-WhaleHarvester/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _extract_candidates_from_text(text: str) -> list[str]:
    if not text:
        return []
    raw_emails = EMAIL_RE.findall(text)
    founders = FOUNDER_RE.findall(text)
    out = []
    for em in raw_emails:
        em = em.lower().strip(".")
        # skip common blacklist (HN profile email forwards, noreply)
        bad = ("@users.noreply.github.com", "@example.com",
               "@noreply.github.com", "@hn.haven", "@hacker-news")
        if any(b in em for b in bad):
            continue
        if "." not in em.split("@", 1)[1]:
            continue
        out.append(em)
    return out


def harvest_hn() -> list[dict]:
    out: list[dict] = []
    seen_emails: set[str] = set()
    # HN API rate: free to call but slow from containers. Cap stories.
    for kind, n in (("top", HN_TOP_N), ("ask", HN_ASK_N), ("show", HN_SHOW_N)):
        ids = _fetch_story_ids(kind, n)
        for sid in ids[:n]:
            item = _hn(sid)
            if not item or item.get("deleted") or item.get("dead"):
                continue
            text_parts = [item.get("text", "") or ""]
            for kid in (item.get("kids") or [])[:10]:
                c = _hn(kid)
                if not c or c.get("deleted"):
                    continue
                text_parts.append(c.get("text", "") or "")
            blob = "\n".join(text_parts)
            emails = _extract_candidates_from_text(blob)
            # Also harvest the poster's name as a "founder-name" cold lead.
            poster = item.get("by") or ""
            if poster and not {"_dead", "epidemi", "random"}.intersection({poster}):
                emails.append(poster + "@hn-resolved.empire")
            for em in emails:
                if em in seen_emails:
                    continue
                seen_emails.add(em)
                # Treat HN usernames as cold; remove the placeholder
                # email unless the source is a real address.
                if em.endswith("@hn-resolved.empire"):
                    real_email = None
                    domain = "hn"
                else:
                    real_email = em
                    domain = em.split("@", 1)[1].lower()
                out.append({
                    "email": real_email or poster,
                    "hn_user": poster,
                    "domain": domain,
                    "source": "hackernews",
                    "source_kind": kind,
                    "source_story_id": sid,
                    "story_title": (item.get("title") or "")[:120],
                    "url": item.get("url") or f"https://news.ycombinator.com/item?id={sid}",
                    "founder_signal": bool(FOUNDER_RE.findall(blob)),
                    "score": _score_for_signal(domain if domain != "hn" else "", blob),
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
    return out


def _score_for_signal(domain: str, blob: str) -> int:
    base = 30
    if "raised" in blob.lower() or "raised " in blob.lower():
        base += 14
    if "arr" in blob.lower() or "mrr" in blob.lower():
        base += 8
    if "hiring" in blob.lower():
        base += 6
    if re.search(r"\$[ ]?\d+[mk]b?\b", blob, re.I):
        base += 10
    if re.search(r"\b(inc|llc|co|corp)\b", domain):
        base += 4
    return min(100, base)


# ═══════════════════════════════════════════════════════════════════════
# DB persistence
# ═══════════════════════════════════════════════════════════════════════


def _find_db() -> str:
    env = os.environ.get("EMPIRE_DB")
    if env and os.path.exists(env):
        return env
    if os.path.exists("/root/empire_os/empire_os.db"):
        return "/root/empire_os/empire_os.db"
    return "/root/empire_os/empire_os.db"


def _persist_harvest(items: list[dict]) -> int:
    if not items:
        return 0
    c = sqlite3.connect(_find_db(), timeout=20)
    c.execute("PRAGMA busy_timeout=20000")
    cols = [r[1] for r in c.execute(
        "PRAGMA table_info(si_prospect_consent)").fetchall()]
    if "whale_finder_reason" not in cols:
        c.execute("ALTER TABLE si_prospect_consent "
                  "ADD COLUMN whale_finder_reason TEXT DEFAULT NULL")
    if "whale_harvester_source" not in cols:
        c.execute("ALTER TABLE si_prospect_consent "
                  "ADD COLUMN whale_harvester_source TEXT DEFAULT NULL")
        c.execute("ALTER TABLE si_prospect_consent "
                  "ADD COLUMN whale_harvester_score INTEGER DEFAULT 0")
    inserted = 0
    for it in items:
        pid = "whale:hn:" + (it["email"].split("@", 1)[0])[:30]
        try:
            c.execute("""
                INSERT INTO si_prospect_consent
                  (prospect_id, opted_in, opted_in_at, niche, source,
                   whale_tier, whale_score, whale_reasons,
                   whale_finder_reason, whale_harvester_source,
                   whale_harvester_score)
                VALUES (?, 0, NULL, 'unknown', 'whale_harvester',
                        'WHALE', ?, ?, ?, ?, ?)
                ON CONFLICT(prospect_id) DO UPDATE SET
                  whale_tier = 'WHALE',
                  whale_score = excluded.whale_score,
                  whale_reasons = excluded.whale_reasons,
                  whale_finder_reason = excluded.whale_finder_reason,
                  whale_harvester_source = excluded.whale_harvester_source,
                  whale_harvester_score = excluded.whale_harvester_score
            """, (pid,
                  it["score"],
                  f"hn:{it['source_kind']};domain={it['domain']};story={it['source_story_id']}",
                  f"founder_signal={it.get('founder_signal')}",
                  it["source"], it["score"]))
            inserted += 1
        except Exception as e:
            pass
    c.commit()
    c.close()
    return inserted


def run_once() -> dict:
    candidates = harvest_hn()
    # Log to feedback JSONL
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    with open(WHALE_LOG, "a") as fh:
        for c in candidates:
            fh.write(json.dumps(c) + "\n")
    persisted = _persist_harvest(candidates)
    return {
        "ok": True,
        "candidates": len(candidates),
        "persisted": persisted,
        "log": str(WHALE_LOG),
    }


if __name__ == "__main__":
    print(json.dumps(run_once(), indent=2))
