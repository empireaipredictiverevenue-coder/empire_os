#!/usr/bin/env python3
"""queue_sender.py — drains Empire AI outgoing Redis queues into live senders.

Layer 17 downstream consumer:
  outgoing_emails -> Brevo (empire_os.mail_sender._brevo_api_send)
  outgoing_ads    -> Meta/Native ad API hook (stub -> logs; wire real creds later)

Self-hosted, runs inside Incus container on empire-net. No managed cloud.
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
    print("redis not installed; /root/venv/bin/python3 -m pip install redis")
    raise

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("queue_sender")

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
EMAIL_QUEUE = "outgoing_emails"
AD_QUEUE = "outgoing_ads"
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

# Brevo sender
try:
    from empire_os.mail_sender import _brevo_api_send
    BREVO_OK = True
except Exception as e:
    BREVO_OK = False
    log.warning("Brevo sender unavailable: %s", e)


def send_email(payload: dict) -> dict:
    target = payload.get("target") or payload.get("to_email")
    subject = payload.get("subject", "")
    body = payload.get("body", "")
    if not target:
        return {"ok": False, "error": "no target"}
    if BREVO_OK:
        res = _brevo_api_send(target, subject, body)
        return {"ok": True, "brevo": res}
    return {"ok": False, "error": "brevo_unavailable"}


def send_ad(payload: dict) -> dict:
    """Meta/Native ad hook. Logs payload; wire real API when creds present."""
    niche = payload.get("niche")
    headline = payload.get("headline")
    # TODO: replace with real Meta Marketing API / native ad network call
    log.info("AD -> niche=%s headline=%s (stub: wire Meta/Native API)", niche, headline)
    return {"ok": True, "status": "logged", "niche": niche}


def main():
    log.info("Queue sender online. Draining %s + %s", EMAIL_QUEUE, AD_QUEUE)
    while True:
        try:
            # blocking pop (BRPOP) with timeout
            ev = r.brpop([EMAIL_QUEUE, AD_QUEUE], timeout=2)
            if not ev:
                continue
            qname, raw = ev
            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                log.warning("bad payload on %s", qname)
                continue
            if qname == EMAIL_QUEUE:
                res = send_email(payload)
                log.info("EMAIL -> %s : %s", payload.get("target"), res.get("ok"))
            else:
                res = send_ad(payload)
                log.info("AD processed: %s", res.get("status"))
        except redis.exceptions.RedisError as e:
            log.error("Redis error: %s", e)
            time.sleep(2)
        except Exception as e:
            log.error("Loop error: %s", e)
            time.sleep(2)


if __name__ == "__main__":
    main()
