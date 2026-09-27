from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.consent_api import create_consent_router


class FakeConsentRepository:
    def __init__(self):
        self.events = []

    def current(self, *, prospect_id, channel):
        rows = [
            row for row in self.events
            if row["prospect_id"] == prospect_id and row["channel"] == channel
        ]
        return rows[-1] if rows else None

    def record(
        self,
        *,
        prospect_id,
        channel,
        decision,
        source,
        evidence,
        occurred_at,
    ):
        row = {
            "id": f"event-{len(self.events) + 1}",
            "prospect_id": prospect_id,
            "channel": channel,
            "decision": decision,
            "source": source,
            "evidence": dict(evidence),
            "occurred_at": occurred_at,
        }
        self.events.append(row)
        return row


def client(repository=None):
    app = FastAPI()
    app.include_router(create_consent_router(repository))
    return TestClient(app)


def test_health_is_append_only_and_non_sending():
    response = client().get("/v1/consent/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "GOVERNED"
    assert body["append_only"] is True
    assert body["outbound_execution"] is False
    assert body["repository_available"] is False


def test_unbound_repository_fails_closed():
    response = client().post(
        "/v1/consent/prospects/prospect-1/opt-in",
        json={"channel": "email"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "canonical_consent_repository_not_activated"
    )


def test_opt_in_records_append_only_consent_without_sending():
    repo = FakeConsentRepository()
    response = client(repo).post(
        "/v1/consent/prospects/prospect-1/opt-in",
        json={
            "channel": "email",
            "source": "damage_opt_in_page",
            "evidence": {"surface": "damage_report"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "granted"
    assert body["outbound_execution"] is False
    assert repo.events[0]["decision"] == "granted"


def test_revoke_appends_new_event():
    repo = FakeConsentRepository()
    c = client(repo)
    assert c.post(
        "/v1/consent/prospects/prospect-1/opt-in",
        json={"channel": "email"},
    ).status_code == 200
    response = c.post(
        "/v1/consent/prospects/prospect-1/revoke",
        json={"channel": "email", "source": "user_revoke"},
    )
    assert response.status_code == 200
    assert len(repo.events) == 2
    assert repo.events[-1]["decision"] == "revoked"


def test_current_returns_latest_decision():
    repo = FakeConsentRepository()
    c = client(repo)
    c.post(
        "/v1/consent/prospects/prospect-1/opt-in",
        json={"channel": "email"},
    )
    c.post(
        "/v1/consent/prospects/prospect-1/revoke",
        json={"channel": "email"},
    )
    response = c.get(
        "/v1/consent/prospects/prospect-1?channel=email"
    )
    assert response.status_code == 200
    assert response.json()["consent"]["decision"] == "revoked"


def test_unknown_channel_is_rejected():
    response = client(FakeConsentRepository()).post(
        "/v1/consent/prospects/prospect-1/opt-in",
        json={"channel": "fax"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "unsupported_consent_channel"
