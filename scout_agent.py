"""
Scout Agent — standalone Neural Scout microservice.

Runs all 6 scanners in a dedicated container on empire-net.
Called by empire-hub for scanning outposts.
"""
import logging, os, json
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from empire_os.neural_scout import NeuralScout, ScoredLead
from empire_os.funnel import SQLiteBackend

logging.basicConfig(level=logging.INFO,
                    format="[scout] %(levelname)s %(message)s")
logger = logging.getLogger("scout-agent")

# ── Global scout instance ────────────────────────────────────────────
scout: Optional[NeuralScout] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global scout
    backend = SQLiteBackend("/data/scout.db")
    backend.ensure_schema()
    scout = NeuralScout(backend, auto_register=True)
    logger.info("Scout agent online — 6 scanners loaded")
    yield
    logger.info("Scout agent shutting down")

app = FastAPI(title="Scout Agent", version="0.1.0", lifespan=lifespan)

# ── Models ───────────────────────────────────────────────────────────
class ScanRequest(BaseModel):
    niches: list[str] = ["roofing", "hvac", "pest-control", "mass-torts",
                         "solar", "windows", "water-damage", "mold"]
    min_score: float = 0.30

class EvaluateRequest(BaseModel):
    niche: str
    details: str
    phone: Optional[str] = ""
    zip_code: Optional[str] = ""
    name: Optional[str] = ""
    source: str = "scout-agent"

class RegisterRequest(BaseModel):
    niche: str
    details: str
    score: float
    phone: Optional[str] = ""
    zip_code: Optional[str] = ""
    name: Optional[str] = ""
    source: str = "scout-agent"

# ── Endpoints ────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "online",
        "service": "scout-agent",
        "scanners": [s.name for s in scout._scanners] if scout else [],
        "version": "0.1.0",
    }

@app.post("/scan")
def scan(req: ScanRequest):
    """Run all scanners and return scored + funnel-registered leads."""
    global scout
    if scout is None:
        raise HTTPException(503, "scout not initialized")
    prev = scout.min_score
    scout.min_score = req.min_score
    try:
        niche_list = req.niches if req.niches != ScanRequest.model_fields["niches"].default else None
        results = scout.tick(niches=niche_list)
        return {
            "scanned": results["scanned"],
            "registered": results["registered"],
            "leads": [
                {
                    "prospect_id": l["prospect_id"],
                    "niche": l["niche"],
                    "score": l["score"],
                }
                for l in results.get("leads", [])
            ],
        }
    except Exception as e:
        logger.exception("scan failed: %s", e)
        raise HTTPException(500, str(e))
    finally:
        scout.min_score = prev

@app.post("/evaluate")
def evaluate(req: EvaluateRequest):
    """Score a single lead without registering it."""
    if scout is None:
        raise HTTPException(503, "scout not initialized")
    lead = scout.evaluate(
        niche=req.niche,
        details=req.details,
        phone=req.phone or "",
        zip_code=req.zip_code or "",
        name=req.name or "",
        source=req.source,
    )
    if lead is None:
        return {"qualified": False, "score": 0}
    return {
        "qualified": True,
        "score": lead.score,
        "prospect_id": lead.prospect_id,
    }

@app.post("/register")
def register(req: RegisterRequest):
    """Register a pre-scored lead into the scout's local funnel."""
    if scout is None:
        raise HTTPException(503, "scout not initialized")
    lead = ScoredLead(
        prospect_id=f"lead:{req.niche}:{abs(hash(req.details)) % 10**8:08x}",
        niche=req.niche,
        details=req.details,
        score=req.score,
        phone=req.phone or "",
        zip_code=req.zip_code or "",
        name=req.name or "",
        source=req.source,
    )
    event_id = scout.register_lead(lead)
    return {"prospect_id": lead.prospect_id, "event_id": event_id}

@app.get("/scanners")
def list_scanners():
    """List all registered scanners and their status."""
    if scout is None:
        raise HTTPException(503, "scout not initialized")
    return {
        "scanners": [
            {
                "name": s.name,
                "niches": list(s.niches),
            }
            for s in scout._scanners
        ]
    }

@app.get("/funnel/counts")
def funnel_counts():
    """Return funnel state counts from scout's local DB."""
    if scout is None:
        raise HTTPException(503, "scout not initialized")
    return {"counts": scout.backend.count_by_state()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9090, log_level="info", timeout_keep_alive=300)
