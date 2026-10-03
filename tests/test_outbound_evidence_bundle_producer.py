from datetime import datetime, timezone

import pytest

from empire_os.outbound_evidence_bundle import load_evidence_bundle
from empire_os.outbound_evidence_bundle_producer import (
    atomic_write_evidence_bundle,
    build_evidence_bundle,
)


NOW = datetime(2026, 10, 3, 20, 0, tzinfo=timezone.utc)
KEY = "empire-test-signing-key-123456"


def test_producer_builds_signed_bundle_that_loader_accepts(tmp_path):
    bundle = build_evidence_bundle(
        {
            "checkdmarc": {
                "domain": "example.com",
                "spf": {"valid": True},
                "dmarc": {"valid": True},
            },
            "dnscontrol_preview": [],
        },
        generated_at=NOW,
        signing_key=KEY,
    )
    path = tmp_path / "evidence.json"
    result = atomic_write_evidence_bundle(path, bundle)
    loaded = load_evidence_bundle(
        path,
        now=NOW,
        hmac_key=KEY,
        require_signature=True,
    )
    assert result["mutation_authorized"] is False
    assert loaded["status"] == "CURRENT"
    assert loaded["signature_status"] == "VERIFIED"


def test_producer_rejects_unknown_source():
    with pytest.raises(ValueError, match="unsupported_evidence_sources"):
        build_evidence_bundle(
            {"untrusted_tool": {"x": 1}},
            generated_at=NOW,
        )


def test_writer_does_not_create_missing_parent(tmp_path):
    bundle = build_evidence_bundle({}, generated_at=NOW)
    with pytest.raises(RuntimeError, match="parent_missing"):
        atomic_write_evidence_bundle(
            tmp_path / "missing" / "evidence.json",
            bundle,
        )


def test_writer_rejects_symlink_target(tmp_path):
    original = tmp_path / "real.json"
    original.write_text("{}\n", encoding="utf-8")
    link = tmp_path / "evidence.json"
    link.symlink_to(original)

    bundle = build_evidence_bundle({}, generated_at=NOW)
    with pytest.raises(RuntimeError, match="symlink_forbidden"):
        atomic_write_evidence_bundle(link, bundle)
