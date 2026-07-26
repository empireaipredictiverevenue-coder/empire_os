"""
Empire OS — Internal Enrichment Webhook
========================================
Self-hosted enrichment endpoint that mirrors our intelligence stack:
- Waterfall enrichment (15 free sources)
- Cortex predictive revenue
- Deep Research (AGI + synthetic)
- Branded nurture emails

Called by outreach_runner when external APIs fail or as primary enrichment.
No external API keys required — uses our own intelligence systems.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from flask import Flask, request, jsonify

# Load .env
for _ln in (Path("/root/empire_os/.env").read_text(encoding="utf-8").splitlines()
            if Path("/root/empire_os/.env").exists() else ()):
    _ln = _ln.strip()
    if not _ln or _ln.startswith("#") or "=" not in _ln: continue
    _k, _, _v = _ln.partition("=")
    os.environ.setdefault(_k.strip(), _v.strip())

# Import our enrichment engine
sys.path.insert(0, "/root/empire_os")
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "empire_enricher", "/root/empire_os/empire_os/agents/empire_enricher.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
EmpireEnricher = _mod.EmpireEnricher

app = Flask(__name__)
_enricher = EmpireEnricher()  # singleton

# Auth: simple shared secret via header
WEBHOOK_SECRET = os.environ.get("ENRICHMENT_WEBHOOK_SECRET", "dev-secret-change-me")


def verify_auth(req) -> bool:
    """Check X-Enrichment-Secret header."""
    return req.headers.get("X-Enrichment-Secret") == WEBHOOK_SECRET


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "enrichment-webhook", "ts": datetime.now(timezone.utc).isoformat()})


@app.route("/enrich", methods=["POST"])
def enrich():
    """Enrich a single prospect.
    
    Request:
    {
        "prospect_id": "abc123",
        "business_name": "ABC Roofing",
        "niche": "roofing",
        "sub_niche": "residential_roofing",
        "metro": "NYC",
        "website": "abcroofing.com",
        "email": "",
        "phone": ""
    }
    
    Response:
    {
        "ok": true,
        "prospect": {...},  # fully enriched
        "emails": [...],    # 3-step nurture sequence
        "enrichment_score": 75.5,
        "enriched_at": "2024-01-01T00:00:00Z"
    }
    """
    if not verify_auth(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json() or {}
    if not data.get("prospect_id") and not data.get("business_name"):
        return jsonify({"ok": False, "error": "prospect_id or business_name required"}), 400

    try:
        # Run full enrichment pipeline
        result = _enricher.get_nurture_ready(data)
        
        return jsonify({
            "ok": True,
            "prospect": result["prospect"],
            "emails": result["emails"],
            "enrichment_score": result["prospect"].get("enrichment_score", 0),
            "enriched_at": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 500


@app.route("/enrich/batch", methods=["POST"])
def enrich_batch():
    """Enrich multiple prospects (max 50)."""
    if not verify_auth(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json() or {}
    prospects = data.get("prospects", [])
    if not prospects:
        return jsonify({"ok": False, "error": "prospects array required"}), 400
    if len(prospects) > 50:
        return jsonify({"ok": False, "error": "max 50 prospects per batch"}), 400

    results = []
    for p in prospects:
        try:
            result = _enricher.get_nurture_ready(p)
            results.append({
                "prospect_id": p.get("prospect_id", ""),
                "ok": True,
                "prospect": result["prospect"],
                "emails": result["emails"],
                "enrichment_score": result["prospect"].get("enrichment_score", 0)
            })
        except Exception as e:
            results.append({"prospect_id": p.get("prospect_id", ""), "ok": False, "error": str(e)[:200]})

    return jsonify({"ok": True, "results": results, "count": len(results)})


@app.route("/enrich/score", methods=["POST"])
def enrich_score():
    """Get just the enrichment score and key fields (lightweight)."""
    if not verify_auth(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json() or {}
    if not data.get("prospect_id") and not data.get("business_name"):
        return jsonify({"ok": False, "error": "prospect_id or business_name required"}), 400

    try:
        # Use deep_enrich directly for score only
        enriched = _enricher.deep_enrich(data, use_cache=True)
        return jsonify({
            "ok": True,
            "prospect_id": data.get("prospect_id", ""),
            "enrichment_score": enriched.get("enrichment_score", 0),
            "tier": enriched.get("cortex", {}).get("tier", "—"),
            "predicted_revenue": enriched.get("cortex", {}).get("predicted_revenue", 0),
            "email": enriched.get("email", ""),
            "phone": enriched.get("phone", ""),
            "website": enriched.get("website", ""),
            "signals": {k: v for k, v in enriched.get("deep_research", {}).get("signals", {}).items() if v},
            "enriched_at": enriched.get("enriched_at", "")
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 500


@app.route("/enrich/email", methods=["POST"])
def enrich_email_only():
    """Fast email-only enrichment for outreach runner."""
    if not verify_auth(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json() or {}
    if not data.get("prospect_id") and not data.get("business_name"):
        return jsonify({"ok": False, "error": "prospect_id or business_name required"}), 400

    try:
        # Quick email pattern guess + website scrape
        emails = []
        website = data.get("website", "") or ""
        biz_name = data.get("business_name", "") or ""
        
        # Pattern-based emails
        if biz_name:
            domain = ""
            if website:
                import re
                domain = re.sub(r"https?://", "", website).split("/")[0]
            elif " " in biz_name:
                # Guess domain from business name
                import re
                slug = re.sub(r"[^a-z0-9]+", "", biz_name.lower())
                domain = f"{slug}.com"
            
            if domain:
                patterns = ["info", "contact", "sales", "hello", "team", "office", "support"]
                for p in patterns:
                    emails.append(f"{p}@{domain}")
        
        return jsonify({
            "ok": True,
            "emails": emails[:5],
            "enriched_at": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 500


if __name__ == "__main__":
    port = int(os.environ.get("ENRICHMENT_WEBHOOK_PORT", "9090"))
    app.run(host="0.0.0.0", port=port, threaded=True)