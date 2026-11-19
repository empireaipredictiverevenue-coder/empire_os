"""Optional execution of the *unmodified* pinned Mautic 7 PHP sender.

This exercises official Mautic WebhookBundle/Http/Client.php, not an invented
Python HMAC emulator. It requires an explicit isolated PHP CLI and a checked
upstream source file. No live Mautic app/DB, no email, no outbound HTTP.
The actual official PHP Client is loaded and its HTTP request intercepted.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.mautic_crm_integration import (
    MauticSource, SqliteMauticReceiptJournal, create_mautic_crm_preview_router,
)

UPSTREAM_CLIENT_SHA256 = (
    "d33316dcb61c6350856316941ca39f9369d3d7783c0141fd667f63b7fe75813c"
)
TENANT = "00000000-0000-0000-0000-000000000101"
PROSPECT = "00000000-0000-0000-0000-000000000201"
SECRET = b"only-synthetic-mautic-contract-secret-20261119"
NOW = datetime(2026, 11, 19, 11, tzinfo=timezone.utc)
SCRIPT = Path(__file__).resolve().parents[1] / (
    "tests/mautic_sandbox/verify_upstream_client.php"
)
PHP_BIN = os.environ.get("EMPIRE_MAUTIC_TEST_PHP_BIN")
PHP_SOURCE = os.environ.get("EMPIRE_MAUTIC_TEST_UPSTREAM_CLIENT")

if not (PHP_BIN and PHP_SOURCE):
    pytest.skip(
        "Official PHP source+CLI contract is opt-in; no executable in production",
        allow_module_level=True,
    )


class SyntheticCrm:
    tenant_id = TENANT

    def prospect(self, prospect_id):
        if prospect_id != PROSPECT:
            return None
        return {
            "tenant_id": TENANT,
            "prospect_id": PROSPECT,
            "prospect_status": "suppressed",
            "conversation_state": "engaged",
        }


def test_unmodified_upstream_php_client_signs_raw_json_consumed_by_crm():
    binary = Path(PHP_BIN)
    upstream = Path(PHP_SOURCE)
    assert binary.is_file() and upstream.is_file()
    assert upstream.stat().st_size < 25000
    assert hashlib.sha256(upstream.read_bytes()).hexdigest() == UPSTREAM_CLIENT_SHA256
    assert SCRIPT.is_file()
    result = subprocess.run(
        [str(binary), "-n", str(SCRIPT), str(upstream)],
        capture_output=True, text=True,
        check=True, timeout=15,
    )
    request = json.loads(result.stdout)
    assert request["method"] == "POST"
    assert request["url"] == "https://synthetic-receiver.example.invalid/preview"
    assert request["source_header_verified"] is True
    assert request["raw_body_signed_by_upstream_php_client"] is True
    body = base64.b64decode(request["body_base64"], validate=True)
    data = json.loads(body)
    assert data["mautic.lead_channel_subscription_changed"][0]["new_status"] == "unsubscribed"
    signature = request["webhook_signature"]

    with tempfile.TemporaryDirectory(prefix="mautic_php_contract_") as private:
        journal = SqliteMauticReceiptJournal(Path(private) / "receipts.sqlite")
        source = MauticSource(
            source_id="official-php-contract",
            tenant_id=TENANT, webhook_secret=SECRET,
            contact_bindings={
                42: {"tenant_id": TENANT, "prospect_id": PROSPECT}
            },
        )
        app = FastAPI()
        app.include_router(create_mautic_crm_preview_router(
            resolve_source=lambda sid: (
                source if sid == "official-php-contract" else None
            ),
            resolve_tenant_reader=lambda tenant: (
                SyntheticCrm() if tenant == TENANT else None
            ),
            receipt_journal=journal,
            allow_synthetic_test_reader=True,
            now_provider=lambda: NOW,
        ))
        uri = (
            "/v1/revenue-crm/integrations/mautic/"
            "official-php-contract/events/preview"
        )
        headers = {
            "Content-Type": "application/json",
            "Webhook-Signature": signature,
        }
        with TestClient(app) as client:
            first = client.post(uri, content=body, headers=headers)
            assert first.status_code == 200, first.text
            outcome = first.json()
            assert outcome["signed_webhook_verified"] is True
            assert outcome["new_events"] == 1
            assert outcome["journey_reviews"][0]["signal"] == (
                "SUPPRESSION_REVIEW_REQUIRED"
            )
            assert outcome["send_authorized"] is False
            assert outcome["canonical_crm_written"] is False
            assert "synthetic-only@example.invalid" not in first.text
            replay = client.post(uri, content=body, headers=headers)
            assert replay.status_code == 200
            assert replay.json()["duplicate_events"] == 1
            tampered = client.post(uri, content=body + b" ", headers=headers)
            assert tampered.status_code == 401
