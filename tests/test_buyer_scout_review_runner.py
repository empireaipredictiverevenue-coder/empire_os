from pathlib import Path


def test_review_readiness_runner_uses_supported_request_json_prefer():
    text = Path(
        "scripts/materialize_buyer_scout_review_readiness.py"
    ).read_text()

    assert 'prefer="return=representation"' in text
    assert "headers=" not in text
