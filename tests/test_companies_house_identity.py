import empire_os.companies_house_identity as ch


def test_company_match_strips_uk_legal_suffixes():
    assert ch.company_match_score(
        "3S Northampton Ltd",
        "3S NORTHAMPTON LIMITED",
    ) == 1.0


def test_companies_house_requires_key(monkeypatch):
    monkeypatch.delenv("COMPANIES_HOUSE_API_KEY", raising=False)
    assert ch.find_companies_house_principals(
        company_name="Example Solar Ltd",
    ) == []


def test_companies_house_returns_active_natural_person_directors(monkeypatch):
    calls = []

    def fake_request(path, *, params=None, api_key, timeout=8.0):
        calls.append(path)
        if path == "/search/companies":
            return {
                "items": [{
                    "title": "EXAMPLE SOLAR LIMITED",
                    "company_number": "12345678",
                    "company_status": "active",
                }]
            }
        if path == "/company/12345678/officers":
            return {
                "items": [
                    {
                        "name": "SMITH, Jane",
                        "officer_role": "director",
                        "occupation": "Managing Director",
                        "appointed_on": "2020-01-01",
                    },
                    {
                        "name": "JONES, Bob",
                        "officer_role": "director",
                        "resigned_on": "2022-01-01",
                    },
                    {
                        "name": "EXAMPLE HOLDINGS LTD",
                        "officer_role": "corporate-director",
                    },
                ]
            }
        raise AssertionError(path)

    monkeypatch.setattr(ch, "_request_json", fake_request)
    rows = ch.find_companies_house_principals(
        company_name="Example Solar Ltd",
        api_key="test-key",
    )

    assert calls == [
        "/search/companies",
        "/company/12345678/officers",
    ]
    assert len(rows) == 1
    assert rows[0]["person_name"] == "Jane Smith"
    assert rows[0]["officer_role"] == "director"
    assert rows[0]["authoritative_registry"] is True
    assert rows[0]["buyer_authority_proven"] is False


def test_companies_house_fails_closed_on_ambiguous_company_match(monkeypatch):
    def fake_request(path, *, params=None, api_key, timeout=8.0):
        assert path == "/search/companies"
        return {
            "items": [
                {
                    "title": "ALPHA SOLAR LIMITED",
                    "company_number": "11111111",
                    "company_status": "active",
                },
                {
                    "title": "ALPHA SOLAR LTD",
                    "company_number": "22222222",
                    "company_status": "active",
                },
            ]
        }

    monkeypatch.setattr(ch, "_request_json", fake_request)
    assert ch.find_companies_house_principals(
        company_name="Alpha Solar Ltd",
        api_key="test-key",
    ) == []


def test_display_name_normalizes_uppercase_component_without_mangling_mixed_case():
    assert ch._display_name("SMITH, Jane") == "Jane Smith"
    assert ch._display_name("McDonald, Anne-Marie") == "Anne-Marie McDonald"
