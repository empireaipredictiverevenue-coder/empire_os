from pathlib import Path


SCRIPT = Path("scripts/activate_empire_coder_builder.sh")


def test_activation_script_proves_builder_before_batch():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "probe_empire_coder_structured_patch" in text
    assert "builder_capability_snapshot" in text
    assert "run_batch1_pi_fallback.py" in text
    assert 'if [[ "$PROBE_RC" -eq 0 ]]' in text


def test_activation_script_never_deploys_or_sends():
    text = SCRIPT.read_text(encoding="utf-8").lower()
    assert "systemctl restart" not in text
    assert "sendgrid" not in text
    assert "resend" not in text
    assert "payment" not in text
