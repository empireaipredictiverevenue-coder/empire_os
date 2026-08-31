#!/usr/bin/env python3
"""router_engine.py — Empire AI Multi-Niche World Model & Omnichannel Execution Engine.

Layer 17 of the Predictive Cloud brain. Ingests real-time multi-niche event
streams from Redis (empire-net bridge), spins up digital-twin market simulations,
generates niche-specific brain-layer content, and routes email + ad campaigns
straight to outgoing Redis queues.

NO Vercel/Dokku/Railway. Pure self-hosted Incus container on empire-net.
Settlement: BSC BEP20 USDT, 15% success fee (vault 0x1339...).
"""
from __future__ import annotations
import os
import sys
import json
import time
import logging

sys.path.insert(0, "/root/empire_os")

try:
    import redis
except ImportError:
    print("redis not installed; run: /root/venv/bin/python3 -m pip install redis")
    raise

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("router_engine")

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
INCOMING_STREAM = "empire_events"
EMAIL_QUEUE = "outgoing_emails"
AD_QUEUE = "outgoing_ads"

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)


# ── Brain Layer Content Engine (niche → copy router) ──────────────────
def generate_brain_content(event: dict) -> dict:
    """Route incoming event through brain layer based on niche tag.

    Acts like a smart kitchen sorting orders by category — each niche gets
    its own psychological hook + subconscious trigger mapping.
    """
    niche = (event.get("niche") or "general").lower()
    location = event.get("location", "US")

    if niche == "roofing":
        subject = f"Urgent Storm Alert: Protect your home in {location}"
        body = (f"Severe weather is hitting {location} right now. Secure your roof and "
                f"book an emergency inspection before water damage sets in.")
        ad_headline = f"Emergency Roof Inspections in {location}"
    elif niche == "legal":
        subject = f"Urgent Notice for {location}: Claim Check"
        body = (f"Market shifts in {location} affect your rights. Check your eligibility "
                f"for fast compensation claims today.")
        ad_headline = f"Fast Claim Review for {location}"
    elif niche == "finance":
        subject = f"Market Shift Alert for {location}"
        body = (f"Protect your portfolio from sudden volatility in {location}. "
                f"Secure your assets before the next dip.")
        ad_headline = f"Secure Your Wealth in {location}"
    elif niche == "mass_tort":
        subject = f"Compensation Alert for {location}"
        body = (f"You may qualify for a settlement tied to recent {location} exposures. "
                f"No upfront cost — only pay on results.")
        ad_headline = f"See If You Qualify in {location}"
    elif niche == "home_services":
        subject = f"Priority Service Slot Open in {location}"
        body = (f"High demand in {location} — lock your priority service slot before "
                f"capacity fills this week.")
        ad_headline = f"Book {location} Pros Today"
    else:
        subject = f"Special Priority Alert for {location}"
        body = f"Act now to secure your priority slot in {location} before capacity fills up."
        ad_headline = f"Priority Access in {location}"

    return {
        "email": {"subject": subject, "body": body},
        "ad": {"headline": ad_headline, "primary_text": body},
    }


# ── Digital Twin Simulation (localized impact + drop-off) ────────────
def simulate_local_market(event: dict) -> dict:
    """Spin a digital-twin of the local market for the event's niche/location.

    Uses empire_os.digital_twin (empirical-Bayes shrinkage model trained on
    historical funnel data) when available; falls back to heuristic.
    """
    niche = (event.get("niche") or "general").lower()
    est = int(event.get("est_volume", 100))
    mult = float(event.get("storm_multiplier", 1.0))
    try:
        from empire_os.digital_twin import predict
        return predict(niche, est, mult)
    except Exception:
        base = {"roofing": 0.18, "legal": 0.09, "finance": 0.07, "mass_tort": 0.12,
                "home_services": 0.22, "general": 0.05}.get(niche, 0.05)
        return {"niche": niche, "est_leads": est, "conversion_rate": base,
                "projected_clients": int(est * base), "drop_off_rate": round(1 - base, 3),
                "confidence": "heuristic"}


def main():
    log.info("Empire AI Multi-Niche Engine Online. Listening to Redis stream %s", INCOMING_STREAM)
    last_id = "$"  # only new events
    while True:
        try:
            streams = r.xread({INCOMING_STREAM: last_id}, block=1000, count=10)
            if streams:
                for _stream, msgs in streams:
                    for msg_id, data in msgs:
                        last_id = msg_id
                        payload = data.get("payload")
                        if not payload:
                            continue
                        try:
                            event = json.loads(payload)
                        except (json.JSONDecodeError, TypeError):
                            event = {"niche": "general", "location": "US", "payload": payload}
                        niche = event.get("niche", "general")
                        loc = event.get("location", "US")
                        log.info("Captured event | niche=%s loc=%s", niche, loc)

                        # Step 1: Brain-layer content
                        content = generate_brain_content(event)
                        # Step 2: Digital twin sim
                        sim = simulate_local_market(event)

                        # Step 3: Push to Email queue
                        email_payload = {
                            "target": event.get("email", "test@example.com"),
                            "subject": content["email"]["subject"],
                            "body": content["email"]["body"],
                            "sim": sim,
                        }
                        r.rpush(EMAIL_QUEUE, json.dumps(email_payload))

                        # Step 4: Push to Ad queue
                        ad_payload = {
                            "niche": niche,
                            "platform": "meta_and_native",
                            "headline": content["ad"]["headline"],
                            "primary_text": content["ad"]["primary_text"],
                            "sim": sim,
                        }
                        r.rpush(AD_QUEUE, json.dumps(ad_payload))
                        log.info("Routed to email+ad queues | proj_clients=%s cvr=%s",
                                 sim["projected_clients"], sim["conversion_rate"])
        except redis.exceptions.RedisError as e:
            log.error("Redis error: %s", e)
            time.sleep(2)
        except Exception as e:
            log.error("Execution loop error: %s", e)
            time.sleep(2)


if __name__ == "__main__":
    main()
