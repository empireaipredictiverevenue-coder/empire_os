from empire_os.lead_sources import permits


def test_nyc_permit_keeps_owner_and_permittee_identity_roles_separate(
    monkeypatch,
):
    row = {
        "job__": "401975190",
        "work_type": "PL",
        "job_type": "A2",
        "job_description": "PLUMBING ALTERATION",
        "permit_status": "ISSUED",
        "owner_s_business_name": "Peykar Realty",
        "owner_s_first_name": "",
        "owner_s_last_name": "",
        "permittee_s_business_name": "Pipe Co",
        "permittee_s_first_name": "",
        "permittee_s_last_name": "",
        "permittee_s_phone__": "7183489398",
        "borough": "QUEENS",
        "house__": "84-90",
        "street_name": "127 STREET",
        "bbl": "4092480052",
        "dobrundate": "2026-08-16T00:00:00.000",
        "residential": "NO",
    }

    class Response:
        status_code = 200

        def json(self):
            return [row]

    monkeypatch.setattr(
        "empire_os.lead_sources.permits.requests.get",
        lambda *args, **kwargs: Response(),
    )

    candidates = list(permits._run_nyc(lookback_days=7))

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.name == "Peykar Realty (Queens)"
    assert candidate.phone == ""
    assert candidate.lead_score == 60
    assert candidate.raw["owner_s_business_name"] == "Peykar Realty"
    roles = candidate.raw["_empire_identity_roles"]
    assert roles["candidate_name_role"] == "property_owner"
    assert roles["candidate_phone_role"] == "none"
    assert roles["permittee_business_name"] == "Pipe Co"
    assert roles["permittee_phone"] == "(718) 348-9398"
    assert "Permittee: Pipe Co" in candidate.details


def test_nyc_permit_owner_score_does_not_use_permittee_phone(monkeypatch):
    base = {
        "job__": "401975190",
        "work_type": "PL",
        "job_type": "A2",
        "job_description": "PLUMBING ALTERATION",
        "permit_status": "ISSUED",
        "owner_s_business_name": "Owner LLC",
        "permittee_s_business_name": "Contractor Inc",
        "borough": "QUEENS",
        "house__": "1",
        "street_name": "MAIN STREET",
        "bbl": "1",
        "dobrundate": "2026-08-16T00:00:00.000",
        "residential": "YES",
    }

    class Response:
        status_code = 200

        def __init__(self, phone):
            self.phone = phone

        def json(self):
            return [{**base, "permittee_s_phone__": self.phone}]

    def score_for(phone):
        monkeypatch.setattr(
            "empire_os.lead_sources.permits.requests.get",
            lambda *args, **kwargs: Response(phone),
        )
        return list(permits._run_nyc(lookback_days=7))[0].lead_score

    assert score_for("7185550000") == 65
    assert score_for("") == 65
