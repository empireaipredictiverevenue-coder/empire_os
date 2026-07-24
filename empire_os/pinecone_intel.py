#!/usr/bin/env python3
"""
Empire OS v3 — Pinecone Vector Intelligence Layer
==================================================
Provides:
- Embedding generation (OpenAI-compatible, local fallback)
- Vector upsert/search for leads, buyers, niches
- Semantic matching for A2A buyer-lead pairing
- Niche clustering for market intelligence

Usage: 
  from empire_os.pinecone_intel import embed_text, upsert_lead, find_similar_buyers
"""

import json
import os
import sys
import time
import subprocess
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Any

sys.path.insert(0, "/root/empire_os")

# Try to use MCP server for Pinecone operations
PINECONE_MCP = "npx -y @pinecone-database/mcp"
INDEX_NAME = os.environ.get("PINECONE_INDEX", "empire-leads")
DIMENSION = 1536

# Cache for MCP responses
_mcp_cache = {}

def _get_api_key() -> str:
    """Read PINECONE_API_KEY from container .env"""
    env_path = Path("/root/empire_os/.env")
    if not env_path.exists():
        return ""
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == "PINECONE_API_KEY":
            return v.strip().strip('"').strip("'")
    return ""

def _mcp_call(method: str, params: dict = None, timeout: int = 15) -> dict:
    """Call Pinecone MCP server via JSON-RPC"""
    cache_key = f"{method}:{json.dumps(params, sort_keys=True)}"
    if cache_key in _mcp_cache:
        return _mcp_cache[cache_key]
    
    api_key = _get_api_key()
    if not api_key:
        return {"error": "no_api_key"}
    
    env = {**os.environ, "PINECONE_API_KEY": api_key}
    
    # JSON-RPC initialize + request
    init_msg = {
        "jsonrpc": "2.0", "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "empire-pinecone", "version": "1.0"}
        }
    }
    notif_msg = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    req_msg = {
        "jsonrpc": "2.0", "id": 2, "method": method, "params": params or {}
    }
    payload = "\n".join([json.dumps(init_msg), json.dumps(notif_msg), json.dumps(req_msg)]) + "\n"
    
    try:
        proc = subprocess.run(
            ["npx", "-y", "@pinecone-database/mcp"],
            input=payload.encode(),
            capture_output=True,
            timeout=timeout,
            env=env,
        )
        out = proc.stdout.decode("utf-8", "ignore").strip().splitlines()
        
        # Find response matching id=2
        for line in reversed(out):
            try:
                d = json.loads(line)
                if d.get("id") == 2:
                    _mcp_cache[cache_key] = d
                    return d
            except Exception:
                continue
        return {"error": "no_response", "raw": out[-3:] if out else []}
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": str(e)}

def embed_text(text: str) -> List[float]:
    """Generate embedding for text via Pinecone MCP or local fallback"""
    # Try to use Pinecone's built-in embedding via MCP
    resp = _mcp_call("tools/call", {
        "name": "embed-text",
        "arguments": {"text": text, "model": "multilingual-e5-large"}
    })
    
    if "result" in resp and "vector" in resp["result"]:
        return resp["result"]["vector"]
    
    # Local deterministic fallback (hash-based pseudo-embedding)
    return _local_embedding(text)

def _local_embedding(text: str) -> List[float]:
    """Deterministic pseudo-embedding for offline/development"""
    # Use multiple hash seeds to create 1536-dim vector
    vec = []
    for i in range(12):  # 12 * 128 = 1536
        seed = f"{text}:{i}"
        h = hashlib.md5(seed.encode()).digest()
        for b in h:
            vec.append((b - 128) / 128.0)  # normalize to [-1, 1]
    return vec[:DIMENSION]

def upsert_lead(lead_id: int, lead_data: dict, namespace: str = "leads") -> bool:
    """Upsert lead vector to Pinecone"""
    # Build rich text for embedding
    text_parts = [
        lead_data.get("niche", ""),
        lead_data.get("sub_niche", ""),
        lead_data.get("metro", ""),
        lead_data.get("city", ""),
        lead_data.get("state", ""),
        f"omega_tier:{lead_data.get('omega_tier', '')}",
        f"omega_score:{lead_data.get('omega_score', 0)}",
        f"predicted_revenue:{lead_data.get('predicted_revenue', 0)}",
    ]
    text = " | ".join(filter(None, text_parts))
    
    vector = embed_text(text)
    
    resp = _mcp_call("tools/call", {
        "name": "upsert-vectors",
        "arguments": {
            "index": INDEX_NAME,
            "vectors": [{
                "id": f"lead_{lead_id}",
                "values": vector,
                "metadata": {
                    "lead_id": lead_id,
                    "niche": lead_data.get("niche", ""),
                    "sub_niche": lead_data.get("sub_niche", ""),
                    "metro": lead_data.get("metro", ""),
                    "omega_score": lead_data.get("omega_score", 0),
                    "omega_tier": lead_data.get("omega_tier", ""),
                    "predicted_revenue": lead_data.get("predicted_revenue", 0),
                    "p_close": lead_data.get("p_close", 0),
                    "payout_usd": lead_data.get("payout_usd", 0),
                    "strategy": lead_data.get("recommended_strategy", ""),
                }
            }],
            "namespace": namespace
        }
    })
    
    return "result" in resp

def upsert_buyer(buyer_id: str, buyer_data: dict, namespace: str = "buyers") -> bool:
    """Upsert buyer vector to Pinecone"""
    text_parts = [
        buyer_data.get("niche", ""),
        buyer_data.get("metro", ""),
        buyer_data.get("company_name", ""),
        f"payout_per_lead:{buyer_data.get('payout_per_lead', 0)}",
    ]
    text = " | ".join(filter(None, text_parts))
    
    vector = embed_text(text)
    
    resp = _mcp_call("tools/call", {
        "name": "upsert-vectors",
        "arguments": {
            "index": INDEX_NAME,
            "vectors": [{
                "id": f"buyer_{buyer_id}",
                "values": vector,
                "metadata": {
                    "buyer_id": buyer_id,
                    "niche": buyer_data.get("niche", ""),
                    "metro": buyer_data.get("metro", ""),
                    "payout_per_lead": buyer_data.get("payout_per_lead", 0),
                    "wallet": buyer_data.get("wallet", ""),
                    "active": buyer_data.get("active", 1),
                }
            }],
            "namespace": namespace
        }
    })
    
    return "result" in resp

def find_similar_buyers(lead_data: dict, top_k: int = 10, namespace: str = "buyers") -> List[dict]:
    """Find buyers semantically similar to a lead"""
    text_parts = [
        lead_data.get("niche", ""),
        lead_data.get("sub_niche", ""),
        lead_data.get("metro", ""),
        f"omega_tier:{lead_data.get('omega_tier', '')}",
        f"predicted_revenue:{lead_data.get('predicted_revenue', 0)}",
    ]
    text = " | ".join(filter(None, text_parts))
    
    vector = embed_text(text)
    
    resp = _mcp_call("tools/call", {
        "name": "query-vectors",
        "arguments": {
            "index": INDEX_NAME,
            "vector": vector,
            "top_k": top_k,
            "namespace": namespace,
            "include_metadata": True,
            "filter": {"active": {"$eq": 1}}  # Only active buyers
        }
    })
    
    if "result" not in resp:
        return []
    
    matches = resp["result"].get("matches", [])
    return [
        {
            "buyer_id": m["metadata"].get("buyer_id"),
            "niche": m["metadata"].get("niche"),
            "metro": m["metadata"].get("metro"),
            "payout_per_lead": m["metadata"].get("payout_per_lead"),
            "score": m.get("score", 0),
        }
        for m in matches
    ]

def find_similar_leads(lead_data: dict, top_k: int = 20, namespace: str = "leads") -> List[dict]:
    """Find leads similar to a given lead (for clustering)"""
    text_parts = [
        lead_data.get("niche", ""),
        lead_data.get("sub_niche", ""),
        lead_data.get("metro", ""),
        f"omega_tier:{lead_data.get('omega_tier', '')}",
    ]
    text = " | ".join(filter(None, text_parts))
    
    vector = embed_text(text)
    
    resp = _mcp_call("tools/call", {
        "name": "query-vectors",
        "arguments": {
            "index": INDEX_NAME,
            "vector": vector,
            "top_k": top_k,
            "namespace": namespace,
            "include_metadata": True,
        }
    })
    
    if "result" not in resp:
        return []
    
    matches = resp["result"].get("matches", [])
    return [
        {
            "lead_id": m["metadata"].get("lead_id"),
            "niche": m["metadata"].get("niche"),
            "metro": m["metadata"].get("metro"),
            "omega_score": m["metadata"].get("omega_score"),
            "score": m.get("score", 0),
        }
        for m in matches
    ]

def semantic_buyer_match(lead_data: dict) -> Optional[dict]:
    """Full semantic matching: find best buyer for lead using vector search + metadata filtering"""
    # 1. Get candidate buyers via vector similarity
    candidates = find_similar_buyers(lead_data, top_k=20)
    
    if not candidates:
        return None
    
    # 2. Re-rank by combined score: vector similarity + payout + niche match
    niche = lead_data.get("niche", "").lower()
    metro = lead_data.get("metro", "").lower()
    
    scored = []
    for b in candidates:
        score = b.get("score", 0)  # Vector similarity [0, 1]
        
        # Boost for niche match
        if niche and niche in (b.get("niche") or "").lower():
            score += 0.2
        
        # Boost for metro match
        if metro and metro in (b.get("metro") or "").lower():
            score += 0.1
        
        # Prefer higher payout
        payout = b.get("payout_per_lead", 0)
        score += min(payout / 100.0, 0.2)
        
        scored.append((score, b))
    
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None

def get_pinecone_stats() -> dict:
    """Get index stats"""
    resp = _mcp_call("tools/call", {
        "name": "describe-index-stats",
        "arguments": {"index": INDEX_NAME}
    })
    if "result" in resp:
        return resp["result"]
    return {"error": resp.get("error", "unknown")}

def bootstrap_index() -> bool:
    """Create index if it doesn't exist"""
    stats = get_pinecone_stats()
    if "error" not in stats:
        return True  # Index exists
    
    # Create index
    resp = _mcp_call("tools/call", {
        "name": "create-index",
        "arguments": {
            "name": INDEX_NAME,
            "dimension": DIMENSION,
            "metric": "cosine",
            "spec": "serverless"
        }
    })
    return "result" in resp

# Export for easy import
__all__ = [
    "embed_text",
    "upsert_lead", 
    "upsert_buyer",
    "find_similar_buyers",
    "find_similar_leads",
    "semantic_buyer_match",
    "get_pinecone_stats",
    "bootstrap_index",
    "INDEX_NAME",
    "DIMENSION",
]