from empire_os.buyer_probe_worker import rejection_reason


def test_rejection_reason_prioritizes_site_and_identity_gates():
    assert rejection_reason({"site_ok": False, "review_ready": False, "outreach_ready": False}) == "site_unavailable"
    assert rejection_reason({"site_ok": True, "decision_maker": None,
                             "review_ready": False, "outreach_ready": False}) == "no_decision_maker"


def test_rejection_reason_requires_bound_contact():
    result = {
        "site_ok": True,
        "decision_maker": {"name": "Jane Smith"},
        "contacts": [{"email": "office@acme.test", "bound_to_decision_maker": False}],
        "verified_contacts": [],
        "review_ready": False, "outreach_ready": False,
    }
    assert rejection_reason(result) == "no_bound_contact"


def test_rejection_reason_reports_role_only_and_ready():
    role_only = {
        "site_ok": True, "decision_maker": {"name": "Jane Smith"},
        "contacts": [{"email": "info@acme.test", "bound_to_decision_maker": True}],
        "verified_contacts": [{"email": "info@acme.test", "is_role_address": True}],
        "review_ready": False, "outreach_ready": False,
    }
    assert rejection_reason(role_only) == "role_address_only"
    assert rejection_reason({"review_ready": True, "outreach_ready": False}) is None


def test_run_promotes_only_native_confirmed_first_party_contact(monkeypatch):
    from types import SimpleNamespace

    import empire_os.buyer_probe_worker as worker
    from empire_os.hunter.models import (
        ContactEvidence,
        DomainPattern,
        VerificationState,
    )

    candidate = SimpleNamespace(
        prospect_id="p1",
        business_name="Acme Roofing",
        website="https://acme.test",
    )
    monkeypatch.setattr(
        worker,
        "build_candidate",
        lambda *args, **kwargs: candidate,
    )
    monkeypatch.setattr(
        worker,
        "probe_site",
        lambda *args, **kwargs: {
            "ok": True,
            "evidence_score": 1.0,
            "budget_exhausted": False,
        },
    )
    monkeypatch.setattr(
        worker,
        "enrich_candidate",
        lambda *args, **kwargs: {
            "decision_maker": {
                "name": "Jane Smith",
                "title": "CEO",
                "decision_score": 1.0,
            },
            "contact_candidates": [],
        },
    )
    confirmed = ContactEvidence(
        email="jane.smith@acme.test",
        state=VerificationState.CONFIRMED,
        confidence=0.96,
        source="first_party_schema_person",
        source_url="https://acme.test/team",
        person_name="Jane Smith",
        person_title="CEO",
        person_bound=True,
        first_party=True,
        syntax_ok=True,
        mx_ok=True,
    )
    report = SimpleNamespace(
        confirmed_contacts=(confirmed,),
        contacts=(confirmed,),
        pattern=DomainPattern(
            domain="acme.test",
            pattern="first.last",
            observations=1,
            agreement=1.0,
            confidence=0.66,
        ),
    )
    monkeypatch.setattr(
        worker,
        "analyze_domain",
        lambda *args, **kwargs: report,
    )

    def merge(enriched, evidence):
        assert evidence[0]["source_kind"] == "official_site"
        return {
            **enriched,
            "contact_candidates": [{
                "email": "jane.smith@acme.test",
                "source": "official_site",
                "bound_to_decision_maker": True,
            }],
        }

    monkeypatch.setattr(
        worker,
        "merge_public_web_contact_evidence",
        merge,
    )
    monkeypatch.setattr(
        worker,
        "verify_contact_plan",
        lambda enriched, *, validator: {
            "verified_contacts": enriched["contact_candidates"],
            "review_ready": True,
            "outreach_ready": True,
            "preferred_email": "jane.smith@acme.test",
        },
    )

    result = worker.run({
        "id": "p1",
        "business_name": "Acme Roofing",
        "website": "https://acme.test",
    })

    assert result["outreach_ready"] is True
    assert result["preferred_email"] == "jane.smith@acme.test"
    assert result["hunter_confirmed_contacts"][0]["state"] == "confirmed"
    assert result["hunter_domain_pattern"]["pattern"] == "first.last"


def test_generated_smtp_contacts_require_non_catchall(monkeypatch):
    import empire_os.buyer_probe_worker as worker

    monkeypatch.setattr(
        worker,
        "generate_work_email_candidates",
        lambda name, website: [
            "jane.smith@acme.test",
            "jane@acme.test",
        ],
    )

    class Result:
        def __init__(self, email, *, accepts):
            self.email = email
            self.is_valid = accepts
            self.confidence = 0.95 if accepts else 0.5
            self.has_mx = True
            self.smtp_accepts = accepts
            self.is_role_address = False
            self.is_disposable = False

    class Validator:
        def __init__(self, *args, **kwargs):
            pass

        def validate(self, email):
            if email.startswith("empire-probe-"):
                return Result(email, accepts=False)
            return Result(email, accepts=email == "jane.smith@acme.test")

    monkeypatch.setattr(worker, "MxValidator", Validator)
    enriched = {
        "decision_maker": {
            "name": "Jane Smith",
            "title": "CEO",
            "decision_score": 1.0,
        }
    }
    valid, meta = worker._smtp_verified_generated_contacts(
        enriched,
        "https://acme.test",
    )
    assert [item["email"] for item in valid] == ["jane.smith@acme.test"]
    assert meta["catch_all"] is False
    assert meta["smtp_valid"] == 1


def test_generated_smtp_contacts_reject_catchall_domain(monkeypatch):
    import empire_os.buyer_probe_worker as worker

    monkeypatch.setattr(
        worker,
        "generate_work_email_candidates",
        lambda name, website: ["jane.smith@acme.test"],
    )

    class Result:
        is_valid = True
        confidence = 0.95
        has_mx = True
        smtp_accepts = True
        is_role_address = False
        is_disposable = False

    class Validator:
        def __init__(self, *args, **kwargs):
            pass

        def validate(self, email):
            result = Result()
            result.email = email
            return result

    monkeypatch.setattr(worker, "MxValidator", Validator)
    valid, meta = worker._smtp_verified_generated_contacts(
        {
            "decision_maker": {
                "name": "Jane Smith",
                "decision_score": 1.0,
            }
        },
        "https://acme.test",
    )
    assert valid == []
    assert meta["catch_all"] is True
