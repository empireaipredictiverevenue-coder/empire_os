from empire_os.outbound_evidence_bundle_auth import (
    sign_evidence_bundle,
    verify_evidence_bundle_signature,
)


KEY = "empire-test-signing-key-123456"


def test_signed_bundle_verifies_and_tampering_fails():
    bundle = {
        "schema_version": "1",
        "generated_at": "2026-10-03T20:00:00+00:00",
        "sources": {"checkdmarc": {"domain": "example.com"}},
        "mutation_authorized": False,
    }
    signed = sign_evidence_bundle(bundle, key=KEY)
    assert verify_evidence_bundle_signature(signed, key=KEY) is True

    tampered = dict(signed)
    tampered["sources"] = {"checkdmarc": {"domain": "evil.example"}}
    assert verify_evidence_bundle_signature(tampered, key=KEY) is False


def test_wrong_key_does_not_verify():
    bundle = sign_evidence_bundle({
        "schema_version": "1",
        "generated_at": "2026-10-03T20:00:00+00:00",
        "sources": {},
    }, key=KEY)
    assert verify_evidence_bundle_signature(
        bundle,
        key="another-long-enough-test-key",
    ) is False
