#!/usr/bin/env python3
"""
pinecone_bootstrap.py — one-shot bootstrap CLI for the Pinecone environment.

Idempotent. Exits 0 only if every step succeeds. Uses the long-lived client
from pinecone_client.py — no subprocess.run per call.

Usage:
    python3 -m empire_os.agents.pinecone_bootstrap
    incus exec empire-hub -- /root/venv/bin/python3 \\
        /root/empire_os/empire_os/agents/pinecone_bootstrap.py
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from typing import Any


def _log(level: str, msg: str, **fields: Any) -> None:
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level": level,
        "msg": msg,
        "component": "pinecone_bootstrap",
    }
    rec.update(fields)
    for k in ("api_key", "text"):
        if k in rec and isinstance(rec[k], str) and len(rec[k]) > 8:
            rec[k] = rec[k][:4] + "..." + rec[k][-2:]
    print(json.dumps(rec, default=str), flush=True)


def main() -> int:
    # Local import keeps the file safe to import for `python3 -c "help(...)"`.
    from empire_os.pinecone_client import PineconeClient, PineconeError, get_client
    from empire_os.pinecone_intel import bootstrap_index, get_stats, upsert_lead

    try:
        client = get_client()
    except PineconeError as e:
        _log("FATAL", "config_or_handshake_failed", error=str(e))
        return 1

    try:
        with client:
            cfg = client.config
            _log("INFO", "config_loaded",
                 index=cfg.index, dim=cfg.dimension,
                 embed=cfg.embed_model, cloud=cfg.cloud, region=cfg.region,
                 key=cfg.redact_key())

            # Step 1: index exists or create it
            try:
                stats = get_stats(client=client)
                _log("INFO", "index_exists", stats=stats)
            except Exception:
                _log("INFO", "creating_index",
                     name=cfg.index, model=cfg.embed_model, dim=cfg.dimension)
                bootstrap_index(client=client)
                stats = get_stats(client=client)
                _log("INFO", "index_created", stats=stats)

            # Step 2: dimension integrity check
            actual_dim = stats.get("dimension")
            if actual_dim and actual_dim != cfg.dimension:
                _log("FATAL", "dimension_mismatch",
                     expected=cfg.dimension, actual=actual_dim,
                     fix=f"recreate index with embed={cfg.embed_model}")
                return 2

            # Step 3: smoke test — upsert + search + delete
            probe_id = f"smoke-{uuid.uuid4().hex[:8]}"
            upsert_lead(probe_id, {
                "niche": "smoke_test",
                "sub_niche": "bootstrap",
                "metro": "system",
                "omega_tier": "probe",
                "omega_score": 0,
                "predicted_revenue": 0,
            }, client=client, namespace="__smoke__")

            hits = client.call("tools/call", {
                "name": "search-records",
                "arguments": {
                    "name": cfg.index,
                    "namespace": "__smoke__",
                    "query": {"topK": 1, "inputs": {"text": "smoke_test bootstrap"}},
                    "includeMetadata": True,
                },
            })
            payload_text = ((hits.get("content") or [{}])[0]).get("text", "{}")
            payload = json.loads(payload_text)
            hit_count = len(payload.get("result", {}).get("hits", []))
            if hit_count == 0:
                _log("FATAL", "smoke_test_no_hits", probe_id=probe_id)
                return 3

            # Cleanup
            client.call("tools/call", {
                "name": "delete-records",
                "arguments": {
                    "name": cfg.index,
                    "namespace": "__smoke__",
                    "ids": [f"lead_{probe_id}"],
                },
            })

            _log("INFO", "smoke_ok", probe_id=probe_id, hits=hit_count)
            _log("INFO", "done", health=client.health())
            return 0

    except PineconeError as e:
        _log("FATAL", "pinecone_error",
             tool=e.tool, mcp=e.mcp_error, attempt=e.attempt, latency_ms=e.latency_ms,
             error=str(e))
        return 4
    except Exception as e:  # last-resort catch — never let bootstrap exit 0 on unknown
        _log("FATAL", "unexpected_error", error_type=type(e).__name__, error=str(e))
        return 5


if __name__ == "__main__":
    sys.exit(main())
