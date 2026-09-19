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
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
import asyncio
import logging
import os
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
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import hmac as _hmac
import hashlib as _hashlib
import hashlib  # used by hub_intake

from empire_os.funnel import (
    SQLiteBackend,
    get_state,
    list_states,
    events_for,
    count_by_state,
)
from empire_os.neural_scout import NeuralScout, calculate_observed_score
from empire_os.traffic_specialist import (
    DiscoveredProspect,
    discover_one,
    mark_matched,
    pipeline_status,
)
from empire_os.marketing import tick as marketing_tick, draft_spec_for_niche
from empire_os.aeo_surface import deploy_spec, list_pages, remove_page
from empire_os.search_intelligence.api import router as search_intelligence_router
from empire_os.coder.api import router as empire_coder_router
from empire_os.revenue_os_api import create_revenue_os_router
from empire_os.enterprise_api import create_enterprise_router
from empire_os.saas_api import create_saas_router
from empire_os.capital_api import create_capital_router
from empire_os.digital_twin_api import create_digital_twin_router
from empire_os.revenue_exchange_api import create_revenue_exchange_router
from empire_os.demand_api import create_demand_router
from empire_os.experiment_api import create_experiment_router
from empire_os.predictive_api import create_predictive_router
from empire_os.advertising_api import create_advertising_router
from empire_os.revenue_crm_api import create_revenue_crm_router
from empire_os.conversation_api import create_conversation_router
from empire_os.a2a_identity_api import create_a2a_identity_router
from empire_os.a2a_commerce_api import create_a2a_commerce_router
from empire_os.astra_api import create_astra_router
from empire_os.consent_api import create_consent_router
from empire_os.first_revenue_api import create_first_revenue_router
from empire_os.outreach_api import create_outreach_router
from empire_os.data_plane_api import create_data_plane_router
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
    if agi_scout.check_health():
        logger.info("agi-scout detected at %s", agi_scout.base_url)
    else:
        logger.info("agi-scout not reachable")
    agi_marketing = AgiMarketingClient()
    if agi_marketing.check_health():
        logger.info("agi-marketing detected at %s", agi_marketing.base_url)
    else:
        logger.info("agi-marketing not reachable")
    # AGI Sales — runs in-process (no separate container needed).
    # Ollama box (10.218.156.211:11434) is down; route through OpenRouter
    # (tencent/hy3:free — same brain model) so loops run instead of dying.
    agi_sales = AgiSalesAgent(
        backend=backend,
        llm=OpenRouterClient(model="tencent/hy3:free", timeout=120))
    logger.info("agi-sales initialized in-process (OpenRouter hy3)")
    # AGI Closer — last-mile closer, also in-process
    global agi_closer
    agi_closer = AgiCloserAgent(
        backend=backend,
        llm=OpenRouterClient(model="tencent/hy3:free", timeout=120))
    logger.info("agi-closer initialized in-process (OpenRouter hy3)")

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

    # Mount AEO surface at /aeo
    aeo_root = Path(AEO_SURFACE_ROOT)
    aeo_root.mkdir(parents=True, exist_ok=True)
    try:
        app.mount("/aeo", StaticFiles(directory=AEO_SURFACE_ROOT, html=True), name="aeo")
        logger.info("AEO surface mounted at /aeo → %s", AEO_SURFACE_ROOT)
    except Exception as e:
        logger.warning("Could not mount AEO surface: %s", e)

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
    if _own_loops and os.environ.get("EMPIRE_OS_TEST_MODE") != "1":
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
    if _own_loops and os.environ.get("EMPIRE_OS_TEST_MODE") != "1":
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
app.include_router(search_intelligence_router)
app.include_router(empire_coder_router)
app.include_router(create_revenue_os_router())
app.include_router(create_enterprise_router())
app.include_router(create_saas_router())
app.include_router(create_capital_router())
app.include_router(create_digital_twin_router())
app.include_router(create_revenue_exchange_router())
app.include_router(create_demand_router())
app.include_router(create_experiment_router())
app.include_router(create_predictive_router())
app.include_router(create_advertising_router())
app.include_router(create_revenue_crm_router())
app.include_router(create_conversation_router())
app.include_router(create_a2a_identity_router())
app.include_router(create_a2a_commerce_router())
app.include_router(create_astra_router())
app.include_router(create_consent_router())
app.include_router(create_first_revenue_router())
app.include_router(create_outreach_router())
app.include_router(create_data_plane_router())


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


# --- Neural Scout / Lead Pipeline ---

@app.post("/v1/pipeline/incoming")
async def incoming_lead(lead: LeadPayload, background_tasks: BackgroundTasks):
    """Retired legacy neural-scout funnel mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_pipeline_incoming_retired_use_canonical_lead_intake",
    )



@app.post("/v1/traffic/discover")
def discover_prospect(prospect: dict):
    """Retired legacy traffic discovery mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_traffic_discover_retired_use_canonical_source_mesh",
    )



@app.post("/v1/traffic/match")
def match_prospect(payload: dict):
    """Retired legacy traffic-match mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_traffic_match_retired_use_canonical_identity_and_allocation",
    )



@app.get("/v1/traffic/status")
def traffic_status():
    """Get pipeline status summary."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return pipeline_status(backend)


# --- Marketing ---

@app.post("/v1/marketing/tick")
def marketing_tick_endpoint():
    """Retired legacy marketing mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_marketing_tick_retired_use_search_intelligence_and_demand_genesis",
    )


@app.get("/v1/marketing/draft/{niche}")
def get_draft(niche: str):
    """Draft an AEO spec for a niche."""
    if not backend:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    draft = draft_spec_for_niche(backend, niche)
    return draft.to_dict()


@app.post("/v1/marketing/draft/{niche}/deploy")
def deploy_niche_page(niche: str, surface_root: Optional[str] = None):
    """Retired direct AEO publish path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_aeo_deploy_retired_use_governed_search_content_flow",
    )


@app.get("/v1/aeo/pages")
def list_aeo_pages(surface_root: Optional[str] = None):
    """List all published AEO pages."""
    return {"pages": list_pages(surface_root=surface_root)}


@app.delete("/v1/aeo/pages/{niche}")
def delete_aeo_page(niche: str, surface_root: Optional[str] = None):
    """Retired direct AEO delete path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_aeo_delete_retired_use_governed_search_content_flow",
    )


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
    lead_id: str = ""
    name: str = ""
    email: str = ""
    phone: str = ""
    state: str = ""
    metro: str = ""
    zip: str = ""
    niche: str = ""
    details: str = ""
    source: str = "aeo_form"
    ip_address: str = ""
    user_agent: str = ""
    intent: str = ""
    consent: str = ""
    url: str = ""
    lead_score: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


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
def damage_scan(req: dict):
    """Retired legacy execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_damage_scan_retired_use_governed_source_mesh",
    )



@app.get("/v1/damage/scan/recent")
def damage_scan_recent(limit: int = 5):
    """Retired legacy internal/read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_damage_scan_history_retired_use_canonical_source_observations",
    )



@app.get("/v1/damage/scan-all")
def damage_scan_all():
    """Retired legacy execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_damage_scan_all_retired_use_governed_source_mesh",
    )



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
    const r=await fetch('/v1/consent/prospects/""" + prospect_id + r"""/opt-in',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        channel:'email',
        source:'damage_opt_in_page',
        evidence:{surface:'damage_report'}
      })
    });
    const j=await r.json();
    if(j.ok){
      res.className='result success'; res.style.display='block';
      res.innerHTML='✓ <strong>Your consent has been recorded.</strong><br>Report delivery is handled separately through our governed outbound process.';
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
    """Retired legacy SQLite consent mutation route."""
    raise HTTPException(
        status_code=410,
        detail="legacy_damage_opt_in_retired_use_canonical_consent_api",
    )


@app.get("/v1/damage/consent/{prospect_id}")
def damage_consent_status(prospect_id: str):
    """Retired legacy SQLite consent read route."""
    raise HTTPException(
        status_code=410,
        detail="legacy_damage_consent_read_retired_use_canonical_consent_api",
    )


@app.post("/v1/satellite/strike")
def satellite_strike(req: dict):
    """Retired storm-alert-to-CRM mutation path.

    Weather/damage events are opportunity signals, not business prospects.
    """
    raise HTTPException(
        status_code=410,
        detail="legacy_satellite_strike_crm_mutation_retired_use_signal_and_canonical_acquisition_flow",
    )


@app.post("/v1/leads/intake")
def lead_intake(req: LeadIntakeRequest):
    """Compatibility URL backed only by canonical Supabase prospects."""
    from empire_os.lead_compat import (
        CanonicalLeadConflict,
        CanonicalLeadIntakeError,
        canonical_lead_intake,
    )
    from empire_os.crawler_runner import ingest_candidate

    payload = (
        req.model_dump()
        if hasattr(req, "model_dump")
        else req.dict()
    )
    try:
        return canonical_lead_intake(payload, ingest_candidate)
    except CanonicalLeadConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except CanonicalLeadIntakeError as exc:
        logging.getLogger(__name__).warning(
            "canonical lead intake failed: %s",
            exc,
        )
        message = str(exc)
        if message == "name, niche and metro required":
            raise HTTPException(400, message) from exc
        raise HTTPException(
            503,
            "canonical prospect ingest temporarily unavailable",
        ) from exc


@app.get("/v1/leads/counts")
def lead_counts():
    """Get lead counts by status and niche."""
    if not backend:
        raise HTTPException(503, "backend not initialized")
    from empire_os.crm import get_lead_counts
    return get_lead_counts(backend)


@app.post("/v1/leads/direct")
def direct_lead_intake(req: dict):
    """Compatibility intake backed only by canonical Supabase prospects."""
    from empire_os.lead_compat import (
        CanonicalLeadConflict,
        CanonicalLeadIntakeError,
        canonical_lead_intake,
    )
    from empire_os.crawler_runner import ingest_candidate

    try:
        return canonical_lead_intake(req, ingest_candidate)
    except CanonicalLeadConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except CanonicalLeadIntakeError as exc:
        logging.getLogger(__name__).warning(
            "canonical direct lead ingest failed: %s",
            exc,
        )
        message = str(exc)
        if message == "name, niche and metro required":
            raise HTTPException(400, message) from exc
        raise HTTPException(
            503,
            "canonical prospect ingest temporarily unavailable",
        ) from exc


class BuyerApplyRequest(BaseModel):
    name: str
    niche: str
    email: str
    tier: str = "silver"
    webhook_url: str = ""
    min_deposit: float = 0.0
    source: str = ""


class BuyerApplyResponse(BaseModel):
    ok: bool
    buyer: str
    niche: str
    tier: str
    seat_price_usd: float | None = None
    funded: bool | None = None
    tenant_id: str | None = None
    subscription_id: str | None = None
    payment: dict | None = None


_BUY_LEADS_TEMPLATE = "/root/empire_os/templates/buy-leads.html"


@app.post("/v1/buyers/apply", response_model=BuyerApplyResponse)
async def buyer_apply(req: BuyerApplyRequest):
    """Retired legacy Solana/USDC buyer auto-onboarding path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_buyer_apply_retired_use_governed_bsc_buyer_onboarding_flow",
    )



@app.get("/buy-leads", response_class=HTMLResponse)
async def buy_leads_page():
    """Branded buyer-acquisition landing page (Empire AI dark/neon theme)."""
    try:
        with open(_BUY_LEADS_TEMPLATE, "r", encoding="utf-8") as fh:
            html = fh.read()
        return HTMLResponse(html)
    except Exception:
        return HTMLResponse("<h1>Empire AI — Buy Leads</h1><p>Signup temporarily unavailable.</p>")



RESEND_WEBHOOK_LOG = Path(
    os.getenv(
        "RESEND_WEBHOOK_LOG",
        "/srv/empire_os/runtime/feedback/resend_webhook.jsonl",
    )
)
RESEND_WEBHOOK_LOG.parent.mkdir(parents=True, exist_ok=True)


@app.post("/v1/resend/webhook")
async def resend_webhook(request: Request):
    """Retired legacy execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_resend_webhook_retired_use_signed_canonical_webhook_service",
    )



@app.get("/v1/resend/webhook/recent")
def resend_webhook_recent(limit: int = 20):
    """Retired legacy internal/read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_resend_webhook_history_retired_use_canonical_outbound_provider_events",
    )



@app.get("/v1/leads/sample")
def sample_lead_for_outreach(niche: str, metro: str):
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_lead_sample_retired_use_canonical_prospect_reader",
    )



@app.get("/v1/leads/{lead_id}")
def get_lead_by_id(lead_id: str):
    """Retired legacy internal/read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_single_lead_read_retired_use_v1_revenue_crm_prospects",
    )



@app.get("/v1/leads")
def list_leads(status: str = "", niche: str = "", metro: str = "", limit: int = 50, offset: int = 0):
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_lead_list_retired_use_v1_revenue_crm_prospects",
    )



@app.patch("/v1/leads/{lead_id}/status")
def update_lead_status(lead_id: str, status: str = "", notes: str = ""):
    """Retired legacy SQLite CRM status mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_lead_status_retired_use_revenue_crm_and_governed_state_flow",
    )



# ─────────────────────────────────────────────────────────────────
# Outreach surface — used by outreach-agent container over HTTP
# Instead of shelling out to incus, the container calls these
# endpoints to read/write si_buyer_outreach.
# ─────────────────────────────────────────────────────────────────


@app.post("/v1/outreach/prospect/register")
def outreach_register(req: dict):
    """Retired legacy SQLite outreach registration path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_outreach_register_retired_use_governed_resend_outbound_flow",
    )


@app.post("/v1/outreach/prospect/touched")
def outreach_touched(req: dict):
    """Retired legacy SQLite outreach lifecycle mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_outreach_touched_retired_use_canonical_outbound_event_flow",
    )


@app.get("/v1/outreach/prospect/{prospect_id}")
def outreach_get(prospect_id: str):
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_outreach_prospect_read_retired_use_canonical_outbound_events",
    )



@app.get("/v1/outreach/prospects/pending")
def outreach_pending(metro: str = None, niche: str = None, limit: int = 20):
    """Retired legacy SQLite outreach queue read."""
    raise HTTPException(
        status_code=410,
        detail="legacy_outreach_pending_retired_use_canonical_outbound_review_flow",
    )



# Legacy Solana/USDC product-catalog runtime removed.
# Governed A2A discovery and canonical product/commercial flows are active.


@app.get("/v1/a2a/catalog")
def a2a_catalog():
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_a2a_catalog_retired_use_a2a_v1_discovery",
    )


@app.get("/v1/products/pricing")
def products_pricing():
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_product_pricing_retired_use_governed_product_catalog",
    )


@app.get("/v1/products/{sku}")
def product_detail(sku: str):
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_product_detail_retired_use_governed_product_catalog",
    )


@app.post("/v1/a2a/negotiate")
def a2a_negotiate(req: dict):
    """Retired legacy AI-to-AI settlement negotiation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_a2a_negotiate_retired_use_governed_a2a_commerce_flow",
    )


@app.post("/v1/products/register")
def product_register(req: dict):
    """Retired legacy SQLite product catalog mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_product_register_retired_use_governed_product_catalog",
    )


# ─────────────────────────────────────────────────────────────────
# Swarm 3.0 — Traffic Hub + Worker Pull + Audit Log endpoints
# All routing decisions flow through /v1/hub/intake. Workers register
# handlers via /v1/swarm/worker-config. Every routing logs to
# /v1/swarm/audit-log. Strict lane isolation.
# ─────────────────────────────────────────────────────────────────

SWARM_REGISTRY_PATH = "/root/feedback/swarm_registry.jsonl"
SWARM_AUDIT_PATH = os.environ.get("SWARM_AUDIT_PATH", os.path.join(os.environ.get("SWARM_AUDIT_DIR", "/srv/empire_os/runtime/feedback"), "swarm_audit.jsonl"))
import json as _json


def _swarm_audit(event_type: str, **fields):
    """Append-only audit trail for every swarm routing decision."""
    Path(os.getenv("SWARM_AUDIT_DIR", "/srv/empire_os/runtime/feedback")).mkdir(parents=True, exist_ok=True)
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
    """Compatibility intake converged onto canonical Supabase prospects.

    This route no longer writes lane_leads or any legacy SQLite queue.
    """
    from empire_os.lead_compat import (
        CanonicalLeadConflict,
        CanonicalLeadIntakeError,
        canonical_lead_intake,
    )
    from empire_os.crawler_runner import ingest_candidate

    text_value = str(req.get("text") or req.get("details") or "").strip()
    name = str(req.get("name") or req.get("business_name") or "").strip()
    niche = str(req.get("niche") or _infer_niche(text_value) or "").strip()
    metro = str(req.get("metro") or _infer_metro(text_value) or "").strip()
    payload_hash = hashlib.sha256(
        (
            text_value
            + str(req.get("email") or "")
            + str(req.get("phone") or "")
        ).encode()
    ).hexdigest()[:16]

    payload = {
        "name": name,
        "niche": niche,
        "metro": metro,
        "source": str(req.get("source") or "hub_intake"),
        "email": str(req.get("email") or ""),
        "phone": str(req.get("phone") or ""),
        "state": str(req.get("state") or ""),
        "details": text_value,
        "url": str(req.get("url") or ""),
        "metadata": {
            "compat_route": "/v1/hub/intake",
            "payload_hash": payload_hash,
        },
    }

    try:
        result = canonical_lead_intake(payload, ingest_candidate)
    except CanonicalLeadConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CanonicalLeadIntakeError as exc:
        message = str(exc)
        if message == "name, niche and metro required":
            raise HTTPException(status_code=400, detail=message) from exc
        raise HTTPException(
            status_code=503,
            detail="canonical_prospect_ingest_unavailable",
        ) from exc

    return {
        **result,
        "labels": {
            "niche": niche,
            "metro": metro,
            "payload_hash": payload_hash,
        },
        "legacy_lane_write": False,
        "canonical_store": "supabase",
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
                           "Empire AI for {metro} {niche}: governed lead intelligence"),
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
        f"this is the Empire AI team reaching out about your "
        f"{brief['niche']} project in {brief['metro']}. We provide "
        f"governed lead-intelligence and commercial service options "
        f"subject to verified terms and capacity. "
        f"Commercial settlement uses governed USDT on BSC after "
        f"verified terms and payment evidence.\n\n"
        f"If useful, we can share the available service options for "
        f"your market before anything is activated.\n\n"
        f"Commercial terms are confirmed before activation.\n\n"
        f"---\nEmpire AI - {subject}\n"
        f"Unsubscribe: https://empire-ai.co.uk/unsub/{brief['niche']}-{brief['metro']}\n"
    )
    audit_id = "ec_" + hex(int(time.time()))[2:]
    return {
        "ok": True,
        "mode": "DRAFT",
        "sent": False,
        "execution_authority": "none",
        "subject": subject,
        "body": body,
        "compliance": compliance,
        "audit_id": audit_id,
    }


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
                              "Empire AI for {metro} {niche}: governed lead intelligence")
    subject = subject_template.format(metro=metro, niche=niche.title())

    # Pre-defined copy per kind. The copywriting-agent can extend later.
    body = (
        f"Hey {name},\n\n"
        f"this is the Empire AI team reaching out about your {niche} project "
        f"in {metro}. We provide governed lead-intelligence and commercial "
        f"service options subject to verified terms, evidence and capacity. "
        f"Commercial settlement uses governed USDT on BSC after verified terms and payment evidence.\n"
        f"\nIf useful, we can share the available governed service options "
        f"and confirm which terms, if any, apply to your requirements.\n"
        f"\nCommercial terms are confirmed before activation. Empire AI\n"
    )

    return {
        "ok": True,
        "mode": "DRAFT",
        "sent": False,
        "execution_authority": "none",
        "subject": subject,
        "body": body,
    }


@app.post("/v1/seo/audit")
def seo_audit(req: dict):
    """Retired file-backed SEO audit ingestion path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_seo_audit_retired_use_search_intelligence_evidence_flow",
    )



@app.get("/v1/seo/recent")
def seo_recent(n: int = 20, kind: str = ""):
    """Retired legacy internal/read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_seo_history_retired_use_search_intelligence_evidence",
    )



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
    return {
        "ok": True,
        "mode": "OBSERVE",
        "persisted": False,
        "execution_authority": "none",
        "record_id": rec_id,
        **record,
    }


@app.post("/v1/finance/replay")
def finance_replay(req: dict):
    """Retired legacy simulation endpoint.

    The former implementation fabricated Solana/USDC deposit evidence and
    mutated invoices, subscriptions, settlements and a pseudo vault balance.
    Canonical production settlement is BSC USDT with independently verified
    chain evidence, so replay-based finance mutation is permanently fail-closed.
    """
    raise HTTPException(
        410,
        "finance replay retired; use governed BSC USDT verification evidence",
    )


@app.post("/v1/swarm/worker-config")
def swarm_worker_config(req: dict):
    """Retired legacy file-backed worker-config mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_swarm_worker_config_retired_use_governed_execution_bus",
    )



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
    """Retired legacy internal/read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_swarm_prompt_retired_use_governed_agent_catalog",
    )



@app.get("/v1/swarm/ledger")
def swarm_ledger():
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_swarm_ledger_retired_use_canonical_observability",
    )



# ═══════════════════════════════════════════════════════════════════
# Blueprint v5 — Carrier DRP Roster Scraper (#1)
# ═══════════════════════════════════════════════════════════════════

_HM_BACKEND = None  # set during lifespan startup

@app.post("/v1/carrier-rosters/scrape")
def carrier_rosters_scrape():
    """Retired public carrier-roster scrape mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_carrier_roster_scrape_retired_use_governed_source_mesh",
    )

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
def homeowner_create_job_retired():
    """Retired legacy state mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_homeowner_job_create_retired_use_canonical_marketplace_flow",
    )


@app.get("/v1/homeowner/jobs")
def homeowner_list_jobs(status: str = None, limit: int = 50):
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_homeowner_jobs_read_retired_use_governed_marketplace_read_model",
    )


@app.get("/v1/homeowner/jobs/{job_id}")
def homeowner_get_job(job_id: int):
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_homeowner_job_read_retired_use_governed_marketplace_read_model",
    )


@app.post("/v1/homeowner/jobs/{job_id}/match")
def homeowner_match_retired(job_id: int):
    """Retired legacy state mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_homeowner_match_retired_use_governed_matching_flow",
    )


@app.patch("/v1/homeowner/jobs/{job_id}/status")
def homeowner_status_retired(job_id: int):
    """Retired legacy state mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_homeowner_status_retired_use_governed_marketplace_flow",
    )


@app.patch("/v1/homeowner/jobs/matches/{match_id}/status")
def homeowner_match_status_retired(match_id: int):
    """Retired legacy state mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_homeowner_match_status_retired_use_governed_marketplace_flow",
    )


# ═══════════════════════════════════════════════════════════════════
# Blueprint v5 — Carrier Application Portal Auto-Filler (#3)
# ═══════════════════════════════════════════════════════════════════

@app.post("/v1/carrier-applications")
def carrier_application_create_retired():
    """Retired legacy state mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_carrier_application_create_retired_use_governed_partner_flow",
    )


@app.get("/v1/carrier-applications")
def carrier_app_list(carrier: str = None, status: str = None, limit: int = 100):
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_carrier_application_read_retired_use_governed_partner_read_model",
    )


@app.get("/v1/carrier-applications/{app_id}")
def carrier_app_get(app_id: int):
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_carrier_application_read_retired_use_governed_partner_read_model",
    )


@app.patch("/v1/carrier-applications/{app_id}")
def carrier_application_update_retired(app_id: int):
    """Retired legacy state mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_carrier_application_update_retired_use_governed_partner_flow",
    )


@app.post("/v1/carrier-applications/{app_id}/auto-fill")
def carrier_application_autofill_retired(app_id: int):
    """Retired legacy state mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_carrier_application_autofill_retired_use_governed_partner_flow",
    )


# ═══════════════════════════════════════════════════════════════════
# Blueprint v5 — Pipeline Extension (homeowner_job → settled) (#4)
# ═══════════════════════════════════════════════════════════════════

@app.post("/v1/homeowner/pipeline/transition")
def homeowner_pipeline_transition_retired():
    """Retired legacy state mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_homeowner_pipeline_transition_retired_use_governed_marketplace_flow",
    )


@app.get("/v1/homeowner/pipeline/timeline/{job_id}")
def homeowner_pipeline_timeline(job_id: str):
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_homeowner_timeline_retired_use_governed_marketplace_read_model",
    )


@app.get("/v1/homeowner/pipeline/stats")
def homeowner_pipeline_stats():
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_homeowner_stats_retired_use_governed_marketplace_read_model",
    )


# ═══════════════════════════════════════════════════════════════════════
# Revenue & Lead Stats
# ═══════════════════════════════════════════════════════════════════════

@app.get("/v1/stats/revenue")
def stats_revenue():
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_revenue_stats_retired_use_v1_revenue_os_board",
    )


@app.get("/v1/stats/leads")
def stats_leads():
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_lead_stats_retired_use_v1_revenue_crm_prospects",
    )



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


# Outbox table bootstrap — legacy mutation endpoints retired
@app.post("/v1/outbox/enqueue")
def outbox_enqueue(req: dict):
    """Retired legacy SQLite outbound queue mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_outbox_enqueue_retired_use_governed_resend_outbound_flow",
    )


@app.post("/v1/buyers/enterprise")
def buyers_enterprise_retired(req: dict):
    """Retired legacy enterprise buyer intake/outbound path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_buyer_enterprise_retired_use_governed_buyer_onboarding_flow",
    )


@app.get("/v1/outbox/pending")
def outbox_pending(n: int = 10):
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_outbox_pending_retired_use_canonical_outbound_events",
    )


@app.post("/v1/outbox/{out_id}/mark")
def outbox_mark(out_id: int, req: dict):
    """Retired legacy SQLite outbound status mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_outbox_mark_retired_use_canonical_outbound_event_flow",
    )


@app.get("/v1/outbox/recent")
def outbox_recent(n: int = 50):
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_outbox_recent_retired_use_canonical_outbound_events",
    )


@app.post("/v1/innovator/ship")
def innovator_ship(req: dict):
    """Retired legacy self-modifying lane/source ship path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_innovator_ship_retired_use_governed_coder_and_product_flow",
    )


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
    """Retired legacy Solana seat signup path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_buyer_signup_seat_retired_use_governed_bsc_buyer_activation_flow",
    )


@app.get("/v1/buyers/seat-tiers")
def seat_tiers_endpoint():
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_buyer_seat_tiers_retired_use_governed_bsc_commercial_terms",
    )



@app.post("/v1/buyers/signup")
def buyer_signup(req: dict):
    """Retired legacy Solana buyer signup path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_buyer_signup_retired_use_governed_bsc_buyer_activation_flow",
    )


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
    """Retired legacy revenue recomputation mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_revenue_snapshot_retired_use_canonical_phase3f_revenue_worker",
    )


@app.post("/v1/revenue/brief")
def revenue_brief_endpoint():
    """Retired legacy revenue worker trigger."""
    raise HTTPException(
        status_code=410,
        detail="legacy_revenue_brief_tick_retired_use_canonical_revenue_read_model",
    )


@app.get("/v1/delegate/scanners")
def delegate_list_scanners():
    """List scanners available on the remote scout-agent container."""
    if not scout_agent:
        raise HTTPException(status_code=503, detail="scout-agent not initialized")
    return {"scanners": scout_agent.list_scanners()}


@app.post("/v1/delegate/scan")
def delegate_scan(niches: Optional[str] = None, min_score: float = 0.30):
    """Retired public remote scanner execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_delegate_scan_retired_use_governed_source_mesh",
    )


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
def sweep_run(req: dict = None):
    """Retired legacy execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_sweep_run_retired_use_governed_source_mesh",
    )



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
    """Retired direct AGI scout execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_agi_scout_tick_retired_use_governed_source_mesh",
    )


@app.get("/v1/agi/marketing/state")
def agi_marketing_state():
    """Get AGI Marketing's current state and content cycle."""
    global agi_marketing
    if not agi_marketing:
        raise HTTPException(503, "agi-marketing not initialized")
    return agi_marketing.state()


@app.post("/v1/agi/marketing/tick")
def agi_marketing_tick():
    """Retired AGI marketing mutation/publish path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_agi_marketing_tick_retired_use_governed_search_and_demand_flow",
    )


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
    """Retired direct shell-based video rendering path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_video_brief_retired_use_governed_advertising_creative_flow",
    )


@app.post("/v1/cinematic/render")
def cinematic_render(req: dict):
    """Generate an in-memory, non-published cinematic landing preview."""
    import html as _html

    headline = _html.escape(str(req.get("headline") or "")[:180])
    subhead = _html.escape(str(req.get("subhead") or "")[:320])
    price = _html.escape(str(req.get("price") or "")[:80])
    cta = _html.escape(str(req.get("cta") or "Learn more")[:80])
    niche = str(req.get("niche") or "")[:120]

    markup = (
        f"<!DOCTYPE html><html><head><title>{headline}</title>"
        f"<meta name='description' content='{subhead}'>"
        f"</head><body><main>"
        f"<h1>{headline}</h1><p>{subhead}</p>"
        f"<div>{price}</div><button>{cta}</button>"
        f"</main></body></html>"
    )
    return {
        "mode": "PREVIEW",
        "published": False,
        "execution_authority": "none",
        "niche": niche,
        "html": markup,
    }


# Tenant Studio endpoint
@app.get("/v1/tenants/portal")
def tenant_portal(tenant: str = ""):
    """Stub. tenant-studio agent renders the HTML on next poll."""
    return {"tenant": tenant, "status": "rendered_by_tenant_studio_agent"}


@app.post("/v1/media/schedule")
def media_schedule(req: dict):
    """Recommendation-only media scheduling preview."""
    return {
        "ok": True,
        "scheduled": False,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "requested": dict(req),
    }


@app.get("/v1/prompts/tiers")
def prompts_tiers():
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_prompt_pricing_retired_use_governed_product_catalog",
    )



@app.get("/v1/prompts/list")
def prompts_list(tier: str = "bronze", q: str = ""):
    """Retired legacy internal/read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_prompt_list_retired_use_governed_product_catalog",
    )



@app.get("/v1/prompts/get")
def prompts_get(slug: str = ""):
    """Retired legacy internal/read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_prompt_body_retired_use_governed_product_entitlement",
    )



@app.post("/v1/agi/sales/tick")
def agi_sales_tick():
    """Retired legacy AGI sales mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_agi_sales_tick_retired_use_revenue_crm_and_conversation_os",
    )


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
    """Legacy closer execution is retired in favor of the governed closer."""
    raise HTTPException(
        410,
        "legacy_agi_closer_execution_retired_use_canonical_supabase_closer",
    )




@app.post("/v1/ai-closer/close")
def ai_closer_close(req: dict):
    """Retired direct-send closer path; canonical governed flow is required."""
    raise HTTPException(
        410,
        "legacy_ai_closer_close_retired_use_canonical_closer_and_outbound",
    )


@app.post("/v1/satellite/idle-watch/report")
def idle_watch_report(req: dict):
    """Retired legacy paid-product execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_idle_watch_report_retired_use_revenue_exchange_and_governed_product_delivery",
    )



@app.post("/v1/warehouse/asset/report")
def warehouse_asset_report(req: dict):
    """Retired legacy paid-product execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_warehouse_asset_report_retired_use_revenue_exchange_and_governed_product_delivery",
    )



@app.post("/v1/leads/engine/discover")
def leads_engine_discover(req: dict):
    """Retired legacy paid-product execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_leads_engine_discover_retired_use_source_mesh_and_governed_product_delivery",
    )









@app.post("/v1/skillspector/audit")
def skillspector_audit(req: dict):
    """Retired legacy paid-product execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_skillspector_audit_retired_use_governed_product_delivery",
    )



@app.post("/v1/opencut/studio")
def opencut_studio(req: dict):
    """Retired legacy paid-product execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_opencut_studio_retired_use_governed_product_delivery",
    )



@app.post("/v1/templates/list")
def empire_templates_list(req: dict):
    """Retired legacy paid-product execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_templates_list_retired_use_governed_product_delivery",
    )



@app.post("/v1/hermes/framework")
def hermes_framework(req: dict):
    """Retired legacy paid-product execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_hermes_framework_retired_use_governed_product_delivery",
    )



@app.post("/v1/lead-lane/access")
def lead_lane_access(req: dict):
    """Retired legacy paid-product execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_lead_lane_access_retired_use_revenue_exchange_and_buyer_allocation",
    )



@app.post("/v1/satellite/wastage/report")
def satellite_wastage_report(req: dict):
    """Retired legacy paid-product execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_satellite_wastage_report_retired_use_revenue_exchange_and_governed_product_delivery",
    )



@app.post("/v1/marketingskills/access")
def marketingskills_access(req: dict):
    """Retired legacy paid-product execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_marketingskills_access_retired_use_governed_product_delivery",
    )



@app.post("/v1/strike-pack/claim")
def strike_pack_claim(req: dict):
    """Retired legacy execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_strike_pack_claim_retired_use_revenue_exchange_and_governed_fulfilment",
    )



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
    """Retired legacy internal/read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_agent_topology_retired_use_canonical_observability",
    )



@app.post("/v1/agents/{agent_name}/dispatch")
def dispatch_to_agent(agent_name: str, payload: dict):
    """Retired public direct-agent dispatch path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_agent_dispatch_retired_use_governed_execution_bus",
    )


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page():
    """Serve the Empire OS dashboard HTML page."""
    return DASHBOARD_HTML


@app.get("/v1/dashboard/data")
def dashboard_data():
    """JSON data endpoint for the dashboard."""
    if not backend:
        raise HTTPException(503, "Engine not initialized")
    return build_dashboard_data(backend)


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
    """Retired legacy execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_decision_approve_retired_use_governed_approval_execution_bus",
    )



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
def funnel_transition(prospect_id: str, req: dict):
    """Retired legacy execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_funnel_transition_retired_use_revenue_crm_and_governed_state_flow",
    )



# --- Price-and-Settle (LLM-priced settlements with fee split) ---

class PriceAndSettleRequest(BaseModel):
    prospect_id: str
    settle: bool = True
    niche: str = ""


@app.post("/v1/funnel/price-and-settle")
def price_and_settle(req: PriceAndSettleRequest):
    """Retired LLM-priced settlement path; verified canonical terms are required."""
    raise HTTPException(
        410,
        "legacy_price_and_settle_retired_use_verified_bsc_usdt_commercial_flow",
    )


# --- Payouts ---

@app.get("/v1/payouts/status")
def payouts_status():
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_payout_status_retired_use_governed_bsc_treasury_read_model",
    )



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
    """Retired legacy SQLite tenant signup path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_tenant_signup_retired_use_canonical_saas_tenant_flow",
    )


@app.get("/v1/tenants/{tenant_id}")
def tenant_info(tenant_id: str):
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_tenant_info_retired_use_canonical_saas_tenant_read_model",
    )



class SubscribeRequest(BaseModel):
    tenant_id: str
    plan: str
    billing_cycle: str = "monthly"
    seats: int = 1
    payment_method: str = "paypal"  # "paypal" or "crypto_usdc"


@app.post("/v1/billing/subscribe")
def billing_subscribe(req: SubscribeRequest):
    """Retired legacy billing subscription execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_billing_subscribe_retired_use_governed_usdt_bsc_subscription_flow",
    )


class CryptoVerifyRequest(BaseModel):
    subscription_id: str
    tx_signature: str
    sender_wallet: str


@app.post("/v1/billing/crypto/verify")
def crypto_verify(req: CryptoVerifyRequest):
    """Retired legacy crypto subscription verification path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_crypto_verify_retired_use_verified_bsc_usdt_commercial_flow",
    )


# --- Payouts (Crypto USDC for TokenPocket etc.) ---

@app.post("/v1/payouts/process-all")
def payouts_process_all():
    """Retired legacy Solana payout batch path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_payout_processing_retired_use_governed_bsc_treasury_flow",
    )


class BatchTxRequest(BaseModel):
    sender_wallet: str = ""
    """Optional — if omitted, uses VAULT_WALLET_ADDRESS."""


@app.post("/v1/payouts/batch-tx")
def payouts_batch_tx(req: BatchTxRequest = None):
    """Retired legacy Solana payout transaction builder."""
    raise HTTPException(
        status_code=410,
        detail="legacy_payout_batch_tx_retired_use_governed_bsc_treasury_flow",
    )


class PayoutVerifyRequest(BaseModel):
    payout_id: str
    tx_signature: str
    sender_wallet: str


@app.post("/v1/payouts/verify")
def payouts_verify(req: PayoutVerifyRequest):
    """Retired legacy Solana payout verification path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_payout_verify_retired_use_governed_bsc_treasury_flow",
    )


# --- Waterfall (Data Provider Orchestrator) ---

class LeadEnrichRequest(BaseModel):
    company: str
    phone: str = ""
    email: str = ""
    name: str = ""
    vertical: str = "default"


@app.post("/v1/leads/enrich")
def leads_enrich(req: dict):
    """Retired legacy execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_lead_enrich_retired_use_evidence_enrichment_planner",
    )



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
def telegram_brief(req: dict = None):
    """Retired legacy execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_telegram_brief_retired_use_governed_notification_flow",
    )



@app.post("/v1/telegram/alert")
def telegram_alert(req: dict = None, message: str = ""):
    """Retired legacy execution path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_telegram_alert_retired_use_governed_notification_flow",
    )



# --- Wallet signing UI + Solana Pay Transaction Request ---

WALLET_SIGN_HTML = (Path(__file__).parent / "templates" / "sign_tx.html").read_text()


@app.get("/wallet/sign", response_class=HTMLResponse)
async def wallet_sign_page():
    """Serve the wallet-adapter signing page."""
    return WALLET_SIGN_HTML


@app.get("/v1/payouts/sign-tx")
def payouts_sign_tx_request_sync():
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_payout_sign_tx_retired_use_governed_bsc_treasury_flow",
    )



@app.get("/v1/payouts/tx-base64")
def payouts_tx_base64():
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_payout_tx_base64_retired_use_governed_bsc_treasury_flow",
    )



class PayoutVerifyBatchRequest(BaseModel):
    tx_signature: str


class PayoutSubmitRequest(BaseModel):
    signed_tx_base64: str
    batch_index: int = 0
    encoding: str = "base64"  # "base64" (default) or "base58"


@app.post("/v1/payouts/submit")
def payouts_submit(req: PayoutSubmitRequest):
    """Retired legacy Solana payout submission path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_payout_submit_retired_use_governed_bsc_treasury_flow",
    )


@app.post("/v1/payouts/verify-batch")
def payouts_verify_batch(req: PayoutVerifyBatchRequest):
    """Retired legacy Solana payout batch verification path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_payout_verify_batch_retired_use_governed_bsc_treasury_flow",
    )


# ── Lane / Lead Supply System ────────────────────────────────────────


@app.get("/v1/lanes")
def list_lanes():
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_lane_list_retired_use_v1_revenue_exchange_markets",
    )



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
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_lane_read_retired_use_revenue_exchange_and_buyer_allocation",
    )



class AssignSeatRequest(BaseModel):
    firm_name: str
    firm_slug: str
    tier: str = "raw"
    price_monthly: float = 0.0


@app.post("/v1/lanes/{lane_id}/seat")
def assign_seat(lane_id: str, req: AssignSeatRequest):
    """Retired legacy SQLite lane seat mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_lane_seat_retired_use_governed_buyer_allocation_flow",
    )


@app.post("/v1/lanes/{lane_id}/release")
def release_seat(lane_id: str):
    """Retired legacy SQLite lane release mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_lane_release_retired_use_governed_buyer_allocation_flow",
    )


@app.get("/v1/lanes/leads/pending")
def pending_lane_leads(limit: int = 100):
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_lane_pending_read_retired_use_canonical_prospect_reader",
    )



@app.get("/v1/lanes/leads/by-source")
def leads_by_source():
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_lane_source_read_retired_use_canonical_source_mesh",
    )



@app.get("/v1/agents/status")
def agents_status():
    """Retired legacy internal/read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_agent_process_status_retired_use_canonical_observability",
    )



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
    """Retired legacy SQLite lead routing mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_lane_route_retired_use_canonical_allocation_planner",
    )


class QualifyBatchRequest(BaseModel):
    leads: list[RouteLeadRequest]


@app.post("/v1/lanes/route-batch")
def route_batch(req: QualifyBatchRequest):
    """Retired legacy SQLite batch routing mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_lane_route_batch_retired_use_canonical_allocation_planner",
    )


@app.get("/v1/lanes/score/{prospect_id}")
def score_prospect(prospect_id: str):
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_lane_score_retired_use_canonical_intelligence_materializer",
    )



# --- Swarm pub/sub (file-backed, lets containers share events) ---
SWARMS_LOG = Path(
    os.getenv(
        "SWARMS_LOG",
        "/srv/empire_os/runtime/swarms/events.jsonl",
    )
)
SWARMS_LOG.parent.mkdir(parents=True, exist_ok=True)
SWARMS_MAX_LINES = 5000  # bounded

# ── PPC ledger ingestion (containers forward charges/invoices here) ──
PPC_DB = "/root/empire_os/empire_os.db"


@app.post("/v1/ppc/log_charge")
async def ppc_log_charge(request: Request):
    """Retired legacy SQLite PPC charge ledger mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_ppc_log_charge_retired_use_canonical_advertising_observation_flow",
    )


@app.post("/v1/ppc/log_invoice")
async def ppc_log_invoice(request: Request):
    """Retired legacy SQLite PPC invoice ledger mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_ppc_log_invoice_retired_use_canonical_advertising_observation_flow",
    )


@app.post("/v1/ppc/charge")
async def ppc_charge(request: Request):
    """Retired legacy direct charging path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_ppc_charge_retired_use_governed_commercial_payment_flow",
    )


@app.get("/v1/ppc/buyer_pms")
async def ppc_buyer_pms():
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_ppc_buyer_pms_retired_use_v1_advertising_observations",
    )



@app.get("/v1/ppc/charges")
async def ppc_list_charges(limit: int = 100, status: str = ""):
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_ppc_charge_read_retired_use_v1_advertising_observations",
    )



@app.get("/v1/ppc/invoices")
async def ppc_list_invoices(limit: int = 50):
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_ppc_invoice_read_retired_use_canonical_advertising_observations",
    )



@app.post("/v1/swarms/events")
async def swarm_log_event(request: Request):
    """Retired unauthenticated file-backed swarm event writer."""
    raise HTTPException(
        status_code=410,
        detail="legacy_swarm_event_writer_retired_use_governed_execution_bus",
    )


@app.get("/v1/swarms/events")
async def swarm_poll_events(since: str = "", limit: int = 50):
    """Retired legacy internal/read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_swarm_event_read_retired_use_canonical_observability",
    )



# ── Carrier DRP Roster Compatibility ───────────────────────────────
# Read-only roster inspection is provided by the earlier canonical route set.
# Duplicate SQLite table-bootstrap/scrape/batch routes were removed.


# ── Carrier Application Portal Auto-Filler (Blueprint v5 #3) ───────────


class CreateCarrierAppRequest(BaseModel):
    company_name: str
    license_no: str
    carrier: str


class UpdateCarrierAppRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None













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
def homeowner_status_post_retired(job_id: int):
    """Retired legacy state mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_homeowner_status_retired_use_governed_marketplace_flow",
    )



# ── Homeowner Pipeline Extension (Blueprint v5 #4) ──────────────────


class HomeownerTransitionRequest(BaseModel):
    job_id: str
    from_status: str
    to_status: str
    notes: str = ""




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
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_crm_lead_list_retired_use_v1_revenue_crm_prospects",
    )



@app.post("/v1/crm/leads/batch-enrich")
def crm_batch_enrich_retired():
    """Retired legacy CRM mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_crm_batch_enrich_retired_use_evidence_enrichment_planner",
    )



@app.get("/v1/crm/leads/{lead_id}")
def crm_get(lead_id: int):
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_crm_lead_read_retired_use_v1_revenue_crm_prospects",
    )



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
def crm_update_retired(lead_id: int, req: dict):
    """Retired legacy CRM mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_crm_lead_update_retired_use_revenue_crm_governed_state_flow",
    )



@app.post("/v1/crm/leads/{lead_id}/status")
def crm_status_retired(lead_id: int, req: dict):
    """Retired legacy CRM mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_crm_status_retired_use_revenue_crm_governed_state_flow",
    )



@app.post("/v1/crm/leads/{lead_id}/enrich")
def crm_enrich_retired(lead_id: int):
    """Retired legacy CRM mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_crm_enrich_retired_use_evidence_enrichment_planner",
    )






@app.get("/v1/crm/pipeline")
def crm_pipeline():
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_crm_pipeline_retired_use_v1_revenue_crm_prospects",
    )



@app.get("/v1/crm/enrichment-stats")
def crm_enrich_stats_endpoint():
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_crm_enrichment_stats_retired_use_canonical_intelligence_materializer",
    )



@app.get("/v1/crm/qualification-summary")
def crm_qualification():
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_crm_qualification_retired_use_canonical_intelligence_materializer",
    )



@app.post("/v1/crm/import-lane-leads")
def crm_import_retired():
    """Retired legacy CRM mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_crm_lane_import_retired_use_canonical_prospect_intake",
    )



@app.get("/v1/crm/analytics")
def crm_analytics():
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_crm_analytics_retired_use_revenue_crm_read_model",
    )



@app.get("/v1/crm/revenue-analytics")
def crm_revenue_analytics():
    """Retired legacy read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_crm_revenue_analytics_retired_use_canonical_revenue_read_model",
    )



# ── ICP Routes ─────────────────────────────────────────────────────


@app.get("/v1/crm/icp/profiles")
def crm_icp_profiles():
    """List all ICP profiles with criteria."""
    from empire_os.icp import DEFAULT_ICP_PROFILES
    return {"profiles": DEFAULT_ICP_PROFILES}


@app.get("/v1/crm/icp/analytics")
def crm_icp_analytics_route():
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_crm_icp_analytics_retired_use_canonical_intelligence_materializer",
    )



@app.get("/v1/crm/icp/score/{lead_id}")
def crm_icp_score_route(lead_id: int):
    """Retired legacy SQLite read surface."""
    raise HTTPException(
        status_code=410,
        detail="legacy_crm_icp_score_retired_use_canonical_intelligence_materializer",
    )



@app.post("/v1/crm/icp/batch")
def crm_icp_batch_retired():
    """Retired legacy CRM mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_crm_icp_batch_retired_use_canonical_intelligence_materializer",
    )



@app.post("/v1/crm/icp/score/{lead_id}")
def crm_icp_refresh_retired(lead_id: int):
    """Retired legacy CRM mutation path."""
    raise HTTPException(
        status_code=410,
        detail="legacy_crm_icp_refresh_retired_use_canonical_intelligence_materializer",
    )



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
