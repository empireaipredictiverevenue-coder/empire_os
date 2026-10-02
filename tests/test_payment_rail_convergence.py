from pathlib import Path

import pytest

from empire_os import charge, crypto_charge, ppc_router
from empire_os.agents import billing_collector_agent, finance_agent
from empire_os.agents import legacy_payment_listener_agent
from empire_os.payment_rail_policy import (
    CANONICAL_ASSET,
    CANONICAL_CHAIN_ID,
    CANONICAL_NETWORK,
    RetiredPaymentRailError,
    canonical_payment_rail,
)


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_payment_rail_is_usdt_bsc():
    assert CANONICAL_ASSET == "USDT"
    assert CANONICAL_NETWORK == "BSC"
    assert CANONICAL_CHAIN_ID == 56
    assert canonical_payment_rail()["actual_revenue"] is False


def test_legacy_direct_charge_paths_fail_closed():
    with pytest.raises(RetiredPaymentRailError):
        charge.charge("buyer", 1, "legacy", 100)
    with pytest.raises(RetiredPaymentRailError):
        crypto_charge.charge_crypto()
    with pytest.raises(RetiredPaymentRailError):
        crypto_charge.reconcile_open_invoices()


def test_legacy_listener_and_collector_are_non_executing():
    for payload in (
        legacy_payment_listener_agent.cycle(),
        billing_collector_agent.cycle(),
        finance_agent.cycle(),
        ppc_router.status(),
    ):
        assert payload["status"] == "RETIRED"
        assert payload["asset"] == "USDT"
        assert payload["network"] == "BSC"
        assert payload["execution_allowed"] is False
        assert payload["actual_revenue"] is False


def test_active_hub_does_not_import_legacy_billing_or_payout_modules():
    text = (ROOT / "empire_os/hub.py").read_text()
    assert "from empire_os.billing import" not in text
    assert "from empire_os.billing_webhooks import" not in text
    assert "from empire_os.payout_batch import" not in text
    assert "billing_engine = BillingEngine()" not in text
    assert "payout_batch_store = PayoutBatchStore()" not in text


def test_buyer_facing_legacy_copy_has_no_usdc_or_solana_payment_instruction():
    paths = (
        ROOT / "empire_os/agents/outreach_runner.py",
        ROOT / "empire_os/agents/lead_handler_agent.py",
        ROOT / "empire_os/agents/cinematic_lp_agent.py",
    )
    for path in paths:
        text = path.read_text()
        assert "USDC" not in text
        assert " on Solana" not in text
        assert "solana:" not in text


def test_retired_service_files_are_safe_noops():
    for relative in (
        "empire-ppc-billing-collector.service",
        "ppc_router.service",
    ):
        text = (ROOT / relative).read_text()
        assert "USDT" in text
        assert "/bin/true" in text
        assert "Restart=always" not in text


def test_canonical_payment_modules_remain_bsc_usdt():
    governance = (ROOT / "empire_os/payment_governance.py").read_text()
    verifier = (ROOT / "empire_os/bsc_usdt_verifier.py").read_text()
    checkout = (ROOT / "empire_os/self_serve_checkout.py").read_text()
    assert "amount_usdt" in governance
    assert "BSC_MAINNET_CHAIN_ID = 56" in verifier
    assert 'settlement_asset": "USDT"' in checkout
    assert 'settlement_network": "BSC"' in checkout
