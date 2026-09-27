from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/observability_smoke.py"
PYPROJECT = ROOT / "pyproject.toml"


def test_observability_extra_is_pinned():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert 'observability = [' in text
    assert '"opentelemetry-api==1.44.0"' in text
    assert '"opentelemetry-sdk==1.44.0"' in text
    assert '"opentelemetry-exporter-otlp-proto-http==1.44.0"' in text


def test_observability_smoke_has_no_authority_or_secret_output():
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"execution_authority": "none"' in text
    assert '"revenue_mutation": False' in text
    assert '"payment_action": False' in text
    assert '"outbound_action": False' in text
    assert "LANGFUSE_SECRET_KEY" not in text
    assert "LANGFUSE_PUBLIC_KEY" not in text
