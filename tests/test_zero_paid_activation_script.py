from pathlib import Path

TEXT = Path("scripts/activate_zero_paid_revenue_runtime.sh").read_text()


def test_activation_applies_only_approved_migrations_and_zero_paid_releases():
    assert "025_owned_campaign_intake.sql" in TEXT
    assert "026_a2a_commercial_intent_authority.sql" in TEXT
    assert "release_owned_campaigns.py" in TEXT
    assert "release_aeo_cohort.py" in TEXT
    assert "--page general_contractor:NYC" in TEXT
    assert "--page hvac:DFW" in TEXT
    assert "--page roofing:DFW" in TEXT


def test_activation_keeps_outbound_payment_and_paid_traffic_out():
    assert "Seth" not in TEXT
    assert "Kieran" not in TEXT
    assert "RESEND" not in TEXT
    assert "payment.execute" not in TEXT
    assert "paid_media" not in TEXT.lower()


def test_activation_live_verifies_before_marking_a2a_activated():
    signed = TEXT.index("A2A_SIGNED_LOOPBACK=PASS")
    flag = TEXT.index("EMPIRE_A2A_LIVE_VERIFIED=true")
    assert signed < flag
    assert "execution_authority" in TEXT
    assert "payment_authority" in TEXT
    assert "allocation_authority" in TEXT


def test_activation_finishes_with_live_verifier():
    assert "verify_zero_paid_revenue_activation.py" in TEXT
    assert "ZERO_PAID_REVENUE_ACTIVATION=PASS" in TEXT
