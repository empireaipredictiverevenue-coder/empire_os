from empire_os.digital_avatar_evidence_pack import build_avatar_evidence_pack
from empire_os.digital_avatar_response_task import AvatarRealtimeResponseTask


class Resolver:
    def __init__(self, values):
        self.values = values

    def resolve(self, evidence_ref):
        return self.values.get(evidence_ref)


def task():
    return AvatarRealtimeResponseTask(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        latest_buyer_utterance="Can you show me proof?",
        objective="qualify fit and agree next step",
        recommended_action_key="present_verified_case_evidence",
        approved_evidence_refs=(
            "conversation:turn:7",
            "evidence:case:7",
        ),
        commercial_terms_ref=None,
        constraints=("Private draft only.",),
    )


def test_evidence_pack_resolves_only_approved_refs():
    resolver = Resolver({
        "conversation:turn:7": {
            "evidence_ref": "conversation:turn:7",
            "content": "Buyer asked: Can you show me proof?",
            "truth_class": "OBSERVED",
            "source_kind": "meeting_transcript",
            "provenance": "recall:transcript:456",
            "verified": True,
        },
        "evidence:case:7": {
            "evidence_ref": "evidence:case:7",
            "content": "Verified deployment case evidence is available.",
            "truth_class": "VERIFIED",
            "source_kind": "commercial_evidence",
            "provenance": "empire:evidence:7",
            "verified": True,
        },
        "evidence:not-approved": {
            "evidence_ref": "evidence:not-approved",
            "content": "Should never be loaded.",
            "truth_class": "VERIFIED",
            "source_kind": "test",
            "provenance": "test",
            "verified": True,
        },
    })
    pack = build_avatar_evidence_pack(task=task(), resolver=resolver)
    assert pack.ready_for_drafting is True
    assert pack.unresolved_refs == ()
    assert [x.evidence_ref for x in pack.items] == [
        "conversation:turn:7",
        "evidence:case:7",
    ]
    assert all(x.evidence_ref != "evidence:not-approved" for x in pack.items)


def test_unresolved_required_ref_blocks_drafting():
    resolver = Resolver({
        "conversation:turn:7": {
            "evidence_ref": "conversation:turn:7",
            "content": "Buyer asked: Can you show me proof?",
            "truth_class": "OBSERVED",
            "source_kind": "meeting_transcript",
            "provenance": "recall:transcript:456",
            "verified": True,
        },
    })
    pack = build_avatar_evidence_pack(task=task(), resolver=resolver)
    assert pack.ready_for_drafting is False
    assert pack.unresolved_refs == ("evidence:case:7",)


def test_unverified_verified_claim_is_not_accepted():
    resolver = Resolver({
        "conversation:turn:7": {
            "evidence_ref": "conversation:turn:7",
            "content": "Buyer asked: Can you show me proof?",
            "truth_class": "OBSERVED",
            "source_kind": "meeting_transcript",
            "provenance": "recall:transcript:456",
            "verified": True,
        },
        "evidence:case:7": {
            "evidence_ref": "evidence:case:7",
            "content": "Claimed result.",
            "truth_class": "VERIFIED",
            "source_kind": "commercial_evidence",
            "provenance": "unverified:test",
            "verified": False,
        },
    })
    pack = build_avatar_evidence_pack(task=task(), resolver=resolver)
    assert pack.ready_for_drafting is False
    assert pack.unresolved_refs == ("evidence:case:7",)
