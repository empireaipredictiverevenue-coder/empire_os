"""Founder CLI can review a short summary or exact non-sending sample."""
import json

from empire_os.earned_media_leadgen_review import REQUESTS, _key, DEMAND_DOC
from scripts.review_earned_media_advisory_bridge_20261025 import main
from tests.test_earned_media_leadgen_review_20261025 import _packet


def _args(root, pr):
    return [
        "--review-only", "--with-leadgen", "--repo-root", str(root),
        "--pr-root", str(pr), "--distribution-root", str(root),
    ]


def test_cli_summary_has_evidence_counts_and_no_sales_authority(tmp_path, capsys):
    root, pr, _ = _packet(tmp_path)
    assert main([*_args(root, pr), "--summary"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["lead_counts"]["total"] == 5
    assert result["lead_counts"]["qualified_buyer"] == 0
    assert result["pr_sent_not_reply_verified"] >= 0
    assert result["outbound_authorized"] is False
    assert result["revenue_verified"] is False
    assert result["founder_decision"] == "VERIFY_ONE_FRESH_BUYER_PROBLEM_AND_SOURCE_BEFORE_OUTREACH"
    assert len(result["top_review_actions"]) == 5
    assert all(not x["outreach_authorized"] for x in result["top_review_actions"])


def test_cli_exact_sample_only_after_verified_packet(tmp_path, capsys):
    root, pr, _ = _packet(tmp_path)
    opportunity = _key("public_request", REQUESTS[0]["url"])
    assert main([*_args(root, pr), "--sample-opportunity-id", opportunity]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["lead_id"] == opportunity
    assert result["message_sent"] is False
    assert result["quote_issued"] is False


def test_cli_unknown_id_holds(tmp_path, capsys):
    root, pr, _ = _packet(tmp_path)
    assert main([*_args(root, pr), "--sample-opportunity-id",
                 "leadreview_" + "a"*24]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "HELD_SAMPLE_NOT_VALID"


def test_cli_changed_source_is_held_and_returns_nonzero(tmp_path, capsys):
    root, pr, _ = _packet(tmp_path)
    (root / DEMAND_DOC).write_text("Source withdrawn\n")
    assert main([*_args(root, pr), "--summary"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["leadgen_state"] == "HELD_SOURCE_OR_PACKET_INTEGRITY"
    assert result["top_review_actions"] == []
    assert result["revenue_verified"] is False
