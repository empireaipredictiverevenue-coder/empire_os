"""Tests for BSC USDT batched payout deeplink building."""
from empire_os.batched_payout import build_batched_payout_tx, verify_batched_payout_tx


class TestBuildBatchedTx:
    def test_empty_payouts(self):
        result = build_batched_payout_tx(
            payouts=[],
            sender_wallet="0x1339b487046B0ad924a10c20b1791608EA8595a8",
            mint="0x55d398326f99059fF775485246999027B3197955",
        )
        assert result.instruction_count == 0
        assert result.total_amount_usdc == 0.0
        assert result.bsc_pay_url == ""

    def test_single_payout(self):
        payouts = [{
            "payout_id": "p1",
            "destination": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "amount_cents": 50000,  # $500
        }]
        result = build_batched_payout_tx(
            payouts=payouts,
            sender_wallet="0x1339b487046B0ad924a10c20b1791608EA8595a8",
            mint="0x55d398326f99059fF775485246999027B3197955",
        )
        assert result.instruction_count == 1
        assert result.total_amount_cents == 50000
        assert result.total_amount_usdc == 500.0
        assert result.bsc_pay_url.startswith("bsc:")
        assert "0x1339b487046B0ad924a10c20b1791608EA8595a8" in result.bsc_pay_url

    def test_skips_zero_amount(self):
        payouts = [
            {"payout_id": "p1", "destination": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
             "amount_cents": 1000},
            {"payout_id": "p2", "destination": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
             "amount_cents": 0},
            {"payout_id": "p3", "destination": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
             "amount_cents": 5000},
        ]
        result = build_batched_payout_tx(
            payouts=payouts,
            sender_wallet="0x1339b487046B0ad924a10c20b1791608EA8595a8",
            mint="0x55d398326f99059fF775485246999027B3197955",
        )
        assert result.instruction_count == 2
        assert result.total_amount_cents == 6000
