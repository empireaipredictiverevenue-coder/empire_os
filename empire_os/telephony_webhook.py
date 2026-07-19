#!/usr/bin/env python3
"""telephony_webhook — carrier webhook sidecar for Empire OS.

Receives carrier telephony webhooks (Twilio/Telnyx/Ringba compatible) and
forwards them to the hub's canonical ledger at /v1/ppc/log_charge. It does
NOT sign Solana transactions — money movement stays inside the hub's
verified billing path (solana_listener + billing_collector). This keeps the
hot-wallet out of the webhook path (watchdog rule: no unverified payout).

Optional: mirror the event to Supabase call_logs + a CRM webhook if those
env vars are set. These are ledger/CRM writes only — no chain signing.

Run: uvicorn empire_os.telephony_webhook:app --port 9100
"""
from __future__ import annotations
import os, json, logging, asyncio, hmac, hashlib
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("empire_telephony_webhook")

HUB_URL = os.getenv("HUB_URL", "http://127.0.0.1:8081").rstrip("/")
CRM_API_URL = os.getenv("CRM_API_URL", "")
CRM_API_KEY = os.getenv("CRM_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
# Shared secret the carrier uses to sign webhooks (HMAC-SHA256 over raw body).
# When unset, signature checks are skipped (local/dev only).
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# Map a carrier call status -> ppc head (1=call/90s, 4=appointment, etc.)
# Defaults to head 1 (pay-per-call) since this is a telephony webhook.
HEAD_BY_STATUS = {
    "completed": 1,
    "answered": 1,
    "no-answer": 0,
    "busy": 0,
    "failed": 0,
    "appointmented": 4,
}


def verify_signature(raw_body: bytes, provided_sig: str | None) -> bool:
    """HMAC-SHA256 verification (Twilio/Telnyx/Ringba-compatible pattern).

    Carrier computes HMAC-SHA256(secret, raw_body) and sends it in the
    X-Signature header (hex). Rejects tampered/forged webhooks before they
    can reach the billing ledger. Returns True when no secret is configured
    (dev mode) so local testing is unaffected.
    """
    if not WEBHOOK_SECRET:
        return True
    if not provided_sig:
        return False
    expected = hmac.new(WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided_sig)


class TelephonyWebhookPayload(BaseModel):
    call_sid: str
    caller_number: str
    destination_number: str
    duration: int = 0
    status: str = "completed"
    payout: float = 0.0
    publisher_wallet_ata: str = ""   # kept for audit; NOT used to sign
    recording_url: Optional[str] = None
    lead_id: Optional[str] = None
    buyer_id: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=10.0)
    yield
    await app.state.http_client.aclose()


app = FastAPI(lifespan=lifespan)


async def forward_to_hub(http_client: httpx.AsyncClient, p: TelephonyWebhookPayload):
    """POST the charge to the hub's canonical ledger. No signing."""
    head = HEAD_BY_STATUS.get(p.status, 1)
    body = {
        "charge_id": f"call-{p.call_sid}",
        "buyer_id": p.buyer_id or p.destination_number,
        "processor": "carrier_webhook",
        "customer_ref": p.caller_number,
        "payment_ref": p.publisher_wallet_ata or "",
        "head": head,
        "reason": f"telephony {p.status} {p.duration}s",
        "amount_cents": int(p.payout * 100),
        "currency": "USD",
        "status": "open" if p.payout > 0 else "pending",
        "lead_id": p.lead_id or "",
        "call_id": p.call_sid,
        "metadata": json.dumps({"recording_url": p.recording_url or ""})[:500],
    }
    try:
        r = await http_client.post(f"{HUB_URL}/v1/ppc/log_charge", json=body)
        r.raise_for_status()
        logger.info("hub ledger updated for call %s -> %s", p.call_sid, r.status_code)
    except Exception as e:
        logger.error("hub forward failed for %s: %s", p.call_sid, e)


async def write_to_supabase(http_client: httpx.AsyncClient, p: TelephonyWebhookPayload):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
               "Content-Type": "application/json", "Prefer": "return=minimal"}
    data = {"call_sid": p.call_sid, "caller_number": p.caller_number,
            "destination_number": p.destination_number, "duration": p.duration,
            "status": p.status, "payout": p.payout,
            "recording_url": p.recording_url}
    try:
        await http_client.post(f"{SUPABASE_URL}/rest/v1/call_logs", json=data, headers=headers)
    except Exception as e:
        logger.error("supabase write failed: %s", e)


async def write_to_crm(http_client: httpx.AsyncClient, p: TelephonyWebhookPayload):
    if not CRM_API_URL or not CRM_API_KEY:
        return
    headers = {"Authorization": f"Bearer {CRM_API_KEY}", "Content-Type": "application/json"}
    data = {"lead_id": p.call_sid, "caller_phone": p.caller_number,
            "target_phone": p.destination_number, "duration_seconds": p.duration,
            "call_status": p.status, "commission_usd": p.payout,
            "call_recording_url": p.recording_url}
    try:
        await http_client.post(CRM_API_URL, json=data, headers=headers)
    except Exception as e:
        logger.error("crm sync failed: %s", e)


@app.post("/telephony/webhook")
async def receive_carrier_webhook(request: Request, p: TelephonyWebhookPayload, background_tasks: BackgroundTasks):
    raw = await request.body()
    sig = request.headers.get("X-Signature") or request.headers.get("X-Twilio-Signature")
    if not verify_signature(raw, sig):
        logger.warning("rejected webhook with bad/missing signature")
        raise HTTPException(status_code=401, detail="invalid signature")
    http_client = app.state.http_client
    # Hub ledger is the source of truth for billing — do it first.
    background_tasks.add_task(forward_to_hub, http_client, p)
    # Optional mirrors (no chain signing).
    background_tasks.add_task(write_to_supabase, http_client, p)
    background_tasks.add_task(write_to_crm, http_client, p)
    return {"status": "processing", "call_sid": p.call_sid}


@app.get("/health")
async def health():
    return {"status": "ok", "hub": HUB_URL}
