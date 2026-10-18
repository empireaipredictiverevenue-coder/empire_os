"""The founder-reviewed solar proposal is permanently non-activating."""
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
DRAFT = HERE / "docs/evidence/organic-release-20261018/solar-measurement-DRAFT-UNAPPROVED.json"


def test_proposal_requires_real_owner_approvals():
    proposal = json.loads(DRAFT.read_text("utf-8"))
    assert proposal["status"] == "DRAFT_UNAPPROVED"
    assert proposal["execution_authority"] == "none"
    assert proposal["automatic_publication"] is False
    assert proposal["automatic_outbound"] is False
    assert proposal["payments_enabled"] is False
    assert proposal["reviews"] == {}
    assert proposal["deployment_evidence_ref"] is None
    assert proposal["readiness"]["event_capture_active"] is False
    for name in ("founder", "privacy", "collector", "live_deployment"):
        assert proposal["readiness"][name + ("_review_approved" if name != "live_deployment" else "_verified")] is False


def test_solar_proposal_binds_one_exact_sector_hash_and_no_buyer_claim():
    proposal = json.loads(DRAFT.read_text("utf-8"))
    assert len(proposal["campaigns"]) == 1
    item = proposal["campaigns"][0]
    cid = "campaign_f6f952e135656e0568e136bb"
    assert item["campaign_id"] == cid
    assert item["asset_id"] == cid + ":landing"
    assert item["landing_path"] == "/industries/solar"
    assert item["sector"] == "solar"
    assert item["html_sha256"] == "a4525081072f3aaf83cd6fd760491fe4ea48199dacd8ebb448033b275600b40e"
    assert item["source_evidence_ref"].startswith("govuk:")
    assert proposal["readiness"]["crm_conversions_verified"] is False
