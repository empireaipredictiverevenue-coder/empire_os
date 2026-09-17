from empire_os.search_fabric.site_probe import _schema_evidence


def test_schema_people_are_separate_from_business_names():
    records = [{
        "@type": "Organization",
        "name": "Acme Ltd",
        "employee": [{
            "@type": "Person",
            "name": "Jane Smith",
            "jobTitle": "Managing Director",
            "email": "mailto:jane@acme.test",
            "url": "https://acme.test/team/jane",
        }],
    }]
    evidence = _schema_evidence(records)
    assert evidence["business_names"] == ["Acme Ltd"]
    assert evidence["people"] == [{
        "name": "Jane Smith",
        "title": "Managing Director",
        "email": "jane@acme.test",
        "url": "https://acme.test/team/jane",
    }]


def test_schema_people_are_deduplicated_by_evidence_tuple():
    person = {"@type":"Person","name":"Alex Doe","jobTitle":"Founder","email":"alex@x.test"}
    evidence = _schema_evidence([person, person.copy()])
    assert len(evidence["people"]) == 1
    assert evidence["business_names"] == []
