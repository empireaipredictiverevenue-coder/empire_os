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


def test_uk_companies_house_seed_requires_first_party_buyer_role(monkeypatch):
    monkeypatch.setattr(
        ir,
        "find_companies_house_principals",
        lambda **kwargs: [{
            "company_name": "Example Solar Limited",
            "company_number": "12345678",
            "person_name": "Jane Smith",
            "officer_role": "director",
            "source": "companies_house",
            "source_url": (
                "https://find-and-update.company-information.service.gov.uk/"
                "company/12345678/officers"
            ),
            "confidence": 0.99,
            "buyer_authority_proven": False,
        }],
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

    def fake_search(query, num=8):
        if '"Jane Smith"' in query:
            return {
                "organic": [{
                    "link": "https://example-solar.co.uk/about",
                    "title": "Jane Smith - Managing Director",
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
                "name": "Jane Smith",
                "title": "Managing Director",
                "url": "https://example-solar.co.uk/about",
            }],
        },
    )
    monkeypatch.setattr(
        ir,
        "rank_site_people",
        lambda people: [{**people[0], "decision_score": 1.0}],
    )

    result = ir.recover_identity(
        business_name="Example Solar Ltd",
        website="https://example-solar.co.uk",
        metro="United Kingdom",
    )

    assert result["recovered"] is True
    assert result["identity"]["name"] == "Jane Smith"
    assert result["identity"]["title"] == "Managing Director"
    assert result["identity"]["source"] == "empire_first_party_people_probe"
    assert result["companies_house_seeds"][0]["person_name"] == "Jane Smith"


def test_companies_house_seed_alone_does_not_prove_buyer_authority(monkeypatch):
    monkeypatch.setattr(
        ir,
        "find_companies_house_principals",
        lambda **kwargs: [{
            "company_name": "Example Solar Limited",
            "company_number": "12345678",
            "person_name": "John Director",
            "officer_role": "director",
            "source": "companies_house",
            "source_url": (
                "https://find-and-update.company-information.service.gov.uk/"
                "company/12345678/officers"
            ),
            "confidence": 0.99,
            "buyer_authority_proven": False,
        }],
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
    monkeypatch.setattr(ir, "search", lambda query, num=8: {"organic": []})

    result = ir.recover_identity(
        business_name="Example Solar Ltd",
        website="https://example-solar.co.uk",
        metro="United Kingdom",
    )

    assert result["recovered"] is False
    assert result["identity"] is None
    assert result["companies_house_seeds"][0]["person_name"] == "John Director"


def test_identity_recovery_serp_adapter_preserves_provenance(monkeypatch):
    monkeypatch.setattr(
        ir,
        "search",
        lambda query, num=8, engine=None: {
            "organic": [{
                "title": "Jane Smith - Managing Director",
                "link": "https://example-solar.co.uk/about",
                "snippet": "Jane Smith is Managing Director.",
                "position": 1,
                "relevance_score": 0.95,
            }],
            "searchParameters": {
                "q": query,
                "num": num,
                "engine": "bing_html",
                "quality_gate": "lexical_v1",
                "cache": False,
            },
        },
    )

    rows = ir._serp_results(
        'site:example-solar.co.uk "Jane Smith"',
        num=5,
    )

    assert len(rows) == 1
    assert rows[0]["link"] == "https://example-solar.co.uk/about"
    assert rows[0]["position"] == 1
    assert rows[0]["engine"] == "bing_html"
    assert "search_fabric" in rows[0]["provenance"]
    assert "engine:bing_html" in rows[0]["provenance"]
    assert "quality_gate:lexical_v1" in rows[0]["provenance"]
