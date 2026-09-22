from scripts.run_voice_outbound_worker import voice_legal_decision


def test_voice_legal_gate_requires_explicit_basis():
    ok, decision = voice_legal_decision({})
    assert ok is False
    assert decision == "HOLD_LEGAL_BASIS_UNVERIFIED"


def test_voice_legal_gate_accepts_written_consent():
    ok, decision = voice_legal_decision({
        "voice_legal_basis": "prior_express_written_consent",
        "line_type": "mobile",
    })
    assert ok is True
    assert decision == "VOICE_LEGAL_BASIS_VERIFIED"


def test_voice_legal_gate_requires_landline_for_b2b_basis():
    ok, decision = voice_legal_decision({
        "voice_legal_basis": "verified_business_landline_b2b",
        "line_type": "mobile",
    })
    assert ok is False
    assert decision == "HOLD_BUSINESS_LANDLINE_UNVERIFIED"

    ok, decision = voice_legal_decision({
        "voice_legal_basis": "verified_business_landline_b2b",
        "line_type": "landline",
    })
    assert ok is True
    assert decision == "VOICE_LEGAL_BASIS_VERIFIED"
