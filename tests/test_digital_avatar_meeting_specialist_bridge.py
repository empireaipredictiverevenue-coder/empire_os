import pytest

from empire_os.digital_avatar_meeting_specialist_bridge import (
    AvatarSpecialistAdvisory,
    build_avatar_meeting_advisory_packet,
)
from empire_os.digital_avatar_turn import AvatarClaimTruth


def advisory(
    domain,
    *,
    available=True,
    summary="Supported specialist summary.",
    truth=AvatarClaimTruth.VERIFIED,
    evidence_refs=("evidence:1",),
    blockers=(),
    **overrides,
):
    values = {
        "domain": domain,
        "source_component": f"empire.{domain}",
        "summary": summary,
        "truth_class": truth,
        "evidence_refs": tuple(evidence_refs),
        "available": available,
        "blockers": tuple(blockers),
    }
    values.update(overrides)
    return AvatarSpecialistAdvisory(**values)
def test_all_requested_specialists_produce_ready_single_voice_context():
    packet = build_avatar_meeting_advisory_packet(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        required_domains=("pricing", "product"),
        advisories=(
            advisory("product", evidence_refs=("product:1",)),
            advisory("pricing", evidence_refs=("price:1",)),
        ),
    )
    assert packet.response_context_ready is True
    assert packet.unresolved_domains == ()
    assert packet.required_domains == ("pricing", "product")
    assert [x.domain for x in packet.advisories] == [
        "pricing",
        "product",
    ]
    assert packet.single_visible_avatar is True
    assert packet.specialist_speech_execution_allowed is False
    assert packet.execution_authority == "none"


def test_missing_or_unavailable_domain_is_unresolved():
    packet = build_avatar_meeting_advisory_packet(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        required_domains=("pricing", "technical"),
        advisories=(
            advisory(
                "technical",
                available=False,
                summary="",
                evidence_refs=(),
                blockers=("technical_evidence_missing",),
            ),
        ),
    )
    assert packet.response_context_ready is False
    assert packet.unresolved_domains == ("pricing", "technical")
def test_duplicate_domain_fails_closed():
    with pytest.raises(ValueError, match="specialist_owner_ambiguous"):
        build_avatar_meeting_advisory_packet(
            meeting_id="meeting-001",
            avatar_id="avatar-phil-v1",
            required_domains=("pricing",),
            advisories=(
                advisory("pricing", summary="A"),
                advisory("pricing", summary="B"),
            ),
        )


def test_available_advisory_requires_evidence():
    with pytest.raises(
        ValueError,
        match="available specialist evidence refs required",
    ):
        build_avatar_meeting_advisory_packet(
            meeting_id="meeting-001",
            avatar_id="avatar-phil-v1",
            required_domains=("pricing",),
            advisories=(
                advisory("pricing", evidence_refs=()),
            ),
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"execution_authority": "live"}, "execution authority forbidden"),
        ({"external_action_performed": True}, "external action forbidden"),
        ({"commercial_authority": "quote"}, "commercial authority forbidden"),
        ({"financial_authority": "payment"}, "financial authority forbidden"),
        (
            {"private_chain_of_thought_persisted": True},
            "private chain-of-thought forbidden",
        ),
    ],
)
def test_authority_bearing_specialist_is_rejected(overrides, message):
    with pytest.raises(ValueError, match=message):
        build_avatar_meeting_advisory_packet(
            meeting_id="meeting-001",
            avatar_id="avatar-phil-v1",
            required_domains=("pricing",),
            advisories=(advisory("pricing", **overrides),),
        )
def test_truth_class_is_preserved_not_upgraded():
    packet = build_avatar_meeting_advisory_packet(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        required_domains=("future_trend",),
        advisories=(
            advisory(
                "future_trend",
                truth=AvatarClaimTruth.FORECAST,
                evidence_refs=("forecast:model:1",),
            ),
        ),
    )
    payload = packet.as_dict()
    assert payload["advisories"][0]["truth_class"] == "FORECAST"


def test_unrequested_specialist_domain_is_rejected():
    with pytest.raises(ValueError, match="unrequested specialist domain"):
        build_avatar_meeting_advisory_packet(
            meeting_id="meeting-001",
            avatar_id="avatar-phil-v1",
            required_domains=("pricing",),
            advisories=(
                advisory("pricing"),
                advisory("technical"),
            ),
        )


def test_packet_has_no_external_or_commercial_authority():
    packet = build_avatar_meeting_advisory_packet(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        required_domains=("pricing",),
        advisories=(advisory("pricing"),),
    )
    assert packet.provider_call_performed is False
    assert packet.external_action_performed is False
    assert packet.commercial_authority == "none"
    assert packet.financial_authority == "none"
    assert packet.execution_authority == "none"
