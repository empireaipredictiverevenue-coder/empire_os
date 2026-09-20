from types import SimpleNamespace

import empire_os.identity_recovery as ir


def test_identity_recovery_uses_same_domain_people(monkeypatch):
    monkeypatch.setattr(
        ir,
        "search",
        lambda query, num=8: {
            "organic": [
                {
                    "title": "About Alpha Roofing",
                    "link": "https://alpha.example/about/team",
                    "snippet": "Owner",
                },
                {
                    "title": "Third party",
                    "link": "https://directory.example/alpha",
                    "snippet": "Owner",
                },
            ]
        },
    )
    monkeypatch.setattr(
        ir,
        "probe_site",
        lambda *args, **kwargs: {
            "ok": True,
            "people": [
                {
                    "name": "Jane Smith",
                    "title": "Owner",
                    "url": "https://alpha.example/about/team",
                }
            ],
        },
    )
    monkeypatch.setattr(
        ir,
        "rank_site_people",
        lambda people: [
            {**people[0], "decision_score": 0.95}
        ],
    )
    monkeypatch.setattr(
        ir,
        "find_official_license_principals",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        ir,
        "RegistryScraper",
        lambda *args, **kwargs: SimpleNamespace(
            search=lambda *a, **k: SimpleNamespace(records=[])
        ),
    )

    result = ir.recover_identity(
        business_name="Alpha Roofing",
        website="https://alpha.example",
        metro="Houston, TX",
    )

    assert result["recovered"] is True
    assert result["identity"]["name"] == "Jane Smith"
    assert result["identity"]["first_party"] is True
    assert result["guessed_identity"] is False
    assert result["outbound_actions"] is False


def test_license_seed_requires_first_party_decision_role(monkeypatch):
    monkeypatch.setattr(
        ir,
        "find_official_license_principals",
        lambda **kwargs: [{
            "company_name": "Patriot Plumbing",
            "person_name": "Jane Doe",
            "role": "Responsible Master Plumber",
            "state": "TX",
            "source": "texas_tsbpe_rmp",
            "source_url": "https://tsbpe.texas.gov/free-licensee-list/",
            "confidence": 0.98,
            "license_status": "current",
        }],
    )

    def fake_search(query, num=8):
        if '"Jane Doe"' in query:
            return {
                "organic": [{
                    "link": "https://patriot.example/about/jane-doe",
                    "title": "Jane Doe | Patriot Plumbing",
                }]
            }
        return {"organic": []}

    monkeypatch.setattr(ir, "search", fake_search)
    monkeypatch.setattr(
        ir,
        "probe_site",
        lambda *args, **kwargs: {
            "ok": True,
            "people": [{
                "name": "Jane Doe",
                "title": "Owner",
                "url": "https://patriot.example/about/jane-doe",
            }],
        },
    )
    monkeypatch.setattr(
        ir,
        "rank_site_people",
        lambda people: [{**people[0], "decision_score": 0.95}],
    )
    monkeypatch.setattr(
        ir,
        "RegistryScraper",
        lambda *args, **kwargs: SimpleNamespace(
            search=lambda *a, **k: SimpleNamespace(records=[])
        ),
    )

    result = ir.recover_identity(
        business_name="Patriot Plumbing LLC",
        website="https://patriot.example",
        metro="San Antonio, TX",
    )

    assert result["recovered"] is True
    assert result["identity"]["name"] == "Jane Doe"
    assert result["identity"]["title"] == "Owner"
    assert result["license_seeds"][0]["role"] == "Responsible Master Plumber"
    assert result["identity"]["source"] == "empire_first_party_people_probe"


def test_license_seed_alone_does_not_promote_identity(monkeypatch):
    monkeypatch.setattr(
        ir,
        "find_official_license_principals",
        lambda **kwargs: [{
            "company_name": "Patriot Plumbing",
            "person_name": "Jane Doe",
            "role": "Responsible Master Plumber",
            "state": "TX",
            "source": "texas_tsbpe_rmp",
            "source_url": "https://tsbpe.texas.gov/free-licensee-list/",
            "confidence": 0.98,
            "license_status": "current",
        }],
    )
    monkeypatch.setattr(ir, "search", lambda query, num=8: {"organic": []})
    monkeypatch.setattr(
        ir,
        "RegistryScraper",
        lambda *args, **kwargs: SimpleNamespace(
            search=lambda *a, **k: SimpleNamespace(records=[])
        ),
    )

    result = ir.recover_identity(
        business_name="Patriot Plumbing LLC",
        website="https://patriot.example",
        metro="San Antonio, TX",
    )

    assert result["recovered"] is False
    assert result["identity"] is None
    assert result["license_seeds"][0]["person_name"] == "Jane Doe"
