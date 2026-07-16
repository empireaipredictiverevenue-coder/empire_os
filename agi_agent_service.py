"""
AGI Agent Service — standalone microservice for any Agent subclass.

Runs the agent in a dedicated container on empire-net.
Exposes observe-reason-act cycle over HTTP, same pattern as scout-agent.
Configured via env vars: AGENT_TYPE, OLLAMA_BASE_URL, DB_PATH.
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from empire_os.agent_core import Agent, OllamaClient, AgentContext
from empire_os.funnel import SQLiteBackend

logging.basicConfig(level=logging.INFO, format="[%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("agi-agent")

# ── Globals ────────────────────────────────────────────────────────────
agent: Optional[Agent] = None


def _resolve_agent(name: str, backend: SQLiteBackend, llm: OllamaClient) -> Agent:
    """Import and instantiate the named agent class."""
    if name == "agi-scout":
        from empire_os.agi_scout import AgiScoutAgent
        return AgiScoutAgent(backend=backend, llm=llm)
    elif name == "agi-marketing":
        from empire_os.agi_marketing import AgiMarketingAgent
        return AgiMarketingAgent(backend=backend, llm=llm)
    else:
        raise ValueError(f"Unknown agent type: {name}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    agent_type = os.environ.get("AGENT_TYPE", "agi-scout")
    db_path = os.environ.get("DB_PATH", f"/data/{agent_type}.db")
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://10.218.156.211:11434")

    backend = SQLiteBackend(db_path)
    backend.ensure_schema()
    llm = OllamaClient(base_url=ollama_url, timeout=120)
    agent = _resolve_agent(agent_type, backend, llm)
    logger.info("AGI agent '%s' online — db=%s llm=%s", agent_type, db_path, ollama_url)
    yield
    logger.info("AGI agent '%s' shutting down", agent_type)


app = FastAPI(title="AGI Agent Service", version="0.1.0", lifespan=lifespan)


# ── Models ────────────────────────────────────────────────────────────
class TickRequest(BaseModel):
    niche: Optional[str] = None
    synthetic_count: Optional[int] = None


class ConfigureRequest(BaseModel):
    niches: Optional[list[str]] = None
    score_threshold: Optional[float] = None


# ── Endpoints ─────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "online",
        "agent": os.environ.get("AGENT_TYPE", "unknown"),
        "cycles": agent.context.cycle if agent else 0,
        "version": "0.1.0",
    }


@app.post("/tick")
def tick(req: TickRequest):
    """Run one observe-reason-act cycle and return the result."""
    global agent
    if agent is None:
        raise HTTPException(503, "agent not initialized")
    try:
        result = agent.tick()
        return {
            "cycle": agent.context.cycle,
            "elapsed": result.get("elapsed", 0),
            "decision_preview": result.get("decision_preview", ""),
            "result": result.get("result", {}),
        }
    except Exception as e:
        logger.exception("tick failed")
        raise HTTPException(500, str(e))


@app.get("/state")
def state():
    """Return current agent context and state."""
    if agent is None:
        raise HTTPException(503, "agent not initialized")
    return {
        "agent": agent.name,
        "cycle": agent.context.cycle,
        "last_result": agent.context.last_result,
    }


@app.post("/configure")
def configure(req: ConfigureRequest):
    """Update agent configuration at runtime."""
    global agent
    if agent is None:
        raise HTTPException(503, "agent not initialized")
    if req.niches:
        agent.niches = req.niches
    if req.score_threshold is not None:
        if hasattr(agent, "neural_scout") and agent.neural_scout:
            agent.neural_scout.min_score = req.score_threshold
    return {
        "configured": True,
        "niches": getattr(agent, "niches", []),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "9091"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info", timeout_keep_alive=300)
