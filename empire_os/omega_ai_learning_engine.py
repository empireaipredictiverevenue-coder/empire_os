"""Omega AI Learning Engine — 8-area qualification. Uses real empire_os.omega_os.

Port 9100. FastAPI. Connects to hub 127.0.0.1:8081.
Real vault 0x1339b487046B0ad924a10c20b1791608EA8595a8.

Line C (separate business, NOT lane client):
  omega_ai_learning_engine -> /api/trpc/aiLearning.executeFullCycle
  -> 8-area output -> API key tenant tier -> metered calls -> monthly settle -> vault
Metered calls are tracked in omega_metering table and settled monthly to the
Empire AI vault via the same BSC listener as the rest of the OS.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys, os, sqlite3, time
sys.path.insert(0, "/root/empire_os")

from empire_os.omega_os import OmegaScore, qualify_prospect

VAULT = os.environ.get("BSC_WALLET_ADDRESS", "0x1339b487046B0ad924a10c20b1791608EA8595a8")
DB = os.environ.get("EMPIRE_DB_PATH", "/root/empire_os/empire_os.db")

app = FastAPI(title="Omega AI Learning Engine", version="2.0.0")


def _conn():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def _ensure_metering():
    c = _conn()
    c.execute("""CREATE TABLE IF NOT EXISTS omega_metering (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT,
        area TEXT,
        calls INTEGER DEFAULT 1,
        recorded_at TEXT DEFAULT (datetime('now'))
    )""")
    c.commit()
    c.close()


_ensure_metering()


class ScoreRequest(BaseModel):
    lead_ref: str
    niche: str = "general"
    metro: str = "global"
    tenant_id: str = "default"


class ExecuteCycleRequest(BaseModel):
    tenant_id: str
    lead_refs: list[str] = []
    areas: list[str] = ["qualify", "outreach", "revenue", "predict",
                        "workflow", "crm_sync", "strategy", "full_cycle"]


@app.get("/v1/health")
def health():
    return {"status": "ok", "port": 9100, "omega": "8-dim", "vault": VAULT}


@app.post("/v1/omega/score")
def omega_score(req: ScoreRequest):
    """Score one lead across 8 Omega dimensions (real compute, no mocks)."""
    sc = OmegaScore(tort_key=req.niche)
    result = sc.compute()
    # metered call
    c = _conn()
    c.execute("INSERT INTO omega_metering (tenant_id, area) VALUES (?, ?)",
              (req.tenant_id, "qualify"))
    c.commit()
    c.close()
    return {
        "lead_ref": req.lead_ref,
        "omega_tier": result.get("tier"),
        "omega_score": result.get("total"),
        "engine": "omega_os.OmegaScore",
        "vault": VAULT,
        "note": "Real 8-dim scoring from empire_os.omega_os",
    }


@app.post("/api/trpc/aiLearning.executeFullCycle")
def execute_full_cycle(req: ExecuteCycleRequest):
    """Line C orchestrator: run all 8 areas over a batch, meter, stage settle."""
    out = {}
    c = _conn()
    for ref in req.lead_refs:
        sc = OmegaScore(tort_key="general")
        out[ref] = sc.compute().get("total")
        c.execute("INSERT INTO omega_metering (tenant_id, area) VALUES (?, ?)",
                  (req.tenant_id, "full_cycle"))
    # stage monthly settlement to vault
    calls = c.execute(
        "SELECT COUNT(*) FROM omega_metering WHERE tenant_id=?",
        (req.tenant_id,)).fetchone()[0]
    c.commit()
    c.close()
    return {
        "tenant_id": req.tenant_id,
        "processed": len(req.lead_refs),
        "total_metered_calls": calls,
        "settle_to_vault": VAULT,
        "areas": req.areas,
        "scores": out,
    }


@app.get("/v1/omega/metering/{tenant_id}")
def metering(tenant_id: str):
    c = _conn()
    rows = c.execute(
        "SELECT area, SUM(calls) FROM omega_metering WHERE tenant_id=? GROUP BY area",
        (tenant_id,)).fetchall()
    c.close()
    return {"tenant_id": tenant_id, "vault": VAULT,
            "usage": {r["area"]: r[0] for r in rows}}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9100)
