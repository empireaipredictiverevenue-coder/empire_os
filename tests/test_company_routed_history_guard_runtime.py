from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_company_routed_materializer_reads_history_read_only():
    text = (
        ROOT / "scripts/materialize_company_routed_buyer_review.py"
    ).read_text()
    assert "SET TRANSACTION READ ONLY" in text
    assert "public.outbound_intents" in text
    assert "public.outbound_suppressions" in text


def test_company_routed_service_has_empiredb_environment():
    text = (
        ROOT / "deploy/systemd/empire-company-routed-buyer-review.service"
    ).read_text()
    assert "EnvironmentFile=/etc/empiredb.env" in text
