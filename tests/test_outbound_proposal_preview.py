from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "outbound_proposal_preview.py"


def _write(path: Path, value):
    path.write_text(json.dumps(value))


def test_review_only_bundle_never_authorizes_write(tmp_path):
    candidate = {
        "id": "598006a1-7872-45c5-a1c9-f616bb83bcfc",
        "business_name": "Acme Roofing",
        "niche": "roofing",
        "metro": "Houston",
        "website": "https://acme.example",
        "contact_name": "Frank Smith",
        "contact_title": "Founder",
    }
    contact = {
        "outreach_ready": True,
        "preferred_email": "frank@acme.example",
        "decision_maker": {"name":"Frank Smith","title":"Founder","decision_score":1.0},
    }
    c = tmp_path / "candidate.json"
    p = tmp_path / "contact.json"
    body = tmp_path / "body.txt"
    _write(c, candidate); _write(p, contact)
    body.write_text("Hi Frank\n\nIf this is not relevant, reply unsubscribe.\n123 Test Street, London")
    cmd = [str(ROOT / ".venv/bin/python"), str(SCRIPT), str(c), str(p),
           "--subject", "Quick question", "--body-file", str(body),
           "--postal-address", "123 Test Street, London",
           "--idempotency-key", "preview-0001"]
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=True)
    data = json.loads(result.stdout)
    assert data["decision"] == "review_only"
    assert data["write_authorized"] is False
    assert data["proposal"]["write_authorized"] is False
    assert data["proposal"]["rpc"] == "propose_outbound_intent"


def test_preview_refuses_unverified_contact(tmp_path):
    candidate = {
        "id": "598006a1-7872-45c5-a1c9-f616bb83bcfc",
        "business_name": "Acme Roofing", "niche": "roofing", "website": "https://acme.example",
        "contact_name": "Frank Smith", "contact_title": "Founder",
    }
    contact = {"outreach_ready": False, "preferred_email": None}
    c = tmp_path / "candidate.json"; p = tmp_path / "contact.json"; body = tmp_path / "body.txt"
    _write(c, candidate); _write(p, contact); body.write_text("unsubscribe\n123 Test Street, London")
    result = subprocess.run([
        str(ROOT / ".venv/bin/python"), str(SCRIPT), str(c), str(p),
        "--subject", "Test", "--body-file", str(body),
        "--postal-address", "123 Test Street, London", "--idempotency-key", "preview-0002"
    ], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode != 0
    assert "verified outreach-ready contact required" in result.stderr
