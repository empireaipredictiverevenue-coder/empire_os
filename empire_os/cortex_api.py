"""Empire Cortex — Intelligence API (public product endpoints).

Exposes three Cortex Intelligence data surfaces over a single FastAPI
APIRouter, plus a self-serve signup that creates a $299/mo subscription:

  GET  /v1/cortex/scores?niche=X&metro=Y  — niche heat 0-100 + competitor/
       market-share breakdown (merged from cortex_scorer + cortex_blueprints)
  GET  /v1/cortex/blueprint?niche=X       — full blueprint (visual_dna +
       script_dna + market breakdown) as JSON
  GET  /v1/cortex/strategies              — strategy_rank ROI board
  POST /v1/cortex/signup                  — creates an SI subscription +
       issues an X-API-Key (same key format as the eval product, $299/mo)

Auth & rate limit model:
  - X-API-Key header: same lookup path as evaluation_product.resolve_buyer
    (si_tenant.api_key). A valid Cortex key = paid tier (unlimited).
  - No key: anonymous IP gets 5 free calls/day, after which they must sign
    up. Free calls read from a small cortex_usage table (per-client-IP).
  - $299/mo "cortex" plan subscription created in si_subscription via the
    signup endpoint so the billing pipeline can charge + revoke it.

All Cortex Intelligence data comes from existing tables + cache files; this
module only reads/writes the cortex_api_key ring + cortex_usage log.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
DB_PATH = os.environ.get("EMPIRE_DB_PATH", "/root/empire_os/empire_os.db")
CORTEX_CACHE = Path("/run/cortex_niche_scores.json")
DEFAULT_SCORE = 55
FREE_CALLS_PER_DAY = 5
PAID_PLAN_CENTS = 29900          # $299.00
PAID_PLAN_NAME = "cortex"        # plan identifier in si_subscription

router = APIRouter(prefix="/v1/cortex", tags=["cortex_intelligence"])


# --------------------------------------------------------------------------
# DB helpers
# --------------------------------------------------------------------------
def _db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=30)
    # Cortex-specific key ring (paid subscribers get an explicit key here so
    # we can revoke Cortex-only access without touching the eval product).
    c.execute(
        """CREATE TABLE IF NOT EXISTS cortex_api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key TEXT UNIQUE,
            tenant_id TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT,
            revoked_at TEXT
        )"""
    )
    # Per-IP free-tier usage log (one row per calendar day per IP).
    c.execute(
        """CREATE TABLE IF NOT EXISTS cortex_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_ip TEXT,
            day TEXT,
            calls INTEGER DEFAULT 0,
            last_call_at TEXT
        )"""
    )
    c.commit()
    return c


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


# --------------------------------------------------------------------------
# Auth / rate limit
# --------------------------------------------------------------------------
def _resolve_cortex_key(api_key: str) -> Optional[str]:
    """Resolve a Cortex-issued X-API-Key to a tenant_id."""
    if not api_key:
        return None
    c = _db()
    try:
        row = c.execute(
            "SELECT tenant_id FROM cortex_api_keys WHERE api_key=? AND status='active'",
            (api_key,),
        ).fetchone()
        if row:
            return row[0]
        # Fall back to the shared si_tenant ring (evaluation_product pattern).
        try:
            row = c.execute(
                "SELECT tenant_id FROM si_tenant WHERE api_key=? AND status='active'",
                (api_key,),
            ).fetchone()
            return row[0] if row else None
        except sqlite3.OperationalError:
            return None
    except sqlite3.Error:
        return None
    finally:
        c.close()


def _ip_free_remaining(client_ip: str) -> int:
    """How many free Cortex calls this IP has left today."""
    if not client_ip:
        return FREE_CALLS_PER_DAY
    c = _db()
    try:
        row = c.execute(
            "SELECT calls FROM cortex_usage WHERE client_ip=? AND day=?",
            (client_ip, _today()),
        ).fetchone()
    finally:
        c.close()
    used = row[0] if row else 0
    return max(0, FREE_CALLS_PER_DAY - used)


def _record_free_call(client_ip: str) -> None:
    """Bump the per-IP free call counter (upsert)."""
    if not client_ip:
        return
    c = _db()
    try:
        existing = c.execute(
            "SELECT id, calls FROM cortex_usage WHERE client_ip=? AND day=?",
            (client_ip, _today()),
        ).fetchone()
        if existing:
            c.execute(
                "UPDATE cortex_usage SET calls=?, last_call_at=? WHERE id=?",
                (existing[1] + 1, _now(), existing[0]),
            )
        else:
            c.execute(
                "INSERT INTO cortex_usage (client_ip, day, calls, last_call_at) "
                "VALUES (?,?,?,?)",
                (client_ip, _today(), 1, _now()),
            )
        c.commit()
    finally:
        c.close()


def _check_auth(request: Request) -> tuple[bool, str, int]:
    """Returns (is_paid, message, free_remaining).

    Raises HTTPException if neither paid nor free budget remains.
    """
    api_key = (request.headers.get("x-api-key") or "").strip()
    tenant = _resolve_cortex_key(api_key)
    if tenant:
        return True, tenant, -1            # paid: unlimited
    client_ip = (request.client.host if request.client else "") or "unknown"
    remaining = _ip_free_remaining(client_ip)
    if remaining <= 0:
        raise HTTPException(
            402,
            "Free Cortex Intelligence calls exhausted for today. "
            "Sign up at POST /v1/cortex/signup for unlimited access ($299/mo).",
        )
    return False, "", remaining


# --------------------------------------------------------------------------
# Cortex scorers (cache + DB)
# --------------------------------------------------------------------------
_SCORES_CACHE: dict = {}
_SCORES_TS = 0.0


def _load_scores() -> dict:
    """Read the niche-score cache written by cortex_engine/cortex_scorer."""
    global _SCORES_CACHE, _SCORES_TS
    if time.time() - _SCORES_TS > 60:
        try:
            if CORTEX_CACHE.exists():
                _SCORES_CACHE = json.loads(
                    CORTEX_CACHE.read_text()
                ).get("scores", {})
            else:
                _SCORES_CACHE = {}
        except Exception:
            _SCORES_CACHE = {}
        _SCORES_TS = time.time()
    return _SCORES_CACHE


def _niche_heat(niche: str, metro: str = "") -> int:
    """Return niche heat score 0-100 (default 55 when no cache)."""
    scores = _load_scores()
    n = (niche or "").lower().strip()
    key = f"{metro.lower()}:{n}" if metro else n
    return scores.get(key, scores.get(n, DEFAULT_SCORE))


# --------------------------------------------------------------------------
# Blueprint queries
# --------------------------------------------------------------------------
def _fetch_blueprint(niche: str, limit: int = 1) -> Optional[dict]:
    """Fetch the latest cortex_blueprint rows for a niche (JSON-parsed)."""
    c = _db()
    try:
        rows = c.execute(
            "SELECT id, blueprint_id, niche, campaign_type, visual_dna, script_dna, created_at "
            "FROM cortex_blueprints WHERE niche=? ORDER BY id DESC LIMIT ?",
            ((niche or "").strip(), int(limit)),
        ).fetchall()
    finally:
        c.close()
    if not rows:
        return None
    items = []
    for r in rows:
        try:
            visual = json.loads(r[4]) if r[4] else {}
        except Exception:
            visual = {}
        try:
            script = json.loads(r[5]) if r[5] else []
        except Exception:
            script = []
        items.append(
            {
                "id": r[0],
                "blueprint_id": r[1],
                "niche": r[2],
                "campaign_type": r[3],
                "visual_dna": visual,
                "script_dna": script,
                "created_at": r[6],
            }
        )
    return {"niche": niche, "count": len(items), "blueprints": items}


def _competitor_breakdown(niche: str) -> list:
    """Pull competitor market-share rows from the most recent blueprint."""
    bp = _fetch_blueprint(niche, limit=1)
    if not bp:
        return []
    return bp["blueprints"][0].get("script_dna", [])


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
@router.get("/scores")
def cortex_scores(request: Request, niche: str = "", metro: str = ""):
    """Niche heat score (0-100) + competitor / market-share breakdown.

    `niche` required. `metro` optional (metro-specific override if cached).
    Returns: heat_score, tier (hot/warm/cold), competitors[], market_share[].
    """
    is_paid, buyer, free_remaining = _check_auth(request)
    if not is_paid:
        _record_free_call(
            request.client.host if request.client else ""
        )
    if not niche.strip():
        raise HTTPException(400, "niche query parameter required")
    score = _niche_heat(niche, metro)
    tier = "hot" if score >= 75 else "warm" if score >= 60 else "cold"
    competitors = _competitor_breakdown(niche)
    market_share = [
        {"domain": c.get("domain"), "share": c.get("market_share"),
         "quality_score": c.get("quality_score")}
        for c in competitors
        if isinstance(c, dict)
    ]
    return JSONResponse(
        {
            "ok": True,
            "niche": niche,
            "metro": metro or None,
            "heat_score": score,
            "tier": tier,
            "competitors": competitors,
            "market_share": market_share,
            "authed": is_paid,
            "buyer": buyer or None,
            "free_remaining": free_remaining if not is_paid else None,
            "blueprint_count": _blueprint_count(niche),
        }
    )


@router.get("/blueprint")
def cortex_blueprint(request: Request, niche: str = "", limit: int = 1):
    """Full Cortex blueprint for a niche (visual_dna + script_dna + market).

    `limit` controls how many blueprint snapshots to return (default 1, max 20).
    """
    is_paid, buyer, free_remaining = _check_auth(request)
    if not is_paid:
        _record_free_call(
            request.client.host if request.client else ""
        )
    if not niche.strip():
        raise HTTPException(400, "niche query parameter required")
    limit = max(1, min(20, int(limit)))
    bp = _fetch_blueprint(niche, limit=limit)
    if not bp:
        raise HTTPException(
            404,
            f"No cortex blueprint found for niche='{niche}'",
        )
    return JSONResponse(
        {
            "ok": True,
            **bp,
            "authed": is_paid,
            "buyer": buyer or None,
            "free_remaining": free_remaining if not is_paid else None,
        }
    )


@router.get("/strategies")
def cortex_strategies(request: Request, niche: str = "", limit: int = 100):
    """Strategy ROI board from the strategy_rank table.

    Returns each (funnel, niche) row with demand / supply / roi / tier.
    Optional `niche` filter; `limit` defaults to 100 (max 500).
    """
    is_paid, buyer, free_remaining = _check_auth(request)
    if not is_paid:
        _record_free_call(
            request.client.host if request.client else ""
        )
    limit = max(1, min(500, int(limit)))
    c = _db()
    try:
        # Lazy-create strategy_rank so the endpoint doesn't 500 on cold boots.
        c.execute(
            """CREATE TABLE IF NOT EXISTS strategy_rank (
                id INTEGER PRIMARY KEY AUTOINCREMENT, funnel TEXT, niche TEXT,
                demand INT, supply INT, roi REAL, tier TEXT, ts TEXT)"""
        )
        q = ("SELECT funnel, niche, demand, supply, roi, tier, ts "
             "FROM strategy_rank")
        params: list = []
        if niche.strip():
            q += " WHERE niche LIKE ?"
            params.append(f"%{niche.strip()}%")
        q += " ORDER BY roi DESC LIMIT ?"
        params.append(limit)
        rows = c.execute(q, params).fetchall()
    finally:
        c.close()
    items = [
        {
            "funnel": r[0], "niche": r[1], "demand": r[2], "supply": r[3],
            "roi": r[4], "tier": r[5], "ts": r[6],
        }
        for r in rows
    ]
    return JSONResponse(
        {
            "ok": True,
            "count": len(items),
            "items": items,
            "authed": is_paid,
            "buyer": buyer or None,
            "free_remaining": free_remaining if not is_paid else None,
        }
    )


@router.post("/signup")
def cortex_signup(req: dict):
    """Self-serve Cortex Intelligence subscription ($299/mo).

    Body: name (str, required) + email? + niche? + wallet? (USDC)
    Returns: {ok, tenant_id, api_key, plan, price_usd, billing_cycle}.
    Issues an X-API-Key usable on all /v1/cortex/* endpoints, and creates
    an si_subscription row so the billing pipeline tracks it.
    """
    name = (req.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    email = (req.get("email") or "").strip()
    niche = (req.get("niche") or "").strip()
    wallet = (req.get("wallet") or "").strip()

    import re
    tenant_id = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or (
        f"cortex_buyer_{int(time.time())}"
    )
    api_key = "cxk_" + secrets.token_urlsafe(24)

    c = _db()
    try:
        # Ensure si_tenant has the columns the existing ring expects.
        tenant_cols = {r[1] for r in c.execute(
            "PRAGMA table_info(si_tenant)"
        ).fetchall()}
        for col in ("api_key", "email", "plan", "name", "niche",
                   "status", "crypto_wallet", "created_at", "updated_at",
                   "billing_cycle"):
            if col not in tenant_cols:
                try:
                    c.execute(f"ALTER TABLE si_tenant ADD COLUMN {col} TEXT")
                except sqlite3.OperationalError:
                    pass
                tenant_cols.add(col)

        # Idempotent: if an active Cortex tenant with this name already has
        # a Cortex key, refresh + return it instead of double-charging.
        existing = c.execute(
            "SELECT tenant_id FROM cortex_api_keys "
            "WHERE tenant_id=? AND status='active'",
            (tenant_id,),
        ).fetchone()
        if existing:
            c.execute(
                "UPDATE cortex_api_keys SET api_key=?, status='active' "
                "WHERE tenant_id=?",
                (api_key, tenant_id),
            )
            c.execute(
                "UPDATE si_tenant SET api_key=?, updated_at=? WHERE tenant_id=?",
                (api_key, _now(), tenant_id),
            )
        else:
            c.execute(
                "INSERT OR REPLACE INTO si_tenant "
                "(tenant_id, name, email, plan, billing_cycle, status, "
                "api_key, crypto_wallet, niche, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (tenant_id, name, email or f"{tenant_id}@cortex.local",
                 PAID_PLAN_NAME, "monthly", "active", api_key, wallet,
                 niche, _now(), _now()),
            )
        # Subscription row so the billing pipeline can charge + revoke.
        c.execute(
            """CREATE TABLE IF NOT EXISTS si_subscription (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT, plan TEXT, per_lead_cents INTEGER,
                seats INTEGER, status TEXT, niche TEXT,
                created_at TEXT, updated_at TEXT)"""
        )
        sub_id = f"sub_cortex_{tenant_id[:12]}"
        c.execute(
            "INSERT OR IGNORE INTO si_subscription "
            "(subscription_id, tenant_id, plan, billing_cycle, seats, "
            "price_cents, status, payment_method, started_at, "
            "current_period_end, created_at, source, niche) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (sub_id, tenant_id, PAID_PLAN_NAME, "monthly", 1,
             PAID_PLAN_CENTS, "active", "crypto_usdt", _now(),
             _now(), _now(), "cortex_api", niche or ""),
        )
        # Persist Cortex key ring entry.
        c.execute(
            "INSERT INTO cortex_api_keys (api_key, tenant_id, status, created_at) "
            "VALUES (?,?,?,?)",
            (api_key, tenant_id, "active", _now()),
        )
        c.commit()
    except sqlite3.Error as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": f"db error: {str(e)[:200]}"},
        )
    finally:
        c.close()
    return JSONResponse(
        {
            "ok": True,
            "tenant_id": tenant_id,
            "api_key": api_key,
            "plan": PAID_PLAN_NAME,
            "price_usd": round(PAID_PLAN_CENTS / 100, 2),
            "billing_cycle": "monthly",
            "niche": niche or None,
            "note": "Use api_key as the X-API-Key header on "
                    "/v1/cortex/scores, /v1/cortex/blueprint, "
                    "/v1/cortex/strategies",
        }
    )


# --------------------------------------------------------------------------
# Helpers used by endpoints above
# --------------------------------------------------------------------------
def _blueprint_count(niche: str) -> int:
    c = _db()
    try:
        row = c.execute(
            "SELECT COUNT(*) FROM cortex_blueprints WHERE niche=?",
            ((niche or "").strip(),),
        ).fetchone()
        return row[0] if row else 0
    except sqlite3.Error:
        return 0
    finally:
        c.close()
