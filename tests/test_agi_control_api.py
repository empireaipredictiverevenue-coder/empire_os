from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.agi_control_api import create_agi_control_router


def client():
    app = FastAPI()
    app.include_router(create_agi_control_router())
    return TestClient(app)


def test_health_does_not_claim_human_level_agi():
    body = client().get("/v1/agi-control/health").json()
    assert body["human_level_agi_claimed"] is False
    assert body["asi_claimed"] is False
    assert body["consequential_autonomy"] is False
    assert body["execution_authority"] == "none"


def test_cognitive_packet_preview_is_non_executing():
    response = client().post(
        "/v1/agi-control/cognitive-packet/preview",
        json={
            "task_id": "task-1",
            "goal": "Review market opportunity",
            "evidence_refs": ["evidence:1"],
            "world_state_ref": "world:1",
            "options": [{
                "option_id": "o1",
                "summary": "Prepare report",
                "reversible": True,
                "required_authority": "none",
                "evidence_refs": ["evidence:1"],
            }],
            "selected_option_id": "o1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["execution_ready"] is False
    assert body["execution_performed"] is False
    assert body["private_chain_of_thought_persisted"] is False


def test_invalid_observe_side_effect_is_422():
    response = client().post(
        "/v1/agi-control/cognitive-packet/preview",
        json={
            "task_id": "task-1",
            "goal": "Send something",
            "evidence_refs": ["evidence:1"],
            "world_state_ref": "world:1",
            "authority_mode": "OBSERVE",
            "side_effect_class": "external_communication",
        },
    )
    assert response.status_code == 422


def test_memory_and_capability_surfaces_are_non_executing():
    memory = client().post(
        "/v1/agi-control/memory/query/preview",
        json={
            "task_type": "planning",
            "task_id": "task-2",
            "entity_refs": ["company:1"],
        },
    )
    assert memory.status_code == 200
    assert memory.json()["retrieval_only"] is True
    assert memory.json()["execution_authority"] == "none"

    caps = client().get("/v1/agi-control/capabilities")
    assert caps.status_code == 200
    assert caps.json()["wildcard_capabilities"] is False

    review = client().post(
        "/v1/agi-control/capabilities/review",
        json={"request": {
            "agent_id": "astra",
            "capability": "outreach.send",
            "authority_mode": "OBSERVE",
            "granted_capabilities": ["evidence.read"],
            "approval_present": True,
        }},
    )
    assert review.status_code == 200
    assert review.json()["permitted"] is False
    assert review.json()["execution_performed"] is False
