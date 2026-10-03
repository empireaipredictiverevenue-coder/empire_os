import json
import pytest

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_authority import (
    AvatarCloseProposal,
    AvatarCommercialAuthorityPolicy,
)
from empire_os.meeting_gateway import MeetingSpeakerRole
from empire_os.recall_shadow_session import (
    RecallShadowSessionManifest,
    load_recall_shadow_session,
    save_recall_shadow_session,
)


def manifest():
    return RecallShadowSessionManifest(
        identity=DigitalAvatarIdentity(
            avatar_id="avatar-phil-v1",
            owner_name="Phil Livesley",
            display_name="Phil — Empire AI Digital Avatar",
            organisation_name="Empire AI",
            disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
            owner_consent_evidence_ref="consent:phil:avatar:v1",
        ),
        session=AvatarMeetingSession(
            meeting_id="meeting-001",
            avatar_id="avatar-phil-v1",
            provider="recall",
            mode=AvatarMeetingMode.SHADOW,
        ),
        account_name="Example Buyer",
        objective="qualify fit and agree next step",
        recording_consent_evidence_ref="consent:meeting:001",
        proof_refs=("evidence:case:7",),
        commercial_terms_ref="terms:pilot:v1",
        predictive_inputs={"demand": 0.8},
        action_candidates=({"action_key": "ask_deadline"},),
        participant_roles={
            "recall-participant:7": MeetingSpeakerRole.BUYER,
        },
    )


def test_manifest_round_trips_privately(tmp_path):
    path = save_recall_shadow_session(
        root=tmp_path / "sessions",
        manifest=manifest(),
    )
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert oct(path.parent.stat().st_mode & 0o777) == "0o700"

    loaded = load_recall_shadow_session(path)
    assert loaded.session.meeting_id == "meeting-001"
    assert loaded.identity.avatar_id == "avatar-phil-v1"
    assert loaded.account_name == "Example Buyer"
    assert loaded.participant_roles["recall-participant:7"] == (
        MeetingSpeakerRole.BUYER
    )
    raw = json.loads(path.read_text())
    assert raw["canonical_truth_written"] is False
    assert raw["execution_authority"] == "none"


def test_manifest_requires_shadow_mode():
    bad = manifest()
    object.__setattr__(
        bad,
        "session",
        AvatarMeetingSession(
            meeting_id="meeting-001",
            avatar_id="avatar-phil-v1",
            provider="recall",
            mode=AvatarMeetingMode.COPILOT,
        ),
    )
    with pytest.raises(ValueError, match="requires SHADOW mode"):
        bad.validate()


def test_manifest_rejects_avatar_identity_mismatch():
    bad = manifest()
    object.__setattr__(
        bad,
        "session",
        AvatarMeetingSession(
            meeting_id="meeting-001",
            avatar_id="other-avatar",
            provider="recall",
            mode=AvatarMeetingMode.SHADOW,
        ),
    )
    with pytest.raises(ValueError, match="session/avatar identity mismatch"):
        bad.validate()


def test_manifest_requires_recording_consent():
    bad = manifest()
    object.__setattr__(bad, "recording_consent_evidence_ref", "")
    with pytest.raises(ValueError, match="recording consent evidence"):
        bad.validate()


def test_manifest_round_trips_delegated_commercial_envelope(tmp_path):
    value = manifest()
    policy = AvatarCommercialAuthorityPolicy(
        allowed_product_codes=("PREDICTIVE-REVENUE-PILOT",),
        approved_terms_refs=("terms:pilot:v1",),
        allowed_currencies=("USD",),
        max_discount_bps=1000,
        max_contract_months=3,
    )
    proposal = AvatarCloseProposal(
        product_code="PREDICTIVE-REVENUE-PILOT",
        list_price_cents=500000,
        proposed_price_cents=475000,
        currency="USD",
        contract_months=1,
        terms_ref="terms:pilot:v1",
        evidence_refs=(
            "commercial_product_code:PREDICTIVE-REVENUE-PILOT",
            "commercial_evidence:11111111-1111-4111-8111-111111111111",
        ),
    )
    object.__setattr__(value, "commercial_policy", policy)
    object.__setattr__(value, "close_proposal", proposal)

    path = save_recall_shadow_session(
        root=tmp_path / "sessions",
        manifest=value,
    )
    loaded = load_recall_shadow_session(path)
    assert loaded.commercial_policy.max_discount_bps == 1000
    assert loaded.close_proposal.proposed_price_cents == 475000
    assert loaded.close_proposal.terms_ref == "terms:pilot:v1"
    raw = json.loads(path.read_text())
    assert raw["commercial_policy"]["max_contract_months"] == 3
    assert raw["close_proposal"]["evidence_refs"][0].startswith(
        "commercial_product_code:"
    )


def test_manifest_rejects_unpaired_commercial_envelope():
    value = manifest()
    object.__setattr__(
        value,
        "commercial_policy",
        AvatarCommercialAuthorityPolicy(
            allowed_product_codes=("PREDICTIVE-REVENUE-PILOT",),
            approved_terms_refs=("terms:pilot:v1",),
        ),
    )
    with pytest.raises(ValueError, match="must be paired"):
        value.validate()
