#!/usr/bin/env python3
"""lead_classifier_agent.py — Read every prospect in si_buyer_outreach,
classify as whale / mid / owner, persist tier + reason, queue outreach
per tier. Cadence: hourly.

Tier semantics (mirror pricing.md tiers):
  WHALE  → T5 ($50k/seat, manual AM, AB manual)
  ENTERPRISE → T4 ($9,900/seat, automated)
  GOLD → T3 ($1,000/seat, automated)
  SILVER → T2 ($500/seat, automated)
  OWNER_OPERATOR → T1 ($200/seat, automated, mostly ignore — no money)

Signal sources (all free, no API key):
  - si_buyer_outreach row (business_name, niches, wallet, score)
  - heuristic title inference (CEO/Founder regex from business_name)
  - LinkedIn URL pattern (none here — out of scope)
  - Reddit / HN source comment (whale_finder companion output)
  - si_prospect_consent.whale_tier when previously classified

Output:
  - DB: update si_prospect_consent with classified_tier + reasons
  - Feedback: writes lead_classifier_segments.jsonl (queue for chief-of-staff)
  - Decision log: lead_classifier_log.jsonl
"""
from __future__ import annotations
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_CANDIDATE_LOG_DIRS = ("/root/empire_os/feedback", "/root/feedback")
FB_DIR = next(
    (Path(p) for p in _CANDIDATE_LOG_DIRS if os.access(p, os.W_OK)),
    Path("/tmp"),
)
FB_DIR.mkdir(parents=True, exist_ok=True)
SEGMENT_LOG = FB_DIR / "lead_classifier_segments.jsonl"
DECISION_LOG = FB_DIR / "lead_classifier_log.jsonl"

INTERVAL_SEC = int(os.environ.get("INTERVAL_SEC", str(60 * 60)))  # hourly
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "1000"))


def _find_db() -> str:
    env = os.environ.get("EMPIRE_DB")
    if env and os.path.exists(env):
        return env
    for c in ("/root/empire_os/empire_os.db",):
        if os.path.exists(c):
            return c
    return "/root/empire_os/empire_os.db"


def _open_db():
    c = sqlite3.connect(_find_db(), timeout=20)
    c.execute("PRAGMA busy_timeout=20000")
    return c


# ═══════════════════════════════════════════════════════════════════════
# Tier classification
# ═══════════════════════════════════════════════════════════════════════

# Title + signal patterns (kept conservative; correct > aggressive)
SIGNAL_PATTERNS = [
    # CEO / top of org — strongest
    (re.compile(r"\bceo\b", re.I), 25, "title:ceo"),
    (re.compile(r"\bchief\s+executive", re.I), 25, "title:ceo"),
    (re.compile(r"\bfounder\b", re.I), 22, "title:founder"),
    (re.compile(r"\bco[- ]?founder\b", re.I), 22, "title:co-founder"),
    (re.compile(r"\bpresident\b", re.I), 18, "title:president"),
    # VP / senior leadership
    (re.compile(r"\bvp\s+(of\s+)?(sales|marketing|growth|revenue|operations)", re.I), 14,
     "title:vp-revops"),
    (re.compile(r"\bhead\s+of\s+(growth|sales|revenue|marketing|ops)", re.I), 12,
     "title:head-of-revops"),
    (re.compile(r"\bregional\s+director\b", re.I), 10, "title:regional-dir"),
    # Negative: tiny
    (re.compile(r"\bowner\s+operator\b"), -16, "title:owner-op"),
    (re.compile(r"\bsolo\s+contractor\b"), -18, "title:solo"),
    (re.compile(r"\bmyself\s+only\b"), -20, "title:solo"),
    (re.compile(r"\boffice\s+(manager|of)\s+(just\s+)?me\b"), -22, "title:solo"),
]

VERTICAL_PREMIUM = {
    "insurance": 12, "auto insurance": 12,
    "real_estate": 11,
    "solar": 9, "commercial solar": 9,
    "roof_repair": 8, "commercial_roofing": 8, "roofing": 7,
    "franchise": 14,
    "logistics": 10,
    "b2b": 8,
    "medical claims": 9, "medicare advantage": 8, "pharmacy": 10,
    "merchant services": 10, "business loan broker": 10,
    "home health agency": 9, "assisted living": 9,
    "managed it": 8,
    "manufacturing": 7,
    "general contractor": 6, "general_contractor": 6,
    "hvac": 5, "plumbing": 5, "restoration": 6,
    "water_mitigation": 7, "debt": 6, "staffing": 5,
}

# Niche tier floor — generic SMB niches never hit whale tier even with
# Niche floor — prevents tier slip from "owner operator in insurance"
# AND prevents arbitrary "gmail.com + hvac" from hitting GOLD.
# Operates as a CAP, not the ONLY signal: with a strong title pattern
# the floor can be lifted.
NICHE_TIER_FLOOR_CAP = {
    "insurance": "ENTERPRISE",        # can whale if CEO + budget
    "auto insurance": "ENTERPRISE",
    "real_estate": "ENTERPRISE",
    "franchise": "ENTERPRISE",
    "solar": "GOLD",
    "commercial solar": "ENTERPRISE",
    "commercial_roofing": "GOLD",
    "commercial hvac": "GOLD",
    "logistics": "GOLD",
    "b2b": "GOLD",
    "medical claims": "ENTERPRISE",
    "pharmacy": "GOLD",
    "merchant services": "GOLD",
    "business loan broker": "ENTERPRISE",
    "managed it": "GOLD",
    "manufacturing": "GOLD",
    "roofing": "GOLD",
    "roof_repair": "GOLD",
    "home health agency": "GOLD",
    "assisted living": "GOLD",
    "general contractor": "SILVER",
    "general_contractor": "SILVER",
    "hvac": "SILVER",
    "plumbing": "SILVER",
    "restoration": "GOLD",
    "debt relief": "GOLD",
    "hr staffing": "GOLD",
    "staffing": "SILVER",
    "water_mitigation": "GOLD",
    "hvac commercial": "GOLD",
}

OWNER_FLOOR_NICHES = {
    "owner operator", "solo", "single", "handyman",
}

FREEMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
    "aol.com", "icloud.com", "protonmail.com", "msn.com",
}


def _tier(score: int) -> str:
    # Thresholds tuned so that CEO + enterprise-niche + custom-domain
    # can clear WHALE on real signals, but a gmail.com + mid-tier niche
    # + no title stays at OWNER_OPERATOR.
    if score >= 55:
        return "WHALE"
    if score >= 38:
        return "ENTERPRISE"
    if score >= 22:
        return "GOLD"
    if score >= 10:
        return "SILVER"
    return "OWNER_OPERATOR"


def classify(business_name: str, email: str, niches: str,
             wallet: str | None, existing_tier: str | None) -> tuple[str, list[str]]:
    """Return (tier, reasons[]). 100 ordinal score, mapped to tier."""
    score = 0
    reasons: list[str] = []

    name = business_name or ""
    em = email or ""
    nich = (niches or "").lower()

    # Title signals from business_name + email local-part
    blob = f"{name} | {em.split('@', 1)[0] if em else ''}"
    for pat, delta, label in SIGNAL_PATTERNS:
        if pat.search(blob):
            score += delta
            reasons.append(f"{label}:{delta:+d}")

    # Niche premium
    niche_boost = 0
    for k, boost in VERTICAL_PREMIUM.items():
        if k in nich:
            niche_boost = max(niche_boost, boost)
    if niche_boost:
        score += niche_boost
        reasons.append(f"niche:{niche_boost:+d}")

    # Custom domain >> free email (whales carry their own)
    if em and "@" in em:
        dom = em.split("@", 1)[1].lower().strip()
        if dom and dom not in FREEMAIL_DOMAINS:
            score += 4
            reasons.append(f"custom_domain:{dom}:+4")
        elif dom:
            reasons.append(f"freemail:{dom}:0")

    # Wallet present = on-chain capable (whale indicator)
    if wallet and len(wallet) > 8:
        score += 8
        reasons.append("has_wallet:+8")

    # Niche maximum — caps the score if no executive title. Without an
    # exec title, the prospect defaults to one tier BELOW their
    # category's typical ceiling (you wouldn't pitch a CEO plan to a
    # gmail.com / owner operator in any niche).
    primary_niche = nich.split(",")[0].strip() if nich else ""
    cap = NICHE_TIER_FLOOR_CAP.get(primary_niche)
    has_strong_title = any("title:" in r and ("ceo" in r or "founder" in r)
                           for r in reasons)
    if not has_strong_title and cap:
        cap_score = _tier_score(cap) - 10
        if score > cap_score:
            score = cap_score
            reasons.append(f"niche_cap:{primary_niche}:{cap_score}")

    # Owner-floor boost down
    if any(o in nich for o in OWNER_FLOOR_NICHES):
        score -= 10
        reasons.append("niche_owner_floor:-10")

    # Bounded ordinal
    score = max(0, min(100, score))

    # Operator signal — if the previous tier from si_prospect_consent
    # said WHALE, trust that + bias up (consistent history wins).
    if existing_tier == "WHALE":
        score = max(score, 70)
        reasons.append("prior_tier_whale:+5")
    tier = _tier(score)
    return tier, reasons


def _tier_score(tier: str) -> int:
    return {
        "WHALE": 75,
        "ENTERPRISE": 55,
        "GOLD": 35,
        "SILVER": 18,
        "OWNER_OPERATOR": 0,
    }.get(tier, 0)


# ═══════════════════════════════════════════════════════════════════════
# DB writes
# ═══════════════════════════════════════════════════════════════════════


def _ensure_columns(c: sqlite3.Connection):
    cur = [r[1] for r in c.execute(
        "PRAGMA table_info(si_prospect_consent)").fetchall()]
    if "classified_tier" not in cur:
        c.execute("ALTER TABLE si_prospect_consent "
                  "ADD COLUMN classified_tier TEXT DEFAULT NULL")
    if "classified_reasons" not in cur:
        c.execute("ALTER TABLE si_prospect_consent "
                  "ADD COLUMN classified_reasons TEXT DEFAULT NULL")
    if "classified_at" not in cur:
        c.execute("ALTER TABLE si_prospect_consent "
                  "ADD COLUMN classified_at TEXT DEFAULT NULL")


def _ensure_outreach_columns(c: sqlite3.Connection):
    cur = [r[1] for r in c.execute(
        "PRAGMA table_info(si_buyer_outreach)").fetchall()]
    if "classified_tier" not in cur:
        c.execute("ALTER TABLE si_buyer_outreach "
                  "ADD COLUMN classified_tier TEXT DEFAULT NULL")
    if "classified_reasons" not in cur:
        c.execute("ALTER TABLE si_buyer_outreach "
                  "ADD COLUMN classified_reasons TEXT DEFAULT NULL")
    if "classified_at" not in cur:
        c.execute("ALTER TABLE si_buyer_outreach "
                  "ADD COLUMN classified_at TEXT DEFAULT NULL")


def _get_existing_tier(c: sqlite3.Connection, prospect_id: str) -> str | None:
    try:
        r = c.execute(
            "SELECT classified_tier FROM si_prospect_consent "
            "WHERE prospect_id=?",
            (prospect_id,)).fetchone()
        return r[0] if r and r[0] else None
    except Exception:
        return None


def classify_batch(batch_size: int = 1000) -> dict:
    """Run a single classification pass over the buyer table."""
    c = _open_db()
    _ensure_columns(c)
    _ensure_outreach_columns(c)

    rows = list(c.execute("""
        SELECT prospect_id, business_name, email, niches, wallet
        FROM si_buyer_outreach
        WHERE (classified_tier IS NULL OR classified_at = ''
               OR classified_at < datetime('now','-7 day'))
        LIMIT ?
    """, (batch_size,)))
    counts = {"WHALE": 0, "ENTERPRISE": 0, "GOLD": 0,
              "SILVER": 0, "OWNER_OPERATOR": 0}
    updated = 0
    whale_log = []
    for row in rows:
        pid, biz, email, niches, wallet = row
        # Map outreach.prospect_id to consent.prospect_id (best-effort).
        consent_pid = pid
        existing = _get_existing_tier(c, consent_pid)
        tier, reasons = classify(biz or "", email or "",
                                 niches or "", wallet, existing)
        ts = datetime.now(timezone.utc).isoformat()
        reasons_b = ",".join(reasons)[:500]
        # upsert in consent table
        try:
            c.execute("""
                INSERT INTO si_prospect_consent
                  (prospect_id, opted_in, opted_in_at, niche, source,
                   classified_tier, classified_reasons, classified_at)
                VALUES (?, 0, NULL, ?, 'lead_classifier_agent',
                        ?, ?, ?)
                ON CONFLICT(prospect_id) DO UPDATE SET
                  classified_tier = excluded.classified_tier,
                  classified_reasons = excluded.classified_reasons,
                  classified_at = excluded.classified_at
            """, (consent_pid,
                  (niches or "unknown").split(",")[0] if niches else "unknown",
                  tier, reasons_b, ts))
        except Exception:
            pass
        # mirror on outreach for the buyer_dashboard reads
        try:
            c.execute("""
                UPDATE si_buyer_outreach
                SET classified_tier=?, classified_reasons=?, classified_at=?
                WHERE prospect_id=?
            """, (tier, reasons_b, ts, pid))
        except Exception:
            pass
        counts[tier] += 1
        updated += 1
        if tier in ("WHALE", "ENTERPRISE"):
            whale_log.append({
                "ts": ts, "tier": tier, "prospect_id": pid,
                "business_name": biz, "email": email,
                "niches": niches, "reasons": reasons,
            })
    c.commit()
    c.close()

    # Append to segment feed for the chief-of-staff loop
    if whale_log:
        with open(SEGMENT_LOG, "a") as fh:
            for entry in whale_log:
                fh.write(json.dumps(entry) + "\n")
    # Decision summary
    with open(DECISION_LOG, "a") as fh:
        fh.write(json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "batch_size": len(rows),
            "updated": updated,
            "tier_breakdown": counts,
            "whales_found": counts["WHALE"],
            "enterprise_found": counts["ENTERPRISE"],
        }) + "\n")
    return {"updated": updated, "tier_breakdown": counts,
            "whales_in_batch": counts["WHALE"],
            "enterprise_in_batch": counts["ENTERPRISE"]}


def main() -> int:
    print(f"[{datetime.now(timezone.utc).isoformat()}] "
          f"lead_classifier_agent online — hourly cadence", flush=True)
    cycle_count = 0
    while True:
        try:
            r = classify_batch(BATCH_SIZE)
            if r["updated"] > 0:
                print(f"  cycle {cycle_count}: {r}", flush=True)
        except Exception as e:
            with open(DECISION_LOG, "a") as fh:
                fh.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                                    "level": "ERROR",
                                    "msg": "cycle_failed",
                                    "err": str(e)[:200]}) + "\n")
        cycle_count += 1
        time.sleep(INTERVAL_SEC)
    return 0


if __name__ == "__main__":
    sys.exit(main())
