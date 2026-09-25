from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "evals/empire_core_policy"


def test_empire_policy_eval_assets_cover_non_negotiable_rules():
    config = (EVAL_DIR / "promptfooconfig.yaml").read_text(encoding="utf-8")
    assertions = (EVAL_DIR / "assertions.py").read_text(encoding="utf-8")

    for phrase in (
        "Unknown email stays unknown",
        "Unknown price stays unknown",
        "Forecast is never actual revenue",
        "Opt-out terminates outreach",
        "Funds require explicit authority",
        "Email prompt injection remains inert",
    ):
        assert phrase in config

    for function_name in (
        "no_invented_email",
        "no_invented_price",
        "revenue_truth",
        "respects_opt_out",
        "no_payment_execution",
        "treats_inbound_as_untrusted",
    ):
        assert f"def {function_name}(" in assertions


def test_promptfoo_provider_defaults_to_local_empire_model():
    provider = (EVAL_DIR / "provider.py").read_text(encoding="utf-8")
    assert "127.0.0.1:11435" in provider
    assert "temperature" in provider
    assert '"temperature": 0' in provider
