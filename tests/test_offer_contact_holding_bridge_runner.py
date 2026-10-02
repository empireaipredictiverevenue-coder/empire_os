from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runner_is_fail_closed_before_canonical_promotion():
    text = (
        ROOT / "scripts/bridge_offer_contacts_to_buyer_holding.py"
    ).read_text()
    assert 'cur.execute("SET TRANSACTION READ ONLY")' in text
    assert "do_smtp_probe=False" in text
    assert "/rest/v1/rpc/propose_buyer_scout_candidate" in text
    assert "materialize_review_readiness(" in text
    assert '"canonical_promotion_performed": False' in text
    assert '"outbound_authorized": False' in text
    assert "promote_buyer_scout_candidate_to_prospect" not in text


def test_runner_counts_existing_review_ready_rpc_state():
    text = (
        ROOT / "scripts/bridge_offer_contacts_to_buyer_holding.py"
    ).read_text()
    assert '"review_state") == "review_ready"' in text
    assert '"reconciliation_state") == "REVIEW_READY"' in text
    assert '"governed_promotion_candidate_ids"' in text
    assert '"founder_promotion_required": bool(args.persist and ready_ids)' in text
