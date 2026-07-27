#!/usr/bin/env python3
"""
pinecone_intel.py — Empire OS domain layer over the Pinecone MCP client.

All subprocess, stdio, and MCP plumbing lives in pinecone_client.py. This
module only builds arguments and shapes results for business callers.

Usage:
    from empire_os.pinecone_client import get_client
    with get_client() as c:
        embed_and_upsert_lead(123, {...}, client=c)
        match = semantic_buyer_match({"niche": "roofing", "metro": "Austin"}, client=c)
"""
from __future__ import annotations

import json
from typing import Any, List, Optional

from empire_os.pinecone_client import (
    PineconeClient,
    PineconeDimensionError,
    PineconeError,
    PineconeNotFoundError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_mcp_payload(resp: dict) -> dict:
    """MCP wraps tool results in content[0].text as a JSON string. Unwrap it."""
    content = resp.get("content") or []
    if not content:
        return {}
    text = (content[0] or {}).get("text", "{}")
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"_raw": text}


def _build_lead_text(lead: dict) -> str:
    parts = [
        lead.get("niche", ""),
        lead.get("sub_niche", ""),
        lead.get("metro", ""),
        lead.get("city", ""),
        lead.get("state", ""),
        f"omega_tier:{lead.get('omega_tier', '')}",
        f"omega_score:{lead.get('omega_score', 0)}",
        f"predicted_revenue:{lead.get('predicted_revenue', 0)}",
    ]
    return " | ".join(p for p in parts if p)


def _build_buyer_text(buyer: dict) -> str:
    parts = [
        buyer.get("niche", ""),
        buyer.get("metro", ""),
        buyer.get("company_name", ""),
        f"payout_per_lead:{buyer.get('payout_per_lead', 0)}",
    ]
    return " | ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upsert_lead(lead_id: int | str, lead: dict, *,
                client: PineconeClient, namespace: str = "leads") -> bool:
    """Upsert a lead record (text + metadata). The index's embed model handles vectorization."""
    record = {
        "_id": f"lead_{lead_id}",
        "text": _build_lead_text(lead),
        "lead_id": lead_id,
        "niche": lead.get("niche", ""),
        "sub_niche": lead.get("sub_niche", ""),
        "metro": lead.get("metro", ""),
        "omega_score": lead.get("omega_score", 0),
        "omega_tier": lead.get("omega_tier", ""),
        "predicted_revenue": lead.get("predicted_revenue", 0),
        "p_close": lead.get("p_close", 0),
        "payout_usd": lead.get("payout_usd", 0),
        "strategy": lead.get("recommended_strategy", ""),
    }
    client.call("tools/call", {
        "name": "upsert-records",
        "arguments": {
            "name": client.config.index,
            "namespace": namespace,
            "records": [record],
        },
    })
    return True


def upsert_buyer(buyer_id: str, buyer: dict, *,
                 client: PineconeClient, namespace: str = "buyers") -> bool:
    """Upsert a buyer record. The index's embed model handles vectorization."""
    record = {
        "_id": f"buyer_{buyer_id}",
        "text": _build_buyer_text(buyer),
        "buyer_id": buyer_id,
        "niche": buyer.get("niche", ""),
        "metro": buyer.get("metro", ""),
        "payout_per_lead": buyer.get("payout_per_lead", 0),
        "wallet": buyer.get("wallet", ""),
        "active": buyer.get("active", 1),
    }
    client.call("tools/call", {
        "name": "upsert-records",
        "arguments": {
            "name": client.config.index,
            "namespace": namespace,
            "records": [record],
        },
    })
    return True


def find_similar_buyers(lead: dict, *, client: PineconeClient,
                        top_k: int = 10, namespace: str = "buyers") -> List[dict]:
    """Find buyers semantically similar to a lead."""
    text = _build_lead_text(lead)
    resp = client.call("tools/call", {
        "name": "search-records",
        "arguments": {
            "name": client.config.index,
            "namespace": namespace,
            "query": {"topK": top_k, "inputs": {"text": text}},
            "includeMetadata": True,
        },
    })
    payload = _parse_mcp_payload(resp)
    hits = payload.get("result", {}).get("hits", [])
    return [
        {
            "buyer_id": h.get("metadata", {}).get("buyer_id"),
            "niche": h.get("metadata", {}).get("niche"),
            "metro": h.get("metadata", {}).get("metro"),
            "payout_per_lead": h.get("metadata", {}).get("payout_per_lead"),
            "score": h.get("score", 0.0),
        }
        for h in hits
    ]


def find_similar_leads(lead: dict, *, client: PineconeClient,
                       top_k: int = 20, namespace: str = "leads") -> List[dict]:
    """Find leads similar to a given lead (for clustering)."""
    text = _build_lead_text(lead)
    resp = client.call("tools/call", {
        "name": "search-records",
        "arguments": {
            "name": client.config.index,
            "namespace": namespace,
            "query": {"topK": top_k, "inputs": {"text": text}},
            "includeMetadata": True,
        },
    })
    payload = _parse_mcp_payload(resp)
    hits = payload.get("result", {}).get("hits", [])
    return [
        {
            "lead_id": h.get("metadata", {}).get("lead_id"),
            "niche": h.get("metadata", {}).get("niche"),
            "metro": h.get("metadata", {}).get("metro"),
            "omega_score": h.get("metadata", {}).get("omega_score"),
            "score": h.get("score", 0.0),
        }
        for h in hits
    ]


def semantic_buyer_match(lead: dict, *, client: PineconeClient) -> Optional[dict]:
    """Re-rank by vector similarity + niche/metro match + payout. Returns best or None."""
    candidates = find_similar_buyers(lead, client=client, top_k=20)
    if not candidates:
        return None

    niche = (lead.get("niche") or "").lower()
    metro = (lead.get("metro") or "").lower()

    scored: list[tuple[float, dict]] = []
    for b in candidates:
        score = float(b.get("score", 0.0))
        bn = (b.get("niche") or "").lower()
        bm = (b.get("metro") or "").lower()
        if niche and niche in bn:
            score += 0.2
        if metro and metro in bm:
            score += 0.1
        payout = float(b.get("payout_per_lead") or 0)
        score += min(payout / 100.0, 0.2)
        scored.append((score, b))

    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None


def get_stats(*, client: PineconeClient) -> dict:
    """Return index stats (dimension, namespaces, record counts)."""
    resp = client.call("tools/call", {
        "name": "describe-index-stats",
        "arguments": {"name": client.config.index},
    })
    return _parse_mcp_payload(resp)


def bootstrap_index(*, client: PineconeClient) -> bool:
    """Create the configured index if it does not exist. Idempotent."""
    try:
        get_stats(client=client)
        return True  # exists
    except PineconeNotFoundError:
        pass

    client.call("tools/call", {
        "name": "create-index-for-model",
        "arguments": {
            "name": client.config.index,
            "cloud": client.config.cloud,
            "region": client.config.region,
            "embed": {
                "model": client.config.embed_model,
                "fieldMap": {"text": client.config.field_map_text},
            },
        },
    })
    return True


__all__ = [
    "upsert_lead",
    "upsert_buyer",
    "find_similar_buyers",
    "find_similar_leads",
    "semantic_buyer_match",
    "get_stats",
    "bootstrap_index",
]
