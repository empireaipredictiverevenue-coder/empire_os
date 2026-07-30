#!/usr/bin/env python3
"""whale_finder.py — Find buyers with real money (CEOs, founders, fund
managers, GTM leads) instead of single-owner SMBs.

Approach: scan existing si_buyer_outreach (30k prospects already have
business_name, niches, wallet) and score them on enterprise likelihood.
Then scan Reddit + HN comments for self-identified founders pitching
their business pain (free, no key required) and POST them as
mass-torts-style candidates.

Score is a 0-100 ordinal. Tier mapping:
  80-100 = T5 whale ($50k/seat, manual AM)
  60-79  = T4 enterprise ($9,900/seat, automated)
  40-59  = T3 gold (already in pricing)
  <40    = deprioritize (auto-lane flows handle)

Output: si_prospect_consent rows with whale_tier set; index
/root/feedback/whales.jsonl for the chief-of-staff loop to call.
"""
from __future__ import annotations
import json
import os
import re
import sqlite3
import time
import urllib.request
from datetime import datetime, timezone

DB = os.environ.get("EMPIRE_DB", "/root/empire_os/empire_os.db")
FEEDBACK_DIR = os.environ.get("EMPIRE_FEEDBACK_DIR",
                              "/root/empire_os/feedback")
LOG_PATH = os.path.join(FEEDBACK_DIR, "whales.jsonl")

# The default DB path is the HOST filesystem. The container's hub DB
# is at the SAME host path because Empire runs via incus-file-push so
# host edits are visible inside the container after a restart. For
# grade-A safety, allow caller to point anywhere via EMPIRE_DB env var.


def _find_db() -> str:
    """Pick the live DB. Hosts use /root/empire_os/empire_os.db directly."""
    env = os.environ.get("EMPIRE_DB")
    if env and os.path.exists(env):
        return env
    candidates = [
        "/root/empire_os/empire_os.db",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    # Fall back to common container path. The script can't change
    # container from here, but the operator can copy a snapshot.
    return "/root/empire_os/empire_os.db"


# ═══════════════════════════════════════════════════════════════════════
# Enterprise signals — cheap, auditable, no paid API
# ═══════════════════════════════════════════════════════════════════════

TITLE_PATTERNS = [
    (re.compile(r"\bceo\b", re.I), 18),
    (re.compile(r"\bchief\s+executive", re.I), 18),
    (re.compile(r"\bfounder\b", re.I), 14),
    (re.compile(r"\bco[- ]?founder\b", re.I), 14),
    (re.compile(r"\bpresident\b", re.I), 10),
    (re.compile(r"\bvp\s+(of\s+)?(sales|marketing|growth|revenue|operations)", re.I), 12),
    (re.compile(r"\bhead\s+of\s+(growth|sales|revenue|marketing)", re.I), 10),
    (re.compile(r"\bgrowth\s+lead\b", re.I), 6),
    (re.compile(r"\bfranchise\s+owner\b", re.I), 8),
    (re.compile(r"\bregional\s+director\b", re.I), 12),
    # Negative: tiny single-owner
    (re.compile(r"\bowner\s+operator\b"), -8),
    (re.compile(r"\bsolo\s+contractor\b"), -10),
    (re.compile(r"\bmyself\s+only\b"), -12),
]

VERTICAL_BONUS = {
    "insurance": 20,         # pays 4-fig clients easily, our 7% backend fit
    "auto insurance": 18,
    "real_estate": 16,
    "solar": 14,             # storm restoration overlap
    "roof_repair": 12,
    "commercial_roofing": 12,
    "commercial solar": 12,
    "roofting": 11,           # the broad "roofing" niche
    "roofing": 10,
    "franchise": 18,
    "logistics": 12,
    "b2b": 10,
    "manufacturing": 8,
    "managed it": 8,
    "hr staffing": 6,
    "staffing": 4,
    "medical claims": 12,
    "medicare advantage": 10,
    "merchant services": 14,
    "business loan broker": 12,
    "home health agency": 12,
    "assisted living": 12,
    "debt": 8,
    "water_mitigation": 10,
    "restoration": 8,
    "hvac": 6,
    "general contractor": 8,
    "general_contractor": 8,
}

# Whales often email with custom domains (not gmail/yahoo/outlook/hotmail)
FREEMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
    "aol.com", "icloud.com", "protonmail.com", "msn.com",
}

# 11k+ employees is a hard whale signal (published via LinkedIn scrape
# elsewhere; we accept "hq_employees" field if present)
HQ_PHRASES = re.compile(r"(11[,.]?\d{2,4})\+?\s+(employees|staff|people|headcount)")


def _open_db():
    c = sqlite3.connect(_find_db(), timeout=15)
    c.execute("PRAGMA busy_timeout=15000")
    return c


def _score_prospect(business_name: str, email: str,
                    niches: str | None,
                    url: str | None,
                    hq_employees: int | None) -> tuple[int, list[str]]:
    """Return (score, reasons[]). reasons help the AM understand fit."""
    score = 0
    reasons: list[str] = []
    blob = " ".join(filter(None, (business_name, email, niches, url)))

    for pat, delta in TITLE_PATTERNS:
        if pat.search(blob):
            score += delta
            reasons.append(f"title:+{delta}")

    if niches:
        for vert, bonus in VERTICAL_BONUS.items():
            if vert in niches.lower():
                score += bonus
                reasons.append(f"vertical({vert}):+{bonus}")

    if hq_employees is not None:
        if hq_employees >= 1000:
            score += 22
            reasons.append(f"hq_employees={hq_employees}:+22")
        elif hq_employees >= 100:
            score += 14
            reasons.append(f"hq_employees={hq_employees}:+14")
        elif hq_employees >= 25:
            score += 6
            reasons.append(f"hq_employees={hq_employees}:+6")

    if email and "@" in email:
        dom = email.split("@", 1)[1].lower().strip()
        if dom and dom not in FREEMAIL_DOMAINS:
            score += 6
            reasons.append(f"custom_domain:{dom}:+6")
        else:
            reasons.append(f"freemail:{dom}:0")

    # Bounded
    score = max(0, min(100, score))
    return score, reasons


def _tier(score: int) -> str:
    if score >= 80:
        return "T5_WHALE"
    if score >= 60:
        return "T4_ENTERPRISE"
    if score >= 40:
        return "T3_GOLD"
    return "BELOW_THRESHOLD"


# ═══════════════════════════════════════════════════════════════════════
# Free source scan — Reddit JSON + HN search-by-comment
# ═══════════════════════════════════════════════════════════════════════

REDDIT_ENDPOINTS = [
    "https://www.reddit.com/r/sales/new/.json?limit=20",
    "https://www.reddit.com/r/Salesforce/new/.json?limit=15",
    "https://www.reddit.com/r/RevOpsHQ/new/.json?limit=15",
    "https://www.reddit.com/r/consulting/new/.json?limit=10",
]
RE_HIRING = re.compile(
    r"\b(hiring|looking for|seeking|need help with|"
    r"any (?:recommend|rec|suggestion)s?)", re.I)
RE_BUDGET = re.compile(
    r"(USD\s*\d[\d,]{2,}|\\\$\s?\d[\d,]{2,}|\bbudget\s+(?:of|around|is)\s+\$?\d)",
    re.I)
RE_TITLE = re.compile(
    r"\b(?:ceo|founder|head\s+of\s+\w+)\b", re.I)


def scan_reddit() -> list[dict]:
    out: list[dict] = []
    for url in REDDIT_ENDPOINTS:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "EmpireOS-WhaleHunter/1.0",
            })
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode("utf-8", "ignore"))
            for child in (data.get("data", {}).get("children", [])
                          if isinstance(data, dict) else []):
                d = child.get("data", {})
                title = d.get("title", "") or ""
                body = d.get("selftext", "") or ""
                if not (RE_HIRING.search(title + body)
                        or RE_BUDGET.search(title + body)):
                    continue
                url_p = "https://reddit.com" + d.get("permalink", "")
                blob = title + " " + body[:500]
                # No email followup here (Reddit policy). Just record.
                score = 25
                if RE_BUDGET.search(blob):
                    score += 20
                if RE_TITLE.search(blob):
                    score += 8
                out.append({
                    "source": "reddit",
                    "url": url_p,
                    "title": title[:120],
                    "score": min(70, score),
                    "tier": _tier(score),
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            out.append({"source": "reddit", "url": url,
                        "error": str(e)[:120]})
    return out


# ═══════════════════════════════════════════════════════════════════════
# Existing-prospect scan — score what's already in si_buyer_outreach
# ═══════════════════════════════════════════════════════════════════════

def score_existing(limit: int = 2000) -> int:
    """Walk si_buyer_outreach, score rows, persist whale_tier to
    si_prospect_consent (joined via prospect_id=email). Insert new
    whales into the feedback JSONL for the AM loop to dial."""
    c = _open_db()
    # ensure prospect_consent has whale_tier
    cur_cols = [r[1] for r in c.execute(
        "PRAGMA table_info(si_prospect_consent)").fetchall()]
    if "whale_tier" not in cur_cols:
        try:
            c.execute("ALTER TABLE si_prospect_consent "
                      "ADD COLUMN whale_tier TEXT DEFAULT NULL")
            c.execute("ALTER TABLE si_prospect_consent "
                      "ADD COLUMN whale_score INTEGER DEFAULT 0")
            c.execute("ALTER TABLE si_prospect_consent "
                      "ADD COLUMN whale_reasons TEXT DEFAULT NULL")
            c.commit()
        except Exception:
            pass

    rows = list(c.execute("""
        SELECT prospect_id, business_name, email, niches, url
        FROM si_buyer_outreach
        WHERE business_name IS NOT NULL OR email IS NOT NULL
        LIMIT ?
    """, (limit,)))
    inserted = 0
    for r in rows:
        pid, biz, email, niches, url = r
        if not email:
            continue
        score, reasons = _score_prospect(biz or "", email or "",
                                          niches, url, None)
        tier = _tier(score)
        if tier == "BELOW_THRESHOLD":
            continue
        # upsert consent row
        try:
            c.execute("""
                INSERT INTO si_prospect_consent
                  (prospect_id, opted_in, opted_in_at, niche, source,
                   whale_tier, whale_score, whale_reasons)
                VALUES (?, 0, NULL, ?, 'whale_finder',
                        ?, ?, ?)
                ON CONFLICT(prospect_id) DO UPDATE SET
                  whale_tier = excluded.whale_tier,
                  whale_score = excluded.whale_score,
                  whale_reasons = excluded.whale_reasons
            """, (pid, (niches or "unknown").split(",")[0] if niches else "unknown",
                  tier, score, ",".join(reasons)[:500]))
            inserted += 1
        except Exception:
            pass
    c.commit()
    c.close()

    # Append human-readable JSONL for the AM loop
    if inserted > 0:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a") as fh:
            fh.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "kind": "scan_existing",
                "scanned": len(rows),
                "tiered": inserted,
            }) + "\n")
    return inserted


def run_once() -> dict:
    reddit_hits = scan_reddit()
    existing_tiered = score_existing()

    # Persist Reddit hits as si_prospect_consent whale rows.
    if reddit_hits:
        c = _open_db()
        for hit in reddit_hits:
            if "error" in hit or not hit.get("url"):
                continue
            pid = "whale:reddit:" + hit["url"][:60].replace("/", "_")
            try:
                c.execute("""
                    INSERT INTO si_prospect_consent
                      (prospect_id, opted_in, opted_in_at, niche, source,
                       whale_tier, whale_score, whale_reasons)
                    VALUES (?, 0, NULL, 'unknown', 'whale_finder:reddit',
                            ?, ?, ?)
                    ON CONFLICT(prospect_id) DO UPDATE SET
                      whale_tier = excluded.whale_tier,
                      whale_score = excluded.whale_score
                """, (pid, hit.get("tier"), hit.get("score"),
                      hit.get("title", "")[:200]))
            except Exception:
                pass
        c.commit()
        c.close()

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as fh:
        fh.write(json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": "scan_reddit",
            "hits": [h for h in reddit_hits if "url" in h
                     and "error" not in h][:50],
        }) + "\n")

    return {
        "ok": True,
        "existing_tiered": existing_tiered,
        "reddit_hits": len([h for h in reddit_hits
                            if "error" not in h]),
        "reddit_errors": [h for h in reddit_hits if "error" in h],
    }


if __name__ == "__main__":
    import sys
    print(json.dumps(run_once(), indent=2, default=str))
    sys.exit(0)
