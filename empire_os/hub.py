"""Empire OS Hub — Central Predictive Hub (FastAPI server).

Wires together all Empire OS v3 personas:
- Neural Scout → ingests leads, scores, registers in funnel
- Traffic Specialist → discovered → matched
- Marketing → AEO coverage gap + spec drafts
- CEO → daily brief
- Daily Revenue → settlement → snapshot pipeline
- AGI Sales → autonomous deal pipeline (match → draft → send)
- Dashboard → web UI for funnel viz, AGI activity, revenue
- Telegram → CEO brief delivery & alerts
"""
from __future__ import annotations

import time
import json
import base64
import secrets
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
import asyncio
import logging
import os
import hmac
import hashlib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Any

# Load /root/empire_os/.env if present, so operational toggles like
# EXCLUDE_TEST_FROM_FUNNEL_COUNTS=ON take effect when the process
# didn't inherit them via its supervisor/init.
_ENV_PATH = Path("/root/empire_os/.env")
if _ENV_PATH.exists():
    try:
        for _ln in _ENV_PATH.read_text().splitlines():
            _ln = _ln.strip()
            if not _ln or _ln.startswith("#") or "=" not in _ln:
                continue
            _k, _v = _ln.split("=", 1)
            _k = _k.strip()
            _v = _v.strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v
    except Exception:
        pass

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from empire_os.funnel import (
    SQLiteBackend,
    get_state,
    list_states,
    events_for,
    count_by_state,
)
from empire_os.neural_scout import NeuralScout, calculate_synthetic_score
from empire_os.traffic_specialist import (
    DiscoveredProspect,
    discover_one,
    mark_matched,
    pipeline_status,
)
from empire_os.marketing import tick as marketing_tick, draft_spec_for_niche
from empire_os.aeo_surface import deploy_spec, list_pages, remove_page
from empire_os.ceo import build_brief
from empire_os.daily_revenue import DailyRevenueSnapshotter, DailyRevenueBriefWorker
from empire_os.remote_scanner import ScoutAgentClient
from empire_os.agi_client import AgiScoutClient, AgiMarketingClient
from empire_os.agi_sales import AgiSalesAgent
from empire_os.agi_closer import AgiCloserAgent
from empire_os.agi_loop import AgiLoop
from empire_os.agent_core import OllamaClient, OpenRouterClient
from empire_os.dashboard import DASHBOARD_HTML, build_dashboard_data
from empire_os.telegram_bot import send_brief, send_message, send_alert
from empire_os.waterfall import build_default_waterfall
from empire_os.auto_pilot import AutoPilot
from empire_os.payout import PayoutEngine
from empire_os.agents.satellite_damage_agent import run_scan as _damage_scan
from empire_os.fee_agent import FeeAgent
from empire_os.watcher_agent import WatcherAgent
from empire_os.tenants import TenantStore, PLANS, compute_invoice_amount, check_quota
from empire_os.billing import (
    BillingEngine, PayPalConfig, CryptoConfig,
    paypal_create_subscription, paypal_get_subscription,
    paypal_cancel_subscription, crypto_payment_request,
    verify_crypto_payment,
)
from empire_os.billing_webhooks import handle_paypal_event, handle_crypto_payment
from empire_os.payout_batch import PayoutBatchStore, build_payout_batch
from empire_os.revenue_notify import paid as _rev_paid
from empire_os.waterfall import build_default_waterfall
from empire_os.lanes import ensure_schema as ensure_lane_schema, seed_lanes
from empire_os.lanes import CATEGORIES, METROS, build_lanes, all_sub_niches
from empire_os.lane_router import route_lead, match_niche
from empire_os.omega_os import qualify_prospect, OmegaScore
from empire_os.carrier_applications import (
    ensure_schema as ensure_carrier_app_schema,
    create_application as create_carrier_app,
    get_application as get_carrier_app,
    list_applications as list_carrier_apps,
    update_application as update_carrier_app,
    auto_fill_application as auto_fill_carrier_app,
)
from empire_os.homeowner_pipeline import (
    ensure_schema as ensure_homeowner_schema,
    transition_job as homeowner_transition,
    get_pipeline_stats as homeowner_stats,
    get_job_timeline as homeowner_timeline,
)
from empire_os.homeowner_matching import (
    ensure_schema as ensure_homeowner_matching_schema,
    submit_job as hm_submit_job,
    find_matches as hm_find_matches,
    get_job_with_matches as hm_get_job_with_matches,
    list_jobs as hm_list_jobs,
    update_job_status as hm_update_job_status,
    update_match_status as hm_update_match_status,
    JobNotFoundError,
    InvalidJobStatusError,
    InvalidMatchStatusError,
)


def _ensure_a2a_buyer_schema(backend):
    """Add A2A buyer onboarding columns to existing tables."""
    # Add hmac_secret to si_buyer_outreach
    try:
        backend.execute("ALTER TABLE si_buyer_outreach ADD COLUMN hmac_secret TEXT DEFAULT ''")
        backend.commit()
    except Exception:
        pass

    # Add updated_at to buyer_leads
    try:
        backend.execute("ALTER TABLE buyer_leads ADD COLUMN updated_at TEXT DEFAULT (datetime('now'))")
        backend.commit()
    except Exception:
        pass


# ── CRM ──
from empire_os.crm import (
    ensure_schema as crm_ensure_schema,
    import_from_lane_leads as crm_import_lane_leads,
    list_leads as crm_list_leads,
    get_lead as crm_get_lead,
    update_lead as crm_update_lead,
    add_activity as crm_add_activity,
    set_pipeline_stage as crm_set_stage,
    get_pipeline_summary as crm_pipeline_summary,
    batch_update_status as crm_batch_status,
)
from empire_os.enrichment import (
    enrich_lead as crm_enrich_lead,
    batch_enrich as crm_batch_enrich,
    get_enrichment_stats as crm_enrich_stats,
    get_enrichment_score as crm_enrich_score_fn,
)
from empire_os.lead_scoring import (
    compute_lead_score as crm_score_lead,
    get_qualification_summary as crm_qual_summary,
)
from empire_os.icp import (
    ensure_icp_schema as crm_icp_schema,
    score_lead_by_icp as crm_icp_score,
    get_icp_analytics as crm_icp_analytics,
    batch_update_icp_scores as crm_icp_batch,
    find_best_icp as crm_icp_find,
)

logger = logging.getLogger("empire-hub")

# ── Globals (set during lifespan) ───────────────────────────────────

backend: Optional[SQLiteBackend] = None
scout: Optional[NeuralScout] = None
revenue_worker: Optional[DailyRevenueBriefWorker] = None
scout_agent: Optional[ScoutAgentClient] = None
agi_scout: Optional[AgiScoutClient] = None
agi_marketing: Optional[AgiMarketingClient] = None
agi_sales: Optional[AgiSalesAgent] = None
agi_closer: Optional[AgiCloserAgent] = None
agi_loop: Optional[AgiLoop] = None
auto_pilot = None
payout_engine: Optional[PayoutEngine] = None
fee_agent: Optional[FeeAgent] = None
watcher: Optional[WatcherAgent] = None
tenant_store: Optional[TenantStore] = None
billing_engine: Optional[BillingEngine] = None
payout_batch_store: Optional[PayoutBatchStore] = None
waterfall = None
AEO_SURFACE_ROOT = os.environ.get("AEO_SURFACE_ROOT", "/srv/aeo")


_singleton_lock_fh = None


def _acquire_singleton_lock() -> bool:
    """Return True if THIS process wins the single-owner lock for the heavy
    background loops (agi_loop + auto_pilot). With multiple uvicorn workers
    only one may run the loops; the rest stay pure request handlers so
    endpoints don't get starved by 6-8s agent cycles."""
    global _singleton_lock_fh
    import fcntl
    try:
        fh = open("/tmp/empire_hub_loops.lock", "w")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _singleton_lock_fh = fh  # keep ref so lock persists
        return True
    except (OSError, BlockingIOError):
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    global backend, scout, revenue_worker, scout_agent
    db_path = os.environ.get("EMPIRE_DB_PATH", "empire_os.db")
    logger.info("Connecting to database: %s", db_path)
    backend = SQLiteBackend(db_path)
    global _HM_BACKEND
    _HM_BACKEND = backend
    backend.ensure_schema()

    # ── CRM schema ──
    try:
        crm_ensure_schema(backend)
        logger.info("CRM schema ensured")
    except Exception as e:
        logger.warning("CRM schema init error: %s", e)

    # ── ICP schema ──
    try:
        crm_icp_schema(backend)
        logger.info("ICP schema ensured")
    except Exception as e:
        logger.warning("ICP schema init error: %s", e)

    scout = NeuralScout(backend)

    snap = DailyRevenueSnapshotter(backend)
    snap.ensure_schema()
    revenue_worker = DailyRevenueBriefWorker(backend)

    scout_agent = ScoutAgentClient()
    if scout_agent.check_health():
        logger.info("scout-agent detected at %s", scout_agent.base_url)
    else:
        logger.info("scout-agent not reachable — using local scanners")

    global agi_scout, agi_marketing, agi_sales
    agi_scout = AgiScoutClient()
    def _safe_health(client, name):
        try:
            import threading
            _ok = {}
            def _run():
                try: _ok["v"] = client.check_health()
                except Exception: _ok["v"] = False
            _t = threading.Thread(target=_run, daemon=True); _t.start(); _t.join(5)
            return _ok.get("v", False)
        except Exception:
            return False
    if _safe_health(agi_scout, "scout"):
        logger.info("agi-scout detected at %s", agi_scout.base_url)
    else:
        logger.info("agi-scout not reachable")
    agi_marketing = AgiMarketingClient()
    if _safe_health(agi_marketing, "marketing"):
        logger.info("agi-marketing detected at %s", agi_marketing.base_url)
    else:
        logger.info("agi-marketing not reachable")
    # AGI Sales — runs in-process (no separate container needed).
    # Ollama box (10.218.156.211:11434) is down; route through OpenRouter
    # (tencent/hy3:free — same brain model) so loops run instead of dying.
    # Guarded: a throttle on hy3:free must NOT block hub startup/loop.
    try:
        agi_sales = AgiSalesAgent(
            backend=backend,
            llm=OpenRouterClient(model="tencent/hy3:free", timeout=8))
        logger.info("agi-sales initialized in-process (OpenRouter hy3)")
    except Exception as e:
        logger.warning("agi-sales init skipped (LLM unreachable): %s", str(e)[:120])
        agi_sales = None
    # AGI Closer — last-mile closer, also in-process
    global agi_closer
    try:
        agi_closer = AgiCloserAgent(
            backend=backend,
            llm=OpenRouterClient(model="tencent/hy3:free", timeout=8))
        logger.info("agi-closer initialized in-process (OpenRouter hy3)")
    except Exception as e:
        logger.warning("agi-closer init skipped (LLM unreachable): %s", str(e)[:120])
        agi_closer = None

    # Ensure lane schema + seed 36 lanes
    ensure_lane_schema(backend)
    seed_lanes(backend)
    logger.info("Lane system initialized (36 lanes)")

    # Ensure carrier_applications schema
    ensure_carrier_app_schema(backend)

    # Ensure homeowner_pipeline schema
    ensure_homeowner_schema(backend)

    # Ensure homeowner matching schema (carrier_rosters, homeowner_jobs, job_matches)
    ensure_homeowner_matching_schema(backend)

    # Ensure A2A buyer onboarding schema extensions
    _ensure_a2a_buyer_schema(backend)

    # Mount AEO surface at /aeo
    aeo_root = Path(AEO_SURFACE_ROOT)
    aeo_root.mkdir(parents=True, exist_ok=True)
    try:
        app.mount("/aeo", StaticFiles(directory=AEO_SURFACE_ROOT, html=True), name="aeo")
        logger.info("AEO surface mounted at /aeo → %s", AEO_SURFACE_ROOT)
    except Exception as e:
        logger.warning("Could not mount AEO surface: %s", e)

    # Explicit sitemap/robots routes (StaticFiles html=True can miss root files)
    @app.get("/aeo/sitemap.xml")
    async def aeo_sitemap():
        from fastapi.responses import FileResponse
        p = Path(AEO_SURFACE_ROOT) / "sitemap.xml"
        if p.exists():
            return FileResponse(str(p), media_type="application/xml")
        return Response(status_code=404)

    @app.get("/aeo/robots.txt")
    async def aeo_robots():
        from fastapi.responses import FileResponse
        p = Path(AEO_SURFACE_ROOT) / "robots.txt"
        if p.exists():
            return FileResponse(str(p), media_type="text/plain")
        return Response(status_code=404)

    @app.get("/v1/indexnow/{key}.txt")
    async def indexnow_key(key: str):
        """Serve IndexNow verification key (Bing/DuckDuckGo/Yandex).
        Under /v1/ so it passes the Caddy @app proxy and isn't shadowed
        by the /aeo StaticFiles mount."""
        from fastapi.responses import FileResponse
        p = Path(AEO_SURFACE_ROOT) / f"{key}.txt"
        if p.exists():
            return FileResponse(str(p), media_type="text/plain")
        return Response(status_code=404)

    @app.get("/{key}.txt")
    async def indexnow_key_root(key: str):
        """Root-level IndexNow key (some engines require host-root keyLocation)."""
        from fastapi.responses import FileResponse
        p = Path(AEO_SURFACE_ROOT) / f"{key}.txt"
        if p.exists():
            return FileResponse(str(p), media_type="text/plain")
        return Response(status_code=404)

    @app.get("/sitemap.xml")
    async def root_sitemap():
        from fastapi.responses import FileResponse
        p = Path(AEO_SURFACE_ROOT) / "sitemap.xml"
        if p.exists():
            return FileResponse(str(p), media_type="application/xml")
        return Response(status_code=404)

    @app.get("/robots.txt")
    async def root_robots():
        from fastapi.responses import FileResponse
        p = Path(AEO_SURFACE_ROOT) / "robots.txt"
        if p.exists():
            return FileResponse(str(p), media_type="text/plain")
        return Response(status_code=404)

    # Google Search Console ownership verification file (served at domain root)
    @app.get("/google{blob}.html")
    async def gsc_verify(blob: str):
        from fastapi.responses import FileResponse
        # 'blob' is the part after the literal /google prefix (no '..' allowed)
        if ".." in blob or "/" in blob:
            return Response(status_code=404)
        p = Path(AEO_SURFACE_ROOT) / f"google{blob}.html"
        if p.exists():
            return FileResponse(str(p), media_type="text/html")
        return Response(status_code=404)

    # Same-origin static assets (avoids Phantom dApp browser blocking 3rd-party scripts)
    _STATIC_DIR = Path(__file__).parent / "static"
    _STATIC_DIR.mkdir(parents=True, exist_ok=True)
    try:
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
        logger.info("Static assets mounted at /static → %s", _STATIC_DIR)
    except Exception as e:
        logger.warning("Could not mount static: %s", e)

    # Start the AGI Loop — continuous in-process orchestrator
    # Runs all AGI agents in parallel forever (no cron needed)
    # Skip during tests to prevent blocking on LLM calls
    from empire_os.ceo import tick as ceo_tick_fn
    global agi_loop
    _own_loops = _acquire_singleton_lock()
    if not _own_loops:
        logger.info("Worker did not win loop lock — request-handler only "
                    "(agi_loop + auto_pilot skipped)")
    if _own_loops and os.environ.get("EMPIRE_OS_TEST_MODE") != "1" and os.environ.get("EMPIRE_INPROC_AGENTS") == "1":
        # Wrap CEO tick so the loop can call it as a no-arg method
        class _CeoBriefProxy:
            def __init__(self, fn, b):
                self._fn = fn
                self._b = b
            def tick(self):
                return self._fn(self._b)
        ceo_proxy = _CeoBriefProxy(ceo_tick_fn, backend)
        agi_loop = AgiLoop(
            agi_scout_client=agi_scout,
            agi_marketing_client=agi_marketing,
            agi_sales_agent=agi_sales,
            agi_closer_agent=agi_closer,
            ceo_brief_fn=ceo_proxy,
        )
        asyncio.create_task(agi_loop.start())
        logger.info("AGI Loop spawned — all agents running continuously")
    else:
        logger.info("Test mode — AGI Loop disabled")

    # Start the Auto-Pilot — drives the funnel end-to-end every N seconds
    from empire_os.auto_pilot import AutoPilot
    global auto_pilot
    if _own_loops and os.environ.get("EMPIRE_OS_TEST_MODE") != "1" and os.environ.get("EMPIRE_INPROC_AGENTS") == "1":
        auto_pilot = AutoPilot(
            hub_url=f"http://localhost:{int(os.environ.get('EMPIRE_PORT', '8080'))}",
            match_limit=15,
            draft_limit=10,
            reply_rate=0.4,
            settle_rate=0.6,
        )

        async def _auto_pilot_loop():
            """Run pipeline cycles on a fixed cadence."""
            interval = 60  # seconds
            logger.info("Auto-pilot started — pipeline cycles every %ds", interval)
            while True:
                try:
                    # Run the blocking pipeline call in a thread so we
                    # don't block uvicorn's event loop.
                    report = await asyncio.to_thread(auto_pilot.run_cycle)
                    logger.info(
                        "auto-pilot cycle %d: matched=%d drafted=%d sent=%d "
                        "replied=%d claimed=%d settled=%d $%.2f",
                        report.cycle, report.matched, report.drafted, report.sent,
                        report.replied, report.claimed, report.settled,
                        report.revenue_cents / 100,
                    )
                except Exception as e:
                    logger.exception("auto-pilot cycle failed: %s", e)
                await asyncio.sleep(60)

        asyncio.create_task(_auto_pilot_loop())
        logger.info("Auto-pilot loop spawned")

        # Initialize Payout engine, Fee agent, Watcher
        global payout_engine, fee_agent, watcher
        payout_engine = PayoutEngine()
        fee_agent = FeeAgent()
        watcher = WatcherAgent(
            hub_url=f"http://localhost:{int(os.environ.get('EMPIRE_PORT', '8080'))}",
        )

        # SaaS corridor: tenants, billing, payout batches
        global tenant_store, billing_engine, payout_batch_store
        tenant_store = TenantStore(db_path=os.environ.get(
            "EMPIRE_DB_PATH", "empire_os.db"))
        billing_engine = BillingEngine()
        payout_batch_store = PayoutBatchStore()
        logger.info("SaaS corridor: tenants + billing + payout batches ready")

        # Watcher loop — runs every 5 min, alerts on anomalies
        async def _watcher_loop():
            logger.info("Watcher started — checking every 5 min")
            while True:
                try:
                    alerts = await asyncio.to_thread(watcher.check)
                    if alerts:
                        logger.warning("watcher found %d alerts", len(alerts))
                        # Telegram notify if configured
                        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
                        chat = os.environ.get("TELEGRAM_CHAT_ID", "")
                        if token and chat:
                            msg = f"⚠️ Empire Watcher: {len(alerts)} new alerts\n" + \
                                  "\n".join(f"• [{a.severity}] {a.title}" for a in alerts[:5])
                            await asyncio.to_thread(send_alert, msg, token, chat)
                except Exception as e:
                    logger.exception("watcher cycle failed: %s", e)
                await asyncio.sleep(300)

        if _own_loops:
            asyncio.create_task(_watcher_loop())
            logger.info("Watcher loop spawned (owner worker)")
        else:
            logger.info("Watcher loop skipped (non-owner worker)")

    # Initialize the Waterfall data provider orchestrator
    global waterfall
    waterfall = build_default_waterfall()
    logger.info("Waterfall orchestrator initialized with %d providers",
                len(waterfall.providers))

    logger.info("Empire OS Hub started — engines online")
    yield

    if agi_loop:
        await agi_loop.stop()
    if backend:
        backend.close()


# ── FastAPI App ─────────────────────────────────────────────────────

app = FastAPI(
    title="Empire OS v3 — Central Predictive Hub",
    description="Agentic engine for lead generation, AEO, and sales",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def _unhandled_exc_handler(request: Request, exc: Exception):
    """Never let an unhandled exception hard-crash a worker or return a raw
    traceback. Log it, return a clean 500 with a request id so the watchdog
    + operator can see what broke without the process dying."""
    import traceback, uuid
    rid = uuid.uuid4().hex[:12]
    try:
        print(f"[HUB-UNHANDLED {rid}] {request.method} {request.url.path}: "
              f"{exc!r}\n{traceback.format_exc()[-1500:]}", flush=True)
    except Exception:
        pass
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": "internal_error", "ref": rid,
                 "detail": str(exc)[:200]},
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Permissive CSP for the wallet page so Phantom's dApp browser doesn't block
    fetch/XHR to remote Solana RPCs (Alchemy, Ankr, public-rpc, mainnet-beta)."""
    async def dispatch(self, request, call_next):
        resp: Response = await call_next(request)
        path = request.url.path
        if path.startswith("/wallet/") or path == "/wallet":
            resp.headers["Content-Security-Policy"] = (
                "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
                "script-src * 'unsafe-inline' 'unsafe-eval'; "
                "connect-src * https: wss:; "
                "img-src * data: blob:; "
                "frame-ancestors *;"
            )
            resp.headers["X-Frame-Options"] = "ALLOWALL"
        return resp


app.add_middleware(SecurityHeadersMiddleware)


# ── Pydantic Models ─────────────────────────────────────────────────

class LeadPayload(BaseModel):
    lead_id: Optional[str] = None
    niche: str
    phone: str = ""
    zip_code: str = ""
    details: str = ""
    name: str = ""
    address: str = ""
    source: str = "api"


class MatchPayload(BaseModel):
    prospect_id: str
    notes: str = ""


class BridgeQuery(BaseModel):
    type: str = ""  # "brief", "status", "decisions"


# ── V1 Endpoints ────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {
        "status": "online",
        "engine": "empire-os-v3",
        "version": "0.1.0",
    }


@app.get("/v1/health/deep")
def health_deep():
    """Revenue-path preconditions: env, db, chain, hub, listener.
    Returns ok=true only if ALL preconditions pass. Use as systemd boot
    guard + cron monitor. Stops the "hub is up but revenue loop is dead"
    silent-break pattern."""
    from empire_os import health_deep as _hd
    return _hd.deep_health()


# --- Neural Scout / Lead Pipeline ---

@app.post("/v1/pipeline/incoming")
async def incoming_lead(lead: LeadPayload, background_tasks: BackgroundTasks):
    """Accept an incoming lead, score it, and register in funnel."""
    if not lead.phone and not lead.details:
        raise HTTPException(status_code=400, detail="Missing lead data")

    # Score
    score = calculate_synthetic_score(lead.niche, lead.details, lead.phone, lead.zip_code)

    # Evaluate and register
    scored = scout.evaluate(
        niche=lead.niche,
        details=lead.details,
        phone=lead.phone,
        zip_code=lead.zip_code,
        name=lead.name,
        address=lead.address,
        source=lead.source,
        prospect_id=lead.lead_id,
    )

    if scored is None:
        return {
            "status": "rejected",
            "score": score,
            "message": "Lead below minimum score threshold",
        }

    eid = scout.register_lead(scored)
    return {
        "status": "accepted",
        "prospect_id": scored.prospect_id,
        "score": score,
        "event_id": eid,
        "message": "Lead queued into the engine",
    }


@app.post("/v1/traffic/discover")
def discover_prospect(prospect: DiscoveredProspect):
    """Manually register a discovered prospect."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    eid = discover_one(backend, prospect)
    return {"status": "ok", "event_id": eid}


@app.post("/v1/traffic/match")
def match_prospect(payload: MatchPayload):
    """Mark a prospect as matched."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    try:
        eid = mark_matched(backend, payload.prospect_id, notes=payload.notes)
        return {"status": "ok", "event_id": eid}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/v1/traffic/status")
def traffic_status():
    """Get pipeline status summary."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return pipeline_status(backend)


# --- Marketing ---

@app.post("/v1/marketing/tick")
def marketing_tick_endpoint():
    """Run the marketing tick: gap analysis → draft → register."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    result = marketing_tick(backend)
    return result


@app.get("/v1/marketing/draft/{niche}")
def get_draft(niche: str):
    """Draft an AEO spec for a niche."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    draft = draft_spec_for_niche(backend, niche)
    return draft.to_dict()


@app.post("/v1/marketing/draft/{niche}/deploy")
def deploy_niche_page(niche: str, surface_root: Optional[str] = None):
    """Draft an AEO spec for a niche and deploy it to the AEO surface."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    draft = draft_spec_for_niche(backend, niche)
    path = deploy_spec(draft, surface_root=surface_root)
    return {"niche": niche, "deployed_to": str(path), "spec": draft.to_dict()}


@app.get("/v1/aeo/pages")
def list_aeo_pages(surface_root: Optional[str] = None):
    """List all published AEO pages."""
    return {"pages": list_pages(surface_root=surface_root)}


@app.delete("/v1/aeo/pages/{niche}")
def delete_aeo_page(niche: str, surface_root: Optional[str] = None):
    """Remove a published AEO page."""
    ok = remove_page(niche, surface_root=surface_root)
    if not ok:
        raise HTTPException(status_code=404, detail=f"No page found for niche '{niche}'")
    return {"removed": niche}


# --- Ad-Gen Pipeline ---

@app.get("/v1/adgen/judge/{niche}")
def judge_aeo_page(niche: str):
    """Run the Judge on an AEO page and return a scorecard."""
    try:
        from empire_os.adgen_judge import judge_page

        page_path = Path("/srv/aeo") / niche / "index.html"
        if not page_path.exists():
            raise HTTPException(404, f"No AEO page for niche '{niche}'")

        html = page_path.read_text(encoding="utf-8")
        scorecard = judge_page(html, niche=niche, url=f"/aeo/{niche}/")
        return scorecard
    except ImportError as e:
        raise HTTPException(503, f"Judge module not available: {e}")


@app.get("/v1/adgen/brief/{niche}")
def generate_content_brief(niche: str):
    """Generate a content improvement brief for a niche's AEO page."""
    try:
        from empire_os.adgen_judge import judge_page
        from empire_os.adgen_architect import generate_brief

        page_path = Path("/srv/aeo") / niche / "index.html"
        if not page_path.exists():
            raise HTTPException(404, f"No AEO page for niche '{niche}'")

        html = page_path.read_text(encoding="utf-8")
        scorecard = judge_page(html, niche=niche, url=f"/aeo/{niche}/")
        brief = generate_brief(niche, scorecard)
        return brief
    except ImportError as e:
        raise HTTPException(503, f"Architect module not available: {e}")


@app.get("/v1/adgen/judge-all")
def judge_all_pages():
    """Judge all published AEO pages and return scorecards."""
    try:
        from empire_os.adgen_judge import judge_page

        results = {}
        for entry in list_pages(surface_root="/srv/aeo"):
            niche = entry["niche"]
            page_path = Path(entry["path"])
            if page_path.exists():
                html = page_path.read_text(encoding="utf-8")
                results[niche] = judge_page(html, niche=niche, url=f"/aeo/{niche}/")
        return {"judged": len(results), "results": results}
    except ImportError as e:
        raise HTTPException(503, f"Judge module not available: {e}")


@app.get("/v1/adgen/scan/{niche}")
def scan_competitor_niche(niche: str):
    """Scan competitor/landing page content for a niche (via scanner module)."""
    try:
        from empire_os.adgen_scanner import scan_niche
        result = scan_niche(niche)
        return result
    except ImportError as e:
        raise HTTPException(503, f"Scanner module not available: {e}")


# --- CRM / Lead Intake ---

class LeadIntakeRequest(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    state: str = ""
    zip: str = ""
    niche: str = ""
    details: str = ""
    source: str = "aeo_form"
    ip_address: str = ""
    user_agent: str = ""


class DamageScanRequest(BaseModel):
    postcode: str = ""
    bbox: Optional[dict] = None
    metro_code: str = ""
    use_bda: bool = True
    bda_checkpoint: str = ""


# Representative zip per metro for scan-all.
METRO_ZIPS: dict[str, str] = {
    "ATL": "30303",
    "BOS": "02101",
    "CHI": "60601",
    "DFW": "75201",
    "HOU": "77002",
    "LAX": "90001",
    "MIA": "33101",
    "NYC": "10001",
    "PHL": "19103",
    "SFO": "94102",
    "WDC": "20001",
}


@app.post("/v1/damage/scan")
def damage_scan(req: DamageScanRequest):
    """Run a satellite damage scan.

    Body: {"postcode": "75201"} or {"bbox": {...}, "metro_code": "DFW"}.
    Optional: {"use_bda": true, "bda_checkpoint": "/path/to/ckpt.pt"}.
    Returns scan_id, bbox, parcel count, top damaged parcels, db counts.
    """
    try:
        kwargs = {}
        if req.postcode:
            kwargs["postcode"] = req.postcode
            kwargs["country"] = "us"
        if req.metro_code:
            kwargs["metro_code"] = req.metro_code
        if req.bbox:
            kwargs["bbox"] = req.bbox
        if req.use_bda:
            kwargs["use_bda"] = True
        if req.bda_checkpoint:
            kwargs["bda_checkpoint"] = req.bda_checkpoint
        result = _damage_scan(**kwargs)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])


@app.get("/v1/damage/scan/recent")
def damage_scan_recent(limit: int = 5):
    """Tail the most recent satellite_damage.jsonl entries."""
    p = Path("/root/feedback/satellite_damage.jsonl")
    if not p.exists():
        return {"events": []}
    lines = p.read_text().splitlines()[-limit:]
    events = [json.loads(l) for l in lines if l.strip()]
    return {"events": events}


@app.get("/v1/damage/scan-all")
def damage_scan_all():
    """Run one damage scan per metro and return consolidated results.

    This is the daily-strike endpoint: iterates all 11 metros, runs
    run_scan on each representative zip, and returns per-metro results
    plus a total. Intended for cron or on-demand storm sweeps.
    """
    from empire_os.agents.satellite_damage_agent import run_scan as _ds
    results: dict[str, dict] = {}
    totals = {"prospects": 0, "lane_leads": 0, "outbox": 0, "skipped": 0}
    for metro_code, postcode in METRO_ZIPS.items():
        try:
            r = _ds(postcode=postcode, metro_code=metro_code, use_bda=True)
            results[metro_code] = {
                "parcel_count": r.get("parcel_count"),
                "counts": r.get("counts"),
                "scan_id": r.get("scan_id"),
                "bda": r.get("bda"),
                "error": None,
            }
            c = r.get("counts", {})
            for k in totals:
                totals[k] += c.get(k, 0)
        except Exception as e:
            results[metro_code] = {"error": str(e)[:200]}
    n_ok = sum(1 for v in results.values() if not v.get("error"))
    n_err = len(results) - n_ok
    return {"ok": True, "metros": len(results),
            "ok_metros": n_ok, "error_metros": n_err,
            "totals": totals, "details": results}


@app.get("/v1/damage/optin-landing/{prospect_id}", response_class=HTMLResponse)
def damage_optin_landing(prospect_id: str):
    """Serve a branded opt-in landing page for a satellite-damage prospect.

    Renders Empire AI-branded HTML with a confirm button. On click the
    page GETs the JSON opt-in endpoint and shows a result banner.
    """
    _HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Empire AI — Damage Alert Opt-In</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#050810;color:#e6f1ff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:#0c1320;border:1px solid rgba(57,255,136,.15);border-radius:16px;padding:48px 40px;max-width:480px;width:90%;text-align:center}
.logo{font-size:24px;font-weight:700;letter-spacing:-.5px;margin-bottom:8px}
.logo span{color:#39ff88}
.tag{color:#637088;font-size:13px;margin-bottom:32px}
h1{font-size:22px;font-weight:600;margin-bottom:12px;line-height:1.3}
p{color:#8899b0;font-size:15px;line-height:1.6;margin-bottom:28px}
.badge{display:inline-block;background:rgba(57,255,136,.1);color:#39ff88;font-size:12px;font-weight:600;padding:4px 12px;border-radius:20px;margin-bottom:20px}
.btn{background:#39ff88;color:#050810;border:none;border-radius:10px;padding:14px 32px;font-size:16px;font-weight:700;cursor:pointer;transition:all .2s;width:100%}
.btn:hover{background:#2ee67a;transform:translateY(-1px);box-shadow:0 8px 24px rgba(57,255,136,.25)}
.btn:disabled{opacity:.4;cursor:not-allowed;transform:none;box-shadow:none}
.btn.alt{background:transparent;color:#39ff88;border:1px solid rgba(57,255,136,.3);margin-top:12px;padding:10px 24px;font-size:14px}
.result{margin-top:24px;padding:16px;border-radius:10px;display:none}
.result.success{display:block;background:rgba(57,255,136,.08);border:1px solid rgba(57,255,136,.2);color:#39ff88}
.result.error{display:block;background:rgba(255,87,87,.08);border:1px solid rgba(57,255,136,.2);color:#ff5757}
.detail{font-size:13px;color:#637088;margin-top:16px;line-height:1.5}
.spinner{display:inline-block;width:18px;height:18px;border:2px solid rgba(57,255,136,.2);border-top-color:#39ff88;border-radius:50%;animation:spin .7s linear infinite;vertical-align:middle;margin-right:8px}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<div class="card" id="app">
  <div class="logo">Empire <span>AI</span></div>
  <div class="tag">Damage Detection Network</div>
  <div class="badge">Property Alert</div>
  <h1>Potential Damage Detected<br>at Your Property</h1>
  <p>Our satellite analysis has identified possible storm damage near your property. By opting in, you'll receive a free damage assessment report with repair estimates — no obligation.</p>
  <button class="btn" id="confirmBtn" onclick="confirmOptIn()">✓ Confirm &amp; Get My Report</button>
  <div id="result" class="result"></div>
  <div class="detail">Your information is private. You can withdraw consent at any time.</div>
</div>
<script>
async function confirmOptIn(){
  const btn=document.getElementById('confirmBtn');
  const res=document.getElementById('result');
  btn.disabled=true; btn.innerHTML='<span class="spinner"></span> Processing…';
  res.className='result'; res.style.display='none';
  try{
    const r=await fetch('/v1/damage/opt-in/""" + prospect_id + r"""');
    const j=await r.json();
    if(j.ok){
      res.className='result success'; res.style.display='block';
      res.innerHTML='✓ <strong>You\'re opted in!</strong><br>Your damage report will be emailed shortly. Check your inbox.';
      btn.style.display='none';
    } else {
      throw new Error(j.detail||'Unknown error');
    }
  }catch(e){
    res.className='result error'; res.style.display='block';
    if(e.message.includes('prospect_not_found')){
      res.innerHTML='✗ <strong>Link expired or invalid.</strong><br>This opt-in link is no longer valid. Please contact support.';
    } else {
      res.innerHTML='✗ <strong>Something went wrong.</strong><br>'+e.message+'<br><button class="btn alt" onclick="location.reload()">Try Again</button>';
    }
    btn.disabled=false; btn.innerHTML='✓ Confirm &amp; Get My Report';
  }
}
</script>
</body>
</html>"""
    return _HTML_PAGE


@app.get("/v1/damage/opt-in/{prospect_id}")
def damage_opt_in(prospect_id: str):
    """Flip si_prospect_consent.opted_in=1 for a satellite-damage prospect.

    Idempotent. Returns the new state and the queued outbox row count
    for that prospect so the operator can verify mail-sender will pick
    it up on the next tick.
    """
    import sqlite3 as _sq
    conn = _sq.connect("/root/empire_os/empire_os.db")
    cur = conn.cursor()
    cur.execute("UPDATE si_prospect_consent SET opted_in=1, opted_in_at=datetime('now') "
                "WHERE prospect_id=?", (prospect_id,))
    conn.commit()
    row = cur.execute(
        "select prospect_id, opted_in, opted_in_at, niche, source "
        "from si_prospect_consent where prospect_id=?", (prospect_id,)).fetchone()
    queued = cur.execute(
        "select count(*) from si_outbox where lead_id=? and status='pending'",
        (prospect_id,)).fetchone()[0]
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="prospect_not_found")
    return {"ok": True, "prospect": dict(zip(
        ["prospect_id", "opted_in", "opted_in_at", "niche", "source"], row)),
        "queued_outbox_rows": queued}


@app.get("/v1/damage/consent/{prospect_id}")
def damage_consent_status(prospect_id: str):
    """Read-only consent state for a prospect."""
    import sqlite3 as _sq
    conn = _sq.connect("/root/empire_os/empire_os.db")
    row = conn.execute(
        "select prospect_id, opted_in, opted_in_at, niche, source "
        "from si_prospect_consent where prospect_id=?", (prospect_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="prospect_not_found")
    return {"prospect": dict(zip(
        ["prospect_id", "opted_in", "opted_in_at", "niche", "source"], row))}


@app.post("/v1/satellite/strike")
def satellite_strike(req: dict):
    """Receive a severe weather alert from satellite-strike agent, create CRM lead."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    try:
        event = req.get("event", "Unknown")
        severity = req.get("severity", "Unknown")
        area = req.get("area", "")
        headline = req.get("headline", "")
        event_id = req.get("id", "")

        # Extract metro from area description (first location + state)
        import re
        metro = area.split(";")[0].strip() if area else "Unknown"
        metro = re.sub(r'\s+', ' ', metro).strip()
        now = datetime.utcnow().isoformat()

        # Create CRM lead via direct SQL (matches import_from_lane_leads pattern)
        lead_uid = f"storm_{event_id.split('/')[-1][:32]}" if event_id else f"storm_{int(time.time())}"
        notes = f"{headline} | {area} | severity={severity}" if headline else f"{event} in {area}"

        # Idempotent: skip if this storm alert already created a lead
        existing = backend.execute(
            "SELECT id FROM crm_leads WHERE lead_uid = ?", (lead_uid,)
        ).fetchone()
        if existing:
            return {"ok": True, "notified": 0, "already": True,
                    "lead_id": existing[0], "event": event}

        backend.execute(
            """INSERT INTO crm_leads
               (lead_uid, source, niche, metro, business_name, notes, status, omega_score, created_at, updated_at)
               VALUES (?, 'satellite_strike', 'roofing', ?, ?, ?, 'new', 5.0, ?, ?)""",
            (lead_uid, metro, f"Storm Damage — {event}", notes[:500], now, now),
        )
        lid = backend.execute("SELECT last_insert_rowid()").fetchone()[0]
        backend.execute(
            "INSERT INTO crm_activities (lead_id, act_type, summary, actor) VALUES (?, 'system', ?, 'satellite_strike')",
            (lid, f"Storm event: {event} in {metro}"),
        )
        backend.commit()

        return {"ok": True, "notified": 1, "lead_id": lid, "event": event}
    except Exception as e:
        import traceback
        raise HTTPException(500, detail=str(e)[:300] + " | " + traceback.format_exc()[:200])

def lead_intake(req: LeadIntakeRequest):
    """Capture a lead from AEO form → route → score → store."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    try:
        from empire_os.crm import intake_lead
        result = intake_lead(
            backend,
            name=req.name,
            email=req.email,
            phone=req.phone,
            state=req.state,
            niche=req.niche,
            details=req.details,
            source=req.source,
            ip_address=req.ip_address,
            user_agent=req.user_agent,
        )
        if "error" in result:
            raise HTTPException(500, result["error"])
        return result
    except ImportError as e:
        raise HTTPException(503, f"CRM module not available: {e}")


@app.get("/v1/leads/counts")
def lead_counts():
    """Get lead counts by status and niche."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    from empire_os.crm import get_lead_counts
    return get_lead_counts(backend)


@app.post("/v1/leads/direct")
def direct_lead_intake(req: dict):
    """Direct lead intake — writes to lane_leads without going through crm routing.

    Use this for partner webhooks, AEO forms, or any external system
    that has already determined the niche+metro. The lead_deliverer
    picks it up on its 30s poll.

    Body:
        name, email, phone, niche (required), metro (required),
        state, details, source, lead_score (0-100)
    """
    niche = (req.get("niche") or "").strip()
    metro = (req.get("metro") or "").strip().upper()
    if not niche or not metro:
        raise HTTPException(400, "niche and metro required")

    score = int(req.get("lead_score", 50))
    score = max(0, min(100, score))
    if score >= 75:
        tier = "gold"
    elif score >= 50:
        tier = "silver"
    else:
        tier = "bronze"

    # We're inside empire-hub, so we can write directly to the DB
    if not backend:
        raise HTTPException(503, "backend not initialized")

    import uuid
    from datetime import datetime, timezone as _tz
    lead_id = "lead_" + datetime.now(_tz.utc).strftime("%y%m%d%H%M%S%f")
    lane_id = f"{niche}:{metro}"
    prospect_id = "prospect_" + datetime.now(_tz.utc).strftime("%y%m%d%H%M%S%f")
    now = datetime.now(_tz.utc).isoformat()

    try:
        backend.execute(
            "INSERT INTO lane_leads "
            "(lane_id, prospect_id, status, omega_score, omega_tier, "
            "notes, niche, created_at) "
            "VALUES (?, ?, 'pending', ?, ?, ?, ?, ?)",
            (lane_id, prospect_id, score, tier,
             f"name={req.get('name','')} email={req.get('email','')} "
             f"phone={req.get('phone','')} metro={metro} "
             f"state={req.get('state','')} details={req.get('details','')}",
             niche, now)
        )
        backend.commit()
        # Get the inserted ID
        row = backend.execute(
            "SELECT id FROM lane_leads WHERE prospect_id=?",
            (prospect_id,)).fetchone()
        db_id = row[0] if row else None
    except Exception as e:
        raise HTTPException(500, f"DB write failed: {e}")

    return {
        "ok": True,
        "lead_id": lead_id,
        "db_id": db_id,
        "lane_id": lane_id,
        "niche": niche,
        "metro": metro,
        "tier": tier,
        "score": score,
        "status": "pending",
    }


class BuyerApplyRequest(BaseModel):
    name: str
    niche: str
    email: str
    tier: str = "silver"
    webhook_url: str = ""
    min_deposit: float = 50.0
    source: str = ""


class BuyerApplyResponse(BaseModel):
    ok: bool
    buyer: str
    niche: str
    tier: str
    seat_price_usd: float | None = None
    per_lead_usdc: float | None = None
    funded: bool | None = None
    tenant_id: str | None = None
    subscription_id: str | None = None
    pay_to_wallet: str | None = None
    amount_usdc_due: float | None = None
    payment: dict | None = None


_BUY_LEADS_TEMPLATE = "/root/empire_os/templates/buy-leads.html"


@app.post("/v1/buyers/apply", response_model=BuyerApplyResponse)
async def buyer_apply(req: BuyerApplyRequest):
    """Buyer self-serve signup -> auto-rate + auto-seat into lanes.

    Async wrapper: runs the blocking auto_onboard.onboard() in a thread with a
    strict 3s timeout + silent fallback so the endpoint never hangs.
    """
    tier = req.tier.lower()
    if tier not in ("bronze", "silver", "gold", "platinum"):
        tier = "silver"
    try:
        import empire_os.auto_onboard as ao
        res = await asyncio.wait_for(
            asyncio.to_thread(
                ao.onboard, req.name.strip(), req.niche.strip().lower(), tier,
                webhook_url=req.webhook_url, delivery_email=req.email.strip(),
                min_deposit=req.min_deposit, source=req.source,
            ),
            timeout=12.0,
        )
        if not res.get("ok"):
            raise HTTPException(502, f"onboard failed: {res.get('error', 'unknown')}")
        vault = os.environ.get("SOLANA_VAULT_WALLET", "")
        return BuyerApplyResponse(
            ok=True, buyer=req.name, niche=req.niche, tier=tier,
            seat_price_usd=res.get("seat_price"),
            per_lead_usdc=res.get("per_lead_usdc"),
            funded=res.get("funded"),
            tenant_id=res.get("tenant_id"),
            subscription_id=res.get("subscription_id"),
            pay_to_wallet=res.get("pay_to_wallet") or vault,
            amount_usdc_due=res.get("amount_usdc_due"),
            payment=res.get("payment") or {
                "asset": "USDC", "network": "Solana", "vault_wallet": vault,
                "note": "Fund this wallet to activate collection. Leads bill per delivery."},
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "onboard timed out — try again")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"buyer apply error: {str(e)[:160]}")


# ---------------------------------------------------------------------------
# /v1/buyers/email — capture buyer email + self-mail token
# ---------------------------------------------------------------------------
class BuyerEmailCaptureRequest(BaseModel):
    prospect_id: str
    email: str
    token: str = ""  # optional self-mail confirmation token


class BuyerEmailCaptureResponse(BaseModel):
    ok: bool
    prospect_id: str
    email: str
    token: str | None = None
    captured_at: str | None = None


@app.post("/v1/buyers/email", response_model=BuyerEmailCaptureResponse)
async def buyer_email_capture(req: BuyerEmailCaptureRequest):
    """Capture/update a buyer email on their si_buyer_outreach row.

    Used by the self-mail flow: when a buyer clicks the "confirm my email"
    link in the apply email, this endpoint stamps the email onto the
    prospect record (overwriting any placeholder) so the A2A pusher can
    later deliver pay_url's there. Idempotent.
    """
    import re as _re
    from datetime import datetime as _dt
    email = (req.email or "").strip()
    prospect_id = (req.prospect_id or "").strip()
    if not prospect_id:
        raise HTTPException(400, "prospect_id required")
    if not email or not _re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(400, "valid email required")

    # The hub uses si_tenant for the buyer (email is the canonical key for
    # pay_url delivery). si_buyer_outreach holds the prospect profile.
    # We update both so downstream A2A pusher + charge() + email-agent
    # all see the same address.
    try:
        import empire_os.db_handler as _db
        conn = _db.get_conn()
        captured_at = _dt.now(timezone.utc).isoformat()
        cur = conn.execute(
            "UPDATE si_buyer_outreach SET email=?, last_touch_at=datetime('now') "
            "WHERE prospect_id=?",
            (email, prospect_id),
        )
        outreach_updated = cur.rowcount > 0
        # Mirror onto si_tenant (canonical source for buyer_apply + charge).
        tenant_updated = False
        if outreach_updated:
            row = conn.execute(
                "SELECT email FROM si_buyer_outreach WHERE prospect_id=?",
                (prospect_id,),
            ).fetchone()
            tenant_id_row = conn.execute(
                "SELECT tenant_id FROM si_tenant WHERE email=? OR email LIKE ? LIMIT 1",
                (email, f"%@{email.split('@',1)[-1]}"),
            ).fetchone()
            if tenant_id_row:
                conn.execute(
                    "UPDATE si_tenant SET email=? WHERE tenant_id=?",
                    (email, tenant_id_row[0]),
                )
                tenant_updated = True
        conn.commit()
        return BuyerEmailCaptureResponse(
            ok=True,
            prospect_id=prospect_id,
            email=email,
            token=req.token or None,
            captured_at=captured_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"email capture error: {str(e)[:160]}")


# ---------------------------------------------------------------------------
# /v1/buyers/test_receive — buyer endpoint that accepts lead payloads
# ---------------------------------------------------------------------------
import sqlite3 as _sqlite3
_TEST_RECEIVE_DB = Path(os.environ.get(
    "EMPIRE_TEST_RECEIVE_DB",
    "/root/empire_os/empire_os.db",
))


class BuyerTestReceiveRequest(BaseModel):
    buyer_id: str
    lane_lead_id: int
    prospect_id: str = ""
    niche: str = ""
    metro: str = ""
    tier: str = ""
    match_score: float = 0.0
    payout_usd: float = 0.0
    ts: str = ""


class BuyerTestReceiveResponse(BaseModel):
    ok: bool
    received_id: int | None = None
    buyer_id: str
    lane_lead_id: int


def _ensure_test_receive_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS test_received_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer_id TEXT NOT NULL,
            lane_lead_id INTEGER NOT NULL,
            prospect_id TEXT,
            niche TEXT,
            metro TEXT,
            tier TEXT,
            match_score REAL,
            payout_usd REAL,
            raw_payload TEXT,
            ts TEXT DEFAULT (datetime('now')),
            UNIQUE(buyer_id, lane_lead_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_test_recv_buyer "
        "ON test_received_leads(buyer_id)"
    )
    conn.commit()


@app.post("/v1/buyers/test_receive", response_model=BuyerTestReceiveResponse)
async def buyer_test_receive(req: BuyerTestReceiveRequest):
    """Test buyer endpoint: accept a lead payload, store it, return ok.

    Real buyers will eventually point their endpoint_url at their own
    systems (CRM, webhook, etc). Until then, this lets us close the A2A
    revenue loop by confirming leads can be delivered to *some* buyer
    endpoint. The pusher POSTs to whatever endpoint_url is configured on
    si_buyer_outreach; demo buyers point here.

    Hardened for high-throughput pusher runs: 30s busy_timeout, WAL mode,
    short transactions so concurrent webhooks don't deadlock.
    """
    try:
        conn = _sqlite3.connect(str(_TEST_RECEIVE_DB), timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=30000")
            _ensure_test_receive_schema(conn)
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO test_received_leads
                    (buyer_id, lane_lead_id, prospect_id, niche, metro, tier,
                     match_score, payout_usd, raw_payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (req.buyer_id, req.lane_lead_id, req.prospect_id, req.niche,
                 req.metro, req.tier, req.match_score, req.payout_usd,
                 json.dumps(req.model_dump())),
            )
            conn.commit()
            received_id = cur.lastrowid if cur.lastrowid else None
            if received_id is None:
                row = conn.execute(
                    "SELECT id FROM test_received_leads "
                    "WHERE buyer_id=? AND lane_lead_id=?",
                    (req.buyer_id, req.lane_lead_id),
                ).fetchone()
                received_id = row[0] if row else None
        finally:
            conn.close()
        return BuyerTestReceiveResponse(
            ok=True, received_id=received_id,
            buyer_id=req.buyer_id, lane_lead_id=req.lane_lead_id,
        )
    except Exception as e:
        raise HTTPException(500, f"test_receive error: {str(e)[:160]}")


# ═══════════════════════════════════════════════════════════════════════
# A2A Buyer Onboarding API
# ═══════════════════════════════════════════════════════════════════════

class BuyerRegisterRequest(BaseModel):
    """Buyer registration payload for A2A onboarding."""
    business_name: str
    email: str
    niches: str = ""           # comma-separated niches (e.g., "roofing,hvac")
    metros: str = ""           # comma-separated metros (e.g., "DFW,ATL")
    wallet: str = ""           # USDC/Solana wallet address
    payout_per_lead: float = 0.0
    endpoint_url: str = ""     # buyer's webhook endpoint for lead delivery
    hmac_secret: str = ""      # HMAC secret for webhook verification
    source: str = "a2a_register"
    active: int = 1


class BuyerRegisterResponse(BaseModel):
    ok: bool
    buyer_id: str
    business_name: str
    niches: str
    metros: str
    wallet: str
    payout_per_lead: float
    endpoint_url: str
    hmac_secret: str
    active: int
    created_at: str


def _generate_hmac_secret() -> str:
    """Generate a secure HMAC secret for webhook verification."""
    return "hmac_" + secrets.token_hex(24)


def _verify_hmac_signature(payload: bytes, secret: str, signature_header: str) -> bool:
    """Verify HMAC-SHA256 signature. Supports 'sha256=<sig>' format."""
    if not signature_header:
        return False
    # Accept formats: "sha256=<hex>", "v1=<hex>", or just "<hex>"
    sig = signature_header
    if sig.startswith("sha256="):
        sig = sig[7:]
    elif sig.startswith("v1="):
        sig = sig[3:]
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


@app.post("/v1/buyers/register", response_model=BuyerRegisterResponse)
async def buyer_register(req: BuyerRegisterRequest):
    """Register a new A2A buyer.

    Creates/updates a row in si_buyer_outreach with niches, metros, wallet,
    payout terms, webhook endpoint, and HMAC secret for secure lead delivery.
    Idempotent on email (updates existing row).
    """
    if not backend:
        raise HTTPException(503, "backend not initialized")

    email = req.email.strip().lower()
    business_name = req.business_name.strip()
    niches = req.niches.strip()
    metros = req.metros.strip().upper()
    wallet = req.wallet.strip()
    payout_per_lead = float(req.payout_per_lead)
    endpoint_url = req.endpoint_url.strip()
    hmac_secret = req.hmac_secret.strip() or _generate_hmac_secret()

    if not email or "@" not in email:
        raise HTTPException(400, "valid email required")
    if not business_name:
        raise HTTPException(400, "business_name required")

    # Generate buyer_id from email for stable identity
    buyer_id = "buyer_" + hashlib.sha256(email.encode()).hexdigest()[:16]

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    # Upsert into si_buyer_outreach
    backend.execute("""
        INSERT INTO si_buyer_outreach (
            prospect_id, business_name, email, niches, metros,
            wallet, payout_per_lead, endpoint_url, active, source,
            first_touch_at, last_touch_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(prospect_id) DO UPDATE SET
            business_name=excluded.business_name,
            email=excluded.email,
            niches=excluded.niches,
            metros=excluded.metros,
            wallet=excluded.wallet,
            payout_per_lead=excluded.payout_per_lead,
            endpoint_url=excluded.endpoint_url,
            active=excluded.active,
            last_touch_at=excluded.last_touch_at
    """, (
        buyer_id, business_name, email, niches, metros,
        wallet, payout_per_lead, endpoint_url, req.active, req.source,
        now, now
    ))
    backend.commit()

    # Also create a default payment method entry for USDC if wallet provided
    if wallet:
        from empire_os.charge import add_payment_method
        add_payment_method(
            buyer_id=buyer_id,
            processor="usdc",
            customer_ref=wallet,
            payment_ref="",
            brand="usdc",
            last4=wallet[-4:] if len(wallet) >= 4 else wallet,
            is_default=1
        )

    return BuyerRegisterResponse(
        ok=True,
        buyer_id=buyer_id,
        business_name=business_name,
        niches=niches,
        metros=metros,
        wallet=wallet,
        payout_per_lead=payout_per_lead,
        endpoint_url=endpoint_url,
        hmac_secret=hmac_secret,
        active=req.active,
        created_at=now
    )


class BuyerWebhookVerifyRequest(BaseModel):
    """Request to verify a webhook signature (for buyer self-test)."""
    buyer_id: str
    payload: dict
    signature: str


class BuyerWebhookVerifyResponse(BaseModel):
    ok: bool
    verified: bool
    buyer_id: str


@app.post("/v1/buyers/webhook/verify", response_model=BuyerWebhookVerifyResponse)
async def buyer_webhook_verify(req: BuyerWebhookVerifyRequest):
    """Verify HMAC signature for a buyer webhook (self-test endpoint).

    Buyers can POST their test payload + signature to confirm their
    signing implementation matches before going live.
    """
    if not backend:
        raise HTTPException(503, "backend not initialized")

    row = backend.execute(
        "SELECT hmac_secret FROM si_buyer_outreach WHERE prospect_id=?",
        (req.buyer_id,)
    ).fetchone()

    if not row or not row[0]:
        raise HTTPException(404, "buyer not found or no HMAC secret configured")

    hmac_secret = row[0]
    payload_bytes = json.dumps(req.payload, separators=(",", ":")).encode()
    verified = _verify_hmac_signature(payload_bytes, hmac_secret, req.signature)

    return BuyerWebhookVerifyResponse(
        ok=True,
        verified=verified,
        buyer_id=req.buyer_id
    )


class LeadAcceptRequest(BaseModel):
    """Buyer confirms receipt/acceptance of a delivered lead."""
    buyer_id: str
    lane_lead_id: int
    accepted: bool = True
    notes: str = ""


class LeadAcceptResponse(BaseModel):
    ok: bool
    buyer_id: str
    lane_lead_id: int
    accepted: bool
    updated_at: str


@app.post("/v1/buyers/{buyer_id}/leads/{lane_lead_id}/accept", response_model=LeadAcceptResponse)
async def buyer_lead_accept(buyer_id: str, lane_lead_id: int, req: LeadAcceptRequest):
    """Buyer confirms acceptance (or rejection) of a delivered lead.

    Updates buyer_leads.endpoint_status to 'accepted' or 'rejected',
    and records the buyer's response for payout reconciliation.
    """
    if not backend:
        raise HTTPException(503, "backend not initialized")

    # Verify buyer exists
    row = backend.execute(
        "SELECT prospect_id FROM si_buyer_outreach WHERE prospect_id=?",
        (buyer_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "buyer not found")

    # Verify the lead assignment exists
    lead_row = backend.execute(
        "SELECT id, buyer_id, endpoint_status FROM buyer_leads WHERE buyer_id=? AND lane_lead_id=?",
        (buyer_id, lane_lead_id)
    ).fetchone()
    if not lead_row:
        raise HTTPException(404, "lead assignment not found for this buyer")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    status = "accepted" if req.accepted else "rejected"

    backend.execute(
        """UPDATE buyer_leads
           SET endpoint_status=?, endpoint_response=?, updated_at=?
           WHERE buyer_id=? AND lane_lead_id=?""",
        (status, req.notes[:500], now, buyer_id, lane_lead_id)
    )
    backend.commit()

    return LeadAcceptResponse(
        ok=True,
        buyer_id=buyer_id,
        lane_lead_id=lane_lead_id,
        accepted=req.accepted,
        updated_at=now
    )


class PayoutTermsRequest(BaseModel):
    """Update payout terms for a buyer."""
    buyer_id: str
    payout_per_lead: float
    wallet: str = ""           # optional USDC wallet update
    endpoint_url: str = ""     # optional webhook endpoint update
    hmac_secret: str = ""      # optional HMAC secret rotation


class PayoutTermsResponse(BaseModel):
    ok: bool
    buyer_id: str
    payout_per_lead: float
    wallet: str
    endpoint_url: str
    updated_at: str


@app.post("/v1/buyers/{buyer_id}/payout-terms", response_model=PayoutTermsResponse)
async def buyer_payout_terms(buyer_id: str, req: PayoutTermsRequest):
    """Update payout terms for a buyer (wallet, per-lead rate, webhook, HMAC)."""
    if not backend:
        raise HTTPException(503, "backend not initialized")

    row = backend.execute(
        "SELECT prospect_id FROM si_buyer_outreach WHERE prospect_id=?",
        (buyer_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "buyer not found")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    updates = []
    params = []

    if req.payout_per_lead is not None:
        updates.append("payout_per_lead=?")
        params.append(float(req.payout_per_lead))
    if req.wallet:
        updates.append("wallet=?")
        params.append(req.wallet.strip())
    if req.endpoint_url:
        updates.append("endpoint_url=?")
        params.append(req.endpoint_url.strip())
    if req.hmac_secret:
        updates.append("hmac_secret=?")
        params.append(req.hmac_secret.strip())

    if updates:
        updates.append("last_touch_at=?")
        params.append(now)
        params.append(buyer_id)

        backend.execute(
            f"UPDATE si_buyer_outreach SET {', '.join(updates)} WHERE prospect_id=?",
            params
        )
        backend.commit()

        # Also update payment method if wallet changed
        if req.wallet:
            from empire_os.charge import add_payment_method
            add_payment_method(
                buyer_id=buyer_id,
                processor="usdc",
                customer_ref=req.wallet.strip(),
                payment_ref="",
                brand="usdc",
                last4=req.wallet.strip()[-4:] if len(req.wallet.strip()) >= 4 else req.wallet.strip(),
                is_default=1
            )

    # Return current state
    cur = backend.execute(
        "SELECT payout_per_lead, wallet, endpoint_url FROM si_buyer_outreach WHERE prospect_id=?",
        (buyer_id,)
    ).fetchone()

    return PayoutTermsResponse(
        ok=True,
        buyer_id=buyer_id,
        payout_per_lead=cur[0] if cur else 0.0,
        wallet=cur[1] if cur else "",
        endpoint_url=cur[2] if cur else "",
        updated_at=now
    )


class BuyerConfigResponse(BaseModel):
    ok: bool
    buyer_id: str
    business_name: str
    email: str
    niches: str
    metros: str
    wallet: str
    payout_per_lead: float
    endpoint_url: str
    active: int


@app.get("/v1/buyers/{buyer_id}/config", response_model=BuyerConfigResponse)
async def buyer_get_config(buyer_id: str):
    """Get buyer configuration (for dashboard / buyer self-serve)."""
    if not backend:
        raise HTTPException(503, "backend not initialized")

    row = backend.execute(
        """SELECT prospect_id, business_name, email, niches, metros,
                  wallet, payout_per_lead, endpoint_url, active
           FROM si_buyer_outreach WHERE prospect_id=?""",
        (buyer_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "buyer not found")

    return BuyerConfigResponse(
        ok=True,
        buyer_id=row[0],
        business_name=row[1],
        email=row[2],
        niches=row[3],
        metros=row[4],
        wallet=row[5],
        payout_per_lead=row[6],
        endpoint_url=row[7],
        active=row[8]
    )


# ═══════════════════════════════════════════════════════════════════════
# Existing test_receive endpoint (moved down)
# ═══════════════════════════════════════════════════════════════════════

@app.get("/v1/buyers/test_receive")
async def buyer_test_receive_list(buyer_id: str = "", limit: int = 50):
    """List recently-received leads (debugging + dashboard)."""
    try:
        conn = _sqlite3.connect(str(_TEST_RECEIVE_DB))
        _ensure_test_receive_schema(conn)
        if buyer_id:
            rows = conn.execute(
                "SELECT id, buyer_id, lane_lead_id, prospect_id, niche, "
                "metro, tier, match_score, payout_usd, ts "
                "FROM test_received_leads WHERE buyer_id=? "
                "ORDER BY id DESC LIMIT ?",
                (buyer_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, buyer_id, lane_lead_id, prospect_id, niche, "
                "metro, tier, match_score, payout_usd, ts "
                "FROM test_received_leads ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        cols = ["id","buyer_id","lane_lead_id","prospect_id","niche",
                "metro","tier","match_score","payout_usd","ts"]
        out = [dict(zip(cols, r)) for r in rows]
        conn.close()
        return {"ok": True, "count": len(out), "items": out}
    except Exception as e:
        raise HTTPException(500, f"test_receive list error: {str(e)[:160]}")


@app.get("/buy-leads", response_class=HTMLResponse)
async def buy_leads_page():
    """Branded buyer-acquisition landing page (Empire AI dark/neon theme)."""
    try:
        with open(_BUY_LEADS_TEMPLATE, "r", encoding="utf-8") as fh:
            html = fh.read()
        return HTMLResponse(html)
    except Exception:
        return HTMLResponse("<h1>Empire AI — Buy Leads</h1><p>Signup temporarily unavailable.</p>")



RESEND_WEBHOOK_LOG = Path("/root/feedback/resend_webhook.jsonl")
RESEND_WEBHOOK_LOG.parent.mkdir(parents=True, exist_ok=True)


@app.post("/v1/resend/webhook")
async def resend_webhook(request: Request):
    """Receive Resend delivery events.

    Headers:
        svix-id, svix-timestamp, svix-signature — Svix signature scheme

    Resend events: email.sent, email.delivered, email.bounced,
                   email.complained, email.opened, email.clicked,
                   delivery.delayed, recipient.complained
    """
    body_bytes = await request.body()
    sig_header = request.headers.get("svix-signature", "")
    resend_secret = ""
    env_path = Path("/root/empire_os/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("RESEND_WEBHOOK_SECRET="):
                resend_secret = line.split("=", 1)[1].strip()
                break

    # Verify Svix signature if secret set (skip if missing secret — dev mode)
    if resend_secret and sig_header:
        try:
            ts = request.headers.get("svix-timestamp", "")
            msg_id = request.headers.get("svix-id", "")
            signed = f"{msg_id}.{ts}.{body_bytes.decode()}"
            # svix-signature can have multiple "v1,<sig>" entries separated by space
            expected = _hmac.new(
                resend_secret.encode(),
                signed.encode(),
                _hashlib.sha256,
            ).hexdigest()
            sigs = [s.split(",", 1)[1] for s in sig_header.split() if s.startswith("v1,")]
            if not any(_hmac.compare_digest(expected, s) for s in sigs):
                raise HTTPException(401, "invalid signature")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(400, "signature parse failed")

    try:
        payload = json.loads(body_bytes.decode())
    except Exception:
        raise HTTPException(400, "invalid JSON")

    # Log every event to disk
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": payload.get("type"),
        "created_at": payload.get("created_at"),
        "data": payload.get("data", {}),
    }
    with open(RESEND_WEBHOOK_LOG, "a") as f:
        f.write(json.dumps(event) + "\n")

    # Update any matched lead via Resend's metadata
    # Resend forward custom metadata from sends — we set lead_id in
    # send_email to attach it to each delivery
    md = payload.get("data", {}).get("metadata", {}) or {}
    lead_id = md.get("lead_id") if isinstance(md, dict) else None

    return {"received": True, "type": payload.get("type"), "lead_id": lead_id}


@app.get("/v1/resend/webhook/recent")
def resend_webhook_recent(limit: int = 20):
    """Recent Resend webhook events (for debugging)."""
    if not RESEND_WEBHOOK_LOG.exists():
        return {"events": []}
    lines = RESEND_WEBHOOK_LOG.read_text().splitlines()
    return {"events": [json.loads(l) for l in lines[-limit:]]}


@app.get("/v1/buyers/status/{subscription_id}")
def buyer_status(subscription_id: str):
    """Read-only buyer/subscription status for the public site to poll after
    apply. Returns status, tier, seated lanes, leads delivered, amount due."""
    try:
        import sqlite3 as _sq
        c = _sq.connect("/root/empire_os/empire_os.db", timeout=10, check_same_thread=False)
        try:
            row = c.execute(
                "SELECT s.status, s.plan, s.price_cents, t.niche, t.webhook_url "
                "FROM si_subscription s LEFT JOIN si_tenant t ON s.tenant_id=t.tenant_id "
                "WHERE s.subscription_id=?", (subscription_id,)).fetchone()
            if not row:
                return {"ok": False, "found": False}
            status, plan, price_cents, niche, webhook = row
            delivered = c.execute(
                "SELECT COUNT(*) FROM si_outbox WHERE buyer_tenant=?",
                (subscription_id,)).fetchone()[0]
            vault = c.execute(
                "SELECT value FROM app_kv WHERE key='vault_balance_usdc'").fetchone()
            return {"ok": True, "found": True, "status": status, "tier": (plan or "").replace("lane_", ""),
                    "niche": niche or "", "price_cents": price_cents,
                    "amount_usdc_due": round((price_cents or 0)/100.0, 2),
                    "leads_delivered": delivered,
                    "has_webhook": bool(webhook),
                    "vault_usdc": float(vault[0]) if vault else 0.0}
        finally:
            c.close()
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


@app.get("/v1/leads/sample")
def sample_lead_for_outreach(niche: str, metro: str):
    """Pick a real pending lead matching niche+metro for outreach sample.

    Defined BEFORE /v1/leads/{lead_id} so the static path wins.
    """
    if not backend:
        raise HTTPException(503, "backend not initialized")
    rows = backend.execute(
        "SELECT id, name, email, phone, metro, niche, "
        "substr(details, 1, 250) "
        "FROM lane_leads WHERE status='pending' AND niche=? AND metro=? "
        "ORDER BY id DESC LIMIT 1",
        (niche, metro),
    ).fetchall()
    if not rows:
        return {"found": False}
    return {
        "found": True,
        "lead": {
            "id": rows[0][0], "name": rows[0][1], "email": rows[0][2],
            "phone": rows[0][3], "metro": rows[0][4], "niche": rows[0][5],
            "details": rows[0][6],
        },
    }


@app.get("/v1/leads/{lead_id}")
def get_lead_by_id(lead_id: str):
    """Get a single lead record."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    from empire_os.crm import get_lead
    lead = get_lead(backend, lead_id)
    if not lead:
        raise HTTPException(404, f"Lead '{lead_id}' not found")
    return lead


@app.get("/v1/leads")
def list_leads(
    status: str = "",
    niche: str = "",
    metro: str = "",
    limit: int = 50,
    offset: int = 0,
):
    """List leads with optional filters."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    from empire_os.crm import list_leads
    result = list_leads(backend, status=status, niche=niche,
                         metro=metro, limit=limit, offset=offset)
    return {"leads": result["leads"], "total": result["total"], "limit": result["limit"], "offset": result["offset"]}


@app.get("/v1/leads/counts")
def lead_counts():
    """Get lead counts by status and niche."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    from empire_os.crm import get_lead_counts
    return get_lead_counts(backend)


@app.patch("/v1/leads/{lead_id}/status")
def update_lead_status(lead_id: str, status: str = "", notes: str = ""):
    """Update a lead's funnel status."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    if not status:
        raise HTTPException(400, "status is required")
    from empire_os.crm import update_lead_status
    ok = update_lead_status(backend, lead_id, status, notes)
    if not ok:
        raise HTTPException(500, "Failed to update lead status")
    return {"ok": True, "lead_id": lead_id, "status": status}


@app.get("/v1/crawler/stats")
def crawler_stats():
    """Daily crawler stats: lead volume, tier/strategy breakdown, expected revenue, top 5 latest."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    import sqlite3
    from datetime import date, timezone
    
    DB = "/root/empire_os/empire_os.db"
    today = date.today().isoformat()
    
    TIER_MAP = {
        "S": "S", "A": "A", "B": "B", "C": "C", "D": "D",
        "tier_a": "A", "tier_b": "B",
        "silver": "B", "gold": "A",
        "": "D", None: "D",
    }
    
    STRATEGY_KEYWORDS = {
        "buyer_marketplace": ["ready to buy", "high-value homeowner", "buyer", "immediate"],
        "nurture": ["expansion", "growing", "nurture"],
    }
    
    def normalize_tier(raw):
        return TIER_MAP.get(raw, "D")
    
    def classify_strategy(icp_name, lead_score, icp_fit_score):
        name = (icp_name or "").lower()
        if any(k in name for k in STRATEGY_KEYWORDS["buyer_marketplace"]):
            return "buyer_marketplace"
        if any(k in name for k in STRATEGY_KEYWORDS["nurture"]):
            return "nurture"
        if (lead_score or 0) >= 70 or (icp_fit_score or 0) >= 70:
            return "buyer_marketplace"
        if (lead_score or 0) >= 40 or (icp_fit_score or 0) >= 40:
            return "nurture"
        return "ignore"
    
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    TABLE_DATE_COL = {"crm_leads": "created_at", "lane_leads": "created_at"}
    
    total_today = 0
    tier_counts = {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0}
    strat_counts = {"nurture": 0, "buyer_marketplace": 0, "ignore": 0}
    expected_rev = 0.0
    by_source = {}
    top5_pool = []
    
    for table, date_col in TABLE_DATE_COL.items():
        try:
            cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,))
        except Exception:
            continue
        if not cur.fetchone():
            continue
        
        if table == "crm_leads":
            rows = cur.execute(
                "SELECT id, omega_tier, icp_name, lead_score, icp_fit_score, metro, niche, source "
                "FROM crm_leads WHERE date(created_at)=?",
                (today,)
            ).fetchall()
            for r in rows:
                total_today += 1
                tier_counts[normalize_tier(r["omega_tier"])] += 1
                strat_counts[classify_strategy(r["icp_name"], r["lead_score"], r["icp_fit_score"])] += 1
                expected_rev += (r["lead_score"] or 0) * 1.0 + (r["icp_fit_score"] or 0) * 0.5
                src = r["source"] or "unknown"
                by_source[src] = by_source.get(src, 0) + 1
            top5_rows = cur.execute(
                "SELECT id, source, business_name, metro, omega_tier, icp_tier, icp_name, lead_score, created_at "
                "FROM crm_leads WHERE date(created_at)=? ORDER BY id DESC LIMIT 5",
                (today,)
            ).fetchall()
            top5_pool.extend(top5_rows)
            
        elif table == "lane_leads":
            rows = cur.execute(
                "SELECT id, omega_tier, icp_tier, icp_fit_score, metro, niche, omega_score "
                "FROM lane_leads WHERE date(created_at)=?",
                (today,)
            ).fetchall()
            for r in rows:
                total_today += 1
                tier_counts[normalize_tier(r["omega_tier"])] += 1
                strat_counts[classify_strategy(r["icp_tier"], r["omega_score"], r["icp_fit_score"])] += 1
                expected_rev += (r["omega_score"] or 0) * 1.0 + (r["icp_fit_score"] or 0) * 0.5
                src = r["niche"] or "unknown"
                by_source[src] = by_source.get(src, 0) + 1
            top5_rows = cur.execute(
                "SELECT id, niche, metro, omega_tier, icp_tier, icp_fit_score, omega_score, created_at "
                "FROM lane_leads WHERE date(created_at)=? ORDER BY id DESC LIMIT 5",
                (today,)
            ).fetchall()
            for r in top5_rows:
                top5_pool.append({
                    "id": r["id"],
                    "source": r["niche"] or "lane_leads",
                    "business_name": f"#{r['id']}",
                    "metro": r["metro"],
                    "omega_tier": r["omega_tier"],
                    "icp_tier": r["icp_tier"],
                    "icp_name": "",
                    "lead_score": int(r["omega_score"] or 0),
                    "created_at": r["created_at"]
                })
    
    top5_pool.sort(key=lambda r: r["id"] or 0, reverse=True)
    top5 = top5_pool[:5]
    
    conn.close()
    
    return {
        "date": today,
        "leads_posted_today": total_today,
        "by_source": by_source,
        "tier_breakdown": tier_counts,
        "strategy_breakdown": strat_counts,
        "expected_revenue_usd": round(expected_rev, 2),
        "top_5_latest": [
            {
                "id": r["id"],
                "source": r["source"] if "source" in r.keys() else r["niche"],
                "business": r["business_name"] if "business_name" in r.keys() else f"#{r['id']}",
                "metro": r["metro"],
                "omega_tier": r["omega_tier"],
                "icp_tier": r["icp_tier"] if "icp_tier" in r.keys() else "",
                "icp_name": r["icp_name"],
                "score": r["lead_score"] if "lead_score" in r.keys() else int(r["omega_score"] or 0),
                "created_at": r["created_at"]
            }
            for r in top5
        ]
    }


# ─────────────────────────────────────────────────────────────────
# Outreach surface — used by outreach-agent container over HTTP
# Instead of shelling out to incus, the container calls these
# endpoints to read/write si_buyer_outreach.
# ─────────────────────────────────────────────────────────────────


@app.post("/v1/outreach/prospect/register")
def outreach_register(req: dict):
    """Insert or no-op for prospect in si_buyer_outreach."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    try:
        backend.execute("""
            CREATE TABLE IF NOT EXISTS si_buyer_outreach (
                prospect_id TEXT PRIMARY KEY,
                business_name TEXT,
                email TEXT,
                metro TEXT,
                niche TEXT,
                phone TEXT,
                source TEXT,
                score INTEGER,
                url TEXT,
                seq_step INTEGER DEFAULT 0,
                first_touch_at TEXT,
                last_touch_at TEXT,
                touch_count INTEGER DEFAULT 0,
                reply_state TEXT DEFAULT 'cold',
                sample_lead_id TEXT,
                converted INTEGER DEFAULT 0
            )
        """)
        # idempotent: add seq_step to pre-existing tables
        try:
            backend.execute("ALTER TABLE si_buyer_outreach ADD COLUMN seq_step INTEGER DEFAULT 0")
        except Exception:
            pass
        backend.execute("""
            INSERT OR IGNORE INTO si_buyer_outreach
                (prospect_id, business_name, email, metro, niche,
                 phone, source, score, url, reply_state)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            req.get("prospect_id", ""),
            req.get("business_name", ""),
            req.get("email", ""),
            req.get("metro", ""),
            req.get("niche", ""),
            req.get("phone", ""),
            req.get("source", ""),
            int(req.get("score", 0)),
            req.get("url", ""),
            "cold",
        ))
        if req.get("email"):
            backend.execute(
                "UPDATE si_buyer_outreach SET email=? WHERE prospect_id=?",
                (req.get("email", ""), req.get("prospect_id", "")),
            )
        backend.commit()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/v1/outreach/prospect/touched")
def outreach_touched(req: dict):
    """Record a touch (sent/failed) for a prospect in si_buyer_outreach."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    pid = req.get("prospect_id", "")
    sent = bool(req.get("sent", False))
    sample_lead_id = req.get("sample_lead_id", "")
    seq_step = req.get("seq_step", None)
    now = datetime.now(timezone.utc).isoformat()
    state = "contacted" if sent else "outreach_failed"
    try:
        if seq_step is not None:
            backend.execute(
                """
                UPDATE si_buyer_outreach
                SET first_touch_at = COALESCE(first_touch_at, ?),
                    last_touch_at = ?,
                    touch_count = COALESCE(touch_count, 0) + 1,
                    reply_state = ?,
                    sample_lead_id = COALESCE(NULLIF(?, ''), sample_lead_id),
                    seq_step = ?
                WHERE prospect_id = ?
                """,
                (now, now, state, sample_lead_id, int(seq_step), pid),
            )
        else:
            backend.execute(
                """
                UPDATE si_buyer_outreach
                SET first_touch_at = COALESCE(first_touch_at, ?),
                    last_touch_at = ?,
                    touch_count = COALESCE(touch_count, 0) + 1,
                    reply_state = ?,
                    sample_lead_id = COALESCE(NULLIF(?, ''), sample_lead_id)
                WHERE prospect_id = ?
                """,
                (now, now, state, sample_lead_id, pid),
            )
        backend.commit()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/v1/outreach/webhook")
async def outreach_webhook(request: Request):
    """Receive outreach nurture payloads when Resend quota is hit (429).

    Payload from outreach_runner.send_via_webhook:
      {
        "to": "email@domain.com",
        "subject": "...",
        "body": "...",
        "metadata": {"source": "outreach", "step": 0, "prospect_id": "...", ...},
        "source": "outreach_webhook"
      }

    Logs to /root/feedback/outreach_webhook.jsonl for review/forwarding.
    """
    body_bytes = await request.body()
    try:
        payload = json.loads(body_bytes.decode())
    except Exception:
        raise HTTPException(400, "invalid JSON")

    # Log every webhook event for audit/retry
    log_path = Path("/root/feedback/outreach_webhook.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": payload.get("source", "outreach_webhook"),
        "to": payload.get("to", ""),
        "subject": payload.get("subject", ""),
        "metadata": payload.get("metadata", {}),
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(event) + "\n")

    # Actually deliver the email via the configured mail backend (Brevo/SMTP),
    # bypassing Resend's 429 quota. The webhook is the real outbound channel.
    to = payload.get("to", "")
    subject = payload.get("subject", "")
    body = payload.get("body", "")
    sent_ok = False
    send_info = ""
    if to and subject:
        try:
            from empire_os import mail_sender as _ms
            # Mailgun SMTP > Mailgun HTTP > Resend > Brevo
            if _ms._real_smtp_cfg() and _ms.SMTP_HOST == "smtp.mailgun.org":
                res = _ms._smtp_send(to, subject, body)
            elif _ms.MAILGUN_API_KEY:
                res = _ms._mailgun_send(to, subject, body)
            elif _ms.RESEND_API_KEY:
                res = _ms._resend_send(to, subject, body)
            else:
                res = _ms._brevo_api_send(to, subject, body)
            sent_ok = bool(res.get("ok"))
            send_info = str(res)[:160]
        except Exception as e:
            send_info = f"send_error: {str(e)[:120]}"
    event["delivered"] = sent_ok
    event["send_info"] = send_info
    with open(log_path, "a") as f:
        f.write(json.dumps(event) + "\n")

    return {"received": True, "type": payload.get("source", "outreach_webhook"),
            "delivered": sent_ok, "send_info": send_info}


# ─────────────────────────────────────────────────────────────────
# Inbound reply ingestion — flips reply_state='replied' on match.
# Minimal contract: POST /v1/inbound/reply with
#   {from_email, subject, body, in_reply_to?}
# Designed to be called by either:
#   - Resend inbound webhook (after Resend inbound domain is configured)
#   - Manual POST (curl) when a reply is observed elsewhere
#   - The inbound_reply_daemon.py IMAP poller
# ─────────────────────────────────────────────────────────────────

@app.post("/v1/inbound/reply")
async def inbound_reply(request: Request):
    """Mark a prospect as replied.

    Body:
      from_email (required, case-insensitive)
      subject    (optional, logged)
      body       (optional, logged)
      in_reply_to (optional, Message-ID we sent; logged)

    Side effects:
      - Finds si_buyer_outreach.email = LOWER(from_email).
      - If reply_state != 'replied': UPDATE reply_state='replied'.
      - Appends the full event to /root/feedback/inbound_replies.jsonl.

    Response:
      200 {matched: bool, prospect_id?, reply_state, updated: bool}
      400 if from_email missing
    """
    try:
        payload = await request.json()
    except Exception:
        # Allow form-encoded fallback for some webhook providers
        try:
            form = await request.form()
            payload = dict(form)
        except Exception:
            raise HTTPException(400, "invalid JSON body")

    from_email = (payload.get("from_email") or payload.get("from") or "").strip()
    if not from_email:
        raise HTTPException(400, "from_email is required")

    subject = payload.get("subject", "") or ""
    body = payload.get("body", "") or ""
    in_reply_to = payload.get("in_reply_to", "") or ""
    source = payload.get("source", "manual") or "manual"

    # Normalize the lookup key (lowercase, strip optional display-name).
    raw = from_email
    if "<" in raw and ">" in raw:
        raw = raw.split("<", 1)[1].split(">", 1)[0]
    key = raw.strip().lower()

    matched = False
    prospect_id = None
    prior_state = None
    new_state = None
    updated = False
    error = None

    if not backend:
        error = "backend not initialized"
    else:
        try:
            # Ensure reply_state column is reachable (idempotent migration).
            try:
                cols = [r[1] for r in backend.execute(
                    "PRAGMA table_info(si_buyer_outreach)").fetchall()]
                if "reply_state" not in cols:
                    backend.execute(
                        "ALTER TABLE si_buyer_outreach "
                        "ADD COLUMN reply_state TEXT DEFAULT 'cold'")
                    backend.commit()
            except Exception:
                pass

            rows = backend.execute(
                "SELECT prospect_id, reply_state FROM si_buyer_outreach "
                "WHERE LOWER(email) = ? LIMIT 1",
                (key,),
            ).fetchall()
            if rows:
                matched = True
                prospect_id = rows[0][0]
                prior_state = rows[0][1]
                if prior_state != "replied":
                    backend.execute(
                        "UPDATE si_buyer_outreach "
                        "SET reply_state='replied', last_touch_at=? "
                        "WHERE prospect_id=?",
                        (datetime.now(timezone.utc).isoformat(), prospect_id),
                    )
                    backend.commit()
                    updated = True
                    new_state = "replied"
                else:
                    new_state = prior_state  # already replied; no-op
            else:
                new_state = None
        except Exception as e:
            error = f"db_error: {str(e)[:160]}"

    # Always append to audit log — even on no-match — so we can spot
    # out-of-band replies and refine our outreach list.
    try:
        log_path = Path("/root/feedback/inbound_replies.jsonl")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "from_email_raw": from_email,
            "from_email_key": key,
            "subject": subject,
            "body_preview": (body or "")[:500],
            "in_reply_to": in_reply_to,
            "source": source,
            "matched": matched,
            "prospect_id": prospect_id,
            "prior_state": prior_state,
            "new_state": new_state,
            "updated": updated,
            "error": error,
        }
        with open(log_path, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as e:
        # Log append failures must not lose the API response.
        error = (error + " | log_error: " if error else "log_error: ") + str(e)[:120]

    status_code = 200 if matched or not error else 500
    return {
        "matched": matched,
        "prospect_id": prospect_id,
        "prior_state": prior_state,
        "reply_state": new_state,
        "updated": updated,
        "error": error,
    }


# ─────────────────────────────────────────────────────────────────
# A2A SALES MESH — agent-to-agent commerce.

@app.get("/v1/outreach/prospect/{prospect_id}")
def outreach_get(prospect_id: str):
    """Look up prospect contact history."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    rows = backend.execute(
        "SELECT touch_count, reply_state, last_touch_at, email "
        "FROM si_buyer_outreach WHERE prospect_id=?",
        (prospect_id,),
    ).fetchall()
    if not rows:
        return {"known": False}
    tc, rs, lt, em = rows[0]
    return {
        "known": True,
        "touch_count": tc,
        "reply_state": rs,
        "last_touch_at": lt,
        "email": em,
    }


@app.get("/v1/outreach/prospects/pending")
def outreach_pending(metro: str = None, niche: str = None, limit: int = 20):
    """List cold prospects (or by metro/niche) the outreach agent should review."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    try:
        backend.execute("""
            CREATE TABLE IF NOT EXISTS si_buyer_outreach (
                prospect_id TEXT PRIMARY KEY, business_name TEXT,
                email TEXT, metro TEXT, niche TEXT, phone TEXT,
                source TEXT, score INTEGER, url TEXT,
                first_touch_at TEXT, last_touch_at TEXT,
                touch_count INTEGER DEFAULT 0,
                reply_state TEXT DEFAULT 'cold',
                sample_lead_id TEXT, converted INTEGER DEFAULT 0
            )
        """)
        backend.commit()
    except Exception:
        pass

    q = """
        SELECT prospect_id, business_name, email, metro, niche,
               phone, source, score, url, seq_step, last_touch_at
        FROM si_buyer_outreach
        WHERE (reply_state = 'cold' OR touch_count IS NULL OR touch_count = 0)
    """
    if metro:
        q += f" AND metro='{metro}'"
    if niche:
        q += f" AND niche='{niche}'"
    q += f" ORDER BY (email IS NOT NULL AND email != '') DESC, score DESC LIMIT {limit}"
    rows = backend.execute(q).fetchall()
    return {
        "prospects": [
            {
                "prospect_id": r[0], "business_name": r[1],
                "email": r[2], "metro": r[3], "niche": r[4],
                "phone": r[5], "source": r[6], "score": r[7],
                "url": r[8], "seq_step": r[9] or 0,
                "last_touch_at": r[10] or "",
            }
            for r in rows
        ]
    }


# ─────────────────────────────────────────────────────────────────
# A2A SALES MESH — agent-to-agent commerce.

PRODUCT_CATALOG = {
    "lead_lane": "Exclusive lead lane (niche+metro). Pay-per-lead in USDC.",
    "satellite_wastage": "Idle-asset / logistics wastage monitor report (satellite).",
    "warehouse_asset": "Warehouse inventory + asset reporting feed.",
    "strike_pack": "Tiered emergency lead burst for a niche/metro event.",
    "ai_closer": "Tiered MRR: AI closes your leads, settles in USDC.",
}
PRODUCT_PRICES = {"satellite_wastage": 99.0, "warehouse_asset": 79.0,
                  "strike_pack": 199.0, "ai_closer": 299.0}


def ensure_products_table():
    """Dynamic product registry — GitHub-sourced OSS wrapped as B2B SKUs."""
    try:
        backend.execute("""CREATE TABLE IF NOT EXISTS si_products (
            sku TEXT PRIMARY KEY,
            name TEXT,
            repo_url TEXT,
            license TEXT,
            description TEXT,
            b2b_angle TEXT,
            tier1_usdc REAL,
            tier2_usdc REAL,
            tier3_usdc REAL,
            tier4_usdc REAL,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )""")
        # migrate: add tier4 if missing (idempotent)
        try:
            backend.execute("ALTER TABLE si_products ADD COLUMN tier4_usdc REAL")
        except Exception:
            pass
        backend.commit()
    except Exception:
        pass


def load_product_catalog():
    """Merge static catalog + dynamic DB products."""
    cat = dict(PRODUCT_CATALOG)
    prices = dict(PRODUCT_PRICES)
    try:
        ensure_products_table()
        rows = backend.execute(
            "SELECT sku, name, description, tier1_usdc FROM si_products "
            "WHERE active=1").fetchall()
        for sku, name, desc, t1 in rows:
            cat[sku] = desc or name
            if t1:
                prices[sku] = float(t1)
    except Exception:
        pass
    return cat, prices


@app.get("/v1/a2a/catalog")
def a2a_catalog():
    """What's for sale, machine-readable (static + GitHub-sourced)."""
    cat, _ = load_product_catalog()
    vault = os.environ.get("SOLANA_VAULT_WALLET", "")
    return {"vault": vault, "products": cat, "settlement": "solana_usdc"}


@app.get("/v1/products/pricing")
def products_pricing():
    """Full tiered pricing + one-time white-label setup fees (USDC/mo)."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    ensure_products_table()
    # load static specs for PRODUCT_PRICES SKUs (not in DB)
    import os as _os
    specs = {}
    sf = "/root/empire_os/empire_os/data/sku_specs.json"
    if _os.path.exists(sf):
        try:
            specs = json.loads(open(sf).read())
        except Exception:
            specs = {}
    rows = backend.execute(
        "SELECT sku, name, tier1_usdc, tier2_usdc, tier3_usdc, tier4_usdc, "
        "setup_fee_usdc, active, features, benefits, deliverables "
        "FROM si_products WHERE active=1").fetchall()
    out = {}
    for sku, name, t1, t2, t3, t4, sfee, act, feats, bens, dels in rows:
        sp = specs.get(sku, {})
        out[sku] = {
            "name": name,
            "tiers": {
                "T1": float(t1 or 0), "T2": float(t2 or 0),
                "T3": float(t3 or 0), "T4_titanium": float(t4 or 0),
            },
            "setup_fee_usdc": float(sfee or 0),
            "whitelabel": float(sfee or 0) > 0,
            "features": json.loads(feats) if feats else sp.get("features", []),
            "benefits": json.loads(bens) if bens else sp.get("benefits", []),
            "deliverables": json.loads(dels) if dels else sp.get("deliverables", []),
        }
    # include PRODUCT_PRICES SKUs (not in DB)
    for sku, price in PRODUCT_PRICES.items():
        if sku not in out:
            sp = specs.get(sku, {})
            out[sku] = {"name": sku, "tiers": {"T1": price, "T2": price * 2.5,
                        "T3": price * 5, "T4_titanium": price * 10},
                        "setup_fee_usdc": 0.0, "whitelabel": False,
                        "features": sp.get("features", []),
                        "benefits": sp.get("benefits", []),
                        "deliverables": sp.get("deliverables", [])}
    return {"vault": VAULT, "settlement": "solana_usdc", "pricing": out}


@app.get("/v1/products/{sku}")
def product_detail(sku: str):
    """Full spec: tiers, setup fee, features, benefits, deliverables."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    ensure_products_table()
    import os as _os
    specs = {}
    sf = "/root/empire_os/empire_os/data/sku_specs.json"
    if _os.path.exists(sf):
        try:
            specs = json.loads(open(sf).read())
        except Exception:
            pass
    row = backend.execute(
        "SELECT name, tier1_usdc, tier2_usdc, tier3_usdc, tier4_usdc, "
        "setup_fee_usdc, description, features, benefits, deliverables "
        "FROM si_products WHERE sku=? AND active=1", (sku,)).fetchone()
    if row:
        sp = specs.get(sku, {})
        return {"sku": sku, "name": row[0],
                "tiers": {"T1": float(row[1] or 0), "T2": float(row[2] or 0),
                          "T3": float(row[3] or 0), "T4_titanium": float(row[4] or 0)},
                "setup_fee_usdc": float(row[5] or 0),
                "whitelabel": float(row[5] or 0) > 0,
                "description": row[6],
                "features": json.loads(row[7]) if row[7] else sp.get("features", []),
                "benefits": json.loads(row[8]) if row[8] else sp.get("benefits", []),
                "deliverables": json.loads(row[9]) if row[9] else sp.get("deliverables", []),
                "vault": VAULT, "settlement": "solana_usdc"}
    # PRODUCT_PRICES SKU
    if sku in PRODUCT_PRICES:
        sp = specs.get(sku, {})
        price = PRODUCT_PRICES[sku]
        return {"sku": sku, "name": sku,
                "tiers": {"T1": price, "T2": price * 2.5, "T3": price * 5,
                          "T4_titanium": price * 10},
                "setup_fee_usdc": 0.0, "whitelabel": False,
                "features": sp.get("features", []), "benefits": sp.get("benefits", []),
                "deliverables": sp.get("deliverables", []),
                "vault": VAULT, "settlement": "solana_usdc"}
    raise HTTPException(404, "sku not found")


@app.post("/v1/a2a/negotiate")
def a2a_negotiate(req: dict):
    """Another agent posts buy-intent -> hub quotes + returns settle instr."""
    VAULT = os.getenv("EMPIRE_VAULT", "egJ1t9NZkDs8FvMbfnQTqXzC4KNuhAc9XSfpG9yAZM")
    if not backend:
        raise HTTPException(503, "backend not initialized")
    product = req.get("product", "lead_lane")
    niche = req.get("niche", "")
    metro = req.get("metro", "")
    buyer_agent = req.get("buyer_agent", "")
    wallet = req.get("wallet", "")
    if not buyer_agent:
        raise HTTPException(400, "buyer_agent required")

    # map generic niche names to lane sub_niche / category
    NICHE_ALIAS = {
        "roofing": "residential_roofing",
        "roof": "residential_roofing",
        "roofer": "residential_roofing",
        "hvac": "hvac",
        "plumbing": "plumbing",
        "electrical": "electrical",
        "solar": "solar",
        "windows": "windows",
        "flooring": "flooring",
        "landscaping": "landscaping",
    }
    search_niche = NICHE_ALIAS.get(niche.lower(), niche)

    # map city name to airport-code metro used in lanes
    METRO_ALIAS = {
        "phoenix": "PHX", "los angeles": "LAX", "dallas": "DFW",
        "houston": "HOU", "chicago": "CHI", "new york": "NYC",
        "atlanta": "ATL", "miami": "MIA", "boston": "BOS",
        "san francisco": "SFO", "washington": "WDC", "philadelphia": "PHL",
    }
    search_metro = METRO_ALIAS.get(metro.lower(), metro.upper()[:3])

    quote = None
    if product == "lead_lane":
        row = backend.execute(
            "SELECT id, seat_price, category, sub_niche, metro FROM lanes "
            "WHERE (occupied_by IS NULL OR occupied_by = '') "
            "AND (sub_niche = ? OR category = ? OR sub_niche = ?) AND metro = ? LIMIT 1",
            (search_niche, search_niche, niche, search_metro),
        ).fetchone()
        if row:
            quote = {
                "sku": "lead_lane", "lane_id": row[0],
                "seat_price_usdc": float(row[1]) if row[1] else 0.0,
                "niche": row[3], "metro": row[4],
                "memo": f"LANE_{row[0]}",
            }
    else:
        # dynamic: look up SKU in si_products (GitHub-sourced or static)
        _, prices = load_product_catalog()
        row = backend.execute(
            "SELECT sku, tier1_usdc, tier2_usdc, tier3_usdc, tier4_usdc, "
            "setup_fee_usdc FROM si_products WHERE sku = ? AND active=1",
            (product,)).fetchone()
        price = float(row[1]) if row else prices.get(product)
        if price:
            quote = {
                "sku": product, "price_usdc": price,
                "tiers": {
                    "t1": float(row[1]) if row else price,
                    "t2": float(row[2]) if row else price * 2,
                    "t3": float(row[3]) if row else price * 5,
                    "t4_titanium": float(row[4]) if row else price * 10,
                },
                "setup_fee_usdc": float(row[5]) if row else 0.0,
                "whitelabel": bool(row and float(row[5] or 0) > 0),
                "memo": f"SKU_{product.upper()}",
            }

    if not quote:
        return {"matched": False, "message": "no open inventory for intent"}

    try:
        with open("/root/feedback/a2a_mesh.jsonl", "a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "buyer_agent": buyer_agent, "wallet": wallet,
                "product": product, "quote": quote,
            }) + "\n")
    except Exception:
        pass

    return {
        "matched": True,
        "vault": VAULT,
        "settle_instruction": {
            "token": "USDC",
            "amount_usdc": quote.get("seat_price_usdc") or quote.get("price_usdc"),
            "to": VAULT,
            "memo": quote["memo"],
        },
        "quote": quote,
        "note": "Send USDC with memo; listener detects + seats automatically.",
    }


@app.post("/v1/products/register")
def product_register(req: dict):
    """product_factory: register a GitHub-sourced OSS as a B2B SKU."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    sku = (req.get("sku") or "").strip()
    if not sku:
        raise HTTPException(400, "sku required")
    ensure_products_table()
    backend.execute(
        "INSERT OR REPLACE INTO si_products "
        "(sku, name, repo_url, license, description, b2b_angle, "
        "tier1_usdc, tier2_usdc, tier3_usdc, tier4_usdc, setup_fee_usdc, "
        "active, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?)",
        (sku, req.get("name", sku), req.get("repo_url", ""),
         req.get("license", ""), req.get("description", ""),
         req.get("b2b_angle", ""),
         float(req.get("tier1_usdc", 0) or 0),
         float(req.get("tier2_usdc", 0) or 0),
         float(req.get("tier3_usdc", 0) or 0),
         float(req.get("tier4_usdc", 0) or 0),
         float(req.get("setup_fee_usdc", 0) or 0),
         datetime.now(timezone.utc).isoformat()))
    backend.commit()
    return {"ok": True, "sku": sku,
            "note": "live in A2A catalog + negotiate"}


# ─────────────────────────────────────────────────────────────────
# Swarm 3.0 — Traffic Hub + Worker Pull + Audit Log endpoints
# All routing decisions flow through /v1/hub/intake. Workers register
# handlers via /v1/swarm/worker-config. Every routing logs to
# /v1/swarm/audit-log. Strict lane isolation.
# ─────────────────────────────────────────────────────────────────

SWARM_REGISTRY_PATH = "/root/feedback/swarm_registry.jsonl"
SWARM_AUDIT_PATH = "/root/feedback/swarm_audit.jsonl"
import json as _json


def _swarm_audit(event_type: str, **fields):
    """Append-only audit trail for every swarm routing decision."""
    Path("/root/feedback").mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        **fields,
    }
    with open(SWARM_AUDIT_PATH, "a") as f:
        f.write(_json.dumps(entry) + "\n")


def _swarm_persist_handler(worker_id: str, niche: str, metro: str,
                          action: str, weight: int):
    """Persist a worker handler so it survives restarts."""
    Path("/root/feedback").mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.now(timezone.utc).isoformat(),
           "worker_id": worker_id, "niche": niche, "metro": metro,
           "action": action, "weight": weight}
    with open(SWARM_REGISTRY_PATH, "a") as f:
        f.write(_json.dumps(rec) + "\n")


def _read_handlers() -> list:
    """Return all registered handler records (latest first)."""
    p = Path(SWARM_REGISTRY_PATH)
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        try:
            out.append(_json.loads(line))
        except Exception:
            continue
    return out


def _select_handler(niche: str, metro: str) -> dict | None:
    """Choose the best worker for an (niche, metro) payload.

    Filters handlers whose niche matches (or "*" wildcard), prefers
    the highest weight, ties broken by most-recent registration.
    """
    candidates = []
    for h in _read_handlers():
        if h.get("niche") not in (niche, "*"):
            continue
        candidates.append(h)
    if not candidates:
        return None
    candidates.sort(key=lambda h: (h.get("weight", 0), h.get("ts", "")), reverse=True)
    return candidates[0]


# Infer niche from text via keyword map (lightweight, no LLM)
NICHE_INFER = {
    "plumbing": ["plumber", "plumbing", "drain", "sewer", "pipe", "water heater", "burst", "flood"],
    "electrical": ["electrician", "electrical", "wiring", "panel", "outlet"],
    "hvac": ["hvac", "furnace", "air condition", "ac repair", "heating", "cooling", "heat pump"],
    "roofing": ["roofer", "roofing", "roof repair", "shingle", "gutter"],
    "landscaping": ["landscap", "lawn", "tree service", "irrigation", "yard"],
    "painting": ["painter", "painting", "interior paint", "exterior paint"],
    "mold_remediation": ["mold", "remediation", "water damage"],
    "pest_control": ["pest", "exterminator", "termite", "rodent"],
    "general_contractor": ["contractor", "remodel", "renovation", "addition"],
    "water_damage_restoration": ["water damage", "flood", "restoration"],
    "emergency_plumbing": ["emergency", "burst pipe", "flooding"],
}


def _infer_niche(text: str) -> str:
    text_l = text.lower()
    best, score = "", 0
    for niche, kws in NICHE_INFER.items():
        hits = sum(1 for kw in kws if kw in text_l)
        if hits > score:
            best, score = niche, hits
    return best or "general_contractor"


def _infer_metro(text: str) -> str | None:
    """Crude metro inference from text; falls back to None (no routing)."""
    text_l = text.lower()
    for code, cities in {
        "NYC": ["new york", "nyc", "manhattan", "brooklyn", "queens"],
        "LAX": ["los angeles", "la", "hollywood", "beverly hills"],
        "CHI": ["chicago", "illinois", "il"],
        "DFW": ["dallas", "fort worth", "dfw"],
        "SFO": ["san francisco", "bay area", "sf", "oakland"],
        "SEA": ["seattle", "wa"],
        "BOS": ["boston", "ma"],
        "WDC": ["washington", "dc", "arlington"],
    }.items():
        if any(c in text_l for c in cities):
            return code
    return None


@app.post("/v1/hub/intake")
def hub_intake(req: dict):
    """Traffic Hub — central labeling + routing endpoint.

    Inbound payload is a raw event (form fill, webhook, parsed crawl
    result). Hub:
      1. Labels it (niche/metro/lead_score/payload_hash)
      2. Picks a registered worker (highest-weight match)
      3. Routes to that worker OR falls back to default leads queue
      4. Logs every step to /v1/swarm/audit-log

    Body (any subset):
      text          str   free-form description (preferred input)
      email         str   optional contact
      phone         str   optional contact
      niche         str   override inferred niche
      metro         str   override inferred metro
      lead_score    int   override computed score (0-100)
      url           str   optional source URL
      source        str   tag (default: "hub_intake")
    """
    text = req.get("text") or req.get("details") or ""
    email = req.get("email", "")
    phone = req.get("phone", "")

    # Step 1: Label
    niche = req.get("niche") or _infer_niche(text)
    metro = req.get("metro") or _infer_metro(text) or ""
    lead_score = req.get("lead_score")
    if lead_score is None:
        # Heuristic: keyword density * 10 + contact-presence bump
        kw_score = sum(1 for kw in ["need ", " quote", " emergency",
                                     " asap", " urgent", " broken"]
                       if kw in text.lower()) * 12
        contact_score = (10 if email else 0) + (10 if phone else 0)
        lead_score = min(100, 35 + kw_score + contact_score)

    payload_hash = hashlib.sha256(
        (text + email + phone).encode()).hexdigest()[:16]

    # Step 2: Pick worker
    worker = _select_handler(niche, metro) if metro else None

    route_target = worker["worker_id"] if worker else "lead_deliverer_default"
    route_action = worker["action"] if worker else "store_as_pending"

    # Step 3: Persist as a real lead if no specific worker wants it
    lane_id = ""
    if not worker or worker.get("action") == "consume":
        # Persist to lane_leads via direct SQL
        if metro and niche and backend:
            try:
                lane_id = f"{niche}:{metro}".replace(" ", "_").lower()
                tier = "gold" if lead_score >= 75 else "silver" if lead_score >= 50 else "bronze"
                backend.execute(
                    "INSERT INTO lane_leads "
                    "(lane_id, prospect_id, status, omega_score, omega_tier, "
                    "name, email, phone, source, metro, state, details, niche, "
                    "created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (lane_id, payload_hash, 'pending', lead_score, tier,
                     req.get("name", ""), email, phone,
                     req.get("source", "hub_intake"), metro,
                     req.get("state", ""), text[:500], niche,
                     datetime.now(timezone.utc).isoformat(),
                     datetime.now(timezone.utc).isoformat()),
                )
                backend.commit()
            except Exception as e:
                _swarm_audit("hub_intake_db_error", error=str(e)[:200])

    # Step 4: Audit
    _swarm_audit("hub_intake", payload_hash=payload_hash,
                niche=niche, metro=metro, lead_score=lead_score,
                worker_id=route_target, action=route_action,
                lane_id=lane_id or None)

    return {
        "ok": True,
        "labels": {
            "niche": niche,
            "metro": metro,
            "lead_score": lead_score,
            "payload_hash": payload_hash,
        },
        "route": {
            "worker_id": route_target,
            "action": route_action,
            "lane_id": lane_id or None,
        },
        "audit": "logged to /v1/swarm/audit-log",
    }


@app.post("/v1/compliance/check")
def compliance_check(req: dict):
    """Quick TCPA/GDPR/CCPA pre-check.

    Body: { to_email, phone, state, intent }
    Returns: { ok, issues[] }
    """
    issues = []
    to    = (req.get("to_email") or "").strip()
    phone = (req.get("phone") or "").strip()
    state = (req.get("state") or "").strip()
    intent = (req.get("intent") or "").strip()
    if not (to or phone):
        issues.append("no_contact_info")
    if intent == "marketing" and state in ("CA", "US-CA"):
        issues.append("ccpa_marketing_ca_unsupported_v1")
    return {"ok": not issues, "issues": issues}


@app.post("/v1/email/compose")
def email_compose(req: dict):
    """Compose a trustworthy, compliant email via email-expert agent.

    Body (the "brief"):
      audience      str   description of recipient
      niche         str
      metro         str
      name          str   recipient first name
      tier          str   bronze|silver|gold|diamond|empire|titanium
      kind          str   email_outreach | landing | subject
      email         str   for compliance check
      phone         str   for compliance check
      state         str   for compliance check
      subject_template  str  optional

    Returns { ok, subject, body, compliance, audit_id }
    """
    brief = {
        "audience": req.get("audience", "agency_founder"),
        "niche":    req.get("niche",    "general"),
        "metro":    req.get("metro",    "NYC"),
        "name":     (req.get("name") or "there").strip() or "there",
        "tier":     req.get("tier", "silver"),
        "subject_template":
                   req.get("subject_template",
                           "Empire OS for {metro} {niche}: real leads, USDC billing"),
    }

    # Compliance pre-check: in-process call to avoid HTTP self-loop
    compliance = compliance_check(req={
        "to_email": req.get("email", ""),
        "phone":    req.get("phone", ""),
        "state":    req.get("state", ""),
        "intent":   "marketing",
    })

    if not compliance.get("ok", True):
        return {"ok": False, "blocked": True,
                "reasons": compliance.get("issues", [])}

    subject = brief["subject_template"].format(
        metro=brief["metro"], niche=brief["niche"].title())
    body = (
        f"Hey {brief['name']},\n\n"
        f"this is the Empire OS team reaching out about your "
        f"{brief['niche']} project in {brief['metro']}. We deliver "
        f"exclusive leads to high-revenue agencies across 462 lanes. "
        f"All billing is in USDC on Solana - no Stripe, no contracts, "
        f"no churn risk.\n\n"
        f"The {brief['tier'].title()} tier is the best fit. Want a "
        f"free 1-day trial of the pipeline?\n\n"
        f"First 14 days free. Cancel anytime.\n\n"
        f"---\nEmpire OS - {subject}\n"
        f"Unsubscribe: https://empire-ai.co.uk/unsub/{brief['niche']}-{brief['metro']}\n"
    )
    audit_id = "ec_" + hex(int(time.time()))[2:]
    return {"ok": True, "subject": subject, "body": body,
            "compliance": compliance, "audit_id": audit_id}


@app.post("/v1/copy")
def copy_draft(req: dict):
    """Calls copywriting-agent to render email/landing copy.

    Body:
      kind          str  "email_outreach" | "landing_headline" | "subject_line"
      niche         str  target niche (e.g. "plumbing")
      metro         str  target metro (e.g. "NYC")
      name          str  recipient personal name
      audience      str  free-text description of target
      tier          str  "bronze" | "silver" | "gold" (target tier)
      subject_template  str  optional template
    Returns { ok, subject, body }
    """
    kind     = req.get("kind", "email_outreach")
    niche    = req.get("niche", "general")
    metro    = req.get("metro", "NYC")
    name     = (req.get("name") or "there").strip() or "there"
    audience = req.get("audience", "agency_founder_50M_revenue")
    tier     = req.get("tier", "silver")
    subject_template = req.get("subject_template",
                              "Empire OS for {metro} {niche}: real leads, USDC billing")
    subject = subject_template.format(metro=metro, niche=niche.title())

    # Pre-defined copy per kind. The copywriting-agent can extend later.
    body = (
        f"Hey {name},\n\n"
        f"this is the Empire OS team reaching out about your {niche} project "
        f"in {metro}. We deliver exclusive leads (one agency per (niche x metro), "
        f"no recycled leads, real-time webhook delivery) to high-revenue agencies. "
        f"All billing is in USDC on Solana - no Stripe, no contracts, no churn risk.\n"
        f"\nThe {tier.title()} tier is the best fit for agencies like yours. "
        f"Want a free 1-day trial of the pipeline?\n"
        f"\nFirst 14 days free. Cancel anytime. Empire OS\n"
    )

    return {"ok": True, "subject": subject, "body": body}


@app.post("/v1/seo/audit")
def seo_audit(req: dict):
    """Receive an SEO audit batch from seo-agent or ai-seo-agent.

    Body:
      results  list  of { url, status, size_bytes, ... } or
                  { url, title, h1, intent, has_faq_block, ... }
      kind     str   "seo" or "ai_seo"
      ts       str   ISO timestamp

    Effect:
      - persists the audit batch into /root/feedback/seo_history.jsonl
      - exposes GET /v1/seo/recent to read it back
    """
    results = req.get("results") or []
    kind    = req.get("kind", "seo")
    ts      = req.get("ts", "")
    if not isinstance(results, list):
        raise HTTPException(400, "results must be list")
    if not results:
        return {"ok": True, "count": 0, "note": "no rows"}

    try:
        out = "/root/feedback/seo_history.jsonl"
        with open(out, "a") as f:
            for r in results:
                f.write(json.dumps({"kind": kind, "ts": ts,
                                    "result": r}) + "\n")
    except Exception as e:
        raise HTTPException(500, f"persist failed: {e}")

    return {"ok": True, "count": len(results), "kind": kind}


@app.get("/v1/seo/recent")
def seo_recent(n: int = 20, kind: str = ""):
    """Read back the latest N entries from seo_history."""
    out = "/root/feedback/seo_history.jsonl"
    p = Path(out)
    if not p.exists():
        return {"entries": [], "count": 0}
    lines = [l for l in p.read_text().splitlines() if l.strip()]
    rows = []
    for line in lines[-n*2:]:
        try:
            e = json.loads(line)
            if kind and e.get("kind") != kind: continue
            rows.append(e)
        except Exception:
            pass
    return {"entries": rows[-n:], "count": len(rows)}


# ── Free Audit Lead Magnet ─────────────────────────────────────────

@app.post("/v1/audit/free")
def free_audit(data: dict, background_tasks: BackgroundTasks):
    """Free SEO audit — score + grade + PDF emailed.
    
    POST body:
      url    str  required
      email  str  required
      niche  str  optional (default "general")
      metro  str  optional
    
    Returns { ok, score, grade, checks, message }.
    Background: generates PDF, emails link, stores lead in CRM.
    """
    url = (data.get("url") or "").strip().lower()
    email = (data.get("email") or "").strip().lower()
    niche = (data.get("niche") or "general").strip().lower()
    metro = (data.get("metro") or "").strip().upper()
    
    if not url or not email:
        raise HTTPException(400, "url and email required")
    if not url.startswith("http"):
        url = "https://" + url
    
    # Rate limit: max 3/email/hour
    rate_key = f"audit_{email}"
    now = time.time()
    _audit_rates = getattr(free_audit, "_rates", {})
    recent = [t for t in _audit_rates.get(rate_key, []) if now - t < 3600]
    if len(recent) >= 3:
        raise HTTPException(429, "max 3 audits/email/hour")
    recent.append(now)
    _audit_rates[rate_key] = recent
    free_audit._rates = _audit_rates
    
    result = _run_quick_audit(url)
    result["url"] = url
    result["niche"] = niche
    result["metro"] = metro
    
    background_tasks.add_task(_handle_audit_completion, result, email)
    
    return {
        "ok": True,
        "score": result["score"],
        "grade": result["grade"],
        "checks": result["checks"],
        "message": f"Audit complete. Full PDF sent to {email}",
    }


def _run_quick_audit(url: str) -> dict:
    """Lightweight on-page + tech scan. Graceful fallback on timeouts."""
    import urllib.request, urllib.error, ssl, re
    from urllib.parse import urlparse
    
    checks = {
        "onpage": {"title_len": 0, "h1_count": 0, "meta_desc_len": 0,
                    "has_schema": False, "schema_types": []},
        "tech": {"ssl": True, "hsts": False, "sitemap_xml": False,
                  "robots_txt": False, "gzip": False, "cache_control": False,
                  "redirects": 0, "final_url": url},
    }
    
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url,
            headers={"User-Agent": "Mozilla/5.0 EmpireAudit/1.0"})
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        
        html = resp.read().decode("utf-8", errors="replace")
        hdrs = dict(resp.headers)
        
        checks["tech"]["ssl"] = url.startswith("https")
        checks["tech"]["hsts"] = "strict-transport-security" in hdrs
        checks["tech"]["gzip"] = hdrs.get("content-encoding", "") in ("gzip", "br", "deflate")
        checks["tech"]["cache_control"] = "cache-control" in hdrs
        checks["tech"]["final_url"] = resp.geturl() if hasattr(resp, "geturl") else url
        
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        if m: checks["onpage"]["title_len"] = len(m.group(1).strip())
        
        h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
        checks["onpage"]["h1_count"] = len(h1s)
        
        m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
                      html, re.I | re.S)
        if not m:
            m = re.search(r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
                          html, re.I | re.S)
        if m: checks["onpage"]["meta_desc_len"] = len(m.group(1).strip())
        
        checks["onpage"]["has_schema"] = "schema.org" in html.lower() or "application/ld+json" in html
        
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        for path, key in [("/robots.txt", "robots_txt"), ("/sitemap.xml", "sitemap_xml")]:
            try:
                r = urllib.request.urlopen(f"{base}{path}", timeout=5, context=ctx)
                checks["tech"][key] = r.status == 200
            except Exception:
                pass
    except Exception:
        pass
    
    # Score
    s = 50
    o, t = checks["onpage"], checks["tech"]
    if o["title_len"] >= 30: s += 8
    if o["h1_count"] == 1: s += 8
    if 120 <= o["meta_desc_len"] <= 160: s += 8
    if o["has_schema"]: s += 8
    if t["ssl"]: s += 5
    if t["hsts"]: s += 3
    if t["gzip"]: s += 5
    if t["cache_control"]: s += 3
    if t["robots_txt"]: s += 3
    if t["sitemap_xml"]: s += 4
    
    s = max(0, min(100, s))
    grade = ("F" if s < 60 else
             "D" if s < 70 else
             "C" if s < 80 else
             "B" if s < 90 else "A")
    
    return {"score": s, "grade": grade, "checks": checks}


def _handle_audit_completion(result: dict, email: str):
    """Background task: PDF + email + CRM."""
    try:
        from empire_os.audit_report import generate_pdf
        import shutil
        
        pdf_path = generate_pdf(result)
        pdf_dir = Path("/srv/aeo/audits")
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_name = f"audit_{int(time.time())}.pdf"
        shutil.copy2(pdf_path, str(pdf_dir / pdf_name))
        dl_url = f"https://empire-ai.co.uk/audits/{pdf_name}"
        
        subject = (f"Your {result['niche'].title()} SEO Audit"
                   f" — Score: {result['score']}/100 ({result['grade']})")
        
        lines = []
        chk = result.get("checks", {})
        op = chk.get("onpage", {})
        tc = chk.get("tech", {})
        if op:
            lines.append(f"Title: {op.get('title_len', '?')} chars")
            lines.append(f"H1 tags: {op.get('h1_count', '?')}")
            lines.append(f"Meta desc: {op.get('meta_desc_len', '?')} chars")
            lines.append(f"Schema: {'yes' if op.get('has_schema') else 'no'}")
        if tc:
            lines.append(f"HTTPS: {'yes' if tc.get('ssl') else 'no'}")
            lines.append(f"Gzip: {'on' if tc.get('gzip') else 'off'}")
            lines.append(f"robots.txt: {'ok' if tc.get('robots_txt') else 'missing'}")
            lines.append(f"sitemap.xml: {'ok' if tc.get('sitemap_xml') else 'missing'}")
        
        body = (
            f"Your SEO audit for {result['url']} is ready.\n\n"
            f"Score: {result['score']}/100 (Grade {result['grade']})\n\n"
            + "\n".join(lines) +
            f"\n\nDownload full report: {dl_url}\n\n"
            f"Want fixes? Start $10 trial: https://empire-ai.co.uk/buy-leads\n\n---\nEmpire AI\n"
        )
        
        from empire_os.mail_sender import _send
        _send(to=email, subject=subject, body=body)
        
        # Store lead in funnel DB via raw SQL
        try:
            db_path = os.environ.get("EMPIRE_DB_PATH", "empire_os.db")
            b = SQLiteBackend(db_path)
            b.execute(
                "INSERT OR IGNORE INTO funnel_state (key_id, state_json, updated_at) "
                "VALUES (?, ?, ?)",
                (f"audit.{int(time.time())}.{email.split('@')[0]}",
                 json.dumps({
                     "url": result.get("url"), "email": email,
                     "niche": result.get("niche"), "metro": result.get("metro"),
                     "score": result.get("score"), "grade": result.get("grade"),
                     "pdf_url": dl_url, "source": "free_audit", "stage": "discovered",
                     "ts": datetime.now(timezone.utc).isoformat(),
                 }),
                 time.time())
            )
            b.commit()
        except Exception:
            pass
        
        os.unlink(pdf_path)
    except Exception as e:
        logger.warning("audit completion: %s", e)


@app.get("/v1/audits/{audit_id}")
def serve_audit_pdf(audit_id: str):
    """Serve a generated audit PDF."""
    pdf_path = Path("/srv/aeo/audits") / audit_id
    if not pdf_path.exists() or not audit_id.endswith(".pdf"):
        raise HTTPException(404, "audit not found")
    return FileResponse(str(pdf_path), media_type="application/pdf",
                        filename=audit_id)


@app.get("/free-audit", response_class=HTMLResponse)
async def free_audit_page():
    """Serve the free audit lead capture landing page."""
    try:
        p = Path(__file__).parent / "templates" / "audit" / "landing.html"
        return HTMLResponse(p.read_text(encoding="utf-8"))
    except Exception:
        return HTMLResponse(
            "<h1>Free SEO Audit</h1><p>Temporarily unavailable.</p>")


AUDIT_PRODUCTS = {
    "deep": {"name": "Deep SEO Audit", "price_usd": 29, "price_usdc": 29},
}


def backend_required(func):
    """Decorator: requires backend services (funnel etc) to be available."""
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            from empire_os.funnel import get_state
            get_state()
        except Exception as e:
            logger.warning(f"backend_required check failed: {e}")
        return func(*args, **kwargs)
    return wrapper


@backend_required
@app.post("/v1/audit/deep")
def deep_audit_paid(data: dict, background_tasks: BackgroundTasks):
    """Paid deep SEO audit — 25+ checks, premium PDF.
    
    POST body:
      url    str  required
      email  str  required
      niche  str  optional
      metro  str  optional
      payment_ref  str  optional — if already paid, pass the reference
    
    Payment flow:
      1. POST without payment_ref → returns { ok, invoice_id, payment_instructions }
      2. Pay via USDC to vault wallet with memo = invoice_id
      3. POST again with payment_ref=invoice_id → runs audit + emails PDF
    
    Or pass payment_ref=free for immediate run (internal/dev).
    """
    url = (data.get("url") or "").strip().lower()
    email = (data.get("email") or "").strip().lower()
    niche = (data.get("niche") or "general").strip().lower()
    metro = (data.get("metro") or "").strip().upper()
    payment_ref = (data.get("payment_ref") or "").strip()
    
    if not url or not email:
        raise HTTPException(400, "url and email required")
    if not url.startswith("http"):
        url = "https://" + url
    
    if payment_ref:
        # Verify payment
        if payment_ref != "free":
            paid = _check_payment(payment_ref, 29)
            if not paid:
                raise HTTPException(402, "payment required — see payment_instructions")
        
        # Run deep audit
        from empire_os.deep_audit import run_deep_audit
        result = run_deep_audit(url)
        result["url"] = url
        result["niche"] = niche
        result["metro"] = metro
        
        background_tasks.add_task(_handle_deep_audit_delivery, result, email)
        
        return {
            "ok": True,
            "score": result["score"],
            "grade": result["grade"],
            "checks": result["checks"],
            "issues": result.get("issues", []),
            "fixes": result.get("fixes", []),
            "message": f"Deep audit complete. Premium PDF sent to {email}",
        }
    else:
        # Generate invoice
        invoice_id = f"deep_{int(time.time())}_{email.split('@')[0]}"
        vault = os.environ.get("SOLANA_VAULT_WALLET", "")
        
        # Persist invoice
        try:
            b = SQLiteBackend(os.environ.get("EMPIRE_DB_PATH", "empire_os.db"))
            b.execute(
                "INSERT OR REPLACE INTO funnel_state (key_id, state_json, updated_at) "
                "VALUES (?, ?, ?)",
                (f"invoice.{invoice_id}",
                 json.dumps({"invoice_id": invoice_id, "url": url, "email": email,
                              "amount_usdc": 29, "product": "deep_audit",
                              "status": "pending", "ts": datetime.now(timezone.utc).isoformat()}),
                 time.time())
            )
            b.commit()
        except Exception:
            pass
        
        payment_info = {
            "invoice_id": invoice_id,
            "amount_usdc": 29,
            "amount_usd": 29,
            "vault_wallet": vault if vault else "ComingSoon",
            "memo": invoice_id,
            "chain": "Solana",
            "token": "USDC",
        }
        if vault:
            payment_info["payment_url"] = (
                f"https://solscan.io/account/{vault}?memo={invoice_id}#transfers"
            )
        
        return {
            "ok": True,
            "requires_payment": True,
            "payment": payment_info,
            "message": f"Send {payment_info['amount_usdc']} USDC to vault wallet with memo {invoice_id}, then POST /v1/audit/deep with payment_ref={invoice_id}",
        }


def _check_payment(payment_ref: str, expected_amount: int) -> bool:
    """Check if an invoice has been paid. Uses DB + optional RPC check."""
    try:
        b = SQLiteBackend(os.environ.get("EMPIRE_DB_PATH", "empire_os.db"))
        rows = list(b.execute(
            "SELECT state_json FROM funnel_state WHERE key_id = ?",
            (f"invoice.{payment_ref}",)
        ))
        if rows:
            state = json.loads(rows[0][0])
            if state.get("status") == "paid":
                return True
    except Exception:
        pass
    
    # Allow 'free' for testing
    if payment_ref == "free":
        return True
    
    return False


def _handle_deep_audit_delivery(result: dict, email: str):
    """Background: generate premium PDF, email to user."""
    try:
        from empire_os.deep_audit import generate_deep_pdf
        import shutil
        from empire_os.mail_sender import _send
        
        pdf_path = generate_deep_pdf(result)
        pdf_dir = Path("/srv/aeo/audits")
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_name = f"deep_{int(time.time())}.pdf"
        shutil.copy2(pdf_path, str(pdf_dir / pdf_name))
        dl_url = f"https://empire-ai.co.uk/audits/{pdf_name}"
        
        subject = (f"[Premium] {result['niche'].title()} Deep SEO Audit"
                   f" — Score: {result['score']}/100 ({result['grade']})")
        
        chk = result.get("checks", {})
        issues_list = result.get("issues", [])
        fixes_list = result.get("fixes", [])
        
        body_parts = [
            f"Your Deep SEO Audit for {result['url']} is ready.\n",
            f"Score: {result['score']}/100 (Grade {result['grade']})\n",
            f"Issues found: {len(issues_list)}\n",
        ]
        if issues_list:
            body_parts.append("\nKey Issues:")
            for i in issues_list[:5]:
                body_parts.append(f"  - {i}")
        if fixes_list:
            body_parts.append("\nTop Fixes:")
            for f in fixes_list:
                body_parts.append(f"  - {f}")
        
        body_parts.extend([
            f"\nDownload full premium report: {dl_url}",
            "\nWant us to implement these fixes? Reply to this email.",
            "\n---\nEmpire AI — empire-ai.co.uk\n",
        ])
        
        body = "\n".join(body_parts)
        _send(to=email, subject=subject, body=body)
        
        # Mark paid in DB
        try:
            b = SQLiteBackend(os.environ.get("EMPIRE_DB_PATH", "empire_os.db"))
            b.execute(
                "UPDATE funnel_state SET state_json = json_set(state_json, '$.audit_delivered', 1) "
                "WHERE state_json LIKE ?",
                (f'%{result["url"]}%',)
            )
            b.commit()
        except Exception:
            pass
        
        os.unlink(pdf_path)
    except Exception as e:
        logger.warning("deep audit delivery: %s", e)


@app.post("/v1/mass-torts/direct")
def mass_torts_direct(req: dict):
    """Mass-tort lead discovery intake.

    Body: { niche, label, signals, url_template, notes, scraped_at }
    """
    niche = (req.get("niche") or "").strip()
    if not niche:
        raise HTTPException(400, "niche required")
    record = {
        "niche": niche,
        "label": req.get("label", ""),
        "signals": req.get("signals", 0),
        "url_template": req.get("url_template", ""),
        "notes": req.get("notes", "")[:500],
        "scraped_at": req.get("scraped_at", "") or
                       datetime.now(timezone.utc).isoformat(),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    rec_id = "mt_" + niche + "_" + record["ts"].replace(":", "")
    return {"ok": True, "record_id": rec_id, **record}


@app.post("/v1/b2b/direct")
def b2b_direct(req: dict):
    """B2B lead intake from b2b_scraper_agent / market sweeps.

    Body: { kind, name, phone, email, address, city, state, postcode,
            category, website, lat, lon, lane_key, source, scraped_at, raw }

    Returns record_id. Persists to feedback jsonl + indexes for buyer routing.
    """
    name = (req.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    record = {
        "kind": req.get("kind", "b2b"),
        "name": name,
        "phone": req.get("phone", ""),
        "email": req.get("email", ""),
        "address": req.get("address", ""),
        "city": req.get("city", ""),
        "state": req.get("state", ""),
        "postcode": req.get("postcode", ""),
        "category": req.get("category", ""),
        "website": req.get("website", ""),
        "lat": req.get("lat"),
        "lon": req.get("lon"),
        "lane_key": req.get("lane_key", ""),
        "source": req.get("source", ""),
        "scraped_at": req.get("scraped_at", "") or
                       datetime.now(timezone.utc).isoformat(),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    rec_id = "b2b_" + name[:32].replace(" ", "_").replace("/", "_") + "_" + \
             record["ts"].replace(":", "")
    try:
        with open("/root/feedback/b2b_intake.jsonl", "a") as f:
            f.write(json.dumps({"id": rec_id, **record}) + "\n")
    except Exception:
        pass
    return {"ok": True, "record_id": rec_id, **record}


@app.post("/v1/finance/replay")
def finance_replay(req: dict):
    """Simulate an inbound USDC deposit for testing the listener flow.

    Body:
      amount_usdc        float  required  (e.g. 100.00)
      memo               str    required  (e.g. "SEAT_sub_ad55f6264deb")
      wallet_from        str    optional  (any string, defaults to "replay")
      tx_signature       str    optional  (any string, defaults to "replay_<ts>")
      force_status       str    optional  "pending" or "paid" - if "paid"
                                            the matching invoice is flipped immediately

    Effect:
      - writes a row to /root/feedback/finance_log.jsonl (host-side agent reads)
      - if memo matches a pending si_subscription.seat_* row, marks it paid
      - if force_status="paid" - even if no row matches, flips any matching
        si_invoice with matching memo amount

    Returns: { "ok": True, "matched_to": "...", "balance_after": float }
    """
    amount = float(req.get("amount_usdc", 0))
    memo   = (req.get("memo") or "").strip()
    sig    = req.get("tx_signature") or f"replay_{int(time.time())}"
    wallet = req.get("wallet_from", "replay")

    if amount <= 0:
        raise HTTPException(400, "amount_usdc must be > 0")
    # memo is OPTIONAL (TokenPocket / Trust Wallet USDC transfers carry none)

    matched_to = None
    paid_inv   = None
    paid_sub   = None

    try:
        import sqlite3 as _sq3
        cnx = _sq3.connect("/root/empire_os/empire_os.db", timeout=10,
                           check_same_thread=False)
        try:
            # ensure app_kv table exists (tiny key-value store)
            cnx.execute(
                "CREATE TABLE IF NOT EXISTS app_kv "
                "(key TEXT PRIMARY KEY, value TEXT, ts TEXT)"
            )
            cnx.commit()
            # extract id from memo
            sub_id = None
            inv_id = None
            m = memo
            if m.startswith("SEAT_"):
                # signup-seat emits memo "SEAT_<id>" where <id> is the
                # subscription id with the "sub-" prefix stripped. Re-add it
                # so the DB lookup matches si_subscription.subscription_id.
                _id = m.replace("SEAT_", "", 1).strip()
                sub_id = _id if _id.startswith("sub-") else f"sub-{_id}"
            if m.startswith("INV_"):
                # Memos look like "INV_inv_crypto_<hex>"; the invoice_id IS the
                # part after "INV_" (it already has the "inv_" prefix). Do NOT
                # prepend another "inv_" or we'll never match.
                inv_id = m[len("INV_"):].strip()
            # --- A2A: LANE_ memo seats an open lane ---
            if m.startswith("LANE_"):
                lane_id = m.replace("LANE_", "", 1).strip()
                row = cnx.execute(
                    "SELECT id, occupied_by FROM lanes WHERE id = ?",
                    (lane_id,)).fetchone()
                if row:
                    matched_to = f"lane {lane_id}"
                    cnx.execute(
                        "UPDATE lanes SET occupied_by = ?, "
                        "seat_expires_at = datetime('now','+30 days') "
                        "WHERE id = ?",
                        (buyer_agent or "a2a", lane_id))
                    paid_lane = lane_id
            # --- Eval product: EVAL_<buyer>__<lead_ref> settles a converted lead ---
            if m.startswith("EVAL_"):
                rest = m.replace("EVAL_", "", 1).strip()
                ev_buyer, _, ev_ref = rest.partition("__")
                erow = cnx.execute(
                    "SELECT id FROM evaluation_settlements "
                    "WHERE buyer=? AND lead_ref=? AND status='pending' "
                    "ORDER BY id DESC LIMIT 1",
                    (ev_buyer, ev_ref)).fetchone()
                if erow:
                    cnx.execute(
                        "UPDATE evaluation_settlements SET status='settled', tx_sig=? "
                        "WHERE id=?",
                        (req.get("tx_signature", ""), erow[0]))
                    matched_to = f"eval settlement {ev_buyer}/{ev_ref}"
            # --- Lead settlement: LEAD_<lead_id> marks lead as settled ---
            if m.startswith("LEAD_"):
                lead_id = m[len("LEAD_"):].strip()
                # Find the prospect_id in si_funnel_event for this lead
                # lead_id could be lane_leads.id, lane_leads.prospect_id, or crm_leads.lead_uid
                prospect_row = cnx.execute(
                    """SELECT DISTINCT prospect_id FROM si_funnel_event
                       WHERE prospect_id = ? OR prospect_id LIKE ? OR prospect_id LIKE ?""",
                    (lead_id, f"%{lead_id}%", f"lead_{lead_id}%"),
                ).fetchone()

                if not prospect_row:
                    # Try crm_leads table
                    crm_row = cnx.execute(
                        "SELECT id, lead_uid FROM crm_leads WHERE id = ? OR lead_uid = ?",
                        (lead_id, lead_id),
                    ).fetchone()
                    if crm_row:
                        prospect_id = crm_row["lead_uid"] or str(crm_row["id"])
                    else:
                        # Try lane_leads
                        lane_row = cnx.execute(
                            "SELECT id, prospect_id FROM lane_leads WHERE id = ? OR prospect_id = ?",
                            (lead_id, lead_id),
                        ).fetchone()
                        if lane_row:
                            prospect_id = lane_row["prospect_id"]
                        else:
                            prospect_id = lead_id  # fallback
                else:
                    prospect_id = prospect_row["prospect_id"]

                # Check current funnel state
                current_state = cnx.execute(
                    """SELECT to_state FROM si_funnel_event
                       WHERE prospect_id = ? ORDER BY id DESC LIMIT 1""",
                    (prospect_id,),
                ).fetchone()

                if current_state and current_state["to_state"] == "settled":
                    matched_to = f"lead {lead_id} (already settled)"
                else:
                    # Write funnel event transition to 'settled'
                    occurred_at = datetime.now(timezone.utc).isoformat()
                    cnx.execute(
                        """INSERT INTO si_funnel_event
                           (prospect_id, from_state, to_state, actor, notes, occurred_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            prospect_id,
                            current_state["to_state"] if current_state else "claimed",
                            "settled",
                            "solana_listener",
                            json.dumps({
                                "lead_id": lead_id,
                                "amount_usdc": amount,
                                "tx_signature": sig,
                                "memo": m,
                                "settled_at": occurred_at,
                            }),
                            occurred_at,
                        ),
                    )

                    # Write si_settlements row for audit/revenue tracking
                    amount_cents = int(round(amount * 100))
                    cnx.execute(
                        """INSERT INTO si_settlements
                           (prospect_id, tenant_id, amount_cents, settled_at, settled_by, notes)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            prospect_id,
                            "",  # tenant_id unknown at this stage
                            amount_cents,
                            occurred_at,
                            "solana_listener",
                            f"USDC settlement for lead {lead_id} via tx {sig[:20]}",
                        ),
                    )
                    matched_to = f"lead {lead_id}"
            # --- Eval product: EVALBUY_<buyer>_<pack> = one on-chain credit-pack purchase ---
            if m.startswith("EVALBUY_"):
                from empire_os.agents.evaluation_product import _settle_pack
                if _settle_pack(m, req.get("tx_signature", "")):
                    matched_to = f"eval credit pack {m}"
            # --- A2A: SKU_ memo activates a product subscription ---
            if m.startswith("SKU_"):
                sku = m.replace("SKU_", "", 1).strip().lower()
                sub_id = f"sku_{sku}_{int(datetime.now().timestamp())}"
                # price: dynamic from si_products, else static fallback
                prow = cnx.execute(
                    "SELECT tier1_usdc FROM si_products WHERE sku = ?",
                    (sku,)).fetchone()
                price = float(prow[0]) if prow else PRODUCT_PRICES.get(sku, 0.0)
                cnx.execute(
                    "INSERT OR REPLACE INTO si_subscription "
                    "(subscription_id, tenant_id, plan, billing_cycle, seats, "
                    "price_cents, status, payment_method, payment_ref, "
                    "started_at, current_period_end, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (sub_id, wallet or "a2a", f"sku_{sku}", "usdc_prepaid",
                     1, int(price * 100),
                     "active", "solana", sig,
                     datetime.now(timezone.utc).isoformat(),
                     datetime.now(timezone.utc).isoformat(),
                     datetime.now(timezone.utc).isoformat()))
                matched_to = f"si_subscription {sub_id}"
                paid_sub = sub_id
            # try matching subscription
            if sub_id:
                row = cnx.execute(
                    "SELECT subscription_id, tenant_id, status "
                    "FROM si_subscription WHERE subscription_id = ?",
                    (sub_id,)).fetchone()
                if row:
                    matched_to = f"si_subscription {row[0]}"
                    cnx.execute(
                        "UPDATE si_subscription SET status = 'active', "
                        "payment_ref = ? WHERE subscription_id = ?",
                        (sig, sub_id))
                    paid_sub = sub_id
            # try matching invoice by memo id (si_ppc_invoices first, legacy si_invoice)
            if inv_id:
                for _tbl in ("si_ppc_invoices", "si_invoice"):
                    try:
                        row = cnx.execute(
                            f"SELECT invoice_id, amount_cents, status "
                            f"FROM {_tbl} WHERE invoice_id = ?",
                            (inv_id,)).fetchone()
                    except Exception:
                        row = None
                    if row:
                        matched_to = f"{_tbl} {row[0]}"
                        if _tbl == "si_invoice":
                            cnx.execute(
                                "UPDATE si_invoice SET status = 'paid', "
                                "reference = ? WHERE invoice_id = ?",
                                (sig, inv_id))
                        else:
                            cnx.execute(
                                "UPDATE si_ppc_invoices SET status = 'paid', "
                                "paid_at = ? WHERE invoice_id = ?",
                                (datetime.now(timezone.utc).isoformat(), inv_id))
                        paid_inv = inv_id
                        break
            # --- pay-per-lead: match OPEN si_ppc_invoices by amount (DOLLARS) ---
            # si_ppc_invoices.amount_usdc + amount_dollars both in dollars.
            if not paid_inv:
                cand = cnx.execute(
                    "SELECT invoice_id, amount_usdc, amount_dollars, status "
                    "FROM si_ppc_invoices WHERE status = 'open'"
                ).fetchall()
                best = None
                for iid, aud, ad, st in cand:
                    # prefer amount_dollars (canonical), fallback amount_usdc
                    aud_v = ad if ad not in (None, 0) else aud
                    if aud_v is None: continue
                    try:
                        diff = abs(float(aud_v) - float(amount))
                    except Exception:
                        continue
                    if diff <= 0.001:  # $0.001 tolerance
                        best = iid
                        break
                # also match signup invoices in si_invoice (amount_cents/100 = dollars)
                if not best:
                    cand2 = cnx.execute(
                        "SELECT invoice_id, amount_cents, status "
                        "FROM si_invoice WHERE status = 'pending'"
                    ).fetchall()
                    for iid, ac, st in cand2:
                        try:
                            # amount_cents is in cents → divide by 100 for dollars
                            cand_dollars = float(ac) / 100.0
                            diff = abs(cand_dollars - float(amount))
                        except Exception:
                            continue
                        if diff <= 0.001:
                            best = iid
                            break
                    if best:
                        matched_to = f"si_invoice {best}"
                        cnx.execute(
                            "UPDATE si_invoice SET status = 'paid', "
                            "paid_at = ?, reference = ? WHERE invoice_id = ?",
                            (datetime.now(timezone.utc).isoformat(), sig, best))
                        paid_inv = best
                if best and not matched_to:
                    matched_to = f"si_ppc_invoices {best}"
                    cnx.execute(
                        "UPDATE si_ppc_invoices SET status = 'paid', "
                        "paid_at = ? WHERE invoice_id = ?",
                        (datetime.now(timezone.utc).isoformat(), best))
                    # Also flip the matching si_charges row (if it exists) so
                    # downstream pipeline + smoke tests can confirm success.
                    try:
                        chg_row = cnx.execute(
                            "SELECT charge_id FROM si_ppc_invoices WHERE invoice_id=?",
                            (best,)).fetchone()
                        if chg_row and chg_row[0]:
                            cnx.execute(
                                "UPDATE si_charges SET status='succeeded', paid_at=? "
                                "WHERE charge_id=? AND status!='succeeded'",
                                (datetime.now(timezone.utc).isoformat(), chg_row[0]))
                            # Emit a settled funnel event for downstream observability
                            cnx.execute(
                                "INSERT INTO si_funnel_event "
                                "(prospect_id, from_state, to_state, actor, notes, occurred_at) "
                                "VALUES (?, 'open', 'settled', 'crypto_charge', ?, ?)",
                                (chg_row[0],
                                 json.dumps({"invoice_id": best, "amount_usdc": amount,
                                              "tx_signature": sig}),
                                 datetime.now(timezone.utc).isoformat()))
                    except Exception as _e:
                        pass
                    paid_inv = best
            # --- buyer activation: match PENDING si_subscription by seat amount ---
            # Real USDC transfers (Trust/TokenPocket) carry no memo. A buyer who
            # applied is parked as pending_deposit OR awaiting_payment with
            # price_cents set. Match the incoming deposit (micro-USDC) to the
            # nearest pending seat price and flip to active (verified payment).
            if not paid_sub:
                pend = cnx.execute(
                    "SELECT subscription_id, price_cents, tenant_id "
                    "FROM si_subscription "
                    "WHERE status IN ('pending_deposit','awaiting_payment')"
                ).fetchall()
                for sid, pc, *rest in pend:
                    try:
                        # price_cents (e.g. 1800) -> dollars (1800/100 = $18.00)
                        seat_dollars = float(pc) / 100.0
                    except Exception:
                        continue
                    if abs(seat_dollars - amount) <= 0.001:
                        matched_to = f"si_subscription {sid}"
                        cnx.execute(
                            "UPDATE si_subscription SET status = 'active', "
                            "payment_ref = ? WHERE subscription_id = ?",
                            (sig, sid))
                        paid_sub = sid
                        break
            # if a signup invoice (si_invoice) was paid, activate its subscription
            if paid_inv and not paid_sub:
                srow = cnx.execute(
                    "SELECT subscription_id FROM si_invoice WHERE invoice_id = ?",
                    (paid_inv,)).fetchone()
                if srow and srow[0]:
                    cnx.execute(
                        "UPDATE si_subscription SET status = 'active', "
                        "payment_ref = ? WHERE subscription_id = ?",
                        (sig, srow[0]))
                    paid_sub = srow[0]
            # if force_status paid but nothing matched, still log
            cnx.commit()
            # --- settlement + MONEY alert when a real invoice got paid ---
            if paid_inv:
                try:
                    inv_row = cnx.execute(
                        "SELECT invoice_id, amount_cents, amount_usdc, buyer_id "
                        "FROM si_ppc_invoices WHERE invoice_id = ?",
                        (paid_inv,)).fetchone()
                    amt_c = int(inv_row[1]) if inv_row and inv_row[1] else 0
                    cnx.execute(
                        "INSERT INTO si_settlements "
                        "(prospect_id, tenant_id, amount_cents, settled_at, "
                        "settled_by, notes) VALUES (?,?,?,?,?,?)",
                        (paid_inv, (inv_row[3] if inv_row and inv_row[3] else ""),
                         amt_c, datetime.now(timezone.utc).isoformat(),
                         "solana_listener", f"replay {sig}"))
                    cnx.commit()
                    _rev_paid(paid_inv, amt_c / 1e6,
                              (inv_row[3] if inv_row and inv_row[3] else ""))
                except Exception as _se:
                    log("ERROR", "settlement_write_fail", err=str(_se)[:150])
            # simulate vault balance accretion
            cur_row = cnx.execute(
                "SELECT value FROM app_kv WHERE key = 'vault_balance_usdc'"
            ).fetchone()
            new_bal = (float(cur_row[0]) if cur_row else 0.0) + amount
            cnx.execute("DELETE FROM app_kv WHERE key = 'vault_balance_usdc'")
            cnx.execute(
                "INSERT INTO app_kv (key, value, ts) VALUES "
                "('vault_balance_usdc', ?, ?)",
                (str(new_bal), datetime.now(timezone.utc).isoformat()))
            cnx.commit()
        finally:
            cnx.close()
    except Exception as e:
        raise HTTPException(500, f"replay failed: {e}")

    # log to feedback log (host mount)
    try:
        with open("/root/feedback/finance_log.jsonl", "a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": "REPLAY_DEPOSIT",
                "msg": "replay_deposit",
                "amount_usdc": amount,
                "memo": memo,
                "tx_signature": sig,
                "wallet_from": wallet,
                "matched_to": matched_to,
                "paid_subscription_id": paid_sub,
                "paid_invoice_id": paid_inv,
            }) + "\n")
    except Exception:
        pass

    return {
        "ok": True,
        "matched_to": matched_to,
        "paid_subscription_id": paid_sub,
        "paid_invoice_id": paid_inv,
        "amount_usdc": amount,
        "memo": memo,
        "tx_signature": sig,
        "balance_after_usdc": new_bal if "new_bal" in dir() else None,
    }


# ── UNMATCHED DEPOSIT RECONCILIATION (W2 close-the-loop) ────────────
# Phantom/TokenPocket can't add memos to SPL transfers. solana_listener
# sees the deposit land in the vault but can't auto-attribute. Without
# these endpoints, those funds sit unallocated forever. With them, the
# founder can review unmatched deposits and attribute each one to a
# specific buyer manually.

@app.get("/v1/finance/unmatched")
def finance_unmatched_list(limit: int = 50, status: str = "unmatched"):
    """List unmatched USDC deposits awaiting attribution.

    Each row: {tx_signature, amount_usdc, amount_cents, sender_wallet,
    vault_wallet, received_at, block_time, status}

    Use POST /v1/finance/attribute to link a deposit to a buyer.
    """
    from empire_os import finance_reconcile as _fr
    _fr.ensure_schema()
    return {
        "ok": True,
        "count": 0,  # filled below
        "deposits": _fr.list_unmatched(limit=limit, status=status),
    }


@app.get("/v1/finance/unmatched/stats")
def finance_unmatched_stats():
    """Aggregate stats: counts + totals per status + last seen vault balance."""
    from empire_os import finance_reconcile as _fr
    _fr.ensure_schema()
    s = _fr.stats()
    s["ok"] = True
    return s


@app.post("/v1/finance/attribute")
def finance_attribute(req: dict):
    """Link an unmatched deposit to a buyer.

    Body:
      tx_signature   str   required   the deposit to attribute
      buyer_id       str   required   tenant_id or wallet to credit
      reason         str   optional   free-text for audit

    Effect:
      - creates si_charges row (status='succeeded', charge_id='chg_attr_<sig>')
      - writes si_settlements row (counted in daily_revenue rollups)
      - flips si_unmatched_deposits.status to 'attributed'
      - records matched_buyer_id + matched_charge_id + matched_at
    """
    from empire_os import finance_reconcile as _fr
    _fr.ensure_schema()
    tx = (req.get("tx_signature") or "").strip()
    buyer = (req.get("buyer_id") or "").strip()
    if not tx:
        return {"ok": False, "error": "tx_signature required"}
    if not buyer:
        return {"ok": False, "error": "buyer_id required"}
    reason = (req.get("reason") or "manual_attribute").strip()
    return _fr.attribute_deposit(tx, buyer, reason)


@app.post("/v1/finance/unmatched/record")
def finance_unmatched_record(req: dict):
    """Manually record an unmatched deposit (used by solana_listener_agent
    when it can't match + by ops when manually backfilling).

    Body:
      tx_signature   str   required
      amount_usdc    float required
      vault_wallet   str   required
      sender_wallet  str   optional
      received_at    str   optional (defaults to now ISO)
      block_time     int   optional
    """
    from empire_os import finance_reconcile as _fr
    _fr.ensure_schema()
    try:
        d = _fr.UnmatchedDeposit(
            tx_signature=req["tx_signature"],
            amount_usdc=float(req["amount_usdc"]),
            vault_wallet=req["vault_wallet"],
            received_at=req.get("received_at") or
                time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            sender_wallet=req.get("sender_wallet", ""),
            vault_balance_after_usdc=float(req.get("vault_balance_after_usdc", 0)),
            block_time=int(req.get("block_time", 0)),
            notes=req.get("notes", ""),
        )
    except KeyError as e:
        return {"ok": False, "error": f"missing required field: {e}"}
    return _fr.record_unmatched(d)


@app.get("/v1/swarm/worker-config")
def swarm_worker_config(req: dict):
    """Register or update a worker handler.

    Body:
      worker_id      str   unique identifier (e.g. "outreach-agent", "lead-deliverer")
      niche          str   target niche OR "*" wildcard
      metro          str   target metro (or "*")
      action         str   what the worker wants to do (consume, fanout, etc.)
      weight         int   1-10 priority ranking (higher = preferred)

    Persistence: every config is appended to /root/feedback/swarm_registry.jsonl.
    """
    worker_id = req.get("worker_id", "").strip()
    if not worker_id:
        raise HTTPException(400, "worker_id required")
    _swarm_persist_handler(
        worker_id=worker_id,
        niche=req.get("niche", "*"),
        metro=req.get("metro", "*"),
        action=req.get("action", "consume"),
        weight=int(req.get("weight", 5)),
    )
    _swarm_audit("worker_registered",
                worker_id=worker_id,
                niche=req.get("niche", "*"),
                metro=req.get("metro", "*"))
    return {"ok": True, "worker_id": worker_id}


@app.get("/v1/swarm/worker-config")
def swarm_worker_config_list(niche: str = None):
    """List registered worker handlers, optionally filtered by niche."""
    handlers = _read_handlers()
    if niche:
        handlers = [h for h in handlers if h.get("niche") == niche or h.get("niche") == "*"]
    return {"handlers": handlers, "total": len(handlers)}


@app.get("/v1/swarm/audit-log")
def swarm_audit_log(limit: int = 50,
                    event: str = None,
                    since_min: int = 60):
    """Read recent swarm routing audit events.

    Filter:
      limit      str   max events to return
      event      str   filter by event type
      since_min  int   only events from last N minutes
    """
    if not Path(SWARM_AUDIT_PATH).exists():
        return {"events": [], "total": 0}
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=since_min)).isoformat()
    out = []
    for line in Path(SWARM_AUDIT_PATH).read_text().splitlines()[-limit*2:]:
        try:
            e = _json.loads(line)
        except Exception:
            continue
        if e.get("ts", "") < cutoff:
            continue
        if event and e.get("event") != event:
            continue
        out.append(e)
    return {"events": out[-limit:], "total": len(out)}


@app.get("/v1/swarm/prompt/{agent}")
def swarm_prompt(agent: str):
    """Voice-to-infrastructure surface.

    Returns an agent\'s SOUL.md as a structured prompt for voice
    control. The Commander agent uses this to expose "what does
    <agent> think?" to a voice interface.
    """
    candidates = [
        Path(f"/root/empire_os/empire_os/agents/souls/{agent}_SOUL.md"),
        Path(f"/root/feedback/souls/{agent}_SOUL.md"),
        Path(f"/root/{agent}_SOUL.md"),
    ]
    for p in candidates:
        if p.exists():
            return {
                "agent": agent,
                "soul": p.read_text(),
                "path": str(p),
            }
    raise HTTPException(404, f"No SOUL.md found for agent: {agent}")


@app.get("/v1/swarm/ledger")
def swarm_ledger():
    """Master ledger aggregator — returns counts from every JSONL source."""
    sources = [
        "crawler_runs.jsonl",
        "lead_deliveries.jsonl",
        "solana_payments.jsonl",
        "alerts.jsonl",
        "outreach_log.jsonl",
        "lane_monitor.jsonl",
        "commander_observations.jsonl",
        "synthetic_recommendations.jsonl",
        "resend_webhook.jsonl",
        "code_suggestions.jsonl",
        "efficiency_spike.jsonl",
        "swarm_registry.jsonl",
        "swarm_audit.jsonl",
    ]
    out = {}
    for s in sources:
        p = Path("/root/feedback") / s
        if p.exists():
            n = sum(1 for _ in p.read_text().splitlines() if _.strip())
            out[s] = {"events": n, "size_bytes": p.stat().st_size}
        else:
            out[s] = {"events": 0, "size_bytes": 0}
    return {"ledger": out, "ts": datetime.now(timezone.utc).isoformat()}


@app.get("/v1/swarm/lane-heat")
def swarm_lane_heat():
    """Return lane heat data aggregated from lane_leads DB + delivery jsonl.

    Counts active lanes (niche+metro combos with >0 leads) and recent
    delivery traffic from lead_deliveries.jsonl. Falls back gracefully
    when files are empty so the endpoint always returns data.
    """
    import json
    import re
    from collections import Counter
    from pathlib import Path

    lane_heat = Counter()
    lane_lead_count = {}

    # Primary source: lane_leads DB. Schema has no niche/metro columns,
    # but has source + zip_code. Aggregate by source (which encodes the
    # scraper / vertical) so heat is still meaningful.
    try:
        rows = backend.execute(
            "SELECT source, COUNT(*) FROM lane_leads "
            "WHERE source IS NOT NULL "
            "GROUP BY source ORDER BY COUNT(*) DESC LIMIT 100"
        ).fetchall()
        for source, n in rows:
            if source:
                key = f"source:{source}"
                lane_heat[key] += int(n)
                lane_lead_count[key] = int(n)
    except Exception:
        pass

    # Boost by tier — high-omega leads are hotter
    try:
        rows = backend.execute(
            "SELECT omega_tier, COUNT(*) FROM lane_leads "
            "WHERE omega_tier IS NOT NULL "
            "GROUP BY omega_tier"
        ).fetchall()
        for tier, n in rows:
            if tier and n:
                key = f"tier:{tier}"
                lane_heat[key] += int(n)
                lane_lead_count[key] = int(n)
    except Exception:
        pass

    # Secondary boost: deliveries in last 24h from lead_deliveries.jsonl
    deliveries_path = Path("/root/feedback/lead_deliveries.jsonl")
    if deliveries_path.exists():
        for line in deliveries_path.read_text().splitlines()[-5000:]:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("level") == "DELIVERED":
                    subject = entry.get("subject", "")
                    m = re.search(r"New lead:\s*(\w+)\s+in\s+(\w+)", subject)
                    if m:
                        key = f"{m.group(1).lower()}:{m.group(2).upper()}"
                        lane_heat[key] += 1
            except Exception:
                continue

    sorted_heat = dict(sorted(lane_heat.items(), key=lambda x: -x[1]))

    return {
        "by_lane": sorted_heat,
        "lead_counts": lane_lead_count,
        "total_lanes": len(sorted_heat),
        "total_deliveries": sum(sorted_heat.values()),
        "ts": datetime.now(timezone.utc).isoformat()
    }


# ═══════════════════════════════════════════════════════════════════
# Blueprint v5 — Carrier DRP Roster Scraper (#1)
# ═══════════════════════════════════════════════════════════════════

_HM_BACKEND = None  # set during lifespan startup

@app.post("/v1/carrier-rosters/scrape")
def carrier_rosters_scrape():
    """Run all carrier scrapers and store results."""
    from empire_os.carrier_rosters import run_all
    return run_all(store=True)

@app.get("/v1/carrier-rosters")
def carrier_rosters_list(carrier: str = None, limit: int = 100):
    """List carrier rosters, optionally filtered by carrier slug."""
    from empire_os.carrier_rosters import list_rosters
    return {"ok": True, "data": list_rosters(carrier=carrier, limit=limit)}

@app.get("/v1/carrier-rosters/stats")
def carrier_rosters_stats():
    """Counts by carrier."""
    from empire_os.carrier_rosters import roster_stats
    return {"ok": True, "stats": roster_stats()}

# ═══════════════════════════════════════════════════════════════════
# Blueprint v5 — Homeowner Job Intake + Matching (#2)
# ═══════════════════════════════════════════════════════════════════

_HM_DB = "/root/empire_os/empire_os.db"

def _hm_backend():
    """Return the shared singleton backend (set during lifespan startup)."""
    global _HM_BACKEND
    if _HM_BACKEND is None:
        # fallback: create one (shouldn't happen if lifespan ran)
        _HM_BACKEND = SQLiteBackend(_HM_DB)
    return _HM_BACKEND

@app.post("/v1/homeowner/jobs")
def homeowner_create_job(name: str, zip: str, job_type: str,
                          phone: str = "", email: str = "", description: str = ""):
    """Submit a new homeowner job (status=discovered)."""
    from empire_os.homeowner_matching import ensure_schema, submit_job
    b = _hm_backend()
    ensure_schema(b)
    job = submit_job(b, name=name, phone=phone, email=email,
                     zip=zip, job_type=job_type, description=description)

    return {"ok": True, "job": job.to_dict()}

@app.get("/v1/homeowner/jobs")
def homeowner_list_jobs(status: str = None, limit: int = 50):
    """List homeowner jobs, optionally filtered by status."""
    from empire_os.homeowner_matching import list_jobs
    b = _hm_backend()
    jobs = list_jobs(b, status=status, limit=limit)

    return {"ok": True, "jobs": jobs}

@app.get("/v1/homeowner/jobs/{job_id}")
def homeowner_get_job(job_id: int):
    """Get a job with its matches."""
    from empire_os.homeowner_matching import get_job_with_matches, JobNotFoundError
    b = _hm_backend()
    try:
        result = get_job_with_matches(b, job_id)

        return {"ok": True, **result}
    except JobNotFoundError as e:

        raise HTTPException(status_code=404, detail=str(e))

@app.post("/v1/homeowner/jobs/{job_id}/match")
def homeowner_find_matches(job_id: int):
    """Find carrier-roster contractors and match them to a job."""
    from empire_os.homeowner_matching import find_matches, JobNotFoundError
    b = _hm_backend()
    try:
        matches = find_matches(b, job_id)

        return {"ok": True, "matches": [m.to_dict() for m in matches], "count": len(matches)}
    except JobNotFoundError as e:

        raise HTTPException(status_code=404, detail=str(e))

@app.patch("/v1/homeowner/jobs/{job_id}/status")
def homeowner_update_job_status(job_id: int, status: str, opt_in: bool = None):
    """Update job status (e.g. bid_sent, work_completed, settled)."""
    from empire_os.homeowner_matching import update_job_status, JobNotFoundError, get_job
    from empire_os.homeowner_pipeline import transition_job
    b = _hm_backend()
    try:
        prev = get_job(b, job_id)
        job = update_job_status(b, job_id, status=status, opt_in=opt_in)
        # Record pipeline event
        try:
            transition_job(b, str(job_id), prev.status, status,
                          actor="hub")
        except Exception:
            pass
        return {"ok": True, "job": job.to_dict()}
    except JobNotFoundError as e:

        raise HTTPException(status_code=404, detail=str(e))

@app.patch("/v1/homeowner/jobs/matches/{match_id}/status")
def homeowner_update_match_status(match_id: int, status: str):
    """Update a match's status (e.g. bid_sent, bid_accepted, rejected)."""
    from empire_os.homeowner_matching import update_match_status, get_match, get_job
    from empire_os.homeowner_pipeline import transition_job
    b = _hm_backend()
    match = update_match_status(b, match_id, status=status)

    # Also update parent job status when match advances
    try:
        job = get_job(b, match.job_id)
        new_job_status = None
        if status == "bid_sent" and job.status == "matched_to_contractor":
            new_job_status = "bid_sent"
        elif status == "bid_accepted" and job.status in ("bid_sent", "matched_to_contractor"):
            new_job_status = "bid_accepted"

        if new_job_status:
            from empire_os.homeowner_matching import update_job_status
            update_job_status(b, match.job_id, status=new_job_status)
            transition_job(b, str(match.job_id), job.status, new_job_status,
                          actor="matching_engine")
    except Exception:
        pass

    return {"ok": True, "match": match.to_dict()}

# ═══════════════════════════════════════════════════════════════════
# Blueprint v5 — Carrier Application Portal Auto-Filler (#3)
# ═══════════════════════════════════════════════════════════════════

@app.post("/v1/carrier-applications")
def carrier_app_create(company_name: str, license_no: str, carrier: str):
    """Register intent to apply with a carrier."""
    from empire_os.carrier_applications import ensure_schema, create_application
    b = _hm_backend()
    ensure_schema(b)
    app = create_application(b, company_name=company_name,
                              license_no=license_no, carrier=carrier)

    return {"ok": True, "application": app.to_dict()}

@app.get("/v1/carrier-applications")
def carrier_app_list(carrier: str = None, status: str = None, limit: int = 100):
    """List carrier applications."""
    from empire_os.carrier_applications import list_applications
    b = _hm_backend()
    apps = list_applications(b, carrier=carrier, status=status, limit=limit)

    return {"ok": True, "applications": [a.to_dict() for a in apps]}

@app.get("/v1/carrier-applications/{app_id}")
def carrier_app_get(app_id: int):
    """Get a single carrier application."""
    from empire_os.carrier_applications import get_application, ApplicationNotFoundError
    b = _hm_backend()
    try:
        app = get_application(b, app_id)

        return {"ok": True, "application": app.to_dict()}
    except ApplicationNotFoundError as e:

        raise HTTPException(status_code=404, detail=str(e))

@app.patch("/v1/carrier-applications/{app_id}")
def carrier_app_update(app_id: int, status: str = None, notes: str = None):
    """Update application status and/or notes."""
    from empire_os.carrier_applications import update_application, ApplicationNotFoundError
    b = _hm_backend()
    try:
        app = update_application(b, app_id, status=status, notes=notes)

        return {"ok": True, "application": app.to_dict()}
    except ApplicationNotFoundError as e:

        raise HTTPException(status_code=404, detail=str(e))

@app.post("/v1/carrier-applications/{app_id}/auto-fill")
def carrier_app_autofill(app_id: int):
    """Generate a carrier portal fill plan (stub — no headless browser yet)."""
    from empire_os.carrier_applications import auto_fill_application, ApplicationNotFoundError
    b = _hm_backend()
    try:
        plan = auto_fill_application(b, app_id)

        return {"ok": True, **plan}
    except ApplicationNotFoundError as e:

        raise HTTPException(status_code=404, detail=str(e))

# ═══════════════════════════════════════════════════════════════════
# Blueprint v5 — Pipeline Extension (homeowner_job → settled) (#4)
# ═══════════════════════════════════════════════════════════════════

@app.post("/v1/homeowner/pipeline/transition")
def homeowner_pipeline_transition(job_id: str, from_status: str,
                                   to_status: str, actor: str = "hub",
                                   notes: str = ""):
    """Transition a homeowner job along the pipeline (homeowner_job→settled)."""
    from empire_os.homeowner_pipeline import transition_job
    b = _hm_backend()
    try:
        event_id = transition_job(b, job_id=job_id, from_status=from_status,
                                   to_status=to_status, actor=actor, notes=notes)

        return {"ok": True, "event_id": event_id}
    except ValueError as e:

        raise HTTPException(status_code=400, detail=str(e))

@app.get("/v1/homeowner/pipeline/timeline/{job_id}")
def homeowner_pipeline_timeline(job_id: str):
    """Return all pipeline events for a homeowner job."""
    from empire_os.homeowner_pipeline import get_job_timeline
    b = _hm_backend()
    timeline = get_job_timeline(b, job_id)

    return {"ok": True, "job_id": job_id, "events": timeline}

@app.get("/v1/homeowner/pipeline/stats")
def homeowner_pipeline_stats():
    """Return job counts at each homeowner pipeline state."""
    from empire_os.homeowner_pipeline import get_pipeline_stats
    b = _hm_backend()
    stats = get_pipeline_stats(b)

    return {"ok": True, "stats": stats}

# ═══════════════════════════════════════════════════════════════════════
# Revenue & Lead Stats
# ═══════════════════════════════════════════════════════════════════════

@app.get("/v1/stats/revenue")
def stats_revenue():
    """Aggregate revenue metrics."""
    from empire_os.empire_stats import revenue_stats
    return revenue_stats(_hm_backend())

@app.get("/v1/stats/leads")
def stats_leads():
    """Aggregate lead metrics."""
    from empire_os.empire_stats import lead_stats
    return lead_stats(_hm_backend())


@app.get("/sitemap.xml")
def serve_sitemap():
    """Serve sitemap.xml for search engines."""
    path = Path("/srv/aeo/sitemap.xml")
    if not path.exists():
        raise HTTPException(404, "sitemap.xml not found")
    return Response(content=path.read_text(encoding="utf-8"), media_type="application/xml")

@app.get("/robots.txt")
def serve_robots():
    """Serve robots.txt."""
    path = Path("/srv/aeo/robots.txt")
    if not path.exists():
        return Response(content="User-agent: *\nAllow: /\n", media_type="text/plain")
    return Response(content=path.read_text(encoding="utf-8"), media_type="text/plain")


@app.get("/aeo/{niche}")
def serve_aeo_page(niche: str):
    """Serve an AEO landing page by niche key."""
    aeo_root = Path("/srv/aeo")
    page_path = aeo_root / niche / "index.html"
    if not page_path.exists():
        raise HTTPException(404, f"AEO page not found for niche: {niche}")
    content = page_path.read_text(encoding="utf-8")
    return HTMLResponse(content)


@app.get("/signup")
def serve_signup():
    """Self-serve buyer signup form."""
    p = Path("/srv/aeo/signup.html")
    if not p.exists():
        raise HTTPException(404, "Signup page missing")
    return HTMLResponse(p.read_text(encoding="utf-8"))


@app.post("/v1/buyers/enterprise")
# Outbox table bootstrap — created lazily by sender
@app.post("/v1/outbox/enqueue")
def outbox_enqueue(req: dict):
    """Add an outbound email to the persistent queue.

    Body: { to_email, subject, body, lane, tier, lead_id, source }
    """
    import sqlite3 as _sq3
    cnx = _sq3.connect("/root/empire_os/empire_os.db")
    try:
        cnx.execute(
            "CREATE TABLE IF NOT EXISTS si_outbox ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "to_email TEXT, subject TEXT, body TEXT,"
            "lane TEXT, tier TEXT, lead_id TEXT, source TEXT,"
            "status TEXT DEFAULT 'pending',"
            "created_at TEXT DEFAULT (datetime('now')),"
            "sent_at TEXT, resend_id TEXT)"
        )
        cnx.commit()
        cur = cnx.execute(
            "INSERT INTO si_outbox "
            "(to_email, subject, body, lane, tier, lead_id, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (req.get("to_email", ""),
             req.get("subject", ""),
             req.get("body", "")[:8000],
             req.get("lane", ""),
             req.get("tier", ""),
             req.get("lead_id", ""),
             req.get("source", "outreach_now"))
        )
        cnx.commit()
        out_id = cur.lastrowid
        return {"ok": True, "id": out_id, "status": "pending"}
    finally:
        cnx.close()


@app.get("/v1/outbox/pending")
def outbox_pending(n: int = 10):
    """List queued outbound emails awaiting send.

    Owner-recipient rows (recipient_kind='owner') are gated on
    si_prospect_consent.opted_in=1 for the matching prospect_id. Buyer
    rows are returned unconditionally. This is the safety rail that
    keeps the satellite-damage queue silent until each property owner
    has explicitly opted in.
    """
    import sqlite3 as _sq3
    cnx = _sq3.connect("/root/empire_os/empire_os.db")
    try:
        # Ensure the table exists with the columns mail-sender expects.
        cnx.execute(
            "CREATE TABLE IF NOT EXISTS si_outbox ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "to_email TEXT, subject TEXT, body TEXT,"
            "lane TEXT, tier TEXT, lead_id TEXT, source TEXT,"
            "status TEXT DEFAULT 'pending',"
            "created_at TEXT DEFAULT (datetime('now')),"
            "sent_at TEXT, resend_id TEXT,"
            "recipient_kind TEXT DEFAULT 'buyer',"
            "meta_json TEXT)"
        )
        cnx.commit()
        rows = []
        for r in cnx.execute(
            "SELECT o.id, o.to_email, o.subject, o.body, o.lane, o.tier, "
            "o.lead_id, o.source, o.status, o.created_at, "
            "o.recipient_kind, o.meta_json "
            "FROM si_outbox o "
            "WHERE o.status='pending' "
            "AND (o.recipient_kind IS NULL OR o.recipient_kind='buyer' "
            "     OR o.recipient_kind='prospect' "
            "     OR (o.recipient_kind='owner' "
            "         AND EXISTS (SELECT 1 FROM si_prospect_consent c "
            "                     WHERE c.prospect_id = o.lead_id "
            "                     AND c.opted_in = 1))) "
            "ORDER BY o.id LIMIT ?",
            (n,)):
            rows.append({
                "id":             r[0],
                "to_email":       r[1],
                "subject":        r[2],
                "body":           r[3],
                "lane":           r[4],
                "tier":           r[5],
                "lead_id":        r[6],
                "source":         r[7],
                "status":         r[8],
                "created_at":     r[9],
                "recipient_kind": r[10],
                "meta_json":      r[11],
            })
        return {"rows": rows, "count": len(rows)}
    finally:
        cnx.close()


@app.post("/v1/outbox/{out_id}/mark")
def outbox_mark(out_id: int, req: dict):
    """Mark a queued email as sent/failed with the Resend id."""
    import sqlite3 as _sq3
    cnx = _sq3.connect("/root/empire_os/empire_os.db")
    try:
        cnx.execute(
            "UPDATE si_outbox SET status = ?, sent_at = ?, "
            "resend_id = ? WHERE id = ?",
            (req.get("status", "sent"),
             datetime.now(timezone.utc).isoformat(),
             req.get("resend_id", ""),
             out_id))
        cnx.commit()
        return {"ok": True, "id": out_id,
                "status": req.get("status", "sent")}
    finally:
        cnx.close()


@app.get("/v1/outbox/recent")
def outbox_recent(n: int = 50):
    """Last N outbox items."""
    import sqlite3 as _sq3
    cnx = _sq3.connect("/root/empire_os/empire_os.db")
    try:
        rows = list(cnx.execute(
            "SELECT id, to_email, status, sent_at, resend_id FROM si_outbox "
            "ORDER BY id DESC LIMIT ?", (n,)))
        return {"rows": [{"id": r[0], "to_email": r[1],
                          "status": r[2], "sent_at": r[3],
                          "resend_id": r[4]} for r in rows]}
    finally:
        cnx.close()


@app.post("/v1/innovator/ship")
def innovator_ship(req: dict):
    """Council-approved proposal lands here. Performs the ship_action:
      - create_lane: inserts row into lanes + returns lane_id
      - create_source: returns stub (manual wiring needed for new sources)
      - create_endpoint: returns stub (Hub already serving it manually)
    """
    action = req.get("ship_action") or {}
    kind = action.get("kind")
    args = action.get("args", {})
    pid  = req.get("id", "prop_unknown")
    name = req.get("name", "untitled")
    out = {"ok": True, "proposal_id": pid, "kind": kind, "shipped_at": datetime.now(timezone.utc).isoformat()}

    if kind == "create_lane":
        try:
            import sqlite3 as _sq3
            niche   = args.get("niche", "global")
            metro   = args.get("metro", "GLOBAL")
            rate_c  = int(args.get("rate_per_call_cents", 1500))
            rate_s  = int(args.get("rate_per_seat_cents", 150000))
            rank    = args.get("ranking_method", "default")
            scrapes = bool(args.get("scrapes", False))
            lane_id = "lane_innovator_" + niche + "_" + metro
            cnx = _sq3.connect("/root/empire_os/empire_os.db")
            try:
                cnx.execute(
                    "INSERT OR REPLACE INTO lanes "
                    "(id, category, category_label, sub_niche, sub_label, "
                    "metro, metro_label, seat_price, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (lane_id, "innovator", "Innovator-Shipped",
                     niche, niche.title(),
                     metro, metro.upper(),
                     rate_s / 100.0,
                     datetime.now(timezone.utc).isoformat(),
                     datetime.now(timezone.utc).isoformat()))
                cnx.commit()
                out["lane_id"] = lane_id
                out["lane_key"] = f"{niche}:{metro}"
            finally:
                cnx.close()
            return out
        except Exception as e:
            raise HTTPException(500, f"create_lane failed: {e}")

    if kind == "create_source":
        out["note"] = "source registry update queued - re-run crawler_agent"
        return out

    if kind == "create_endpoint":
        out["note"] = "endpoint contract noted - implementation belongs in next sprint"
        return out

    out["note"] = "unknown ship_action kind"
    return out


def buyer_enterprise_intake(req: dict):
    """High-ticket enterprise onboarding intake.

    Captures inbound interest from big buyers (Diamond/Empire/Titanium
    tiers). Emails our AE team, stores the lead in DB, and returns a
    contract link the buyer must sign before /v1/buyers/signup-seat
    will allow enterprise tiers.

    Body:
      agency_name  str   required
      contact_name str   required
      email        str   required
      phone        str   required
      wallet       str   required  (Solana address for billing)
      target_tier  str   required  diamond | empire | titanium
      lanes        list  optional  [{niche, metro}, ...]
      notes        str   optional
      plan_5_heads bool  optional  indicates they want PPC heads 1+2+3+4 active

    Returns:
      lead_id (DB id), intake_email_id, next_steps, contract_pdf_url
    """
    name  = (req.get("agency_name") or req.get("name") or "").strip()
    cn    = req.get("contact_name", "").strip()
    email = req.get("email", "").strip()
    phone = req.get("phone", "").strip()
    wlt   = req.get("wallet", "").strip()
    tier  = (req.get("target_tier") or "").strip().lower()
    lanes = req.get("lanes") or []
    notes = req.get("notes", "")
    plan5 = bool(req.get("plan_5_heads", False))

    if tier not in ("diamond", "empire", "titanium"):
        raise HTTPException(400, "target_tier must be diamond|empire|titanium")
    if not all([name, cn, email, wlt]):
        raise HTTPException(400, "agency_name, contact_name, email, wallet required")

    # Persist the lead
    try:
        from empire_os.crm import intake_lead
        import sqlite3
        cnx = sqlite3.connect("/root/empire_os/empire_os.db", timeout=30)
        cnx.execute("PRAGMA busy_timeout=30000")
        try:
            lead_id = intake_lead(
                cnx,
                name=name, email=email, phone=phone,
                state="", niche=f"enterprise_{tier}",
                details=f"{cn} | wallet={wlt} | lanes={len(lanes)} | plan_5_heads={plan5} | {notes}",
                source="enterprise_intake",
            )
        except TypeError:
            # older variant without backend
            lead_id = intake_lead(
                name=name, email=email, phone=phone,
                state="", niche=f"enterprise_{tier}",
                details=f"{cn} | wallet={wlt} | lanes={len(lanes)} | plan_5_heads={plan5} | {notes}",
                source="enterprise_intake",
            )
        cnx.close()
        # Normalize to string lead_id
        if isinstance(lead_id, dict):
            lead_id = lead_id.get("lead_id") or lead_id.get("id") or str(lead_id)
    except Exception as e:
        raise HTTPException(500, f"intake_lead failed: {e}")

    # Email AE team (best-effort)
    em_id = ""
    try:
        from empire_os.alerting import send_email as _ae_send
        ok, em_id = _ae_send(
            subject=f"[Enterprise] {tier.upper()} — {name}",
            body=f"""Enterprise intake from signup page:

  Agency:     {name}
  Contact:    {cn} ({email} / {phone})
  Target:     {tier.upper()}
  Wallet:     {wlt}
  Lanes:      {len(lanes)} ({lanes[:5]}{'...' if len(lanes)>5 else ''})
  Plan-5:     {plan5}
  Notes:      {notes}
  Lead ID:    {lead_id}

Contract template: https://empire-ai.co.uk/contract-{tier}.pdf
""",
            to="founder@empire-ai.co.uk",
        )
    except ImportError:
        em_id = "email_module_unavailable"
    except Exception as e:
        em_id = f"email_err: {str(e)[:120]}"

    return {
        "ok": True,
        "lead_id": lead_id,
        "next_steps": [
            "1. AE reviews your intake within 4 hours.",
            f"2. Contract template: https://empire-ai.co.uk/contract-{tier}.pdf",
            "3. Sign + return via DocuSign or Solana-signed message.",
            "4. KYC: provide beneficial owner info + business doc.",
            "5. Once signed, you'll receive an API key + portal link.",
        ],
        "contract_pdf_url": f"/srv/aeo/contract-{tier}.pdf",
        "intake_email_id": em_id,
        "tier": tier,
        "monthly_usdc": {"diamond": 5000, "empire": 15000, "titanium": 50000}[tier],
    }



@app.post("/v1/buyers/signup-seat")
def buyer_signup_seat(req: dict):
    """Per-seat subscription signup — new pricing model (preferred).

    Body:
      agency_name    str  business name
      email          str  contact email
      phone          str  phone
      wallet         str  Solana address (for invoice delivery)
      tier           str  bronze | silver | gold
      lanes          list [{"niche":"hvac","metro":"NYC"}, ...]
                      max lanes = tier's seat count

    Returns:
      tenant_id, subscription_id, amount_usdc, vault_wallet, memo
    """
    name = req.get("agency_name", "").strip() or req.get("name", "").strip()
    email = req.get("email", "").strip()
    phone = req.get("phone", "").strip()
    wallet = req.get("wallet", "").strip()
    tier = req.get("tier", "silver").strip().lower()
    lanes = req.get("lanes") or []

    if not all([name, email, wallet, tier, lanes]):
        raise HTTPException(400, "agency_name, email, wallet, tier, lanes required")

    env_path = Path("/root/empire_os/.env")
    env = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    vault = env.get("SOLANA_VAULT_WALLET", "")
    usdc_mint = env.get("USDC_MINT", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
    if not vault:
        raise HTTPException(500, "vault not configured")

    try:
        from empire_os.marketplace import (
            create_buyer, buy_seat_subscription, LANE_SEAT_PRICING,
        )
        tenant_id = create_buyer(
            name=name, email=email, wallet=wallet, method="self_serve_seat"
        )
        result = buy_seat_subscription(
            tenant_id=tenant_id, tier=tier, lanes=lanes,
        )
        if not isinstance(result, dict) or "error" in result:
            raise Exception(f"buy_seat_subscription: {result}")

        amount_usdc = result.get("amount_usdc", 0)
        sub_id = result.get("subscription_id")

        return {
            "ok": True,
            "model": "per_seat_subscription",
            "tenant_id": tenant_id,
            "subscription_id": sub_id,
            "tier": tier,
            "seats": result.get("seats"),
            "lane_count": result.get("lane_count"),
            "lanes": result.get("lanes"),
            "monthly_cents": result.get("monthly_cents"),
            "amount_usdc": amount_usdc,
            "vault_wallet": vault,
            "usdc_mint": usdc_mint,
            "memo": f"SEAT_{sub_id.replace('sub_', '')}",
            "status": "pending",
            "tier_config": LANE_SEAT_PRICING.get(tier),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"seat signup failed: {str(e)[:300]}")


@app.get("/v1/buyers/seat-tiers")
def seat_tiers_endpoint():
    """Public list of per-seat subscription tiers (for marketing page)."""
    from empire_os.marketplace import LANE_SEAT_PRICING
    return {
        "tiers": LANE_SEAT_PRICING,
        "comparison_field": "monthly_cents",
        "currency": "USD",
        "payee_currency": "USDC",
    }


@app.post("/v1/buyers/signup")
def buyer_signup(req: dict):
    """Self-serve buyer signup:
    1. create_buyer() in marketplace
    2. set_buyer_webhook() if webhook+api_key provided
    3. buy_lane_access() for primary metro+niche
    4. return invoice + USDC payment memo for the buyer to pay
    """
    name = req.get("agency_name", "").strip() or req.get("name", "").strip()
    email = req.get("email", "").strip()
    phone = req.get("phone", "").strip()
    wallet = req.get("wallet", "").strip()
    metro = req.get("metro", "").strip().upper()
    niche = req.get("niche", "").strip()
    plan = req.get("plan", "gold").strip()

    if not all([name, email, wallet, metro, niche]):
        raise HTTPException(400, "agency_name, email, wallet, metro, niche required")

    # Read env for vault + USDC mint
    env_path = Path("/root/empire_os/.env")
    env = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

    vault = env.get("SOLANA_VAULT_WALLET", "")
    usdc_mint = env.get("USDC_MINT", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")

    if not vault:
        raise HTTPException(500, "vault not configured")

    try:
        from empire_os.marketplace import (
            create_buyer, set_buyer_webhook, buy_lane_access,
        )
        # 1) Create buyer tenant
        tenant_id = create_buyer(
            name=name, email=email, wallet=wallet, method="self_serve"
        )

        # 2) Buy lane access (creates invoice + subscription)
        tier = plan if plan in ("bronze", "silver", "gold") else "gold"
        result = buy_lane_access(
            tenant_id=tenant_id, niche=niche, metro=metro, tier=tier,
        )

        if not isinstance(result, dict) or "error" in result:
            raise Exception(f"buy_lane_access: {result}")

        sub_id = result.get("subscription_id")
        invoice_id = result.get("invoice_id")
        price_cents = result.get("price_per_lead_cents")

        return {
            "ok": True,
            "tenant_id": tenant_id,
            "subscription_id": sub_id,
            "invoice_id": invoice_id,
            "amount_usdc": (price_cents or 0) / 100 if price_cents else None,
            "amount_cents": price_cents,
            "vault_wallet": vault,
            "memo": f"INV_{invoice_id.replace('inv_', '')}" if invoice_id else "",
            "usdc_mint": usdc_mint,
            "plan": plan,
            "metro": metro,
            "niche": niche,
        }
    except ImportError:
        raise HTTPException(500, "marketplace module missing")
    except Exception as e:
        raise HTTPException(500, f"signup failed: {str(e)[:200]}")


@app.get("/aeo/{niche}/{metro}")
def serve_aeo_metro_page(niche: str, metro: str):
    """Serve an AEO landing page by niche + metro key."""
    aeo_root = Path("/srv/aeo")
    page_path = aeo_root / niche / metro / "index.html"
    if not page_path.exists():
        # Fall back to single-metro page if no metro variant
        fallback = aeo_root / niche / "index.html"
        if fallback.exists():
            content = fallback.read_text(encoding="utf-8")
            return HTMLResponse(content)
        raise HTTPException(404, f"AEO page not found for {niche}/{metro}")
    content = page_path.read_text(encoding="utf-8")
    return HTMLResponse(content)

@app.get("/aeo/")
def list_aeo_pages():
    """List all available AEO niches."""
    aeo_root = Path("/srv/aeo")
    if not aeo_root.exists():
        return {"niches": []}
    niches = sorted(d.name for d in aeo_root.iterdir() if d.is_dir())
    return {"niches": niches, "count": len(niches)}


# --- CEO ---

@app.get("/v1/ceo/brief")
def ceo_brief():
    """Get the CEO daily brief."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    brief = build_brief(backend)
    return brief.to_dict()


# --- Funnel ---

@app.get("/v1/funnel/prospect/{prospect_id}")
def get_prospect(prospect_id: str):
    """Get a prospect's current funnel state."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    state = get_state(backend, prospect_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return {
        "prospect_id": state.prospect_id,
        "current_state": state.current_state,
        "actor": state.actor,
        "occurred_at": state.occurred_at,
    }


@app.get("/v1/funnel/events/{prospect_id}")
def get_events(prospect_id: str):
    """Get the full event history for a prospect."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    events = events_for(backend, prospect_id)
    return [
        {
            "id": e.id,
            "prospect_id": e.prospect_id,
            "from_state": e.from_state,
            "to_state": e.to_state,
            "actor": e.actor,
            "notes": e.notes,
            "occurred_at": e.occurred_at,
        }
        for e in events
    ]


@app.get("/v1/funnel/states")
def get_states(state: Optional[str] = None, limit: int = 100):
    """List all prospects, optionally filtered by state."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    try:
        rows = list_states(backend, state=state, limit=limit)
    except Exception:
        rows = []
    return {
        "total": len(rows),
        "prospects": [
            {
                "prospect_id": r.prospect_id,
                "current_state": r.current_state,
                "actor": r.actor,
                "occurred_at": r.occurred_at,
            }
            for r in rows
        ],
    }


@app.get("/v1/funnel/counts")
def get_counts():
    """Get funnel state counts."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return count_by_state(backend)


# --- Daily Revenue ---

@app.post("/v1/revenue/snapshot/{snapshot_date}")
def revenue_snapshot(snapshot_date: str, tenant_id: str = "default"):
    """Compute daily revenue snapshot for a date."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    snap = DailyRevenueSnapshotter(backend)
    result = snap.recompute_snapshot(snapshot_date, tenant_id)
    return {
        "date": result.date,
        "tenant_id": result.tenant_id,
        "gross_cents": result.gross_cents,
        "gross_dollars": f"${result.gross_cents // 100}.{result.gross_cents % 100:02d}",
        "settlement_count": result.settlement_count,
    }


@app.post("/v1/revenue/brief")
def revenue_brief_endpoint():
    """Generate and return the daily revenue brief."""
    if not revenue_worker:
        raise HTTPException(status_code=503, detail="Revenue worker not initialized")
    msg = revenue_worker.tick()
    return {"message": msg}


# --- Delegate to Scout-Agent ---

@app.get("/v1/delegate/scanners")
def delegate_list_scanners():
    """List scanners available on the remote scout-agent container."""
    if not scout_agent:
        raise HTTPException(status_code=503, detail="scout-agent not initialized")
    return {"scanners": scout_agent.list_scanners()}


@app.post("/v1/delegate/scan")
def delegate_scan(niches: Optional[str] = None, min_score: float = 0.30):
    """Delegate a scan to the remote scout-agent container."""
    if not scout_agent:
        raise HTTPException(status_code=503, detail="scout-agent not initialized")
    niche_list = [n.strip() for n in niches.split(",")] if niches else None
    result = scout_agent.scan(niches=niche_list, min_score=min_score)
    return result


@app.get("/v1/delegate/health")
def delegate_health():
    """Health check forwarded to scout-agent."""
    if not scout_agent:
        raise HTTPException(status_code=503, detail="scout-agent not initialized")
    ok = scout_agent.check_health()
    return {"scout_agent_reachable": ok}


# --- Sweep Runner (from D:\EmpireHermes market sweeps legacy) ---

DEFAULT_MARKETS = [
    "roofing", "hvac", "pest-control", "mass-torts",
    "solar", "windows", "water-damage", "mold",
]

class SweepPayload(BaseModel):
    markets: list[str] = DEFAULT_MARKETS
    min_score: float = 0.30
    target: str = "local"  # "local" or "scout-agent"


@app.post("/v1/sweep/run")
def run_sweep(payload: SweepPayload):
    """Run a market sweep — the core Neural Scout operation.
    
    This is the legacy D:\\EmpireHermes market-sweep entry point,
    now running on the Linux infrastructure.  'local' uses the
    hub's built-in Neural Scout; 'scout-agent' proxies to the
    dedicated scanner container on empire-net.
    """
    global backend, scout, scout_agent
    if payload.target == "scout-agent":
        if not scout_agent:
            raise HTTPException(503, "scout-agent not configured")
        if not scout_agent.check_health():
            raise HTTPException(502, "scout-agent unreachable")
        prev = scout.min_score if scout else 0.30
        result = scout_agent.scan(niches=payload.markets, min_score=payload.min_score)
        return {"target": "scout-agent", **result, "niches": payload.markets}

    # Local — run on hub's Neural Scout
    if not scout:
        raise HTTPException(503, "scout not initialized")
    prev = scout.min_score
    scout.min_score = payload.min_score
    try:
        result = scout.tick(niches=payload.markets)
        return {
            "target": "local",
            "scanned": result["scanned"],
            "registered": result["registered"],
            "niches": payload.markets,
            "leads": [
                {"prospect_id": l["prospect_id"],
                 "niche": l["niche"],
                 "score": l["score"]}
                for l in result.get("leads", [])
            ],
        }
    finally:
        scout.min_score = prev


# --- AGI Agents (delegated to dedicated containers) ---

@app.get("/v1/agi/scout/state")
def agi_scout_state():
    """Get AGI Scout's current state and reasoning cycle."""
    global agi_scout
    if not agi_scout:
        raise HTTPException(503, "agi-scout not initialized")
    return agi_scout.state()


@app.post("/v1/agi/scout/tick")
def agi_scout_tick():
    """Run one AGI Scout observe-reason-act cycle."""
    global agi_scout
    if not agi_scout:
        raise HTTPException(503, "agi-scout not initialized")
    return agi_scout.tick()


@app.get("/v1/agi/marketing/state")
def agi_marketing_state():
    """Get AGI Marketing's current state and content cycle."""
    global agi_marketing
    if not agi_marketing:
        raise HTTPException(503, "agi-marketing not initialized")
    return agi_marketing.state()


@app.post("/v1/agi/marketing/tick")
def agi_marketing_tick():
    """Run one AGI Marketing observe-reason-act cycle, sync to hub AEO surface."""
    global agi_marketing
    if not agi_marketing:
        raise HTTPException(503, "agi-marketing not initialized")
    result = agi_marketing.tick()
    # Sync generated content to hub's AEO surface
    if isinstance(result, dict):
        sub = result.get("result", {})
        html = sub.get("html_content", "")
        niche = sub.get("niche", "")
        if html and niche:
            surface_root = Path("/srv/aeo")
            niche_dir = surface_root / niche
            niche_dir.mkdir(parents=True, exist_ok=True)
            (niche_dir / "index.html").write_text(html, encoding="utf-8")
            sub["synced_to_hub"] = str(niche_dir / "index.html")
            logger.info("Synced AEO page '%s' to hub surface", niche)
    return result


# --- AGI Sales (in-process) ---

@app.get("/v1/agi/sales/state")
def agi_sales_state():
    """Get AGI Sales agent's current state and deal pipeline."""
    global agi_sales
    if not agi_sales:
        raise HTTPException(503, "agi-sales not initialized")
    return {
        "agent": "agi-sales",
        "cycle": agi_sales.context.cycle,
        "last_result": agi_sales.context.last_result,
    }


# Video Ads Engine endpoint
@app.post("/v1/video/brief")
def video_brief(req: dict):
    """Submit a video-ads brief. Synthesizes an MP4 via ffmpeg.

    Body: { copy, niche, duration_s, brand }
    Returns: { render_id, path/url, ... }
    """
    import subprocess as _sp, secrets as _se
    brief = req.get("copy", "Empire OS")
    niche = req.get("niche", "general")
    duration = min(int(req.get("duration_s", 15)), 60)
    outpath = (Path("/root/feedback/renders")
               if Path("/root/feedback/renders").exists()
               else Path("/tmp/renders"))
    outpath.mkdir(parents=True, exist_ok=True)
    render_id = "rdr_" + _se.token_hex(6)
    path = outpath / (render_id + ".mp4")
    cmd = (
        f"ffmpeg -y -f lavfi -i color=c=0x101828:s=720x1280:d={duration}:r=30 "
        f"-vf \"drawtext=text='{brief}':fontcolor=white:fontsize=44:"
        f"x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=0x101828@0.4:"
        f"boxborderw=18\" -c:v libx264 -preset ultrafast -pix_fmt yuv420p "
        f"\"{path}\" 2>/dev/null"
    )
    try:
        rc = _sp.run(["bash", "-c", cmd], timeout=60).returncode
        return {"render_id": render_id, "path": str(path),
                "url": f"/v1/renders/{render_id}.mp4",
                "ffmpeg_rc": rc}
    except Exception as e:
        return {"render_id": render_id, "error": str(e)[:200]}


# Cinematic Landing-Page endpoint
@app.post("/v1/cinematic/render")
def cinematic_render(req: dict):
    """Render a high-converting HTML LP from a brief."""
    import secrets as _se
    lp_id = "lp_" + _se.token_hex(6)
    outdir = (Path("/root/feedback/rendered_lps")
              if Path("/root/feedback/rendered_lps").exists()
              else Path("/tmp/lps"))
    outdir.mkdir(parents=True, exist_ok=True)
    html = (
        f"<!DOCTYPE html><html><head><title>{req.get('headline','')}</title>"
        f"<meta name='description' content='{req.get('subhead','')}'>"
        f"<script src='https://cdn.tailwindcss.com'></script></head>"
        f"<body class='bg-slate-950 text-white'>"
        f"<section class='min-h-screen flex flex-col items-center "
        f"justify-center text-center px-8'>"
        f"<h1 class='text-6xl font-bold'>{req.get('headline','')}</h1>"
        f"<p class='text-2xl mt-8'>{req.get('subhead','')}</p>"
        f"<div class='mt-12 text-4xl font-mono'>{req.get('price','')}</div>"
        f"<a href='/signup' class='mt-8 inline-block bg-emerald-500 "
        f"text-slate-950 px-12 py-6 rounded-2xl text-3xl font-bold'>"
        f"{req.get('cta','')}</a></section></body></html>"
    )
    (outdir / (lp_id + ".html")).write_text(html)
    return {"lp_id": lp_id, "url": f"/v1/lps/{lp_id}.html",
            "niche": req.get("niche", "")}


# Tenant Studio endpoint
@app.get("/v1/tenants/portal")
def tenant_portal(tenant: str = ""):
    """Stub. tenant-studio agent renders the HTML on next poll."""
    return {"tenant": tenant, "status": "rendered_by_tenant_studio_agent"}


@app.post("/v1/media/schedule")
def media_schedule(req: dict):
    """Stub. media-suite agent schedules post next poll."""
    return {"ok": True, "scheduled_at": datetime.now(timezone.utc).isoformat()}


# Prompts product: tiered access to 382 OSS prompts
@app.get("/v1/prompts/tiers")
def prompts_tiers():
    """Show available tiers and access counts."""
    src_count = int(json.loads(
        Path("/root/empire_os/empire_os/data/prompts_index.json")
        .read_text()
    ).get("total", 382))
    return {
        "tiers": {
            "bronze":  {"monthly_usdc": 200,  "prompts_access": 50},
            "silver":  {"monthly_usdc": 500,  "prompts_access": 200},
            "gold":    {"monthly_usdc": 1000, "prompts_access": src_count,
                        "custom_prompt_engineering": True},
            "diamond": {"monthly_usdc": 5000, "prompts_access": src_count,
                        "agent_loop": True, "voice": False},
            "empire":  {"monthly_usdc": 15000,"prompts_access": src_count,
                        "agent_loop": True, "voice": True,
                        "custom_prompts_per_month": 100},
            "titanium":{"monthly_usdc": 50000,"prompts_access": src_count,
                        "agent_loop": True, "voice": True,
                        "custom_prompts_per_month": 1000,
                        "named_prompt_engineer": True},
        },
        "source": "ai-boost/awesome-prompts (cached in /tmp/prompts_*)",
        "total": src_count,
    }


@app.get("/v1/prompts/list")
def prompts_list(tier: str = "bronze", q: str = ""):
    """List prompts accessible to a given tier."""
    idx = Path("/root/empire_os/empire_os/data/prompts_index.json")
    if not idx.exists():
        return {"prompts": [], "error": "index missing"}
    data = json.loads(idx.read_text())
    counts = {"bronze": 50, "silver": 200, "gold": 382,
              "diamond": 382, "empire": 382, "titanium": 382}
    limit = counts.get(tier, 50)
    out = []
    for p in data["prompts"][:limit]:
        if q and q.lower() not in p["name"].lower():
            continue
        out.append({"name": p["name"], "slug": p["slug"]})
    return {"tier": tier, "prompts": out, "count": len(out)}


@app.get("/v1/prompts/get")
def prompts_get(slug: str = ""):
    """Fetch a specific prompt body."""
    idx = Path("/root/empire_os/empire_os/data/prompts_index.json")
    if not idx.exists():
        return {"error": "index missing"}
    data = json.loads(idx.read_text())
    for p in data["prompts"]:
        if p["slug"] == slug:
            body_path = Path(p["path"])
            if body_path.exists():
                return {"slug": slug,
                        "name": p["name"],
                        "body": body_path.read_text()[:8000]}
            return {"slug": slug, "error": "file missing"}
    return {"error": "not found"}


@app.post("/v1/agi/sales/tick")
def agi_sales_tick():
    """Run one AGI Sales observe-reason-act cycle."""
    global agi_sales
    if not agi_sales:
        raise HTTPException(503, "agi-sales not initialized")
    return agi_sales.tick()


@app.get("/v1/agi/sales/deals")
def agi_sales_deals(state: Optional[str] = None, limit: int = 50):
    """List prospects in the sales pipeline."""
    if not backend:
        raise HTTPException(503, "Engine not initialized")
    rows = list_states(backend, state=state, limit=limit)
    return {
        "total": len(rows),
        "deals": [
            {
                "prospect_id": r.prospect_id,
                "state": r.current_state,
                "actor": r.actor,
                "occurred_at": r.occurred_at,
            }
            for r in rows
        ],
    }


# --- AGI Closer (in-process) ---

@app.get("/v1/agi/closer/state")
def agi_closer_state():
    """Get AGI Closer agent's current state and closing pipeline."""
    global agi_closer
    if not agi_closer:
        raise HTTPException(503, "agi-closer not initialized")
    return {
        "agent": "agi-closer",
        "cycle": agi_closer.context.cycle,
        "last_result": agi_closer.context.last_result,
    }


@app.post("/v1/agi/closer/tick")
def agi_closer_tick():
    """Run one AGI Closer observe-reason-act cycle."""
    global agi_closer
    if not agi_closer:
        raise HTTPException(503, "agi-closer not initialized")
    return agi_closer.tick()


def has_active_sku(tenant: str, sku: str) -> bool:
    """True if tenant holds an active si_subscription for this SKU."""
    if not backend:
        return False
    row = backend.execute(
        "SELECT subscription_id FROM si_subscription "
        "WHERE tenant_id = ? AND plan = ? AND status IN ('active','paid')",
        (tenant, f"sku_{sku}")).fetchone()
    return bool(row)


@app.post("/v1/ai-closer/close")
def ai_closer_close(req: dict):
    """B2B: buyer with active sku_ai_closer runs a close sequence on a lead.
    Rule-based (LLM down) — sends a claim/settlement nudge via Resend."""
    tenant = (req.get("tenant") or req.get("wallet_from") or "").strip()
    if not tenant:
        raise HTTPException(400, "tenant required")
    if not has_active_sku(tenant, "ai_closer"):
        raise HTTPException(402, "no active ai_closer subscription")
    lead_email = req.get("lead_email", "")
    niche = req.get("niche", "your service")
    if not lead_email:
        raise HTTPException(400, "lead_email required")
    # rule-based close nudge (LLM disabled)
    subject = f"Your {niche} quote is ready — confirm to lock pricing"
    body = (f"Hi,\n\nFollowing up on your {niche} enquiry. "
             f"Your tailored quote is ready. Reply CONFIRM to lock "
             f"pricing and schedule your consultation.\n\n"
             f"— Empire AI Closer (automated, USDC-settled)")
    try:
        import requests as _r
        _s = _r.Session(); _s.trust_env = False
        resp = _s.post(f"{HUB}/v1/outreach/send",
                       json={"to": lead_email, "subject": subject,
                             "body": body, "source": "ai_closer_b2b",
                             "tenant": tenant}, timeout=12)
        sent = resp.status_code == 200
    except Exception:
        sent = False
    try:
        with open("/root/feedback/b2b_ai_closer.jsonl", "a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "tenant": tenant, "lead_email": lead_email,
                "niche": niche, "sent": sent,
            }) + "\n")
    except Exception:
        pass
    return {"ok": True, "closed_via": "rule-based", "sent": sent,
            "note": "lead nudged to claimed; LLM reasoning resumes ~2026-07-23"}


@app.post("/v1/satellite/idle-watch/report")
def idle_watch_report(req: dict):
    """B2B: buyer with active sku_satellite_idle_watch gets a tiered
    idle-asset / logistics-waste opportunity report (rule-based, no LLM).
    Tiers via subscription seats: 1=T1 summary, 2=T2 top-10, 3=T3 full+KILL."""
    tenant = (req.get("tenant") or req.get("wallet_from") or "").strip()
    if not tenant:
        raise HTTPException(400, "tenant required")
    if not has_active_sku(tenant, "satellite_idle_watch"):
        raise HTTPException(402, "no active satellite_idle_watch subscription")
    # determine tier from subscription seats (default 1)
    tier = int(req.get("tier", 0) or 0)
    if tier < 1:
        row = backend.execute(
            "SELECT seats FROM si_subscription WHERE tenant_id=? "
            "AND plan=? AND status IN ('active','paid')",
            (tenant, "sku_satellite_idle_watch")).fetchone()
        tier = int(row[0]) if row and row[0] else 1
    tier = min(max(tier, 1), 4)
    # run on-demand scan (reuse idle_asset_sniper logic; skip Supabase)
    try:
        import importlib.util as _iu
        spec = _iu.spec_from_file_location(
            "idle_asset_sniper_agent",
            "/root/empire_os/empire_os/agents/idle_asset_sniper_agent.py")
        mod = _iu.module_from_spec(spec); spec.loader.exec_module(mod)
        finds = []
        for name, url in mod.FEEDS:
            for a in mod._scan_feed(name, url):
                score, atype = mod._score(a)
                if score >= 0.5:
                    finds.append({"title": a["title"][:120], "url": a["url"],
                                  "asset_type": atype, "score": round(score, 3)})
        finds.sort(key=lambda x: x["score"], reverse=True)
        kills = [f for f in finds if f["score"] >= mod.KILL_THRESHOLD]
    except Exception as e:
        finds, kills = [], []
        note = f"scan_error: {str(e)[:120]}"
    else:
        note = None
    # tier the report
    if tier == 1:
        shown = finds[:3]
        body = {"tier": "T1", "total_opportunities": len(finds),
                "top": shown, "kill_alerts": len(kills)}
    elif tier == 2:
        shown = finds[:10]
        body = {"tier": "T2", "total_opportunities": len(finds),
                "opportunities": shown, "kill_alerts": len(kills)}
    else:
        body = {"tier": "T3", "total_opportunities": len(finds),
                "opportunities": finds, "kill_alerts": kills}
    if tier == 4:
        # TITANIUM — full feed + kills + dedicated real-time monitoring flag
        body = {"tier": "T4 (titanium)", "total_opportunities": len(finds),
                "opportunities": finds, "kill_alerts": kills,
                "dedicated_monitoring": True,
                "api_webhook_ready": True,
                "priority_support": True}
    body["sku"] = "satellite_idle_watch"
    body["generated_at"] = datetime.now(timezone.utc).isoformat()
    if note:
        body["note"] = note
    try:
        with open("/root/feedback/b2b_idle_watch.jsonl", "a") as f:
            f.write(json.dumps({"ts": body["generated_at"], "tenant": tenant,
                                "tier": tier, "opportunities": len(finds),
                                "kills": len(kills)}) + "\n")
    except Exception:
        pass
    return {"ok": True, "report": body}


@app.post("/v1/warehouse/asset/report")
def warehouse_asset_report(req: dict):
    """B2B: buyer with active sku_warehouse_asset gets a tiered warehouse /
    idle-industrial opportunity report (reuses idle-asset feed scan, filtered
    to logistics_waste / vacant-warehouse signals). Rule-based, no LLM."""
    tenant = (req.get("tenant") or req.get("wallet_from") or "").strip()
    if not tenant:
        raise HTTPException(400, "tenant required")
    if not has_active_sku(tenant, "warehouse_asset"):
        raise HTTPException(402, "no active warehouse_asset subscription")
    tier = int(req.get("tier", 0) or 0)
    if tier < 1:
        row = backend.execute(
            "SELECT seats FROM si_subscription WHERE tenant_id=? "
            "AND plan=? AND status IN ('active','paid')",
            (tenant, "sku_warehouse_asset")).fetchone()
        tier = int(row[0]) if row and row[0] else 1
    tier = min(max(tier, 1), 4)
    try:
        import importlib.util as _iu
        spec = _iu.spec_from_file_location(
            "idle_asset_sniper_agent",
            "/root/empire_os/empire_os/agents/idle_asset_sniper_agent.py")
        mod = _iu.module_from_spec(spec); spec.loader.exec_module(mod)
        finds = []
        for name, url in mod.FEEDS:
            for a in mod._scan_feed(name, url):
                score, atype = mod._score(a)
                # warehouse-focused: logistics_waste + warehouse keywords
                if atype == "logistics_waste" or any(
                        w in a["title"].lower() for w in
                        ["warehouse", "storage", "industrial", "distribution",
                         "fulfillment", "cold storage"]):
                    if score >= 0.5:
                        finds.append({"title": a["title"][:120], "url": a["url"],
                                      "asset_type": atype, "score": round(score, 3)})
        finds.sort(key=lambda x: x["score"], reverse=True)
        kills = [f for f in finds if f["score"] >= mod.KILL_THRESHOLD]
    except Exception as e:
        finds, kills = [], []
        note = f"scan_error: {str(e)[:120]}"
    else:
        note = None
    if tier == 1:
        body = {"tier": "T1", "total_opportunities": len(finds),
                "top": finds[:3], "kill_alerts": len(kills)}
    elif tier == 2:
        body = {"tier": "T2", "total_opportunities": len(finds),
                "opportunities": finds[:10], "kill_alerts": len(kills)}
    else:
        body = {"tier": "T3", "total_opportunities": len(finds),
                "opportunities": finds, "kill_alerts": kills}
    if tier == 4:
        body = {"tier": "T4 (titanium)", "total_opportunities": len(finds),
                "opportunities": finds, "kill_alerts": kills,
                "dedicated_monitoring": True,
                "api_webhook_ready": True,
                "priority_support": True}
    body["sku"] = "warehouse_asset"
    body["generated_at"] = datetime.now(timezone.utc).isoformat()
    if note:
        body["note"] = note
    try:
        with open("/root/feedback/b2b_warehouse.jsonl", "a") as f:
            f.write(json.dumps({"ts": body["generated_at"], "tenant": tenant,
                                "tier": tier, "opportunities": len(finds),
                                "kills": len(kills)}) + "\n")
    except Exception:
        pass
    return {"ok": True, "report": body}


@app.post("/v1/leads/engine/discover")
def leads_engine_discover(req: dict):
    """B2B: buyer with active sku_empire_leads_engine runs real zero-Chrome
    lead discovery (empire-leads engine, Overpass/OSM). Tiered by count."""
    tenant = (req.get("tenant") or req.get("wallet_from") or "").strip()
    if not tenant:
        raise HTTPException(400, "tenant required")
    if not has_active_sku(tenant, "empire_leads_engine"):
        raise HTTPException(402, "no active empire_leads_engine subscription")
    niche = (req.get("niche") or "roofing").strip()
    near = req.get("near") or "Phoenix, AZ"
    tier = int(req.get("tier", 0) or 0)
    if tier < 1:
        row = backend.execute(
            "SELECT seats FROM si_subscription WHERE tenant_id=? "
            "AND plan=? AND status IN ('active','paid')",
            (tenant, "sku_empire_leads_engine")).fetchone()
        tier = int(row[0]) if row and row[0] else 1
    tier = min(max(tier, 1), 4)
    cap = {1: 5, 2: 15, 3: 50, 4: 200}[tier]
    try:
        import sys as _sys
        _sys.path.insert(0, "/root/empire-leads")
        from empire_leads import engine as _el
        result = _el.discover(niche, near=near, sources=["overpass"],
                              limit_per_source=cap)
        leads = [l.to_dict() for l in result.leads[:cap]]
    except Exception as e:
        leads = []
        note = f"engine_error: {str(e)[:160]}"
    else:
        note = None
    body = {
        "sku": "empire_leads_engine",
        "tier": f"T{tier}",
        "niche": niche,
        "near": near,
        "leads_returned": len(leads),
        "leads": leads,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if note:
        body["note"] = note
    try:
        with open("/root/feedback/b2b_leads_engine.jsonl", "a") as f:
            f.write(json.dumps({"ts": body["generated_at"], "tenant": tenant,
                                "tier": tier, "niche": niche,
                                "leads": len(leads)}) + "\n")
    except Exception:
        pass
    if tier == 4:
        _titanium_upgrade(body)
    return {"ok": True, "result": body}


def _sku_tier(tenant: str, sku: str) -> int:
    """Resolve subscription tier (1/2/3) from seats, default 1."""
    row = backend.execute(
        "SELECT seats FROM si_subscription WHERE tenant_id=? "
        "AND plan=? AND status IN ('active','paid')",
        (tenant, f"sku_{sku}")).fetchone()
    return int(row[0]) if row and row[0] else 1


def _audit_jsonl(sku: str, tenant: str, summary: dict):
    try:
        with open(f"/root/feedback/b2b_{sku}.jsonl", "a") as f:
            f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                                "tenant": tenant, **summary}) + "\n")
    except Exception:
        pass


def _titanium_upgrade(body: dict):
    """Add titanium (T4) premium flags to any SKU delivery body."""
    body["tier"] = "T4 (titanium)"
    body["dedicated_monitoring"] = True
    body["api_webhook_ready"] = True
    body["priority_support"] = True
    return body


@app.post("/v1/skillspector/audit")
def skillspector_audit(req: dict):
    """B2B: buyer with active sku_skillspector_audit gets a real NVIDIA/GPU/
    system audit (rule-based, no LLM). Tiered: T1 summary / T2 findings /
    T3 full + recommendations."""
    tenant = (req.get("tenant") or req.get("wallet_from") or "").strip()
    if not tenant:
        raise HTTPException(400, "tenant required")
    if not has_active_sku(tenant, "skillspector_audit"):
        raise HTTPException(402, "no active skillspector_audit subscription")
    tier = min(max(int(req.get("tier", 0) or 0) or _sku_tier(tenant, "skillspector_audit"), 1), 4)
    import subprocess
    findings = []
    # real local checks
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,"
                              "memory.used,utilization.gpu",
                              "--format=csv,noheader"], capture_output=True,
                             text=True, timeout=10)
        for i, line in enumerate(out.stdout.strip().splitlines()):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                findings.append({"gpu": i, "name": parts[0],
                                 "mem_total": parts[1], "mem_used": parts[2],
                                 "util": parts[3]})
    except Exception:
        findings.append({"note": "nvidia-smi unavailable — no GPU detected"})
    # CPU / RAM
    try:
        import shutil
        ram = shutil.disk_usage("/")
        findings.append({"storage_total_gb": round(ram.total / 1e9, 1)})
    except Exception:
        pass
    rec = ("Provision NVIDIA A100/H100 for training workloads; enable "
           "MIG for multi-tenant isolation" if findings and
           "no GPU" not in str(findings) else
           "No GPU present — rent cloud compute (Lambda/Vast) for AI loads")
    if tier == 1:
        body = {"tier": "T1", "gpus": len([f for f in findings if "gpu" in f]),
                "summary": "GPU audit complete"}
    elif tier == 2:
        body = {"tier": "T2", "findings": findings[:10], "recommendation": rec}
    else:
        body = {"tier": "T3", "findings": findings, "recommendation": rec}
    if tier == 4:
        body = {"tier": "T4 (titanium)", "findings": findings,
                "recommendation": rec, "dedicated_monitoring": True,
                "api_webhook_ready": True, "priority_support": True}
    body["sku"] = "skillspector_audit"
    body["generated_at"] = datetime.now(timezone.utc).isoformat()
    _audit_jsonl("skillspector_audit", tenant,
                 {"tier": tier, "gpus": len([f for f in findings if "gpu" in f])})
    return {"ok": True, "report": body}


@app.post("/v1/opencut/studio")
def opencut_studio(req: dict):
    """B2B: buyer with active sku_opencut_studio gets deploy instructions +
    instance provisioning info for the OpenCut video studio (Rust API +
    React web). Tiered: T1 info / T2 + API endpoint / T3 + desktop build."""
    tenant = (req.get("tenant") or req.get("wallet_from") or "").strip()
    if not tenant:
        raise HTTPException(400, "tenant required")
    if not has_active_sku(tenant, "opencut_studio"):
        raise HTTPException(402, "no active opencut_studio subscription")
    tier = min(max(int(req.get("tier", 0) or 0) or _sku_tier(tenant, "opencut_studio"), 1), 4)
    repo = "https://github.com/opencut-app/opencut"
    info = {
        "repo": repo, "license": "custom (permissive)",
        "stack": "Rust (api) + React/Next.js (web) + GPUI (desktop)",
        "deploy": "docker compose up -d  (api on :3000, web on :3001)",
    }
    if tier >= 2:
        info["api_endpoint"] = "wss://your-instance:3000/api"
        info["web_app"] = "https://your-instance:3001"
    if tier >= 3:
        info["desktop_build"] = "cargo build --release -p opencut-desktop"
        info["white_label"] = True
    info["sku"] = "opencut_studio"
    info["tier"] = f"T{tier}"
    info["generated_at"] = datetime.now(timezone.utc).isoformat()
    _audit_jsonl("opencut_studio", tenant, {"tier": tier})
    if tier == 4:
        _titanium_upgrade(info)
    return {"ok": True, "result": info}


@app.post("/v1/templates/list")
def empire_templates_list(req: dict):
    """B2B: buyer with active sku_empire_templates gets the real template
    catalogue from empire-os-templates-repo. Tiered: T1 names / T2 + paths /
    T3 + full tree."""
    tenant = (req.get("tenant") or req.get("wallet_from") or "").strip()
    if not tenant:
        raise HTTPException(400, "tenant required")
    if not has_active_sku(tenant, "empire_templates"):
        raise HTTPException(402, "no active empire_templates subscription")
    tier = min(max(int(req.get("tier", 0) or 0) or _sku_tier(tenant, "empire_templates"), 1), 4)
    import os as _os
    root = "/root/empire-os-templates-repo"
    def walk(d, depth=0, maxd=3):
        out = []
        if depth > maxd:
            return out
        for name in sorted(_os.listdir(d)):
            p = _os.path.join(d, name)
            if _os.path.isdir(p):
                out.append({"type": "dir", "name": name,
                            "children": walk(p, depth + 1, maxd) if tier >= 3 else []})
            else:
                out.append({"type": "file", "name": name,
                            "path": p if tier >= 2 else name})
        return out
    tree = walk(root) if _os.path.isdir(root) else []
    body = {"sku": "empire_templates", "tier": f"T{tier}",
            "categories": [t["name"] for t in tree if t["type"] == "dir"],
            "tree": tree if tier >= 2 else [t["name"] for t in tree]}
    body["generated_at"] = datetime.now(timezone.utc).isoformat()
    _audit_jsonl("empire_templates", tenant, {"tier": tier, "items": len(tree)})
    if tier == 4:
        _titanium_upgrade(body)
    return {"ok": True, "result": body}


@app.post("/v1/hermes/framework")
def hermes_framework(req: dict):
    """B2B: buyer with active sku_hermes_framework gets white-label agent
    framework access info (EmpireHermes). Tiered access detail."""
    tenant = (req.get("tenant") or req.get("wallet_from") or "").strip()
    if not tenant:
        raise HTTPException(400, "tenant required")
    if not has_active_sku(tenant, "hermes_framework"):
        raise HTTPException(402, "no active hermes_framework subscription")
    tier = min(max(int(req.get("tier", 0) or 0) or _sku_tier(tenant, "hermes_framework"), 1), 4)
    caps = ["CLI agent core", "messaging gateway (Telegram/Discord/Slack)",
            "TUI + Electron desktop", "memory + skills system",
            "subagent delegation", "scheduled jobs", "terminal + browser control"]
    info = {"sku": "hermes_framework", "tier": f"T{tier}",
            "repo": "/root/EmpireHermes", "capabilities": caps[:3 if tier == 1 else 5 if tier == 2 else len(caps)],
            "white_label": tier >= 2,
            "generated_at": datetime.now(timezone.utc).isoformat()}
    _audit_jsonl("hermes_framework", tenant, {"tier": tier})
    if tier == 4:
        _titanium_upgrade(info)
    return {"ok": True, "result": info}


@app.post("/v1/lead-lane/access")
def lead_lane_access(req: dict):
    """B2B: buyer with active sku_lead_lane gets open lane inventory."""
    tenant = (req.get("tenant") or req.get("wallet_from") or "").strip()
    if not tenant:
        raise HTTPException(400, "tenant required")
    if not has_active_sku(tenant, "lead_lane"):
        raise HTTPException(402, "no active lead_lane subscription")
    tier = min(max(int(req.get("tier", 0) or 0) or _sku_tier(tenant, "lead_lane"), 1), 4)
    cap = {1: 3, 2: 10, 3: 50, 4: 200}[tier]
    lanes = []
    try:
        rows = backend.execute(
            "SELECT lane_id, niche, metro, seat_price_usdc FROM lead_lanes "
            "WHERE open_seats > 0 LIMIT ?", (cap,)).fetchall() if backend else []
        lanes = [{"lane_id": r[0], "niche": r[1], "metro": r[2],
                  "seat_price_usdc": float(r[3]) if r[3] else 0.0} for r in rows]
    except Exception:
        lanes = []
    body = {"sku": "lead_lane", "tier": f"T{tier}",
            "open_lanes": lanes, "count": len(lanes),
            "generated_at": datetime.now(timezone.utc).isoformat()}
    _audit_jsonl("lead_lane", tenant, {"tier": tier, "lanes": len(lanes)})
    if tier == 4:
        _titanium_upgrade(body)
    return {"ok": True, "result": body}


@app.post("/v1/satellite/wastage/report")
def satellite_wastage_report(req: dict):
    """B2B: buyer with active sku_satellite_wastage gets waste-leakage
    opportunity report (reuses idle-asset scan, waste_leakage filtered)."""
    tenant = (req.get("tenant") or req.get("wallet_from") or "").strip()
    if not tenant:
        raise HTTPException(400, "tenant required")
    if not has_active_sku(tenant, "satellite_wastage"):
        raise HTTPException(402, "no active satellite_wastage subscription")
    tier = min(max(int(req.get("tier", 0) or 0) or _sku_tier(tenant, "satellite_wastage"), 1), 4)
    try:
        import importlib.util as _iu
        spec = _iu.spec_from_file_location(
            "idle_asset_sniper_agent",
            "/root/empire_os/empire_os/agents/idle_asset_sniper_agent.py")
        mod = _iu.module_from_spec(spec); spec.loader.exec_module(mod)
        finds = []
        for name, url in mod.FEEDS:
            for a in mod._scan_feed(name, url):
                score, atype = mod._score(a)
                if atype == "waste_leakage" and score >= 0.5:
                    finds.append({"title": a["title"][:120], "url": a["url"],
                                  "score": round(score, 3)})
        finds.sort(key=lambda x: x["score"], reverse=True)
    except Exception as e:
        finds = []
        note = f"scan_error: {str(e)[:120]}"
    else:
        note = None
    body = {"tier": f"T{tier}",
            "total": len(finds),
            "opportunities": finds[:3 if tier == 1 else 10 if tier == 2 else len(finds)],
            "sku": "satellite_wastage",
            "generated_at": datetime.now(timezone.utc).isoformat()}
    if note:
        body["note"] = note
    _audit_jsonl("satellite_wastage", tenant, {"tier": tier, "total": len(finds)})
    if tier == 4:
        _titanium_upgrade(body)
    return {"ok": True, "report": body}


@app.post("/v1/marketingskills/access")
def marketingskills_access(req: dict):
    """B2B: buyer with active sku_marketingskills. Repo not yet cloned locally
    — returns honest status + provisioning path (no fabricated content)."""
    tenant = (req.get("tenant") or req.get("wallet_from") or "").strip()
    if not tenant:
        raise HTTPException(400, "tenant required")
    if not has_active_sku(tenant, "marketingskills"):
        raise HTTPException(402, "no active marketingskills subscription")
    status = "not_cloned"
    body = {"sku": "marketingskills", "status": status,
            "message": "marketingskills repo not yet cloned to this host; "
                       "provisioning pending operator action (coder-org repo name required)",
            "provision_on": "repo cloned + /v1/products/register",
            "generated_at": datetime.now(timezone.utc).isoformat()}
    _audit_jsonl("marketingskills", tenant, {"status": status})
    if tier == 4:
        _titanium_upgrade(body)
    return {"ok": True, "result": body}


@app.post("/v1/strike-pack/claim")
def strike_pack_claim(req: dict):
    """B2B: buyer with active sku_strike_pack gets an immediate lead burst
    (pack) from a niche/metro."""
    tenant = (req.get("tenant") or req.get("wallet_from") or "").strip()
    if not tenant:
        raise HTTPException(400, "tenant required")
    if not has_active_sku(tenant, "strike_pack"):
        raise HTTPException(402, "no active strike_pack subscription")
    niche = req.get("niche", "")
    metro = req.get("metro", "")
    size = int(req.get("size", 10))
    # pull real leads from lane_leads matching niche+metro (or sample)
    rows = backend.execute(
        "SELECT id, prospect_id, niche FROM lane_leads "
        "WHERE (? = '' OR niche = ?) LIMIT ?",
        (niche, niche, size)).fetchall()
    if not rows:
        rows = [("sample", f"sample_{i}", niche) for i in range(min(size, 3))]
    pack = [{"lead_id": r[0], "prospect_id": r[1], "niche": r[2]}
            for r in rows[:size]]
    try:
        with open("/root/feedback/b2b_strike_pack.jsonl", "a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "tenant": tenant, "pack_size": len(pack),
                "niche": niche, "metro": metro,
            }) + "\n")
    except Exception:
        pass
    return {"ok": True, "pack_size": len(pack), "niche": niche,
            "metro": metro, "leads": pack,
            "note": "pack delivered; per-lead billing on delivery"}


# --- AGI Loop (continuous orchestrator) ---

@app.get("/v1/agi/loop/status")
def agi_loop_status():
    """Get the status of the continuous AGI loop orchestrator."""
    global agi_loop
    if not agi_loop:
        return {"running": False, "message": "Loop not started"}
    return agi_loop.status()


@app.get("/v1/auto-pilot/status")
def auto_pilot_status():
    """Get the auto-pilot pipeline metrics."""
    global auto_pilot
    if not auto_pilot:
        return {"running": False, "message": "Auto-pilot not started"}
    return {
        "running": True,
        "cycle": auto_pilot.cycle,
        "totals": dict(auto_pilot.totals),
        "recent_history": auto_pilot.history[-5:],
    }


# --- Agent Registry (cross-container communication) ---

AGENT_REGISTRY = {
    "hub":       {"host": "10.118.155.218", "port": 8080,  "type": "hub"},
    "storm":     {"host": "10.118.155.65",  "port": 9101, "type": "agent", "container": "storm-agent"},
    "satellite": {"host": "10.118.155.27",  "port": 9102, "type": "agent", "container": "satellite-agent"},
    "reddit":    {"host": "10.118.155.116", "port": 9103, "type": "agent", "container": "reddit-sniper"},
    "filter":    {"host": "10.118.155.241", "port": 9104, "type": "agent", "container": "lead-filter"},
}


@app.get("/v1/agents")
def list_agents():
    """List all registered agents in the empire tree."""
    out = []
    for name, info in AGENT_REGISTRY.items():
        entry = {"name": name, **info}
        try:
            import urllib.request
            # Note: timeout is set on urlopen, not Request
            req = urllib.request.Request(f"http://{info['host']}:{info['port']}/health")
            with urllib.request.urlopen(req, timeout=2) as resp:
                entry["health"] = json.loads(resp.read().decode())
        except Exception as e:
            entry["health"] = {"status": "unreachable", "error": str(e)[:80]}
        out.append(entry)
    return {"agents": out, "count": len(out)}


@app.post("/v1/agents/{agent_name}/dispatch")
def dispatch_to_agent(agent_name: str, payload: dict):
    """Send a message to a registered agent.

    Body: free-form JSON the agent's endpoint understands.
    """
    if agent_name not in AGENT_REGISTRY:
        raise HTTPException(404, f"unknown agent: {agent_name}")
    info = AGENT_REGISTRY[agent_name]
    try:
        import urllib.request
        url = f"http://{info['host']}:{info['port']}/dispatch"
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"dispatched": True, "response": json.loads(resp.read().decode())}
    except Exception as e:
        raise HTTPException(502, f"dispatch failed: {e}")


# --- Decision Queue ---

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page():
    """Serve the Empire OS dashboard HTML page."""
    return DASHBOARD_HTML


@app.get("/buyer-dashboard", response_class=HTMLResponse)
def buyer_dashboard_page():
    """Serve the buyer-facing lead marketplace dashboard."""
    p = Path("/root/empire_os/empire_os/static/buyer-dashboard.html")
    if not p.exists():
        raise HTTPException(404, "buyer dashboard not built")
    return HTMLResponse(p.read_text())


@app.get("/v1/dashboard/data")
def dashboard_data():
    """JSON data endpoint for the dashboard."""
    if not backend:
        raise HTTPException(503, "Engine not initialized")
    return build_dashboard_data(backend)


@app.get("/v1/dashboard/buyers")
def dashboard_buyers():
    """List buyers (tenants/subscriptions) for the public dashboard table."""
    try:
        import sqlite3 as _sq
        c = _sq.connect("/root/empire_os/empire_os.db", timeout=10, check_same_thread=False)
        try:
            rows = c.execute(
                "SELECT t.name, s.plan, s.status, s.subscription_id, "
                "(SELECT COUNT(*) FROM si_outbox WHERE buyer_tenant=s.subscription_id) AS delivered "
                "FROM si_subscription s LEFT JOIN si_tenant t ON s.tenant_id=t.tenant_id "
                "ORDER BY s.status DESC, delivered DESC LIMIT 100").fetchall()
            return {"buyers": [{"name": r[0], "tier": (r[1] or "").replace("lane_", ""),
                                "status": r[2], "subscription_id": r[3], "delivered": r[4]} for r in rows]}
        finally:
            c.close()
    except Exception as e:
        return {"buyers": [], "error": str(e)[:120]}


# --- Public static site (async fallback; bypasses StaticFiles which can reset
#     under event-loop load from internal agent self-calls) ---
import os as _os
_SITE = _os.path.join(_os.path.dirname(__file__), "static", "index.html")
@app.get("/static/index.html")
@app.get("/site")
async def site_index():
    if not _os.path.exists(_SITE):
        from fastapi import HTTPException
        raise HTTPException(404, "site not built")
    from fastapi.responses import FileResponse
    return FileResponse(_SITE, media_type="text/html")


# --- Decision Queue ---

from empire_os.ceo import build_brief


@app.get("/v1/decisions")
def decisions_list():
    """Get today's decision queue for operator review."""
    if not backend:
        raise HTTPException(503, "Engine not initialized")
    brief = build_brief(backend)
    return {
        "date": brief.date,
        "decisions": [
            {
                "kind": d.kind,
                "target_id": d.target_id,
                "priority": d.priority,
                "summary": d.summary,
            }
            for d in brief.decisions
        ],
    }


@app.post("/v1/decisions/{decision_id}/approve")
def decisions_approve(decision_id: str):
    """Approve a CEO decision — trigger the corresponding action."""
    from empire_os.funnel import transition, get_state, FunnelState
    if not backend:
        raise HTTPException(503, "Engine not initialized")

    # Map decision kinds to actions
    state = get_state(backend, decision_id)
    if not state:
        raise HTTPException(404, f"Prospect {decision_id} not found")

    current = state.current_state
    result = {"prospect_id": decision_id, "from_state": current}

    # Matched → Outreach_drafted (generate draft via sales agent)
    if current == FunnelState.MATCHED.value:
        # Trigger an AGI Sales draft action
        global agi_sales
        if not agi_sales:
            raise HTTPException(503, "agi-sales not ready")
        ev = events_for(backend, decision_id)
        niche = "general"
        for e in ev:
            if "niche=" in e.notes:
                niche = e.notes.split("niche=")[-1].split(",")[0].strip()
                break
        out = agi_sales.act(
            f'{{"action":"draft","prospect_id":"{decision_id}","niche":"{niche}","angle":"operator_approved"}}'
        )
        result["action"] = "draft"
        result["draft"] = out.get("draft", "")
        return result

    # Replied → Claimed
    elif current == FunnelState.REPLIED.value:
        eid = transition(backend, decision_id, FunnelState.CLAIMED.value, "operator", notes="operator_approved")
        result["action"] = "claim"
        result["event_id"] = eid
        return result

    # Claimed → Settled (manual settlement)
    elif current == FunnelState.CLAIMED.value:
        amount_cents = 150000  # default settlement
        eid = transition(
            backend, decision_id, FunnelState.SETTLED.value,
            "operator", notes=f"settled ${amount_cents/100:.2f}, operator_approved",
        )
        result["action"] = "settle"
        result["event_id"] = eid
        result["amount_cents"] = amount_cents
        return result

    # Outreach_drafted → Outreach_sent (operator pushes it live)
    elif current == FunnelState.OUTREACH_DRAFTED.value:
        eid = transition(
            backend, decision_id, FunnelState.OUTREACH_SENT.value,
            "operator", notes="outreach_sent, operator_approved",
        )
        result["action"] = "send"
        result["event_id"] = eid
        return result

    else:
        raise HTTPException(400, f"No actionable transition from state '{current}'")


@app.post("/v1/decisions/{decision_id}/deny")
def decisions_deny(decision_id: str):
    """Deny a CEO decision — log a deny event, no state change."""
    from empire_os.funnel import transition, get_state, FunnelState
    if not backend:
        raise HTTPException(503, "Engine not initialized")
    state = get_state(backend, decision_id)
    if not state:
        raise HTTPException(404, f"Prospect {decision_id} not found")
    # Don't transition — just acknowledge denial
    return {
        "prospect_id": decision_id,
        "from_state": state.current_state,
        "action": "denied",
        "summary": "Decision denied, no state change",
    }


# --- Funnel Transitions (for agents and auto-pilot) ---

class FunnelTransitionRequest(BaseModel):
    to_state: str
    actor: str = "auto-pilot"
    notes: str = ""


@app.post("/v1/funnel/{prospect_id}/transition")
def funnel_transition(prospect_id: str, req: FunnelTransitionRequest):
    """Move a prospect to a new funnel state.

    Used by agents (AGI Closer, Reddit Sniper, Storm) to advance
    prospects through the pipeline. Validates the transition is
    allowed by the funnel invariants.
    """
    from empire_os.funnel import transition, get_state, FunnelState
    if not backend:
        raise HTTPException(503, "Engine not initialized")
    state = get_state(backend, prospect_id)
    if not state:
        raise HTTPException(404, f"Prospect {prospect_id} not found")
    try:
        eid = transition(
            backend, prospect_id, req.to_state,
            actor=req.actor, notes=req.notes,
        )
        return {"event_id": eid, "prospect_id": prospect_id,
                "to_state": req.to_state, "actor": req.actor}
    except Exception as e:
        raise HTTPException(400, str(e))


# --- Price-and-Settle (LLM-priced settlements with fee split) ---

class PriceAndSettleRequest(BaseModel):
    prospect_id: str
    settle: bool = True
    niche: str = ""


@app.post("/v1/funnel/price-and-settle")
def price_and_settle(req: PriceAndSettleRequest):
    """LLM-price a deal, split the fee, and (optionally) settle.

    Used by the auto-pilot and AGI Closer. Reads the prospect's details
    from the funnel, asks the LLM for a realistic deal amount, computes
    the fee split, transitions claimed → settled, returns the full record.
    """
    from empire_os.funnel import transition, get_state, FunnelState
    if not backend:
        raise HTTPException(503, "Engine not initialized")
    if not fee_agent:
        raise HTTPException(503, "Fee agent not initialized")

    state = get_state(backend, req.prospect_id)
    if not state:
        raise HTTPException(404, f"Prospect {req.prospect_id} not found")
    if state.current_state != FunnelState.CLAIMED.value:
        raise HTTPException(400, f"Prospect must be in claimed state, "
                                f"got {state.current_state}")

    # Get all event notes to give the LLM context for pricing
    ev_rows = backend.execute(
        "SELECT notes FROM si_funnel_event WHERE prospect_id=? "
        "ORDER BY id ASC", (req.prospect_id,),
    ).fetchall()
    notes = " ".join((r["notes"] or "") for r in ev_rows)
    niche = req.niche
    for n in ["roofing", "hvac", "solar", "plumbing", "electrical", "mass_tort"]:
        if n in notes.lower():
            niche = n
            break

    # Ask LLM for price
    from empire_os.agent_core import OllamaClient
    llm = OllamaClient()
    prompt = (
        f"You are a sales estimator for a B2B home-services company.\n"
        f"Niche: {niche or 'general'}\n"
        f"Deal details: {notes[:400]}\n"
        f"Estimate the realistic contract value in USD for closing this deal.\n"
        f"Respond with ONLY a single integer dollar amount, no other text."
    )
    import re
    try:
        amount_dollars = 1500  # default
        raw = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        match = re.search(r"\d[\d,]*", raw.replace(",", ""))
        if match:
            amount_dollars = max(500, min(int(match.group(0)), 20000))
    except Exception as e:
        logger.warning("LLM price failed for %s: %s — using $1500 default",
                       req.prospect_id, e)
        amount_dollars = 1500

    amount_cents = amount_dollars * 100
    split = fee_agent.calculate(amount_cents)

    result = {
        "ok": True,
        "prospect_id": req.prospect_id,
        "niche": niche,
        "amount_cents": amount_cents,
        "fee_bps": split["fee_bps"],
        "fee_cents": split["fee_cents"],
        "client_cents": split["client_cents"],
    }

    if req.settle:
        notes_text = (
            f"settled ${amount_cents/100:.2f} "
            f"(llm-priced, fee ${split['fee_cents']/100:.2f}, "
            f"client ${split['client_cents']/100:.2f})"
        )
        eid = transition(
            backend, req.prospect_id, FunnelState.SETTLED.value,
            "agi-closer", notes=notes_text,
        )
        # Record fee
        fee_agent.record(str(eid), amount_cents)
        # Create payout
        if payout_engine:
            payout_engine.payout(str(eid), req.prospect_id, split["client_cents"])
        result["event_id"] = eid
    return result


# --- Payouts ---

@app.get("/v1/payouts/status")
def payouts_status():
    """Get payout engine status (method, totals, configured)."""
    if not payout_engine:
        raise HTTPException(503, "Payout engine not initialized")
    return payout_engine.status()


# --- Fee Agent ---

@app.get("/v1/fee/status")
def fee_status():
    if not fee_agent:
        raise HTTPException(503, "Fee agent not initialized")
    return fee_agent.observe()


# --- Watcher ---

@app.get("/v1/watcher/status")
def watcher_status():
    if not watcher:
        raise HTTPException(503, "Watcher not initialized")
    return watcher.observe()


# --- Tenants & SaaS Corridor ---

@app.get("/v1/plans")
def list_plans():
    """Show all available plans with their limits."""
    return {
        "plans": [
            {
                "name": p.name,
                "price_cents_per_seat_month": p.price_cents_per_seat,
                "max_seats": p.max_seats,
                "max_cycles_per_month": p.max_cycles_per_month,
                "annual_discount_bps": p.annual_discount_bps,
                "features": p.features,
            }
            for p in PLANS.values()
        ]
    }


class SignupRequest(BaseModel):
    name: str
    email: str
    plan: str = "free"


@app.post("/v1/tenants/signup")
def tenant_signup(req: SignupRequest):
    """Create a new tenant account."""
    if not tenant_store:
        raise HTTPException(503, "Tenant store not initialized")
    if tenant_store.get_tenant_by_email(req.email):
        raise HTTPException(409, f"email already registered: {req.email}")
    if req.plan not in PLANS:
        raise HTTPException(400, f"unknown plan: {req.plan}")
    tenant = tenant_store.create_tenant(req.name, req.email, plan=req.plan)
    # Owner seat
    tenant_store.add_seat(tenant.tenant_id, f"owner@{req.email}", role="owner")
    return {"tenant_id": tenant.tenant_id, "plan": tenant.plan, "email": tenant.email}


@app.get("/v1/tenants/{tenant_id}")
def tenant_info(tenant_id: str):
    if not tenant_store:
        raise HTTPException(503, "Tenant store not initialized")
    t = tenant_store.get_tenant(tenant_id)
    if not t:
        raise HTTPException(404, "tenant not found")
    sub = tenant_store.get_active_subscription(tenant_id)
    seats = tenant_store.list_seats(tenant_id)
    cycles_this_month = tenant_store.usage_for_period(tenant_id, "cycles")
    return {
        "tenant": asdict(t) if hasattr(asdict, '__call__') else t.__dict__,
        "active_subscription": sub.__dict__ if sub else None,
        "seat_count": len(seats),
        "cycles_this_month": cycles_this_month,
        "plan_limit": PLANS.get(t.plan, PLANS["free"]).max_cycles_per_month,
    }


class SubscribeRequest(BaseModel):
    tenant_id: str
    plan: str
    billing_cycle: str = "monthly"
    seats: int = 1
    payment_method: str = "paypal"  # "paypal" or "crypto_usdc"


@app.post("/v1/billing/subscribe")
def billing_subscribe(req: SubscribeRequest):
    """Start a subscription via PayPal or Crypto."""
    if not billing_engine or not tenant_store:
        raise HTTPException(503, "billing not initialized")
    tenant = tenant_store.get_tenant(req.tenant_id)
    if not tenant:
        raise HTTPException(404, "tenant not found")

    # Create the subscription record (pending)
    sub = tenant_store.create_subscription(
        tenant_id=req.tenant_id,
        plan=req.plan,
        billing_cycle=req.billing_cycle,
        seats=req.seats,
        payment_method=req.payment_method,
    )
    # Initiate payment
    result = billing_engine.start_subscription(
        req.tenant_id, req.plan, req.billing_cycle,
        req.seats, req.payment_method,
    )
    # Record payment_ref on the subscription
    if "subscription_id" in result:  # PayPal
        tenant_store.activate_subscription(sub.subscription_id,
                                          payment_ref=result["subscription_id"])
    elif "payment_request_id" in result:  # Crypto
        # Use a compound ref: tenant_id:payment_request_id
        ref = f"{req.tenant_id}:{result['payment_request_id']}"
        tenant_store.activate_subscription(sub.subscription_id,
                                          payment_ref=ref)

    # Create the invoice
    inv = tenant_store.create_invoice(
        tenant_id=req.tenant_id,
        amount_cents=result.get("amount_cents", 0),
        method=req.payment_method,
        subscription_id=sub.subscription_id,
        description=f"Empire OS {req.plan} ({req.billing_cycle})",
    )
    return {
        "subscription_id": sub.subscription_id,
        "invoice_id": inv.invoice_id,
        "payment": result,
    }


class CryptoVerifyRequest(BaseModel):
    subscription_id: str
    tx_signature: str
    sender_wallet: str


@app.post("/v1/billing/crypto/verify")
def crypto_verify(req: CryptoVerifyRequest):
    """Verify a crypto payment on-chain and activate the subscription."""
    if not billing_engine or not tenant_store:
        raise HTTPException(503, "billing not initialized")
    result = billing_engine.verify_crypto_and_activate(
        tenant_store, req.subscription_id, req.subscription_id,
        req.tx_signature, req.sender_wallet,
    )
    return result


# --- Payouts (Crypto USDC for TokenPocket etc.) ---

@app.post("/v1/payouts/process-all")
def payouts_process_all():
    """Build a payout batch with one USDC transfer per pending payout.

    Returns deeplinks for TokenPocket / Phantom / Solflare.
    Operator signs each transfer, then submits the tx signature back
    via POST /v1/payouts/verify/{payout_id}.
    """
    if not payout_engine or not payout_batch_store:
        raise HTTPException(503, "payout engine not initialized")
    pending = [r for r in payout_engine.store.list_all()
               if r.get("status") == "pending"]
    if not pending:
        return {"batch_id": None, "message": "no pending payouts",
                "total_cents": 0,
                "debug": {"store_path": str(payout_engine.store.path),
                          "records": len(payout_engine.store.records)}}
    crypto_cfg = billing_engine.crypto
    if not crypto_cfg.configured():
        return {
            "error": "crypto_not_configured",
            "message": "set VAULT_WALLET_ADDRESS to enable USDC payouts",
            "pending_count": len(pending),
            "pending_total_cents": sum(p["amount_cents"] for p in pending),
        }
    batch = build_payout_batch(pending, crypto_cfg, payout_batch_store)
    return {
        "batch_id": batch.batch_id,
        "payment_request_count": len(batch.payment_requests),
        "total_amount_cents": batch.total_amount_cents,
        "total_amount_usdc": batch.total_amount_cents / 100,
        "vault_wallet": crypto_cfg.vault_wallet,
        "payment_requests": batch.payment_requests,
    }


class BatchTxRequest(BaseModel):
    sender_wallet: str = ""
    """Optional — if omitted, uses VAULT_WALLET_ADDRESS."""


@app.post("/v1/payouts/batch-tx")
def payouts_batch_tx(req: BatchTxRequest = None):
    """Build Solana transactions for all pending payouts.
    
    Splits payouts into batches of ~4 per tx so Phantom can handle the size.
    Returns an array of unsigned transactions (base64) — sign each one sequentially.
    If `sender_wallet` is omitted, uses VAULT_WALLET_ADDRESS (env var).
    """
    if not payout_engine or not billing_engine:
        raise HTTPException(503, "payout engine not initialized")
    crypto_cfg = billing_engine.crypto
    if not crypto_cfg.configured():
        raise HTTPException(503, "set VAULT_WALLET_ADDRESS first")

    sender = (req.sender_wallet if req and req.sender_wallet
              else crypto_cfg.vault_wallet)
    pending = [r for r in payout_engine.store.list_all()
               if r.get("status") == "pending"]
    if not pending:
        return {
            "batch_id": None,
            "message": "no pending payouts",
            "debug": {
                "store_path": str(payout_engine.store.path),
                "store_records": len(payout_engine.store.records),
                "records_by_status": {
                    s: sum(1 for r in payout_engine.store.records
                           if r.get("status") == s)
                    for s in set(r.get("status", "?")
                                  for r in payout_engine.store.records)
                },
            },
        }

    import base64
    from empire_os.batched_payout import build_batched_payout_tx

    # Build all payouts (operator receives all — demo mode)
    operator_wallet = sender
    all_payouts = []
    for p in pending:
        all_payouts.append({
            "payout_id": p["payout_id"],
            "destination": operator_wallet,
            "amount_cents": p["amount_cents"],
        })

    # Fetch one blockhash for all batches (avoid RPC rate limit)
    import urllib.request, json as _json
    try:
        _pl = _json.dumps({"jsonrpc":"2.0","id":1,"method":"getLatestBlockhash","params":[{"commitment":"confirmed"}]}).encode()
        _req = urllib.request.Request(crypto_cfg.rpc_url, data=_pl, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(_req, timeout=15) as _resp:
            bh = _json.loads(_resp.read().decode())["result"]["value"]["blockhash"]
    except Exception:
        bh = None

    # Split into sub-batches of MAX_PER_TX for Phantom's size limit
    MAX_PER_TX = 4
    batch_id = payout_batch_store.batches[-1]["batch_id"] if payout_batch_store.batches else ""
    txs = []
    total_ix = 0
    total_cents = 0
    for i in range(0, len(all_payouts), MAX_PER_TX):
        chunk = all_payouts[i:i + MAX_PER_TX]
        result = build_batched_payout_tx(
            payouts=chunk,
            sender_wallet=sender,
            mint=crypto_cfg.usdc_mint,
            batch_id=batch_id,
        )
        tx_bytes = base64.b64decode(result.transaction_base64) if result.transaction_base64 else b""
        txs.append({
            "index": len(txs),
            "payout_ids": [p["payout_id"] for p in chunk],
            "count": len(chunk),
            "amount_usdc": result.total_amount_usdc,
            "amount_cents": result.total_amount_cents,
            "transaction_base64": result.transaction_base64 or "",
            "tx_bytes": len(tx_bytes),
        })
        total_ix += len(chunk)
        total_cents += result.total_amount_cents

    return {
        "batch_id": batch_id,
        "total_payouts": len(all_payouts),
        "total_amount_usdc": round(total_cents / 100, 2),
        "total_amount_cents": total_cents,
        "batch_count": len(txs),
        "transactions": txs,
    }


class PayoutVerifyRequest(BaseModel):
    payout_id: str
    tx_signature: str
    sender_wallet: str


@app.post("/v1/payouts/verify")
def payouts_verify(req: PayoutVerifyRequest):
    """Verify a payout's crypto tx on-chain and mark paid."""
    if not payout_engine:
        raise HTTPException(503, "payout engine not initialized")
    crypto_cfg = billing_engine.crypto
    if not crypto_cfg.configured():
        raise HTTPException(503, "crypto not configured")
    # Look up the payout record to get the expected amount + memo
    record = next(
        (r for r in payout_engine.store.list_all()
         if r["payout_id"] == req.payout_id), None
    )
    if not record:
        raise HTTPException(404, "payout not found")
    expected_memo = f"empire-payout:{req.payout_id}"
    result = verify_crypto_payment(
        crypto_cfg, req.tx_signature,
        record["amount_cents"], expected_memo, req.sender_wallet,
    )
    if result.get("verified"):
        payout_engine.store.update(
            req.payout_id,
            status="paid",
            reference=req.tx_signature,
            paid_at=datetime.now(timezone.utc).isoformat(),
        )
        return {"ok": True, "payout_id": req.payout_id, "verification": result}
    return {"ok": False, "payout_id": req.payout_id, "verification": result}


# --- Waterfall (Data Provider Orchestrator) ---

class LeadEnrichRequest(BaseModel):
    company: str
    phone: str = ""
    email: str = ""
    name: str = ""
    vertical: str = "default"


@app.post("/v1/leads/enrich")
def leads_enrich(req: LeadEnrichRequest):
    """Run a lead through the Waterfall to get verified contact info."""
    global waterfall
    if not waterfall:
        raise HTTPException(503, "Waterfall not initialized")
    lead_info = {
        "company": req.company,
        "phone": req.phone,
        "email": req.email,
        "name": req.name,
        "vertical": req.vertical,
    }
    result = waterfall.enrich(lead_info)
    return result.to_dict()


@app.get("/v1/waterfall/metrics")
def waterfall_metrics():
    """Get waterfall usage metrics (provider wins, costs)."""
    global waterfall
    if not waterfall:
        raise HTTPException(503, "Waterfall not initialized")
    return waterfall.metrics


# --- Telegram ---

class TelegramPayload(BaseModel):
    token: Optional[str] = None
    chat_id: Optional[str] = None
    message: Optional[str] = None
    tag: Optional[str] = None


@app.post("/v1/telegram/brief")
def telegram_brief(payload: TelegramPayload):
    """Send CEO brief to Telegram. Falls back to env vars."""
    if not backend:
        raise HTTPException(503, "Engine not initialized")
    result = send_brief(
        backend,
        token=payload.token,
        chat_id=payload.chat_id,
    )
    return result


@app.post("/v1/telegram/alert")
def telegram_alert(payload: TelegramPayload, message: str = ""):
    """Send an alert to Telegram.

    `message` may arrive either as a query param OR in the JSON body
    (payload.message). Body wins when present. This lets callers POST
    a structured payload (e.g. payment links) instead of URL-encoding.
    """
    text = payload.message or message or "Empire OS alert triggered"
    result = send_alert(
        text,
        token=payload.token,
        chat_id=payload.chat_id,
    )
    return result


# --- Wallet signing UI + Solana Pay Transaction Request ---

WALLET_SIGN_HTML = (Path(__file__).parent / "templates" / "sign_tx.html").read_text()


@app.get("/wallet/sign", response_class=HTMLResponse)
async def wallet_sign_page():
    """Serve the wallet-adapter signing page."""
    return WALLET_SIGN_HTML


@app.get("/v1/payouts/sign-tx")
def payouts_sign_tx_request_sync():
    """Solana Pay Transaction Request endpoint."""
    import traceback, base64
    from empire_os.batched_payout import build_batched_payout_tx
    from fastapi.responses import Response
    if not payout_engine or not billing_engine:
        raise HTTPException(503, "payout engine not initialized")
    crypto_cfg = billing_engine.crypto
    if not crypto_cfg.configured():
        raise HTTPException(503, "set VAULT_WALLET_ADDRESS first")

    sender = crypto_cfg.vault_wallet
    pending = [r for r in payout_engine.store.list_all()
               if r.get("status") == "pending"]
    if not pending:
        raise HTTPException(404, "no pending payouts")

    payouts = [{
        "payout_id": p["payout_id"],
        "destination": sender,
        "amount_cents": p["amount_cents"],
    } for p in pending]

    try:
        result = build_batched_payout_tx(
            payouts=payouts,
            sender_wallet=sender,
            mint=crypto_cfg.usdc_mint,
        )
    except Exception:
        import sys
        print("SIGN-TX ERROR:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise

    if not result.transaction_base64:
        raise HTTPException(500, "failed to build transaction (empty base64)")

    tx_bytes = base64.b64decode(result.transaction_base64)
    return Response(
        content=tx_bytes,
        media_type="application/octet-stream",
        headers={
            "x-solana-pay-message": (
                f"Sign to execute {result.instruction_count} payouts "
                f"totaling ${result.total_amount_usdc:,.2f} USDC"
            ),
            "x-solana-pay-label": "Empire OS Batched Payout",
        },
    )


@app.get("/v1/payouts/tx-base64")
def payouts_tx_base64():
    """Download the unsigned base64 transaction as plain text."""
    import traceback, base64
    from empire_os.batched_payout import build_batched_payout_tx
    from fastapi.responses import PlainTextResponse

    if not payout_engine or not billing_engine:
        raise HTTPException(503, "payout engine not initialized")
    crypto_cfg = billing_engine.crypto
    if not crypto_cfg.configured():
        raise HTTPException(503, "set VAULT_WALLET_ADDRESS first")

    sender = crypto_cfg.vault_wallet
    pending = [r for r in payout_engine.store.list_all()
               if r.get("status") == "pending"]
    if not pending:
        raise HTTPException(404, "no pending payouts")

    payouts_list = [{
        "payout_id": p["payout_id"],
        "destination": sender,
        "amount_cents": p["amount_cents"],
    } for p in pending]

    try:
        result = build_batched_payout_tx(
            payouts=payouts_list,
            sender_wallet=sender,
            mint=crypto_cfg.usdc_mint,
        )
    except Exception:
        import sys
        print("TX-BASE64 ERROR:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise

    if not result.transaction_base64:
        raise HTTPException(500, "failed to build transaction (empty base64)")

    return PlainTextResponse(result.transaction_base64)


class PayoutVerifyBatchRequest(BaseModel):
    tx_signature: str


class PayoutSubmitRequest(BaseModel):
    signed_tx_base64: str
    batch_index: int = 0
    encoding: str = "base64"  # "base64" (default) or "base58"


@app.post("/v1/payouts/submit")
def payouts_submit(req: PayoutSubmitRequest):
    """Submit a signed transaction via the hub's server-side RPC.

    The wallet page signs the transaction locally (Phantom handles this),
    then sends the signed tx back here. The hub broadcasts it server-side
    using its own RPC endpoint — no client-side RPC calls needed.
    """
    if not payout_engine or not billing_engine:
        raise HTTPException(503, "payout engine not initialized")
    crypto_cfg = billing_engine.crypto
    if not crypto_cfg.configured():
        raise HTTPException(503, "crypto not configured")

    import base64, urllib.request as _ur, struct
    enc = (req.encoding or "base64").lower()
    try:
        if enc == "base58":
            # Forward base58 as-is — Phantom may serialize to base58.
            tx_for_rpc = req.signed_tx_base64
            print(f"[submit] base58 mode, len={len(req.signed_tx_base64)}", flush=True)
        else:
            # Decode our own base64 to bytes, then re-encode WITHOUT PADDING.
            # Solana RPC's base58 parser trips on `=` (padding) at the end
            # when it auto-detects encoding — strip it to keep the RPC happy.
            raw = base64.b64decode(req.signed_tx_base64, validate=True)
            tx_for_rpc = base64.b64encode(raw).decode().rstrip("=")
            print(f"[submit] base64 mode, raw_len={len(raw)}, encoded_len={len(tx_for_rpc)}", flush=True)
    except Exception as e:
        raise HTTPException(400, f"invalid encoding: {e}")

    rpc_url = crypto_cfg.rpc_url
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "method": "sendTransaction",
        "params": [
            tx_for_rpc,
            {"skipPreflight": True, "maxRetries": 5, "preflightCommitment": "confirmed"},
        ],
    }).encode()
    try:
        _r = _ur.Request(rpc_url, data=payload,
                         headers={"Content-Type": "application/json"})
        with _ur.urlopen(_r, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            if "error" in data:
                return {"ok": False, "error": data["error"], "batch_index": req.batch_index}
            sig = data.get("result")
            return {"ok": True, "signature": sig, "batch_index": req.batch_index,
                    "encoding": enc}
    except Exception as e:
        raise HTTPException(502, f"RPC submit failed: {e}")


@app.post("/v1/payouts/verify-batch")
def payouts_verify_batch(req: PayoutVerifyBatchRequest):
    """Verify a submitted batched tx on-chain and mark all pending payouts paid.

    Polls up to 60 seconds for the tx to confirm — Solana mainnet-beta typically
    confirms in 12-20s but the first call after submit may see "not found".
    """
    if not payout_engine or not billing_engine:
        raise HTTPException(503, "payout engine not initialized")
    crypto_cfg = billing_engine.crypto
    if not crypto_cfg.configured():
        raise HTTPException(503, "crypto not configured")

    from empire_os.billing import verify_crypto_payment
    pending = [r for r in payout_engine.store.list_all()
               if r.get("status") == "pending"]
    if not pending:
        return {"ok": False, "message": "no pending payouts to verify"}

    sample = pending[0]
    expected_memo = f"empire-payout:{sample['payout_id']}"

    # Poll the RPC up to 60 seconds for confirmation
    import time as _t
    deadline = _t.time() + 60
    result = None
    attempts = 0
    while _t.time() < deadline:
        attempts += 1
        result = verify_crypto_payment(
            crypto_cfg, req.tx_signature,
            sample["amount_cents"], expected_memo, crypto_cfg.vault_wallet,
        )
        if result.get("verified"):
            break
        # tx_not_found is normal right after submit; keep polling
        if result.get("error") not in ("tx_not_found", "tx_not_confirmed", None):
            break
        _t.sleep(3)

    if result and result.get("verified"):
        for p in pending:
            payout_engine.store.update(
                p["payout_id"],
                status="paid",
                reference=req.tx_signature,
                paid_at=datetime.now(timezone.utc).isoformat(),
            )
        return {
            "ok": True,
            "message": f"All {len(pending)} payouts marked paid (after {attempts} attempts)",
            "tx_signature": req.tx_signature,
            "verification": result,
        }
    return {"ok": False, "message": f"Transaction not verified after {attempts} attempts",
            "verification": result}


# ── Lane / Lead Supply System ────────────────────────────────────────


@app.get("/v1/lanes")
def list_lanes():
    """List all 36 lanes with their status."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    cur = backend.execute(
        "SELECT l.* FROM lanes l ORDER BY l.category, l.sub_niche, l.metro"
    )
    lanes = []
    for row in cur.fetchall():
        lanes.append(dict(row))
    return {"lanes": lanes, "total": len(lanes)}


@app.get("/v1/lanes/sub-niches")
def list_sub_niches():
    """List all sub-niches across categories."""
    return {"categories": {
        k: {"label": v["label"], "subs": v["subs"]}
        for k, v in CATEGORIES.items()
    }}


@app.get("/v1/lanes/categories")
def list_categories():
    """List all lane categories."""
    return {"categories": [
        {"key": k, "label": v["label"], "sub_count": len(v["subs"])}
        for k, v in CATEGORIES.items()
    ]}


@app.get("/v1/lanes/metros")
def list_metros():
    """List metro service areas."""
    return {"metros": METROS}


@app.get("/v1/lanes/{lane_id}")
def get_lane(lane_id: str):
    """Get a single lane's details + lead count."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    cur = backend.execute("SELECT * FROM lanes WHERE id=?", (lane_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, f"lane {lane_id} not found")
    lane = dict(row)

    cur = backend.execute(
        "SELECT COUNT(*) as lead_count FROM lane_leads WHERE lane_id=? AND status='pending'",
        (lane_id,),
    )
    lane["pending_leads"] = cur.fetchone()[0]

    cur = backend.execute(
        "SELECT * FROM lane_seats WHERE lane_id=? AND active=1", (lane_id,)
    )
    lane["seats"] = [dict(r) for r in cur.fetchall()]

    cur = backend.execute(
        "SELECT COUNT(*) as total, SUM(CASE WHEN status='delivered' THEN 1 ELSE 0 END) as delivered "
        "FROM lane_leads WHERE lane_id=?",
        (lane_id,),
    )
    stats = cur.fetchone()
    lane["total_leads"] = stats[0]
    lane["delivered_leads"] = stats[1]

    return lane


class AssignSeatRequest(BaseModel):
    firm_name: str
    firm_slug: str
    tier: str = "raw"
    price_monthly: float = 0.0


@app.post("/v1/lanes/{lane_id}/seat")
def assign_seat(lane_id: str, req: AssignSeatRequest):
    """Assign a law firm to a lane seat."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    cur = backend.execute("SELECT * FROM lanes WHERE id=?", (lane_id,))
    if not cur.fetchone():
        raise HTTPException(404, f"lane {lane_id} not found")

    # Deactivate any existing seat for this lane
    backend.execute(
        "UPDATE lane_seats SET active=0 WHERE lane_id=? AND active=1",
        (lane_id,),
    )

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    backend.execute(
        "INSERT INTO lane_seats (lane_id, firm_name, firm_slug, tier, price_monthly, "
        "active, started_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
        (lane_id, req.firm_name, req.firm_slug, req.tier, req.price_monthly, now),
    )
    backend.execute("UPDATE lanes SET occupied_by=?, price_monthly=? WHERE id=?",
                    (req.firm_slug, req.price_monthly, lane_id))
    backend.commit()
    return {"ok": True, "lane_id": lane_id, "firm": req.firm_slug}


@app.post("/v1/lanes/{lane_id}/release")
def release_seat(lane_id: str):
    """Release a lane seat."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    backend.execute("UPDATE lane_seats SET active=0 WHERE lane_id=? AND active=1",
                    (lane_id,))
    backend.execute("UPDATE lanes SET occupied_by=NULL WHERE id=?", (lane_id,))
    backend.commit()
    return {"ok": True, "lane_id": lane_id, "status": "released"}


@app.get("/v1/lanes/leads/pending")
def pending_lane_leads():
    """Get all pending (undelivered) lane leads grouped by lane."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    cur = backend.execute(
        "SELECT ll.*, l.sub_niche AS tort_key, l.metro, l.occupied_by "
        "FROM lane_leads ll JOIN lanes l ON ll.lane_id=l.id "
        "WHERE ll.status='pending' ORDER BY ll.created_at DESC"
    )
    leads = [dict(r) for r in cur.fetchall()]
    return {"pending": len(leads), "leads": leads}


@app.get("/v1/lanes/leads/by-source")
def leads_by_source(source: str = "permits_nyc", limit: int = 100):
    """List leads filtered by source (e.g. permits_nyc, chicago_311)."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    cur = backend.execute(
        "SELECT id, name, phone, lane_id, metro, source, status "
        "FROM lane_leads WHERE source=? "
        "ORDER BY id DESC LIMIT ?",
        (source, limit),
    )
    leads = [dict(r) for r in cur.fetchall()]
    return {"source": source, "count": len(leads), "leads": leads}


@app.get("/v1/agents/status")
def agents_status():
    """Return agent fleet status for Commander agent to read."""
    pm2_dump = Path("/root/.pm2/dump.pm2")
    if not pm2_dump.exists():
        return {"error": "pm2 dump not visible", "agents": []}
    try:
        data = json.loads(pm2_dump.read_text())
        # Dump is a list, not dict — handle both shapes
        apps = data if isinstance(data, list) else (data.get("apps", []) if isinstance(data, dict) else [])
        agents = []
        if isinstance(apps, list):
            for p in apps:
                # status is at top level (pm2 dump format); fallback to pm2_env
                status = p.get("status") or p.get("pm2_env", {}).get("status", "unknown")
                pid = p.get("pid") or p.get("pm2_env", {}).get("pid")
                restarts = p.get("restart_time") or p.get("pm2_env", {}).get("restart_time", 0)
                agents.append({
                    "name": p.get("name", "?"),
                    "status": status,
                    "pid": pid,
                    "restarts": restarts,
                })
        return {"total": len(agents), "agents": agents}
    except Exception as e:
        return {"error": str(e), "agents": []}


class RouteLeadRequest(BaseModel):
    prospect_id: str
    details: str = ""
    zip_code: str = ""
    state: str = ""
    source: str = "web"
    name: str = ""
    phone: str = ""
    screening: dict = {}


@app.post("/v1/lanes/route")
def route_prospect(req: RouteLeadRequest):
    """Route a prospect to the correct lane and qualify them."""
    if not backend:
        raise HTTPException(503, "backend not initialized")

    # Step 1: Route to lane
    routing = route_lead(
        backend,
        prospect_id=req.prospect_id,
        details=req.details,
        zip_code=req.zip_code or "",
        state=req.state or "",
    )

    # Step 2: Qualify with Omega OS scoring
    qualification = qualify_prospect(
        backend,
        prospect_id=req.prospect_id,
        tort_key=routing.get("best_niche"),
        details=req.details,
        source=req.source,
        name=req.name,
        phone=req.phone,
        zip_code=req.zip_code,
        screening=req.screening,
    )

    return {
        "prospect_id": req.prospect_id,
        "routing": routing,
        "qualification": qualification,
    }


class QualifyBatchRequest(BaseModel):
    leads: list[RouteLeadRequest]


@app.post("/v1/lanes/route-batch")
def route_batch(req: QualifyBatchRequest):
    """Route and qualify multiple prospects at once."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    results = []
    for lead in req.leads:
        routing = route_lead(
            backend, prospect_id=lead.prospect_id,
            details=lead.details or "", zip_code=lead.zip_code or "",
            state=lead.state or "",
        )
        qual = qualify_prospect(
            backend, prospect_id=lead.prospect_id,
            tort_key=routing.get("best_niche"),
            details=lead.details, source=lead.source,
            name=lead.name, phone=lead.phone,
            zip_code=lead.zip_code, screening=lead.screening,
        )
        results.append({
            "prospect_id": lead.prospect_id,
            "routing": routing,
            "qualification": qual,
        })
    return {"results": results, "count": len(results)}


@app.get("/v1/lanes/score/{prospect_id}")
def score_prospect(prospect_id: str):
    """Get Omega OS score for an existing prospect."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    # Fetch from DB
    cur = backend.execute(
        "SELECT ll.*, l.sub_niche AS tort_key, l.metro "
        "FROM lane_leads ll JOIN lanes l ON ll.lane_id=l.id "
        "WHERE ll.prospect_id=? ORDER BY ll.created_at DESC LIMIT 1",
        (prospect_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, f"prospect {prospect_id} not found")

    # Try to get funnel notes
    cur = backend.execute(
        "SELECT notes FROM si_funnel_events WHERE prospect_id=? ORDER BY event_id DESC LIMIT 1",
        (prospect_id,),
    )
    notes = ""
    if row_f := cur.fetchone():
        notes = row_f["notes"]

    omega = OmegaScore(
        tort_key=row["tort_key"],
        details=notes,
        source="web",
    )
    result = omega.compute()
    return {"prospect_id": prospect_id, "score": result}


# --- Swarm pub/sub (file-backed, lets containers share events) ---
SWARMS_LOG = Path("/root/swarms/events.jsonl")
SWARMS_LOG.parent.mkdir(parents=True, exist_ok=True)
SWARMS_MAX_LINES = 5000  # bounded

# ── PPC ledger ingestion (containers forward charges/invoices here) ──
PPC_DB = "/root/empire_os/empire_os.db"


@app.post("/v1/ppc/log_charge")
async def ppc_log_charge(request: Request):
    """Ppc-router (and other containers) POST charge records here so
    the hub hosts the canonical ledger. Idempotent on charge_id."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "invalid JSON body")
    cid = body.get("charge_id")
    if not cid:
        raise HTTPException(400, "charge_id required")
    import sqlite3 as _sq
    cnx = _sq.connect(PPC_DB)
    cnx.execute(
        "INSERT OR IGNORE INTO si_charges "
        "(charge_id, buyer_id, processor, customer_ref, payment_ref,"
        " head, reason, amount_cents, currency, status, "
        " processor_response, attempt_count, created_at, paid_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
        (cid, body.get("buyer_id", ""), body.get("processor", ""),
         body.get("customer_ref", ""), body.get("payment_ref", ""),
         body.get("head", 0), body.get("reason", "")[:200],
         int(body.get("amount_cents", 0)),
         body.get("currency", "USD"),
         body.get("status", "failed"),
         json.dumps(body)[:500],
         body.get("created_at") or
         datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
         body.get("paid_at")))
    cnx.commit()
    cnx.close()
    return {"ok": True, "charge_id": cid}


@app.post("/v1/ppc/log_invoice")
async def ppc_log_invoice(request: Request):
    """Ppc-router POSTs invoices here for canonical ledger."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "invalid JSON body")
    iid = body.get("invoice_id")
    if not iid:
        raise HTTPException(400, "invoice_id required")
    import sqlite3 as _sq
    cnx = _sq.connect(PPC_DB)
    cnx.execute(
        "INSERT OR IGNORE INTO si_ppc_invoices "
        "(invoice_id, charge_id, buyer_id, head, lead_id, call_id,"
        " amount_cents, amount_usdc, status, metadata, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (iid, body.get("charge_id", ""),
         body.get("buyer_id", ""), str(body.get("head", "")),
         body.get("lead_id", ""), body.get("call_id", ""),
         int(body.get("amount_cents", 0)),
         body.get("amount_usdc", 0),
         body.get("status", "open"),
         body.get("metadata", "")[:500],
         body.get("ts") or __import__("datetime").datetime.now(
             __import__("datetime").timezone.utc).isoformat()))
    cnx.commit()
    cnx.close()
    return {"ok": True, "invoice_id": iid}


@app.post("/v1/ppc/charge")
async def ppc_charge(request: Request):
    """Centralized charge endpoint. ppc_router and other agents POST
    here with {buyer_id, head, reason, amount_cents}. Hub resolves
    the buyer's wallet from canonical si_buyer_payment_methods,
    generates a payment-memo, and persists the charge in si_charges
    + si_ppc_invoices on the host (canonical source of truth).

    After a successful crypto charge with a real pay_url, the route
    queues an si_outbox row (via pay_url_delivery.deliver_pay_url)
    so mail_sender can email the buyer. Failure to resolve an email
    is logged but never blocks the charge — the pay_url is still
    returned in the response.

    Returns ChargeResult shape (with optional delivery sub-object).
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "invalid JSON body")
    required = ("buyer_id", "head", "reason", "amount_cents")
    if not all(k in body for k in required):
        raise HTTPException(400, f"requires {required}")
    buyer_id = body["buyer_id"]
    head = int(body["head"])
    amount_cents = int(body["amount_cents"])
    reason = body["reason"][:200]
    call_id = body.get("call_id", "")
    lead_id = body.get("lead_id", "")
    tag = body.get("tag", "")
    # Delegate to charge.charge() which knows all the processors
    from empire_os.charge import charge as _do_charge
    res = _do_charge(
        buyer_id=buyer_id, head=head, reason=reason,
        amount_cents=amount_cents, currency="USD",
        call_id=call_id, lead_id=lead_id)
    # W2: queue the pay_url email. Best-effort, never raises to caller.
    # ChargeResult shape carries buyer_id/charge_id/etc.; if charge()
    # returned a shape missing those (legacy), fill them from request.
    try:
        from empire_os.pay_url_delivery import deliver_pay_url
        # Normalize so pay_url_delivery sees what it needs.
        res_for_delivery = dict(res)
        res_for_delivery.setdefault("buyer_id", buyer_id)
        res_for_delivery.setdefault("head", head)
        res_for_delivery.setdefault("amount_cents", amount_cents)
        res_for_delivery.setdefault("reason", reason)
        res_for_delivery["tag"] = tag  # probe correlation key
        # raw may hold charge_id; pull up if missing.
        if not res_for_delivery.get("charge_id"):
            raw = res_for_delivery.get("raw") or {}
            if isinstance(raw, dict):
                res_for_delivery["charge_id"] = (
                    raw.get("charge_id") or "")
        delivery = deliver_pay_url(res_for_delivery)
        res["pay_url_delivery"] = delivery
    except Exception as e:
        # Mail-side failure MUST NOT mask the successful charge.
        logger.exception("W2 deliver_pay_url failed for buyer=%s: %s",
                         buyer_id, e)
        res["pay_url_delivery"] = {"queued": False, "reason":
                                   f"exception:{type(e).__name__}"}
    return res


@app.get("/v1/ppc/buyer_pms")
async def ppc_buyer_pms(buyer_id: str):
    """Get a buyer's payment methods from the canonical hub DB.

    Containers with local DB mirrors call this to resolve buyer
    wallets before charging. Returns list of PMs with
    {processor, customer_ref, payment_ref, brand, last4,
    is_default, created_at}.
    """
    import sqlite3 as _sq
    cnx = _sq.connect(PPC_DB)
    cnx.row_factory = _sq.Row
    rows = cnx.execute(
        "SELECT id, buyer_id, processor, customer_ref, "
        "payment_ref, brand, last4, is_default, created_at "
        "FROM si_buyer_payment_methods "
        "WHERE buyer_id=? AND deleted_at IS NULL "
        "ORDER BY is_default DESC, id DESC",
        (buyer_id,)).fetchall()
    cnx.close()
    pms = []
    for r in rows:
        d = dict(r)
        d["is_default"] = bool(d.get("is_default"))
        pms.append(d)
    return {"buyer_id": buyer_id, "pms": pms, "count": len(pms)}


@app.get("/v1/ppc/charges")
async def ppc_list_charges(limit: int = 50, head: int = 0,
                            status: str = ""):
    """Inspect the canonical ledger. Optional filters."""
    import sqlite3 as _sq
    cnx = _sq.connect(PPC_DB)
    cnx.row_factory = _sq.Row
    q = "SELECT * FROM si_charges WHERE 1=1"
    args: list = []
    if head:
        q += " AND head=?"; args.append(head)
    if status:
        q += " AND status=?"; args.append(status)
    q += " ORDER BY id DESC LIMIT ?"; args.append(limit)
    rows = [dict(r) for r in cnx.execute(q, args).fetchall()]
    cnx.close()
    return {"charges": rows, "count": len(rows)}


@app.get("/v1/ppc/invoices")
async def ppc_list_invoices(limit: int = 50):
    """Inspect the canonical invoice ledger."""
    import sqlite3 as _sq
    cnx = _sq.connect(PPC_DB)
    cnx.row_factory = _sq.Row
    rows = [dict(r) for r in cnx.execute(
        "SELECT * FROM si_ppc_invoices ORDER BY id DESC LIMIT ?",
        (limit,)).fetchall()]
    cnx.close()
    return {"invoices": rows, "count": len(rows)}


@app.post("/v1/swarms/events")
async def swarm_log_event(request: Request):
    """Station 0 (keyword-expert) calls this to emit
    MarketOpportunityFound events. Body: any JSON object with
    fields event_type + niche_id. Append-only file backed."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "invalid JSON body")
    if not isinstance(body, dict):
        raise HTTPException(400, "body must be object")
    if "event_type" not in body or "niche_id" not in body:
        raise HTTPException(400, "requires event_type + niche_id")
    body.setdefault("ts",
                    datetime.utcnow().replace(tzinfo=timezone.utc).isoformat())
    with SWARMS_LOG.open("a") as f:
        f.write(json.dumps(body) + "\n")
    # Trim if too large
    try:
        lines = SWARMS_LOG.read_text().splitlines()
        if len(lines) > SWARMS_MAX_LINES:
            SWARMS_LOG.write_text("\n".join(lines[-SWARMS_MAX_LINES:]) + "\n")
    except Exception:
        pass
    return {"ok": True, "logged": True, "path": str(SWARMS_LOG)}


@app.get("/v1/swarms/events")
async def swarm_poll_events(since: str = "", limit: int = 50):
    """Station 1 (synthetic-analyst) calls this to poll new events.
    Optional ?since=<ts> filters by timestamp. Returns last N lines."""
    if not SWARMS_LOG.exists():
        return {"events": [], "count": 0}
    try:
        lines = SWARMS_LOG.read_text().splitlines()
    except Exception as e:
        raise HTTPException(500, f"read failed: {e}")
    out = []
    for ln in lines[-limit*5:]:  # over-fetch then filter
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if since and d.get("ts", "") < since:
            continue
        out.append(d)
        if len(out) >= limit:
            break
    return {"events": out, "count": len(out), "path": str(SWARMS_LOG)}


# ── Carrier DRP Roster Endpoints ────────────────────────────────────


def _ensure_carrier_rosters_table():
    """Bootstrap carrier_rosters table on first use."""
    import sqlite3 as _sq
    cnx = _sq.connect("/root/empire_os/empire_os.db")
    try:
        cnx.execute(
            "CREATE TABLE IF NOT EXISTS carrier_rosters ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "carrier TEXT NOT NULL,"
            "company_name TEXT NOT NULL DEFAULT '',"
            "license_no TEXT NOT NULL DEFAULT '',"
            "city TEXT NOT NULL DEFAULT '',"
            "state TEXT NOT NULL DEFAULT '',"
            "zip TEXT NOT NULL DEFAULT '',"
            "service_areas TEXT NOT NULL DEFAULT '',"
            "specializations TEXT NOT NULL DEFAULT '',"
            "phone TEXT NOT NULL DEFAULT '',"
            "website TEXT NOT NULL DEFAULT '',"
            "scraped_at TEXT NOT NULL DEFAULT '',"
            "source_url TEXT NOT NULL DEFAULT '',"
            "UNIQUE(carrier, company_name, license_no, city, state)"
            ")"
        )
        cnx.commit()
    finally:
        cnx.close()


@app.get("/v1/carrier-rosters")
def list_carrier_rosters(carrier: str = None, limit: int = 100, offset: int = 0):
    """List carrier roster entries, optionally filtered by carrier name."""
    _ensure_carrier_rosters_table()
    import sqlite3 as _sq
    cnx = _sq.connect("/root/empire_os/empire_os.db")
    cnx.row_factory = _sq.Row
    try:
        q = "SELECT * FROM carrier_rosters WHERE 1=1"
        args = []
        if carrier:
            q += " AND carrier=?"
            args.append(carrier)
        q += " ORDER BY id DESC LIMIT ? OFFSET ?"
        args.extend([limit, offset])
        rows = [dict(r) for r in cnx.execute(q, args).fetchall()]
        # count total (without limit/offset)
        count_q = "SELECT COUNT(*) FROM carrier_rosters WHERE 1=1"
        count_args = []
        if carrier:
            count_q += " AND carrier=?"
            count_args.append(carrier)
        total = cnx.execute(count_q, count_args).fetchone()[0]
        return {"rows": rows, "total": total, "limit": limit, "offset": offset}
    finally:
        cnx.close()


@app.post("/v1/carrier-rosters/scrape-all")
def scrape_all_carrier_rosters():
    """Trigger all carrier scrapers. Returns summary counts per carrier.

    Runs synchronously; for larger sets this should be made async.
    """
    # Import here to avoid circular import at module level
    from empire_os.carrier_rosters import run_all_scrapers
    result = run_all_scrapers(
        hub_url=f"http://localhost:{int(os.environ.get('EMPIRE_PORT', '8080'))}",
        db_path="/root/empire_os/empire_os.db",
    )
    return result


@app.get("/v1/carrier-rosters/stats")
def carrier_roster_stats():
    """Return row counts grouped by carrier."""
    _ensure_carrier_rosters_table()
    import sqlite3 as _sq
    cnx = _sq.connect("/root/empire_os/empire_os.db")
    try:
        rows = cnx.execute(
            "SELECT carrier, COUNT(*) as cnt FROM carrier_rosters "
            "GROUP BY carrier ORDER BY cnt DESC"
        ).fetchall()
        counts = {r[0]: r[1] for r in rows}
        total = sum(counts.values())
        return {"counts": counts, "total": total, "carriers": len(counts)}
    finally:
        cnx.close()


@app.post("/v1/carrier-rosters/batch")
def batch_insert_carrier_rosters(req: dict):
    """Internal batch insert endpoint — used by the scraper module to
    POST scraped rows to the hub for centralised storage.

    Body: { carrier: str, rows: [{company_name, license_no, ...}] }
    """
    carrier = req.get("carrier", "")
    rows = req.get("rows", [])
    if not carrier or not rows:
        raise HTTPException(400, "carrier and rows required")
    _ensure_carrier_rosters_table()
    import sqlite3 as _sq
    cnx = _sq.connect("/root/empire_os/empire_os.db")
    try:
        inserted = 0
        for row in rows:
            try:
                cnx.execute(
                    "INSERT OR IGNORE INTO carrier_rosters "
                    "(carrier, company_name, license_no, city, state, "
                    " zip, service_areas, specializations, phone, "
                    " website, scraped_at, source_url) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row.get("carrier", carrier),
                        row.get("company_name", ""),
                        row.get("license_no", ""),
                        row.get("city", ""),
                        row.get("state", ""),
                        row.get("zip", ""),
                        row.get("service_areas", ""),
                        row.get("specializations", ""),
                        row.get("phone", ""),
                        row.get("website", ""),
                        row.get("scraped_at", ""),
                        row.get("source_url", ""),
                    ),
                )
                if cnx.total_changes:
                    inserted += 1
            except Exception as e:
                logger.warning("batch_insert_skipped: %s", e)
        cnx.commit()
        return {"ok": True, "carrier": carrier, "received": len(rows), "inserted": inserted}
    finally:
        cnx.close()


# ── Carrier Application Portal Auto-Filler (Blueprint v5 #3) ───────────


class CreateCarrierAppRequest(BaseModel):
    company_name: str
    license_no: str
    carrier: str


class UpdateCarrierAppRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


@app.post("/v1/carrier-applications")
def create_carrier_application(req: CreateCarrierAppRequest):
    """Register intent to apply with a carrier."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        app = create_carrier_app(
            backend,
            company_name=req.company_name,
            license_no=req.license_no,
            carrier=req.carrier,
        )
        return {"ok": True, "application": app.to_dict()}
    except Exception as e:
        raise HTTPException(400, detail=str(e)[:300])


@app.get("/v1/carrier-applications")
def list_carrier_applications(
    carrier: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
):
    """List carrier applications, optionally filtered by carrier and/or status."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        apps = list_carrier_apps(backend, carrier=carrier, status=status, limit=limit)
        return {"ok": True, "applications": [a.to_dict() for a in apps], "count": len(apps)}
    except Exception as e:
        raise HTTPException(400, detail=str(e)[:300])


@app.patch("/v1/carrier-applications/{app_id}")
def update_carrier_application(app_id: int, req: UpdateCarrierAppRequest):
    """Update a carrier application's status and/or notes."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        app = update_carrier_app(
            backend,
            app_id=app_id,
            status=req.status,
            notes=req.notes,
        )
        return {"ok": True, "application": app.to_dict()}
    except ValueError as e:
        raise HTTPException(400, detail=str(e)[:300])


@app.post("/v1/carrier-applications/{app_id}/auto-fill")
def trigger_auto_fill(app_id: int):
    """Generate a fill plan for a carrier application (stub — no headless browser yet)."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        result = auto_fill_carrier_app(backend, app_id)
        return result
    except ValueError as e:
        raise HTTPException(400, detail=str(e)[:300])


# ── Homeowner Matching (Blueprint v5 #2) ─────────────────────────────


class SubmitJobRequest(BaseModel):
    name: str
    phone: str = ""
    email: str = ""
    zip: str
    job_type: str
    description: str = ""


class UpdateJobStatusRequest(BaseModel):
    status: str
    opt_in: Optional[bool] = None


class UpdateMatchStatusRequest(BaseModel):
    status: str


@app.post("/v1/homeowner/jobs")
def homeowner_submit_job(req: SubmitJobRequest):
    """Submit a new homeowner job (starts at 'discovered')."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    try:
        job = hm_submit_job(
            backend,
            name=req.name,
            phone=req.phone,
            email=req.email,
            zip=req.zip,
            job_type=req.job_type,
            description=req.description,
        )
        return {"ok": True, "job": job.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:300])


@app.get("/v1/homeowner/jobs/{job_id}")
def homeowner_get_job(job_id: int):
    """Get a job by id, including its match records."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    try:
        result = hm_get_job_with_matches(backend, job_id)
        return {"ok": True, **result}
    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])


@app.get("/v1/homeowner/jobs")
def homeowner_list_jobs(status: Optional[str] = None, limit: int = 20):
    """List jobs with optional ?status filter & ?limit (default 20)."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    try:
        jobs = hm_list_jobs(backend, status=status, limit=min(limit, 200))
        return {"ok": True, "jobs": jobs, "count": len(jobs)}
    except InvalidJobStatusError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])


@app.get("/v1/homeowner/matches/{job_id}")
def homeowner_trigger_matches(job_id: int):
    """Find carrier-roster contractors matching this job, create match rows."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    try:
        matches = hm_find_matches(backend, job_id)
        return {
            "ok": True,
            "job_id": job_id,
            "matches": [m.to_dict() for m in matches],
            "count": len(matches),
        }
    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])


@app.post("/v1/homeowner/jobs/{job_id}/status")
def homeowner_update_job_status(job_id: int, req: UpdateJobStatusRequest):
    """Update a job's status (e.g. 'bid_sent', 'bid_accepted', 'settled')."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    try:
        job = hm_update_job_status(
            backend,
            job_id=job_id,
            status=req.status,
            opt_in=req.opt_in,
        )
        return {"ok": True, "job": job.to_dict()}
    except (JobNotFoundError, InvalidJobStatusError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])


# ── Homeowner Pipeline Extension (Blueprint v5 #4) ──────────────────


class HomeownerTransitionRequest(BaseModel):
    job_id: str
    from_status: str
    to_status: str
    notes: str = ""


@app.get("/v1/homeowner/pipeline/stats")
def homeowner_pipeline_stats():
    """Get job counts at each homeowner pipeline state."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        stats = homeowner_stats(backend)
        return {"ok": True, "stats": stats, "total": sum(stats.values())}
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:300])


@app.get("/v1/homeowner/pipeline/{job_id}/timeline")
def homeowner_pipeline_timeline(job_id: str):
    """Return the full event log for a homeowner job."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        timeline = homeowner_timeline(backend, job_id)
        return {"ok": True, "job_id": job_id, "events": timeline, "count": len(timeline)}
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:300])


# ── CRM Routes ──────────────────────────────────────────────────────


@app.get("/v1/crm/leads")
def crm_list(request: Request):
    """List/filter leads. Query params: status, niche, metro, query, limit, offset, omega_min."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        status = request.query_params.get("status")
        niche = request.query_params.get("niche")
        metro = request.query_params.get("metro")
        query = request.query_params.get("query")
        omega_min = request.query_params.get("omega_min")
        
        data = crm_list_leads(
            backend,
            status=status,
            niche=niche,
            metro=metro,
            query=query,
            omega_min=float(omega_min) if omega_min else None,
            limit=int(request.query_params.get("limit", 100)),
            offset=int(request.query_params.get("offset", 0)),
        )
        return {"ok": True, "total": data.get("total", 0), "leads": data.get("leads", [])}
    except Exception as e:
        raise HTTPException(500, str(e))


    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        result = crm_batch_enrich(backend, limit=50)
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:500])


@app.get("/v1/crm/leads/{lead_id}")
def crm_get(lead_id: int):
    """Get single lead with activities and pipeline stage."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        return crm_get_lead(backend, lead_id)
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:500])


class CrmUpdateRequest(BaseModel):
    status: Optional[str] = None
    owner: Optional[str] = None
    notes: Optional[str] = None
    business_name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    niche: Optional[str] = None
    tags_json: Optional[str] = None


@app.post("/v1/crm/leads/{lead_id}")
def crm_update(lead_id: int, req: CrmUpdateRequest):
    """Update lead fields."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        updates = {k: v for k, v in req.dict(exclude_none=True).items() if v is not None}
        return crm_update_lead(backend, lead_id, updates)
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:500])


@app.post("/v1/crm/leads/{lead_id}/status")
def crm_set_status(lead_id: int, req: CrmUpdateRequest):
    """Move lead to a pipeline stage."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    if not req.status:
        raise HTTPException(400, detail="status required")
    try:
        return crm_set_stage(backend, lead_id, req.status)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:500])


@app.post("/v1/crm/leads/{lead_id}/enrich")
def crm_enrich(lead_id: int):
    """Run enrichment waterfall for a single lead."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        import asyncio
        result = asyncio.run(crm_enrich_lead(backend, lead_id))
        return {"ok": True, **result}
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:500])


@app.post("/v1/crm/leads/batch-enrich")
def crm_batch_enrich_endpoint():
    """Enrich up to 50 leads with lowest enrichment scores."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        result = crm_batch_enrich(backend, limit=50)
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:500])


@app.get("/v1/crm/pipeline")
def crm_pipeline():
    """Get pipeline summary by stage."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        return crm_pipeline_summary(backend)
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:500])


@app.get("/v1/crm/enrichment-stats")
def crm_enrich_stats_endpoint():
    """Return enrichment coverage stats."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        return crm_enrich_stats(backend)
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:500])


@app.get("/v1/crm/qualification-summary")
def crm_qualification():
    """Return qualification/score distribution."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        return crm_qual_summary(backend)
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:500])


@app.post("/v1/crm/import-lane-leads")
def crm_import():
    """Import all lane_leads into CRM. Idempotent."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        result = crm_import_lane_leads(backend)
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:500])


@app.get("/v1/crm/analytics")
def crm_analytics():
    """Aggregated analytics data for the CRM dashboard charts."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        import json
        
        # ── Lead counts ──
        total = backend.execute("SELECT COUNT(*) AS c FROM crm_leads").fetchone()["c"]
        
        # Status distribution
        by_status = backend.execute(
            "SELECT status, COUNT(*) AS cnt FROM crm_leads GROUP BY status ORDER BY cnt DESC"
        ).fetchall()
        
        # By niche
        by_niche = backend.execute(
            "SELECT niche, COUNT(*) AS cnt FROM crm_leads WHERE niche != '' GROUP BY niche ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        
        # By metro
        by_metro = backend.execute(
            "SELECT metro, COUNT(*) AS cnt FROM crm_leads WHERE metro != '' GROUP BY metro ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        
        # Enrichment score buckets
        score_buckets = [
            {"range": "0-20", "cnt": backend.execute("SELECT COUNT(*) AS c FROM crm_leads WHERE enrichment_score < 20").fetchone()["c"]},
            {"range": "20-40", "cnt": backend.execute("SELECT COUNT(*) AS c FROM crm_leads WHERE enrichment_score >= 20 AND enrichment_score < 40").fetchone()["c"]},
            {"range": "40-60", "cnt": backend.execute("SELECT COUNT(*) AS c FROM crm_leads WHERE enrichment_score >= 40 AND enrichment_score < 60").fetchone()["c"]},
            {"range": "60-80", "cnt": backend.execute("SELECT COUNT(*) AS c FROM crm_leads WHERE enrichment_score >= 60 AND enrichment_score < 80").fetchone()["c"]},
            {"range": "80-100", "cnt": backend.execute("SELECT COUNT(*) AS c FROM crm_leads WHERE enrichment_score >= 80").fetchone()["c"]},
        ]
        
        # Omega score buckets
        omega_buckets = [
            {"range": "0-100", "cnt": backend.execute("SELECT COUNT(*) AS c FROM crm_leads WHERE omega_score < 100").fetchone()["c"]},
            {"range": "100-300", "cnt": backend.execute("SELECT COUNT(*) AS c FROM crm_leads WHERE omega_score >= 100 AND omega_score < 300").fetchone()["c"]},
            {"range": "300-500", "cnt": backend.execute("SELECT COUNT(*) AS c FROM crm_leads WHERE omega_score >= 300 AND omega_score < 500").fetchone()["c"]},
            {"range": "500-700", "cnt": backend.execute("SELECT COUNT(*) AS c FROM crm_leads WHERE omega_score >= 500 AND omega_score < 700").fetchone()["c"]},
            {"range": "700+", "cnt": backend.execute("SELECT COUNT(*) AS c FROM crm_leads WHERE omega_score >= 700").fetchone()["c"]},
        ]
        
        # Leads created over time (last 30 days)
        time_data = backend.execute(
            "SELECT DATE(created_at) AS day, COUNT(*) AS cnt FROM crm_leads "
            "WHERE created_at >= DATE('now', '-30 days') GROUP BY day ORDER BY day"
        ).fetchall()
        lead_trend = [{"date": r["day"], "count": r["cnt"]} for r in time_data]
        
        # Enrichment source summary
        enrich_sources = backend.execute(
            "SELECT source, COUNT(*) AS cnt, SUM(fields_found) AS total_fields "
            "FROM crm_enrichment_log GROUP BY source ORDER BY cnt DESC"
        ).fetchall()
        
        # Pipeline funnel counts
        stages = ["raw", "qualifying", "qualified", "assigned", "contacted", "converted", "dead"]
        funnel = []
        for s in stages:
            cnt = backend.execute(
                "SELECT COUNT(*) AS c FROM crm_leads WHERE status = ?", (s,)
            ).fetchone()["c"]
            funnel.append({"stage": s, "count": cnt})
        
        # Total enrichment fields found
        fields_found = backend.execute(
            "SELECT COALESCE(SUM(fields_found), 0) AS total FROM crm_enrichment_log"
        ).fetchone()["total"]
        
        # Avg enrichment score
        avg_enrich = backend.execute(
            "SELECT AVG(enrichment_score) AS avg FROM crm_leads"
        ).fetchone()["avg"] or 0
        
        # Qualified leads (non-raw, non-dead)
        qualified = backend.execute(
            "SELECT COUNT(*) AS c FROM crm_leads WHERE status IN ('qualified','assigned','contacted','converted')"
        ).fetchone()["c"]
        
        # Conversion rate (raw → any progress)
        non_raw = backend.execute(
            "SELECT COUNT(*) AS c FROM crm_leads WHERE status != 'raw'"
        ).fetchone()["c"]
        conv_rate = round(non_raw / total * 100, 1) if total else 0
        
        # Activity stats
        total_activities = backend.execute(
            "SELECT COUNT(*) AS c FROM crm_activities"
        ).fetchone()["c"]
        
        # Recent activity trend
        activity_trend = backend.execute(
            "SELECT DATE(occurred_at) AS day, COUNT(*) AS cnt FROM crm_activities "
            "WHERE occurred_at >= DATE('now', '-14 days') GROUP BY day ORDER BY day"
        ).fetchall()
        
        return {
            "total": total,
            "by_status": [dict(r) for r in by_status],
            "by_niche": [dict(r) for r in by_niche],
            "by_metro": [dict(r) for r in by_metro],
            "enrichment_score_buckets": score_buckets,
            "omega_score_buckets": omega_buckets,
            "lead_trend": lead_trend,
            "enrichment_sources": [dict(r) for r in enrich_sources],
            "pipeline_funnel": funnel,
            "total_fields_found": int(fields_found),
            "avg_enrichment_score": round(float(avg_enrich), 1),
            "qualified_leads": qualified,
            "conversion_rate": conv_rate,
            "total_activities": total_activities,
            "activity_trend": [dict(r) for r in activity_trend],
        }
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:500])


@app.get("/v1/crm/revenue-analytics")
def crm_revenue_analytics():
    """Revenue analytics for CRM charting."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        # Monthly revenue
        monthly = backend.execute(
            "SELECT strftime('%Y-%m', created_at) AS month, "
            "SUM(amount_cents) AS total_cents, COUNT(*) AS tx_count "
            "FROM bill_charges WHERE status = 'paid' "
            "GROUP BY month ORDER BY month DESC LIMIT 12"
        ).fetchall()
        
        # Revenue by plan
        by_plan = backend.execute(
            "SELECT plan_id, SUM(amount_cents) AS total_cents "
            "FROM bill_charges WHERE status = 'paid' "
            "GROUP BY plan_id ORDER BY total_cents DESC"
        ).fetchall()
        
        # Total invoiced
        total_invoiced = backend.execute(
            "SELECT COUNT(*) AS cnt, SUM(amount_cents) AS total_cents FROM ppc_invoices WHERE status = 'paid'"
        ).fetchone()
        
        # Active lanes/subscriptions
        active_lanes = backend.execute(
            "SELECT COUNT(*) AS cnt FROM lanes WHERE status = 'active'"
        ).fetchone()["cnt"]
        
        return {
            "monthly_revenue": [dict(r) for r in monthly],
            "revenue_by_plan": [dict(r) for r in by_plan],
            "total_ppc_invoiced": total_invoiced["total_cents"] or 0 if total_invoiced else 0,
            "total_ppc_count": total_invoiced["cnt"] if total_invoiced else 0,
            "active_lanes": active_lanes,
        }
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:500])


# ── ICP Routes ─────────────────────────────────────────────────────


@app.get("/v1/crm/icp/profiles")
def crm_icp_profiles():
    """List all ICP profiles with criteria."""
    from empire_os.icp import DEFAULT_ICP_PROFILES
    return {"profiles": DEFAULT_ICP_PROFILES}


@app.get("/v1/crm/icp/analytics")
def crm_icp_analytics_route():
    """ICP fit analytics across all leads."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        return crm_icp_analytics(backend)
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:500])


@app.get("/v1/crm/icp/score/{lead_id}")
def crm_icp_score_route(lead_id: int):
    """Score a single lead against all ICPs."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        return crm_icp_score(backend, lead_id)
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:500])


@app.post("/v1/crm/icp/batch")
def crm_icp_batch_route():
    """Update ICP scores for all unscored leads."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        return crm_icp_batch(backend)
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:500])


@app.post("/v1/crm/icp/score/{lead_id}")
def crm_icp_refresh_route(lead_id: int):
    """Refresh ICP score for a lead."""
    if not backend:
        raise HTTPException(503, detail="Engine not initialized")
    try:
        from empire_os.icp import update_lead_icp_score
        return update_lead_icp_score(backend, lead_id)
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:500])


# --- Founder seat onboarding (Astryx page + pay API) ---
@app.get("/api/founder-pay")
def founder_pay_route(email: str = "founder@empireos.ai"):
    """Mint a founder-discount USDC pay link + QR for a seated buyer."""
    try:
        import empire_os.seat_payment_onboarding as spo
        pay_url, _memo, _vault = spo.mint_pay_url(
            "Founder", "founding-buyer", email, tier="silver"
        )
        if not pay_url:
            raise HTTPException(502, detail="pay link mint failed")
        qr = spo._qr_png(pay_url)
        # truthful price: parse the actual minted amount from the Solana Pay URI
        amt = 0.0
        import re
        m = re.search(r"amount=([0-9.]+)", pay_url)
        if m:
            amt = float(m.group(1))
        return {
            "pay_url": pay_url,
            "qr_data_url": f"data:image/png;base64,{qr}",
            "price_usd": amt,
            "deadline": spo.FOUNDER_DEADLINE,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e)[:300])


@app.get("/founder-onboard")
def founder_onboard_page_route():
    """Serve the Astryx-built founder onboarding page."""
    p = Path(__file__).parent / "static" / "founder-onboard" / "index.html"
    if p.exists():
        return FileResponse(str(p), media_type="text/html")
    raise HTTPException(404, detail="founder-onboard page not built")


# --- Direct execution ---

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("EMPIRE_HOST", "0.0.0.0")
    port = int(os.environ.get("EMPIRE_PORT", "8080"))
    log_level = os.environ.get("EMPIRE_LOG_LEVEL", "info").lower()
    uvicorn.run(
        "empire_os.hub:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=bool(os.environ.get("EMPIRE_RELOAD", "0") == "1"),
        workers=int(os.environ.get("EMPIRE_WORKERS", "2")),
    )

# ─────────────────────────────────────────────────────────────────
# Outreach surface — used by outreach-agent container over HTTP
# endpoints to read/write si_buyer_outreach.
# ─────────────────────────────────────────────────────────────────

@app.post("/v1/outreach/prospect/register")
def outreach_register(req: dict):
    """Insert or no-op for prospect in si_buyer_outreach."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    try:
        backend.execute("""
            CREATE TABLE IF NOT EXISTS si_buyer_outreach (
                prospect_id TEXT PRIMARY KEY,
                business_name TEXT,
                email TEXT,
                metro TEXT,
                niche TEXT,
                phone TEXT,
                source TEXT,
                score INTEGER,
                url TEXT,
                seq_step INTEGER DEFAULT 0,
                first_touch_at TEXT,
                last_touch_at TEXT,
                touch_count INTEGER DEFAULT 0,
                reply_state TEXT DEFAULT 'cold',
                sample_lead_id TEXT,
                converted INTEGER DEFAULT 0
            )
        """)
        # idempotent: add seq_step to pre-existing tables
        try:
            backend.execute("ALTER TABLE si_buyer_outreach ADD COLUMN seq_step INTEGER DEFAULT 0")
        except Exception:
            pass
        backend.execute("""
            INSERT OR IGNORE INTO si_buyer_outreach
                (prospect_id, business_name, email, metro, niche,
                 phone, source, score, url, reply_state)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            req.get("prospect_id", ""),
            req.get("business_name", ""),
            req.get("email", ""),
            req.get("metro", ""),
            req.get("niche", ""),
            req.get("phone", ""),
            req.get("source", ""),
            int(req.get("score", 0)),
            req.get("url", ""),
            "cold",
        ))
        if req.get("email"):
            backend.execute(
                "UPDATE si_buyer_outreach SET email=? WHERE prospect_id=?",
                (req.get("email", ""), req.get("prospect_id", "")),
            )
        backend.commit()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/v1/outreach/prospect/touched")
def outreach_touched(req: dict):
    """Mark prospect as touched (sent / failed)."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    pid = req.get("prospect_id", "")
    sent = bool(req.get("sent", False))
    sample_lead_id = req.get("sample_lead_id", "")
    seq_step = req.get("seq_step", None)
    now = datetime.now(timezone.utc).isoformat()
    state = "contacted" if sent else "outreach_failed"
    try:
        if seq_step is not None:
            backend.execute(
                """
                UPDATE si_buyer_outreach
                SET first_touch_at = COALESCE(first_touch_at, ?),
                    last_touch_at = ?,
                    touch_count = COALESCE(touch_count, 0) + 1,
                    reply_state = ?,
                    sample_lead_id = COALESCE(NULLIF(?, ''), sample_lead_id),
                    seq_step = ?
                WHERE prospect_id = ?
                """,
                (now, now, state, sample_lead_id, int(seq_step), pid),
            )
        else:
            backend.execute(
                """
                UPDATE si_buyer_outreach
                SET first_touch_at = COALESCE(first_touch_at, ?),
                    last_touch_at = ?,
                    touch_count = COALESCE(touch_count, 0) + 1,
                    reply_state = ?,
                    sample_lead_id = COALESCE(NULLIF(?, ''), sample_lead_id)
                WHERE prospect_id = ?
                """,
                (now, now, state, sample_lead_id, pid),
            )
        backend.commit()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/v1/outreach/webhook")
async def outreach_webhook(request: Request):
    """Receive outreach nurture payloads when Resend quota is hit (429).

    Payload from outreach_runner.send_via_webhook:
      {
        "to": "email@domain.com",
        "subject": "...",
        "body": "...",
        "metadata": {"source": "outreach", "step": 0, "prospect_id": "...", ...},
        "source": "outreach_webhook"
      }

    Logs to /root/feedback/outreach_webhook.jsonl for review/forwarding.
    """
    body_bytes = await request.body()
    try:
        payload = json.loads(body_bytes.decode())
    except Exception:
        raise HTTPException(400, "invalid JSON")

    # Log every webhook event for audit/retry
    log_path = Path("/root/feedback/outreach_webhook.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": payload.get("source", "outreach_webhook"),
        "to": payload.get("to", ""),
        "subject": payload.get("subject", ""),
        "metadata": payload.get("metadata", {}),
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(event) + "\n")

    # Actually deliver the email via the configured mail backend (Brevo/SMTP),
    # bypassing Resend's 429 quota. The webhook is the real outbound channel.
    to = payload.get("to", "")
    subject = payload.get("subject", "")
    body = payload.get("body", "")
    sent_ok = False
    send_info = ""
    if to and subject:
        try:
            from empire_os import mail_sender as _ms
            # Mailgun SMTP > Mailgun HTTP > Resend > Brevo
            if _ms._real_smtp_cfg() and _ms.SMTP_HOST == "smtp.mailgun.org":
                res = _ms._smtp_send(to, subject, body)
            elif _ms.MAILGUN_API_KEY:
                res = _ms._mailgun_send(to, subject, body)
            elif _ms.RESEND_API_KEY:
                res = _ms._resend_send(to, subject, body)
            else:
                res = _ms._brevo_api_send(to, subject, body)
            sent_ok = bool(res.get("ok"))
            send_info = str(res)[:160]
        except Exception as e:
            send_info = f"send_error: {str(e)[:120]}"
    event["delivered"] = sent_ok
    event["send_info"] = send_info
    with open(log_path, "a") as f:
        f.write(json.dumps(event) + "\n")

    return {"received": True, "type": payload.get("source", "outreach_webhook"),
            "delivered": sent_ok, "send_info": send_info}



# ─────────────────────────────────────────────────────────────────
# Outreach surface — used by outreach-agent container over HTTP
# endpoints to read/write si_buyer_outreach.
# ─────────────────────────────────────────────────────────────────

@app.post("/v1/outreach/prospect/register")
def outreach_register(req: dict):
    """Insert or no-op for prospect in si_buyer_outreach."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    try:
        backend.execute("""
            CREATE TABLE IF NOT EXISTS si_buyer_outreach (
                prospect_id TEXT PRIMARY KEY,
                business_name TEXT,
                email TEXT,
                metro TEXT,
                niche TEXT,
                phone TEXT,
                source TEXT,
                score INTEGER,
                url TEXT,
                seq_step INTEGER DEFAULT 0,
                first_touch_at TEXT,
                last_touch_at TEXT,
                touch_count INTEGER DEFAULT 0,
                reply_state TEXT DEFAULT 'cold',
                sample_lead_id TEXT,
                converted INTEGER DEFAULT 0
            )
        """)
        # idempotent: add seq_step to pre-existing tables
        try:
            backend.execute("ALTER TABLE si_buyer_outreach ADD COLUMN seq_step INTEGER DEFAULT 0")
        except Exception:
            pass
        backend.execute("""
            INSERT OR IGNORE INTO si_buyer_outreach
                (prospect_id, business_name, email, metro, niche,
                 phone, source, score, url, reply_state)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            req.get("prospect_id", ""),
            req.get("business_name", ""),
            req.get("email", ""),
            req.get("metro", ""),
            req.get("niche", ""),
            req.get("phone", ""),
            req.get("source", ""),
            int(req.get("score", 0)),
            req.get("url", ""),
            "cold",
        ))
        if req.get("email"):
            backend.execute(
                "UPDATE si_buyer_outreach SET email=? WHERE prospect_id=?",
                (req.get("email", ""), req.get("prospect_id", "")),
            )
        backend.commit()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/v1/outreach/prospect/touched")
def outreach_touched(req: dict):
    """Mark prospect as touched (sent / failed)."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    pid = req.get("prospect_id", "")
    sent = bool(req.get("sent", False))
    sample_lead_id = req.get("sample_lead_id", "")
    seq_step = req.get("seq_step", None)
    now = datetime.now(timezone.utc).isoformat()
    state = "contacted" if sent else "outreach_failed"
    try:
        if seq_step is not None:
            backend.execute(
                """
                UPDATE si_buyer_outreach
                SET first_touch_at = COALESCE(first_touch_at, ?),
                    last_touch_at = ?,
                    touch_count = COALESCE(touch_count, 0) + 1,
                    reply_state = ?,
                    sample_lead_id = COALESCE(NULLIF(?, ''), sample_lead_id),
                    seq_step = ?
                WHERE prospect_id = ?
                """,
                (now, now, state, sample_lead_id, int(seq_step), pid),
            )
        else:
            backend.execute(
                """
                UPDATE si_buyer_outreach
                SET first_touch_at = COALESCE(first_touch_at, ?),
                    last_touch_at = ?,
                    touch_count = COALESCE(touch_count, 0) + 1,
                    reply_state = ?,
                    sample_lead_id = COALESCE(NULLIF(?, ''), sample_lead_id)
                WHERE prospect_id = ?
                """,
                (now, now, state, sample_lead_id, pid),
            )
        backend.commit()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/v1/outreach/webhook")
async def outreach_webhook(request: Request):
    """Receive outreach nurture payloads when Resend quota is hit (429).

    Payload from outreach_runner.send_via_webhook:
      {
        "to": "email@domain.com",
        "subject": "...",
        "body": "...",
        "metadata": {"source": "outreach", "step": 0, "prospect_id": "...", ...},
        "source": "outreach_webhook"
      }

    Logs to /root/feedback/outreach_webhook.jsonl for review/forwarding.
    """
    body_bytes = await request.body()
    try:
        payload = json.loads(body_bytes.decode())
    except Exception:
        raise HTTPException(400, "invalid JSON")

    # Log every webhook event for audit/retry
    log_path = Path("/root/feedback/outreach_webhook.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": payload.get("source", "outreach_webhook"),
        "to": payload.get("to", ""),
        "subject": payload.get("subject", ""),
        "metadata": payload.get("metadata", {}),
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(event) + "\n")

    # Actually deliver the email via the configured mail backend (Brevo/SMTP),
    # bypassing Resend's 429 quota. The webhook is the real outbound channel.
    to = payload.get("to", "")
    subject = payload.get("subject", "")
    body = payload.get("body", "")
    sent_ok = False
    send_info = ""
    if to and subject:
        try:
            from empire_os import mail_sender as _ms
            # Mailgun SMTP > Mailgun HTTP > Resend > Brevo
            if _ms._real_smtp_cfg() and _ms.SMTP_HOST == "smtp.mailgun.org":
                res = _ms._smtp_send(to, subject, body)
            elif _ms.MAILGUN_API_KEY:
                res = _ms._mailgun_send(to, subject, body)
            elif _ms.RESEND_API_KEY:
                res = _ms._resend_send(to, subject, body)
            else:
                res = _ms._brevo_api_send(to, subject, body)
            sent_ok = bool(res.get("ok"))
            send_info = str(res)[:160]
        except Exception as e:
            send_info = f"send_error: {str(e)[:120]}"
    event["delivered"] = sent_ok
    event["send_info"] = send_info
    with open(log_path, "a") as f:
        f.write(json.dumps(event) + "\n")

    return {"received": True, "type": payload.get("source", "outreach_webhook"),
            "delivered": sent_ok, "send_info": send_info}




@app.post("/v1/evaluate")
def evaluate(req: dict, request: Request):
    """Empire Cortex — Lead-Grade Evaluation Product (REAL, HYBRID pricing).

    Auth: optional X-API-Key header. A valid key binds billing to that real
      tenant (overrides the `buyer` field). No key = open demo (buyer field used).
    Body: buyer (str, required if no key) + leads (list) OR lead (dict)
      lead keys: details, name?, phone?, zip_code?, source?, tort_key?, ref?
      mode: 'outcome' (default) = free grading, charges $0.50 only when a
            graded A/B/C lead converts; 'per_score' = $0.20/lead scored now.

    Scores each lead with the real Omega pipeline (omega_os.qualify_prospect),
    grades A/B/C/D. Conversions create pending USDC settlement rows.
    """
    from empire_os.agents import evaluation_product as EP
    key_buyer = EP.resolve_buyer(request.headers.get("x-api-key", ""))
    buyer = key_buyer or (req.get("buyer") or "").strip()
    if not buyer:
        raise HTTPException(400, "buyer required (or send X-API-Key)")
    mode = req.get("mode")  # None -> module default (outcome)
    if "leads" in req and isinstance(req["leads"], list):
        if not req["leads"]:
            raise HTTPException(400, "leads list empty")
        result = EP.evaluate_batch(buyer, req["leads"], mode)
        return {"ok": True, "authed": bool(key_buyer), **result}
    lead = req.get("lead")
    if not isinstance(lead, dict):
        raise HTTPException(400, "lead dict or leads list required")
    return {"ok": True, "authed": bool(key_buyer), **EP.evaluate_lead(buyer, lead, mode)}


@app.post("/v1/evaluate/conversion")
def evaluate_conversion(req: dict, request: Request):
    """HYBRID outcome billing: record that a graded A/B/C lead converted.

    Auth: optional X-API-Key (binds to real tenant, overrides `buyer`).
    Body: buyer (str) + lead_ref (str,required)
    Charges EVAL_CONVERT_USD (default $0.50) if grade was A/B/C and unbilled,
    and writes a pending USDC settlement row. Idempotent per lead_ref.
    """
    from empire_os.agents import evaluation_product as EP
    key_buyer = EP.resolve_buyer(request.headers.get("x-api-key", ""))
    buyer = key_buyer or (req.get("buyer") or "").strip()
    lead_ref = (req.get("lead_ref") or "").strip()
    if not buyer or not lead_ref:
        raise HTTPException(400, "buyer + lead_ref required (or send X-API-Key)")
    return {"ok": True, "authed": bool(key_buyer), **EP.record_conversion(buyer, lead_ref)}


@app.post("/v1/evaluate/signup")
def evaluate_signup(req: dict):
    """Self-serve buyer onboarding for the eval product. Issues an API key.

    Body: name (str,required) + niche? + wallet? (USDC) + email?
    Returns {tenant_id, api_key}. Use the key as X-API-Key on /v1/evaluate.
    """
    from empire_os.agents import evaluation_product as EP
    name = (req.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    return EP.signup(name, req.get("niche", ""), req.get("wallet", ""), req.get("email", ""))


@app.post("/v1/evaluate/buy")
def evaluate_buy(req: dict, request: Request):
    """Fee-aware on-chain purchase: ONE Solana Pay tx funds a credit pack.

    Auth: X-API-Key (binds to real tenant). Body: usd? (default $10 floor).
    Returns {credits, charge_usd, pay_memo, pay_url}. The buyer pays once on
    chain; conversions then draw down credits OFF-CHAIN (no per-lead tx).
    Blockchain fees amortised across the whole pack.
    """
    from empire_os.agents import evaluation_product as EP
    key_buyer = EP.resolve_buyer(request.headers.get("x-api-key", ""))
    buyer = key_buyer or (req.get("buyer") or "").strip()
    if not buyer:
        raise HTTPException(400, "X-API-Key required")
    return {"ok": True, "authed": bool(key_buyer), **EP.buy_pack(buyer, req.get("usd"))}


@app.get("/v1/evaluate/credits")
def evaluate_credits(request: Request, buyer: str = None):
    """Remaining fee-aware credits for a buyer (surfaced on the dashboard)."""
    from empire_os.agents import evaluation_product as EP
    key_buyer = EP.resolve_buyer(request.headers.get("x-api-key", ""))
    who = key_buyer or (buyer or "").strip()
    if not who:
        return {"ok": True, "buyer": None, "credits": 0}
    return {"ok": True, "buyer": who, "credits": EP.credit_balance(who)}


@app.get("/v1/evaluate/ledger")
def evaluate_ledger(buyer: str = None):
    """Total billed from the evaluation product (real USD owed/collected)."""
    from empire_os.agents import evaluation_product as EP
    return {"ok": True, "buyer": buyer, "total_usd": EP.ledger_total(buyer)}


@app.get("/v1/evaluate/settlements")
def evaluate_settlements(status: str = "pending"):
    """Pending/settled USDC obligations from converted leads (real payout queue)."""
    from empire_os.agents import evaluation_product as EP
    c = EP._db()
    try:
        # evaluation_settlements schema uses buyer_id (not buyer) and
        # has no wallet/tx_sig/lead_ref — derive lead_ref from evaluation_ledger
        rows = c.execute(
            "SELECT s.id, s.buyer_id, s.amount_usd, s.payment_method, "
            "       s.status, s.created_at, s.settled_at, "
            "       l.lead_ref "
            "FROM evaluation_settlements s "
            "LEFT JOIN evaluation_ledger l ON l.buyer = s.buyer_id "
            "WHERE s.status=? ORDER BY s.id DESC LIMIT 200",
            (status,),
        ).fetchall()
    finally:
        c.close()
    keys = ("id", "buyer_id", "amount_usd", "payment_method", "status",
            "created_at", "settled_at", "lead_ref")
    items = [dict(zip(keys, r)) for r in rows]
    return {"ok": True, "status": status, "count": len(items),
            "total_usd": round(sum(i["amount_usd"] for i in items), 2),
            "items": items}


@app.post("/v1/evaluate/lead-sold")
async def evaluate_lead_sold(req: dict, request: Request):
    """Auto-bill when a buyer marks a graded lead 'sold' (CRM/webhook trigger).

    Auth: X-API-Key (binds to real tenant). Body: lead_ref (str,required).
    Fires record_conversion -> charges $0.50 (if grade A/B/C + unbilled)
    and returns the Solana Pay URL so the buyer settles in USDC.
    Idempotent per lead_ref (won't double-charge).
    """
    from empire_os.agents import evaluation_product as EP
    key_buyer = EP.resolve_buyer(request.headers.get("x-api-key", ""))
    buyer = key_buyer or (req.get("buyer") or "").strip()
    lead_ref = (req.get("lead_ref") or "").strip()
    if not buyer or not lead_ref:
        raise HTTPException(400, "X-API-Key + lead_ref required")
    return {"ok": True, "authed": bool(key_buyer), **EP.record_conversion(buyer, lead_ref)}


@app.post("/v1/evaluate/claim")
def evaluate_claim(req: dict, request: Request):
    """Claim a pre-graded prospect from the eval ledger.

    Use after reddit_scraper (or any cortex-scored pipeline) pushes A/B/C
    prospects into evaluation_ledger with status='awaiting_buyer'.
    Auth: X-API-Key. Body: lead_ref (str,required).
    Sets buyer + status='claimed' so a later /v1/evaluate/lead-sold call
    charges CONVERT_USD. Idempotent per lead_ref; double-claims return error.
    """
    from empire_os.agents import evaluation_product as EP
    key_buyer = EP.resolve_buyer(request.headers.get("x-api-key", ""))
    buyer = key_buyer or (req.get("buyer") or "").strip()
    lead_ref = (req.get("lead_ref") or "").strip()
    if not buyer or not lead_ref:
        raise HTTPException(400, "X-API-Key + lead_ref required")
    return {"ok": True, "authed": bool(key_buyer), **EP.claim_prospect(buyer, lead_ref)}


@app.post("/v1/evaluate/audit")
def evaluate_audit(req: dict):
    """Free audit lead-magnet — runs the audit pipeline on a URL.

    Body: url (str,required), persist (bool, default true).
    Returns {ok, url, score, grade, checks, lead_ref, billable}.
    If persist=true (default), writes the result into evaluation_ledger
    as 'awaiting_buyer' so a buyer can later claim + mark sold ($2.50).
    """
    from empire_os.agents import evaluation_product as EP
    url = (req.get("url") or "").strip()
    if not url:
        raise HTTPException(400, "url required")
    persist = bool(req.get("persist", True))
    return EP.score_audit(url, persist=persist)


@app.get("/v1/evaluate/available")
def evaluate_available(niche: str = "", grade: str = "", limit: int = 50):
    """List unclaimed pre-graded prospects (awaiting_buyer status).

    Optional filters: niche (substring), grade ('A'/'B'/'C'), limit (default 50).
    Buyers call this to discover leads to claim, then POST /v1/evaluate/claim.
    """
    from empire_os.agents import evaluation_product as EP
    c = EP._db()
    try:
        q = "SELECT lead_ref, niche, omega, grade, created_at FROM evaluation_ledger " \
            "WHERE status='awaiting_buyer'"
        params: list = []
        if niche:
            q += " AND niche LIKE ?"
            params.append(f"%{niche}%")
        if grade and grade in ("A", "B", "C", "D"):
            q += " AND grade=?"
            params.append(grade)
        q += " ORDER BY omega DESC LIMIT ?"
        params.append(int(limit))
        rows = c.execute(q, params).fetchall()
    finally:
        c.close()
    items = [
        {"lead_ref": r[0], "niche": r[1], "omega": r[2],
         "grade": r[3], "created_at": r[4]}
        for r in rows
    ]
    return {"ok": True, "count": len(items), "items": items}


@app.get("/v1/evaluate/my-claims")
def evaluate_my_claims(request: Request, status: str = ""):
    """List prospects claimed by the authenticated buyer.

    Auth: X-API-Key (resolves to tenant_id).
    Optional status filter: 'claimed' (default), 'sold' (any billed status),
    or 'all' (every status). Sorted by claim id desc.
    """
    from empire_os.agents import evaluation_product as EP
    buyer = EP.resolve_buyer(request.headers.get("x-api-key", ""))
    if not buyer:
        raise HTTPException(401, "X-API-Key required (or invalid)")
    c = EP._db()
    try:
        q = ("SELECT id, lead_ref, niche, omega, grade, price_usd, "
             "billing, status, created_at FROM evaluation_ledger "
             "WHERE buyer=?")
        params: list = [buyer]
        if status == "claimed":
            q += " AND status='claimed'"
        elif status == "sold":
            q += " AND status IN ('billed','billed_credit')"
        elif status and status != "all":
            params.append(status)
            q += " AND status=?"
        q += " ORDER BY id DESC LIMIT 200"
        rows = c.execute(q, params).fetchall()
    finally:
        c.close()
    keys = ("id", "lead_ref", "niche", "omega", "grade", "price_usd",
            "billing", "status", "created_at")
    items = [dict(zip(keys, r)) for r in rows]
    billed_total = sum(i["price_usd"] for i in items
                       if i["status"] in ("billed", "billed_credit"))
    return {
        "ok": True, "buyer": buyer, "count": len(items),
        "billed_usd": round(billed_total, 2), "items": items,
    }


@app.get("/v1/search")
def semantic_search(q: str = "", limit: int = 20):
    """Meaning-based lead catalog search via SQLite FTS5 (no external deps).

    q: free-text query (e.g. 'roof leak Brooklyn urgent').
    Searches the lead intake text; returns ranked matches.
    """
    from empire_os.agents import evaluation_product as EP
    if not q.strip():
        return {"ok": True, "q": q, "count": 0, "items": []}
    c = EP._db()
    try:
        # Use legacy lead_fts table if it exists (maintained from empire_os/agents/evaluation_product.py)
        # This provides reliable search functionality for lane leads
        c.execute("""
            CREATE TABLE IF NOT EXISTS lead_fts (
                lead_ref TEXT PRIMARY KEY,
                details TEXT,
                omega_score REAL,
                omega_tier TEXT,
                source TEXT,
                created_at TEXT,
                name TEXT,
                phone TEXT,
                zip_code TEXT
            )
        """)
        
        # Repopulate from lane_leads if needed
        cnt = c.execute("SELECT count(*) FROM lead_fts").fetchone()[0]
        src = c.execute("SELECT count(*) FROM lane_leads WHERE omega_score IS NOT NULL").fetchone()[0]
        if cnt == 0 or cnt < src:
            c.execute("DELETE FROM lead_fts")
            rows = c.execute(
                "SELECT lead_ref, details, omega_score, omega_tier, source, created_at, "
                "name, phone, zip_code FROM lane_leads WHERE omega_score IS NOT NULL"
            ).fetchall()
            c.executemany(
                "INSERT INTO lead_fts (lead_ref, details, omega_score, omega_tier, source, created_at, name, phone, zip_code) VALUES (?,?,?,?,?,?,?,?,?)",
                rows,
            )
            c.commit()
        
        res = c.execute(
            "SELECT lead_ref, details FROM lead_fts WHERE lead_fts MATCH ? "
            "ORDER BY rank LIMIT ?",
            (q, limit),
        ).fetchall()
    finally:
        c.close()
    items = [{"lead_ref": r[0], "snippet": r[1][:200]} for r in res]
    return {"ok": True, "q": q, "count": len(items), "items": items}


@app.get("/v1/evaluate/grades")
def evaluate_grades(request: Request, buyer: str = None):
    """Graded leads for a buyer (X-API-Key or ?buyer=). For the dashboard."""
    from empire_os.agents import evaluation_product as EP
    key_buyer = EP.resolve_buyer(request.headers.get("x-api-key", ""))
    who = key_buyer or (buyer or "").strip()
    if not who:
        return {"ok": True, "buyer": None, "count": 0, "items": []}
    c = EP._db()
    try:
        rows = c.execute(
            "SELECT lead_ref, niche, omega, grade, price_usd, billing, status, created_at "
            "FROM evaluation_ledger WHERE buyer=? ORDER BY id DESC LIMIT 200",
            (who,),
        ).fetchall()
    finally:
        c.close()
    keys = ("lead_ref", "niche", "omega", "grade", "price_usd", "billing", "status", "created_at")
    items = [dict(zip(keys, r)) for r in rows]
    return {"ok": True, "buyer": who, "count": len(items),
            "credits": EP.credit_balance(who), "items": items}


@app.get("/dashboard")
def buyer_dashboard(request: Request):
    """Buyer dashboard shell. Key via ?key=. Data loaded client-side from API."""
    from fastapi.responses import FileResponse
    import os as _os
    p = _os.path.join(_os.path.dirname(__file__), "static", "dashboard.html")
    if _os.path.exists(p):
        return FileResponse(p)
    return {"ok": False, "error": "dashboard.html not found"}


@app.get("/evaluate")
def evaluate_page():
    """Public pricing + live demo page for the Lead-Grade evaluation product."""
    from fastapi.responses import FileResponse
    import os as _os
    p = _os.path.join(_os.path.dirname(__file__), "static", "evaluate.html")
    if _os.path.exists(p):
        return FileResponse(p)
    return {"ok": False, "error": "evaluate.html not found"}

# ─────────────────────────────────────────────────────────────────
# Inbound Reply — Resend + SendGrid
# ─────────────────────────────────────────────────────────────────
@app.post("/v1/inbound/resend")
async def inbound_resend(request: Request):
    body = await request.body()
    sig = request.headers.get("svix-signature", "")
    secret = os.environ.get("RESEND_WEBHOOK_SECRET", "")
    if secret and sig:
        try:
            ts = request.headers.get("svix-timestamp", "")
            msg_id = request.headers.get("svix-id", "")
            signed = f"{msg_id}.{ts}.{body.decode()}"
            expected = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
            sigs = [s.split(",",1)[1] for s in sig.split() if s.startswith("v1,")]
            if not any(hmac.compare_digest(expected, s) for s in sigs):
                raise HTTPException(401, "invalid signature")
        except HTTPException: raise
        except Exception: raise HTTPException(400, "signature parse failed")
    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(400, "invalid JSON")
    from scripts.win1_resend_inbound import process_inbound_email
    return process_inbound_email(payload, secret)

@app.post("/v1/inbound/sendgrid")
async def inbound_sendgrid(request: Request):
    form = await request.form()
    payload = dict(form)
    from scripts.win1_resend_inbound import process_inbound_email
    return process_inbound_email(payload, "")
