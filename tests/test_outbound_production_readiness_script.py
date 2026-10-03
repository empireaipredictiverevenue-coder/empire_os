from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/verify_outbound_production_readiness.sh"


def test_production_readiness_wrapper_is_read_only_and_uses_canonical_doctor():
    text = PATH.read_text(encoding="utf-8")
    lowered = text.lower()

    assert "no migration / no role change / no service change / no send" in lowered
    assert "empire_os.outbound_production_doctor" in text
    assert "exec ./.venv/bin/python -m empire_os.outbound_production_doctor" in text

    for forbidden in (
        "systemctl start ",
        "systemctl restart ",
        "systemctl enable ",
        "systemctl disable ",
        "systemctl stop ",
        "psql ",
        "cloudflare",
        "claim_outbound_send",
        "approve_outbound_intent",
    ):
        assert forbidden not in lowered


def test_production_readiness_wrapper_contains_no_duplicate_gate_logic():
    text = PATH.read_text(encoding="utf-8")
    assert "outbound_release_attestation" not in text
    assert "outbound_empiredb_activation_probe" not in text
    assert "curl " not in text
    assert "systemctl is-active" not in text
