import json

from empire_os.digital_avatar_evidence_resolver import (
    CompositeAvatarEvidenceResolver,
    MappingAvatarEvidenceResolver,
    RecallObservationEvidenceResolver,
    build_production_avatar_evidence_resolver,
)


def test_recall_observation_resolver_returns_exact_observed_evidence(tmp_path):
    root = tmp_path / "observations"
    root.mkdir()
    payload = {
        "verification_ref": "recall-verification:msg:1:abc",
        "observation": {
            "evidence_ref": "recall:bot-1:transcript-1:abcdef",
            "text": "Can you deploy this quickly?",
        },
    }
    (root / "q1.json").write_text(json.dumps(payload), encoding="utf-8")

    resolver = RecallObservationEvidenceResolver(root)
    value = resolver.resolve("recall:bot-1:transcript-1:abcdef")
    assert value["content"] == "Can you deploy this quickly?"
    assert value["truth_class"] == "OBSERVED"
    assert value["verified"] is True
    assert value["provenance"] == "recall-verification:msg:1:abc"


def test_recall_resolver_does_not_match_partial_or_other_refs(tmp_path):
    root = tmp_path / "observations"
    root.mkdir()
    (root / "q1.json").write_text(json.dumps({
        "verification_ref": "recall-verification:msg:1:abc",
        "observation": {
            "evidence_ref": "recall:bot-1:transcript-1:abcdef",
            "text": "Hello",
        },
    }))
    resolver = RecallObservationEvidenceResolver(root)
    assert resolver.resolve("recall:bot-1:transcript-1") is None
    assert resolver.resolve("terms:pilot:v1") is None


def test_composite_resolver_falls_through_to_canonical_mapping(tmp_path):
    recall = RecallObservationEvidenceResolver(tmp_path / "missing")
    canonical = MappingAvatarEvidenceResolver({
        "terms:pilot:v1": {
            "evidence_ref": "terms:pilot:v1",
            "content": "Approved pilot terms are available.",
            "truth_class": "VERIFIED",
            "source_kind": "commercial_terms",
            "provenance": "terms-registry:v1",
            "verified": True,
        }
    })
    resolver = CompositeAvatarEvidenceResolver((recall, canonical))
    value = resolver.resolve("terms:pilot:v1")
    assert value["source_kind"] == "commercial_terms"
    assert value["verified"] is True


class FakeCanonicalGateway:
    def __init__(self):
        self.query_calls = []
        self.rpc_calls = []

    def query(self, table, columns, **kwargs):
        self.query_calls.append((table, columns, kwargs))
        if table == "commercial_evidence_registry":
            return [{
                "id": "11111111-1111-4111-8111-111111111111",
                "evidence_kind": "price",
                "niche": "roofing",
                "metro": "London",
                "amount_cents": 49900,
                "currency": "USD",
                "unit": "per_month",
                "source_type": "founder_approved",
                "status": "verified",
                "valid_until": "2027-01-01T00:00:00+00:00",
                "verified_at": "2026-10-01T12:00:00+00:00",
            }]
        return []

    def rpc(self, name, params=None):
        self.rpc_calls.append((name, params))
        return None


def test_production_resolver_combines_recall_and_canonical_price(tmp_path):
    root = tmp_path / "observations"
    root.mkdir()
    recall_ref = "recall:bot-1:transcript-1:abcdef"
    (root / "q1.json").write_text(json.dumps({
        "verification_ref": "recall-verification:msg:1:abc",
        "observation": {
            "evidence_ref": recall_ref,
            "text": "What does it cost?",
        },
    }))

    gateway = FakeCanonicalGateway()
    resolver = build_production_avatar_evidence_resolver(
        observation_root=root,
        gateway=gateway,
    )

    recall = resolver.resolve(recall_ref)
    price = resolver.resolve(
        "commercial_evidence:11111111-1111-4111-8111-111111111111"
    )
    assert recall["source_kind"] == "meeting_transcript"
    assert price["source_kind"] == "commercial_price"
    assert "$499.00 USD" in price["content"]
