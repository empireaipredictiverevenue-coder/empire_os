from empire_os.agent_web import (
    a2a_agent_card,
    capability_manifest,
    public_capabilities,
)


def test_agent_card_advertises_each_public_a2a_capability_as_skill():
    card = a2a_agent_card("https://empire-ai.co.uk/")
    capabilities = public_capabilities("a2a")
    assert len(capabilities) == 8
    assert len(card["skills"]) == len(capabilities)

    ids = {skill["id"] for skill in card["skills"]}
    assert ids == {f"empire.{cap.key}" for cap in capabilities}


def test_agent_card_skills_match_public_read_only_manifest():
    card = a2a_agent_card("https://empire-ai.co.uk")
    manifest = {row["name"]: row for row in capability_manifest("a2a")}

    for skill in card["skills"]:
        capability_key = skill["id"].removeprefix("empire.")
        assert capability_key in manifest
        row = manifest[capability_key]
        assert row["annotations"]["readOnlyHint"] is True
        assert row["annotations"]["consequentialHint"] is False
        assert skill["name"] == row["title"]
        assert skill["description"] == row["description"]


def test_agent_card_does_not_advertise_commerce_as_active_skill():
    card = a2a_agent_card("https://empire-ai.co.uk")
    ids = {skill["id"] for skill in card["skills"]}
    assert not any(skill_id.startswith("empire.commerce.") for skill_id in ids)
    assert card["capabilities"]["extendedAgentCard"] is False
