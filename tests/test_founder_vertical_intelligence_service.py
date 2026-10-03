from fastapi.testclient import TestClient

from empire_os.founder_vertical_intelligence_service import (
    build_founder_vertical_intelligence_service,
)


def test_vertical_read_service():
    client = TestClient(
        build_founder_vertical_intelligence_service()
    )

    health = client.get("/health")

    assert health.status_code == 200
    assert health.json()["mode"] == "OBSERVE"
    assert (
        health.json()["execution_allowed"]
        is False
    )

    for endpoint in (
        "permit",
        "property",
        "private-capital",
    ):
        response = client.get(
            "/v1/founder-vertical-intelligence/"
            + endpoint
        )

        assert response.status_code == 200
        assert response.json()["mode"] == "OBSERVE"
        assert (
            response.json()[
                "execution_authority"
            ]
            == "none"
        )
