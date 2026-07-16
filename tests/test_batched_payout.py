"""Tests for batched payout transactions."""
from unittest.mock import MagicMock, patch
import json

import pytest

from empire_os.batched_payout import (
    build_spl_transfer_ix, derive_associated_token_address,
    build_batched_payout_tx, verify_batched_payout_tx,
    SPL_TOKEN_PROGRAM_ID, SPL_TRANSFER_DISCRIMINATOR, USDC_DECIMALS,
    BatchedPayout,
)


class TestSPLTransfer:
    def test_discriminator_byte(self):
        assert SPL_TRANSFER_DISCRIMINATOR[0] == 12  # SPL Token Transfer

    def test_build_ix_data_layout(self):
        data = build_spl_transfer_ix(
            source_ata="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            dest_ata="So11111111111111111111111111111111111111112",
            owner="9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
            amount_raw=1000000,  # 1 USDC
        )
        # 1 byte discriminator + 8 bytes amount + 32 + 32 + 32 = 105 bytes
        assert len(data) == 1 + 8 + 32 + 32 + 32
        assert data[0] == 12  # discriminator
        # Next 8 bytes are amount in little-endian
        assert int.from_bytes(data[1:9], "little") == 1000000


class TestBuildBatchedTx:
    def test_empty_payouts(self):
        result = build_batched_payout_tx(
            payouts=[],
            sender_wallet="9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
            mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        )
        assert result.instruction_count == 0
        assert result.total_amount_usdc == 0.0

    def test_single_payout(self):
        payouts = [{
            "payout_id": "p1",
            "destination": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "amount_cents": 50000,  # $500
        }]
        result = build_batched_payout_tx(
            payouts=payouts,
            sender_wallet="9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
            mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        )
        assert result.instruction_count == 1
        assert result.total_amount_cents == 50000
        assert result.total_amount_usdc == 500.0

    def test_skips_zero_amount(self):
        payouts = [
            {"payout_id": "p1", "destination": "So11111111111111111111111111111111111111112",
             "amount_cents": 1000},
            {"payout_id": "p2", "destination": "So11111111111111111111111111111111111111113",
             "amount_cents": 0},  # skip
            {"payout_id": "p3", "destination": "So11111111111111111111111111111111111111114",
             "amount_cents": 5000},
        ]
        result = build_batched_payout_tx(
            payouts=payouts,
            sender_wallet="So11111111111111111111111111111111111111111",
            mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        )
        assert result.instruction_count == 2

    def test_blockhash_fetched(self):
        """The blockhash RPC should be called."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "result": {"value": {"blockhash": "abc123"}}
            }).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = lambda s, *a: None
            mock_urlopen.return_value = mock_resp
            result = build_batched_payout_tx(
                payouts=[{"payout_id": "p1", "destination": "So11111111111111111111111111111111111111112",
                         "amount_cents": 1000}],
                sender_wallet="So11111111111111111111111111111111111111111",
                mint="USDC",
            )
        assert result.recent_blockhash == "abc123"

    def test_solana_pay_url_built(self):
        result = build_batched_payout_tx(
            payouts=[{"payout_id": "p1", "destination": "So11111111111111111111111111111111111111112",
                     "amount_cents": 10000}],
            sender_wallet="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        )
        assert result.solana_pay_url.startswith("solana:")