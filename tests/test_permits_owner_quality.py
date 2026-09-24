from empire_os.lead_sources import permits


def test_generic_owner_labels_emit_project_signals(monkeypatch):
    base = {
        "job__": "401975190",
        "work_type": "PL",
        "job_type": "A2",
        "job_description": "PLUMBING ALTERATION",
        "permit_status": "ISSUED",
        "owner_s_first_name": "",
        "owner_s_last_name": "",
        "permittee_s_business_name": "Pipe Co",
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

        def __init__(self, label):
            self.label = label

        def json(self):
            return [{**base, "owner_s_business_name": self.label}]

    for label in ("OWNER", "N.A", "245"):
        response = Response(label)
        monkeypatch.setattr(
            "empire_os.lead_sources.permits.requests.get",
            lambda *args, _response=response, **kwargs: _response,
        )
        candidates = list(permits._run_nyc(lookback_days=7))
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.name == "NYC Permit 401975190 (Queens)"
        assert candidate.phone == ""
        roles = candidate.raw["_empire_identity_roles"]
        assert roles["candidate_name_role"] == "project_signal"
        assert roles["owner_identity_available"] is False
        assert roles["source_owner_name"] == label
