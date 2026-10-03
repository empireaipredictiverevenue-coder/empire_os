from empire_os.outbound_evidence_chain import GENESIS, chain_evidence, verify_chain


def test_reputation_passport_chain_detects_tampering():
    one = chain_evidence({"kind": "auth", "spf": True})
    two = chain_evidence(
        {"kind": "placement", "inbox": 0.95},
        previous_hash=one["evidence_hash"],
    )

    valid = verify_chain([one, two])
    assert valid["valid"] is True

    tampered = dict(two)
    tampered["evidence"] = {"kind": "placement", "inbox": 0.10}
    invalid = verify_chain([one, tampered])
    assert invalid["valid"] is False
    assert invalid["reason"] == "evidence_hash_mismatch"


def test_chain_starts_from_genesis():
    row = chain_evidence({"kind": "test"})
    assert row["previous_evidence_hash"] == GENESIS
