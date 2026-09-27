from pathlib import Path


def test_reconciliation_runner_uses_live_buyer_schema():
    text = Path(
        "scripts/reconcile_buyer_acquisition_scout.py"
    ).read_text()

    assert '"select": "id,buyer_name,email,status,is_active"' in text
    assert '"email": "not.is.null"' in text
    assert "buyer_name,website" not in text
