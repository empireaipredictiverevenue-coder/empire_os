"""Lead Grader API — self-serve lead quality scoring product.

Three endpoints (wired in hub.py):
  POST /v1/leads/grade        — grade one business lead 0-100, bill per quota
  GET  /v1/leads/grade/stats  — aggregate stats (total graded, avg, dist)
  POST /v1/leads/grade/signup — self-serve signup, issue API key, 3 free/day then $49/mo

Scoring model: Omega score (lane_leads.omega_score, 0-100) + Cortex niche heat
(cortex_score, 0-100). We benchmark the submitted lead against the EXISTING
lane_leads population for that niche+metro to produce a comparable 0-100 score,
a letter grade, niche average, a metro multiplier, and a recommended price.

Auth: same X-API-Key / si_tenant pattern as evaluation_product. New signups get
3 free grades/day; over-quota requires a paid plan ($49/mo, plan='lead_grader').
"""
from __future__ import annotations

import os
import re
import secrets
import sqlite3
import time
from typing import Optional

DB_PATH = os.environ.get("EMPIRE_DB_PATH", "/root/empire_os/empire_os.db")

FREE_DAILY_QUOTA = 3
PAID_PLAN = "lead_grader"
PAID_PRICE_USD = 49.0
PRICE_PER_GRADE = 0.0  # paid plan = unlimited grades within the cycle

# Letter-grade thresholds on the final 0-100 score
GRADE_A = 80
GRADE_B = 65
GRADE_C = 50
GRADE_D = 35


def _db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    _ensure_schema(c)
    return c


def _ensure_schema(c: sqlite3.Connection) -> None:
    """Create lead_grader tables + migrate si_tenant for the new plan."""
    c.execute(
        """CREATE TABLE IF NOT EXISTS lead_grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            business_name TEXT,
            niche TEXT,
            metro TEXT,
            website TEXT,
            omega_score REAL,
            cortex_score REAL,
            score REAL,
            grade TEXT,
            niche_avg REAL,
            metro_multiplier REAL,
            recommended_price REAL,
            billed INTEGER DEFAULT 0,
            created_at TEXT
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS lead_grader_quota (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            used_today INTEGER DEFAULT 0,
            quota_date TEXT,
            updated_at TEXT
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS lead_grader_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            amount_usd REAL,
            billing_cycle TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )"""
    )
    # migrate si_tenant: ensure api_key col exists (parent system may lack it)
    try:
        cols = {r[1] for r in c.execute("PRAGMA table_info(si_tenant)").fetchall()}
        for col in ("api_key", "source", "niche"):
            if col not in cols:
                c.execute(f"ALTER TABLE si_tenant ADD COLUMN {col} TEXT")
    except sqlite3.OperationalError:
        pass
    c.commit()


# ── API key resolution (same pattern as evaluation_product) ──────────

def resolve_tenant(api_key: str) -> Optional[str]:
    """Map X-API-Key -> tenant_id. Returns None if unknown/inactive."""
    if not api_key:
        return None
    c = _db()
    try:
        row = c.execute(
            "SELECT tenant_id FROM si_tenant WHERE api_key=? AND status='active'",
            (api_key,),
        ).fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        c.close()


# ── Signup ───────────────────────────────────────────────────────────

def signup(name: str, email: str = "", niche: str = "", website: str = "") -> dict:
    """Self-serve onboarding. Issues an API key, 3 free grades/day then $49/mo.

    Returns {tenant_id, api_key, free_quota, paid_plan, paid_price}.
    Idempotent: a repeat name with an active key gets the existing key back.
    """
    name = (name or "").strip()
    if not name:
        return {"ok": False, "error": "name required"}
    tenant_id = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or f"lg_{int(time.time())}"
    api_key = "lgk_" + secrets.token_urlsafe(24)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    c = _db()
    try:
        existing = c.execute(
            "SELECT tenant_id, api_key FROM si_tenant WHERE tenant_id=? AND status='active'",
            (tenant_id,),
        ).fetchone()
        if existing and existing["api_key"]:
            return {
                "ok": True,
                "tenant_id": existing["tenant_id"],
                "api_key": existing["api_key"],
                "free_quota": FREE_DAILY_QUOTA,
                "paid_plan": PAID_PLAN,
                "paid_price_usd": PAID_PRICE_USD,
                "note": "existing active tenant",
            }
        c.execute(
            "INSERT OR REPLACE INTO si_tenant "
            "(tenant_id, name, email, plan, billing_cycle, status, api_key, niche, source, "
            " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                tenant_id,
                name,
                email or f"{tenant_id}@leadgrader.local",
                "free",
                "monthly",
                "active",
                api_key,
                niche,
                "lead_grader_signup",
                now,
                now,
            ),
        )
        c.execute(
            "INSERT INTO lead_grader_quota (tenant_id, used_today, quota_date, updated_at) "
            "VALUES (?,?,?,?)",
            (tenant_id, 0, _today(), now),
        )
        c.commit()
    except sqlite3.OperationalError as e:
        return {"ok": False, "error": f"si_tenant unavailable: {e}"}
    finally:
        c.close()
    return {
        "ok": True,
        "tenant_id": tenant_id,
        "api_key": api_key,
        "free_quota": FREE_DAILY_QUOTA,
        "paid_plan": PAID_PLAN,
        "paid_price_usd": PAID_PRICE_USD,
        "message": f"{FREE_DAILY_QUOTA} free grades/day, then ${PAID_PRICE_USD:.0f}/mo for unlimited",
    }


# ── Quota / billing ──────────────────────────────────────────────────

def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _is_paid(c: sqlite3.Connection, tenant_id: str) -> bool:
    row = c.execute(
        "SELECT plan FROM si_tenant WHERE tenant_id=?", (tenant_id,)
    ).fetchone()
    return bool(row and row["plan"] == PAID_PLAN and row["plan"] != "free")


def _check_and_decrement_quota(c: sqlite3.Connection, tenant_id: str) -> dict:
    """Return {allowed, paid, used_today, quota, reason}. Mutates quota row."""
    if _is_paid(c, tenant_id):
        return {"allowed": True, "paid": True, "quota": None}
    today = _today()
    row = c.execute(
        "SELECT id, used_today, quota_date FROM lead_grader_quota WHERE tenant_id=?",
        (tenant_id,),
    ).fetchone()
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if not row:
        c.execute(
            "INSERT INTO lead_grader_quota (tenant_id, used_today, quota_date, updated_at) "
            "VALUES (?,?,?,?)",
            (tenant_id, 0, today, now),
        )
        used = 0
        qid = c.execute(
            "SELECT id FROM lead_grader_quota WHERE tenant_id=?", (tenant_id,)
        ).fetchone()["id"]
    else:
        qid = row["id"]
        # reset if new day
        if row["quota_date"] != today:
            c.execute(
                "UPDATE lead_grader_quota SET used_today=0, quota_date=?, updated_at=? WHERE id=?",
                (today, now, qid),
            )
            used = 0
        else:
            used = row["used_today"]
    if used >= FREE_DAILY_QUOTA:
        return {
            "allowed": False,
            "paid": False,
            "used_today": used,
            "quota": FREE_DAILY_QUOTA,
            "reason": "free daily quota exhausted — upgrade to ${:.0f}/mo".format(PAID_PRICE_USD),
        }
    c.execute(
        "UPDATE lead_grader_quota SET used_today=used_today+1, updated_at=? WHERE id=?",
        (now, qid),
    )
    return {"allowed": True, "paid": False, "used_today": used + 1, "quota": FREE_DAILY_QUOTA}


# ── Scoring ──────────────────────────────────────────────────────────

def _grade_for(score: float) -> str:
    if score >= GRADE_A:
        return "A"
    if score >= GRADE_B:
        return "B"
    if score >= GRADE_C:
        return "C"
    if score >= GRADE_D:
        return "D"
    return "F"


def _benchmark(c: sqlite3.Connection, niche: str, metro: str) -> dict:
    """Pull aggregate stats for the niche+metro from lane_leads.

    Returns {niche_avg, metro_avg, overall_avg, sample_n, avg_cortex,
             avg_payout, avg_buyer_count, metro_multiplier}.
    """
    niche = (niche or "").strip().lower()
    metro = (metro or "").strip().upper()
    # niche average (all metros)
    r = c.execute(
        "SELECT AVG(omega_score) AS a, COUNT(*) AS n, AVG(cortex_score) AS c, "
        "AVG(payout_usd) AS p, AVG(buyer_count) AS b "
        "FROM lane_leads WHERE lower(niche)=?",
        (niche,),
    ).fetchone()
    niche_avg = r["a"] if r and r["a"] is not None else 0.0
    niche_n = r["n"] if r and r["n"] else 0
    niche_cortex = r["c"] if r and r["c"] is not None else 0.0
    niche_payout = r["p"] if r and r["p"] is not None else 0.0
    niche_buyers = r["b"] if r and r["b"] is not None else 0.0
    # metro-specific average for this niche
    metro_avg = 0.0
    metro_n = 0
    if metro:
        rm = c.execute(
            "SELECT AVG(omega_score) AS a, COUNT(*) AS n "
            "FROM lane_leads WHERE lower(niche)=? AND upper(metro)=?",
            (niche, metro),
        ).fetchone()
        metro_avg = rm["a"] if rm and rm["a"] is not None else 0.0
        metro_n = rm["n"] if rm and rm["n"] else 0
    # overall avg (fallback if niche unknown)
    ro = c.execute(
        "SELECT AVG(omega_score) AS a FROM lane_leads"
    ).fetchone()
    overall_avg = ro["a"] if ro and ro["a"] is not None else 50.0
    # metro multiplier = metro_avg / niche_avg (demand heat vs niche baseline)
    if niche_avg > 0:
        metro_mult = round(metro_avg / niche_avg, 3) if metro_avg > 0 else 1.0
    else:
        metro_mult = 1.0
    return {
        "niche_avg": round(niche_avg, 2),
        "metro_avg": round(metro_avg, 2),
        "overall_avg": round(overall_avg, 2),
        "niche_sample": niche_n,
        "metro_sample": metro_n,
        "avg_cortex": round(niche_cortex, 2),
        "avg_payout": round(niche_payout, 2),
        "avg_buyer_count": round(niche_buyers, 2),
        "metro_multiplier": metro_mult,
    }


def _score_lead(bench: dict, omega: float, cortex: float) -> tuple[float, float]:
    """Combine the benchmark with this lead's signals into a 0-100 score.

    weighted: 55% omega (lead quality), 25% market heat (niche_avg normalized),
              20% cortex (buyer demand signal). metro_multiplier nudges the result.
    Returns (score_0_100, recommended_price).
    """
    omega_component = max(0.0, min(100.0, float(omega or 0.0)))
    # market heat: how the niche avg compares to the overall avg
    market_heat = 50.0
    if bench["niche_avg"] > 0 and bench["overall_avg"] > 0:
        market_heat = min(100.0, max(0.0, bench["niche_avg"]))
    cortex_component = max(0.0, min(100.0, float(cortex or 0.0)))
    raw = 0.55 * omega_component + 0.25 * market_heat + 0.20 * cortex_component
    # metro multiplier: markets hotter than niche baseline get a boost
    mult = bench["metro_multiplier"]
    if mult > 0:
        raw = raw * (0.85 + 0.15 * mult)  # ±15% swing from metro heat
    score = round(max(0.0, min(100.0, raw)), 1)
    # recommended price: scale with score + avg buyer count (demand proxy)
    base = 15.0  # $15 floor for a graded lead
    demand_boost = min(35.0, bench["avg_buyer_count"] * 0.5)
    score_boost = (score / 100.0) * 50.0
    price = round(base + demand_boost + score_boost, 2)
    return score, price


def grade(
    tenant_id: str,
    business_name: str,
    niche: str,
    metro: str,
    website: str = "",
) -> dict:
    """Grade one lead. Returns the full grade record + quota state."""
    niche = (niche or "").strip()
    metro = (metro or "").strip()
    if not niche or not metro:
        return {"ok": False, "error": "niche and metro required"}
    c = _db()
    try:
        quota = _check_and_decrement_quota(c, tenant_id)
        if not quota["allowed"]:
            return {
                "ok": False,
                "error": quota.get("reason", "quota exhausted"),
                "quota": quota,
                "upgrade_url": f"/v1/leads/grade/signup (plan={PAID_PLAN}, ${PAID_PRICE_USD:.0f}/mo)",
            }
        bench = _benchmark(c, niche, metro)
        # Use the niche+metro average omega + cortex as the lead's own signals
        # when no website (would need a scrape); if metro has data, prefer it.
        if bench["metro_avg"] > 0:
            omega = bench["metro_avg"]
        else:
            omega = bench["niche_avg"] or bench["overall_avg"]
        cortex = bench["avg_cortex"]
        score, price = _score_lead(bench, omega, cortex)
        grade_letter = _grade_for(score)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        cur = c.execute(
            "INSERT INTO lead_grades "
            "(tenant_id, business_name, niche, metro, website, omega_score, "
            " cortex_score, score, grade, niche_avg, metro_multiplier, "
            " recommended_price, billed, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                tenant_id,
                business_name or "",
                niche,
                metro,
                website or "",
                round(omega, 2),
                round(cortex, 2),
                score,
                grade_letter,
                bench["niche_avg"],
                bench["metro_multiplier"],
                price,
                1 if quota["paid"] else 0,
                now,
            ),
        )
        c.commit()
        return {
            "ok": True,
            "business_name": business_name or "",
            "niche": niche,
            "metro": metro,
            "website": website or "",
            "score": score,
            "grade": grade_letter,
            "niche_avg": bench["niche_avg"],
            "metro_avg": bench["metro_avg"],
            "metro_multiplier": bench["metro_multiplier"],
            "avg_cortex": bench["avg_cortex"],
            "recommended_price": price,
            "benchmark_sample": bench["niche_sample"],
            "metro_sample": bench["metro_sample"],
            "quota": quota,
        }
    finally:
        c.close()


# ── Stats ────────────────────────────────────────────────────────────

def stats() -> dict:
    """Aggregate stats across all graded leads."""
    c = _db()
    try:
        r = c.execute(
            "SELECT COUNT(*) AS n, AVG(score) AS avg_score "
            "FROM lead_grades"
        ).fetchone()
        total = r["n"] if r and r["n"] else 0
        avg = round(r["avg_score"], 2) if r and r["avg_score"] is not None else 0.0
        dist_rows = c.execute(
            "SELECT grade, COUNT(*) AS n FROM lead_grades GROUP BY grade"
        ).fetchall()
        dist = {row["grade"]: row["n"] for row in dist_rows}
        # ensure all letters present
        for g in ("A", "B", "C", "D", "F"):
            dist.setdefault(g, 0)
        # top niches graded
        top_niches = [
            dict(r)
            for r in c.execute(
                "SELECT niche, COUNT(*) AS n, AVG(score) AS avg_score "
                "FROM lead_grades WHERE niche != '' "
                "GROUP BY niche ORDER BY n DESC LIMIT 10"
            ).fetchall()
        ]
        # paid vs free
        paid_r = c.execute(
            "SELECT COUNT(*) AS n FROM lead_grades WHERE billed=1"
        ).fetchone()
        paid_count = paid_r["n"] if paid_r else 0
        return {
            "ok": True,
            "total_graded": total,
            "avg_score": avg,
            "grade_distribution": dist,
            "top_niches": top_niches,
            "paid_grades": paid_count,
            "free_grades": total - paid_count,
        }
    finally:
        c.close()


def upgrade_to_paid(tenant_id: str) -> dict:
    """Mark a tenant as paid ($49/mo). Writes a ledger row + flips plan."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    c = _db()
    try:
        row = c.execute(
            "SELECT tenant_id FROM si_tenant WHERE tenant_id=? AND status='active'",
            (tenant_id,),
        ).fetchone()
        if not row:
            return {"ok": False, "error": "tenant not found / inactive"}
        c.execute(
            "UPDATE si_tenant SET plan=?, updated_at=? WHERE tenant_id=?",
            (PAID_PLAN, now, tenant_id),
        )
        c.execute(
            "INSERT INTO lead_grader_ledger "
            "(tenant_id, amount_usd, billing_cycle, status, created_at) "
            "VALUES (?,?,?,?,?)",
            (tenant_id, PAID_PRICE_USD, "monthly", "pending", now),
        )
        c.commit()
        return {
            "ok": True,
            "tenant_id": tenant_id,
            "plan": PAID_PLAN,
            "amount_usd": PAID_PRICE_USD,
            "status": "pending",
            "message": f"Upgraded to ${PAID_PRICE_USD:.0f}/mo — unlimited grades",
        }
    finally:
        c.close()
