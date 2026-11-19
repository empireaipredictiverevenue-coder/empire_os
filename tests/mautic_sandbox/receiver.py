"""Isolated synthetic receiver; uses the REAL EmpireOS Mautic HMAC adapter.

No sends, no external network, no real contact data, no CRM write. An actual
installed Mautic 7 application will POST its queued webhook to this container
on the Docker-internal bridge. Only non-PII proof is stored.
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Load exactly the existing signed-webhook adapter by absolute source path.
# Importing the parent empire_os package would execute unrelated startup
# imports that inspect the production owner's /root/empire_os/.env. A
# sandbox-only, nonroot receiver must never need that home directory.
ADAPTER = "/app/mautic_webhook_review.py"
_spec = importlib.util.spec_from_file_location("isolated_mautic_review", ADAPTER)
if _spec is None or _spec.loader is None:
    raise SystemExit("MAUTIC_REVIEW_ADAPTER_UNAVAILABLE")
_review = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_review)
MAX_BODY_BYTES = _review.MAX_BODY_BYTES
MauticWebhookReviewError = _review.MauticWebhookReviewError
preview_signed_mautic_webhook = _review.preview_signed_mautic_webhook

TENANT = "00000000-0000-0000-0000-000000000101"
PROSPECT = "00000000-0000-0000-0000-000000000201"
PATH = "/v1/revenue-crm/integrations/mautic/ci/events/preview"
RECEIPT = pathlib.Path("/tmp/mautic_native_queue_receipt.json")
SECRET = os.environ.get("MAUTIC_CONTRACT_WEBHOOK_SECRET", "").encode("utf-8")
RETRY_FIRST_ONCE = os.environ.get("MAUTIC_CONTRACT_FORCE_FIRST_RETRY") == "true"
DELIVERY_ATTEMPTS = 0
if len(SECRET) < 32:
    raise SystemExit("SYNTHETIC_TEST_SECRET_MISSING")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return
        self._reply(200, {"ok": True, "sender_enabled": False})

    def do_POST(self) -> None:
        if self.path != PATH:
            self._reply(404, {"status": "not_found"})
            return
        signatures = self.headers.get_all("Webhook-Signature", [])
        try:
            size = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            size = -1
        if (
            len(signatures) != 1 or size < 1 or size > MAX_BODY_BYTES
            or self.headers.get_content_type() != "application/json"
        ):
            self._reply(400, {"status": "invalid_request"})
            return
        raw = self.rfile.read(size)
        try:
            result = preview_signed_mautic_webhook(
                raw_body=raw,
                signature=signatures[0],
                secret=SECRET,
                authenticated_tenant_id=TENANT,
                trusted_contact_bindings={
                    42: {"tenant_id": TENANT, "prospect_id": PROSPECT}
                },
                now=datetime.now(timezone.utc),
            )
        except MauticWebhookReviewError:
            self._reply(401, {"status": "signature_or_payload_rejected"})
            return
        if (
            result["unbound_event_count"] != 0
            or result["bound_event_count"] != 1
            or result["signals"][0]["signal"] != "SUPPRESSION_REVIEW_REQUIRED"
            or result["signals"][0]["send_authorized"] is not False
        ):
            self._reply(503, {"status": "canonical_review_not_ready"})
            return
        # Exercise native Mautic queue retry once with a real HTTP 503.
        # The first failed attempt must NOT be acknowledged or persisted
        # as an accepted synthetic review. Only the retry can return 200.
        global DELIVERY_ATTEMPTS
        DELIVERY_ATTEMPTS += 1
        if RETRY_FIRST_ONCE and DELIVERY_ATTEMPTS == 1:
            print("NATIVE_MAUTIC_QUEUE_FIRST_DELIVERY_REJECTED_503", flush=True)
            self._reply(503, {"status": "synthetic_retry_required"})
            return
        # The first successfully authenticated event deliberately receives
        # HTTP 503 in this disposable test: Mautic must retain its real queue
        # row for retry. Never use a 410 (which would disable the source).
        self.server.verified_posts = getattr(self.server, "verified_posts", 0) + 1
        if self.server.verified_posts == 1:
            print("NATIVE_MAUTIC_SIGNED_QUEUE_FIRST_HTTP503_RETRY_REQUIRED", flush=True)
            self._reply(503, {"status": "synthetic_temporary_unavailable"})
            return
        # Store sanitized allowlisted fields only, never the Mautic raw body.
        evidence = result["signals"][0]
        receipt = {
            "signed_webhook_verified": True,
            "producer": "native_mautic_7_queue",
            "source_event": evidence["source_event"],
            "signal": evidence["signal"],
            "timestamp_state": evidence["timestamp_state"],
            "event_evidence_hmac": evidence["event_evidence_hmac"],
            "marketing_consent_verified": False,
            "send_authorized": False,
            "canonical_crm_written": False,
            "native_queue_verified_attempts": self.server.verified_posts,
        }
        RECEIPT.write_text(json.dumps(receipt, sort_keys=True))
        print(
            "NATIVE_MAUTIC_7_SIGNED_QUEUE_HTTP_DELIVERY_ACCEPTED"
            " SUPPRESSION_REVIEW_REQUIRED",
            flush=True,
        )
        self._reply(200, {"status": "accepted", "signed_webhook_verified": True})

    def _reply(self, status: int, data: dict) -> None:
        payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format: str, *_args: object) -> None:
        return


if __name__ == "__main__":
    print("SYNTHETIC_EMPIREOS_MAUTIC_RECEIVER_PRIVATE_NETWORK_ONLY", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8081), Handler).serve_forever()
