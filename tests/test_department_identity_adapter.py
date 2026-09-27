from empire_os.department_identity_adapter import (
    resolve_entity_decision_maker,
)


def test_existing_canonical_contact_is_available_without_recovery():
    calls = []

    def request(method, path, payload=None, prefer=None):
        calls.append((method, path, payload, prefer))
        if path.startswith("/rest/v1/prospect_entity_links?"):
            return [{
                "prospect_id": "p1",
                "entity_id": "e1",
                "active": True,
                "match_score": 0.9,
            }]
        if path.startswith("/rest/v1/prospects?"):
            return [{
                "id": "p1",
                "business_name": "Acme",
                "website": "https://acme.example",
                "metro": "Denver, CO",
                "contact_name": "Alex Smith",
                "contact_title": "Owner",
                "contact_source": "first_party",
            }]
        raise AssertionError(path)

    result = resolve_entity_decision_maker(
        entity_id="e1",
        request=request,
        recoverer=lambda **_: (_ for _ in ()).throw(
            AssertionError("recovery should not run")
        ),
    )
    assert result["status"] == "AVAILABLE"
    assert result["new_identity_persisted"] is False
    assert result["decision_maker"]["name"] == "Alex Smith"
    assert result["outreach_executed"] is False


def test_targeted_first_party_recovery_is_persisted():
    patched = []

    def request(method, path, payload=None, prefer=None):
        if path.startswith("/rest/v1/prospect_entity_links?"):
            return [{
                "prospect_id": "p1",
                "entity_id": "e1",
                "active": True,
                "match_score": 0.9,
            }]
        if method == "GET" and path.startswith("/rest/v1/prospects?"):
            return [{
                "id": "p1",
                "business_name": "Acme",
                "website": "https://acme.example",
                "metro": "Denver, CO",
                "contact_name": None,
                "contact_title": None,
                "contact_source": None,
            }]
        if method == "PATCH":
            patched.append(payload)
            return None
        raise AssertionError((method, path))

    def recoverer(**kwargs):
        return {
            "recovered": True,
            "identity": {
                "name": "Alex Smith",
                "title": "Owner",
                "source": "empire_first_party_people_probe",
                "source_url": "https://acme.example/team",
                "confidence": 0.82,
                "first_party": True,
                "authoritative_registry": False,
            },
        }

    result = resolve_entity_decision_maker(
        entity_id="e1",
        request=request,
        recoverer=recoverer,
    )
    assert result["status"] == "AVAILABLE"
    assert result["new_identity_persisted"] is True
    assert patched[0]["contact_name"] == "Alex Smith"
    assert result["guessed_identity"] is False
    assert result["execution_authority"] == "none"


def test_unresolved_identity_stays_unavailable():
    def request(method, path, payload=None, prefer=None):
        if path.startswith("/rest/v1/prospect_entity_links?"):
            return [{
                "prospect_id": "p1",
                "entity_id": "e1",
                "active": True,
                "match_score": 0.9,
            }]
        if path.startswith("/rest/v1/prospects?"):
            return [{
                "id": "p1",
                "business_name": "Acme",
                "website": "https://acme.example",
                "metro": "Denver, CO",
            }]
        raise AssertionError(path)

    result = resolve_entity_decision_maker(
        entity_id="e1",
        request=request,
        recoverer=lambda **_: {
            "recovered": False,
            "identity": None,
        },
    )
    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == (
        "decision_maker_not_resolved_from_bounded_evidence"
    )
    assert result["outreach_executed"] is False
