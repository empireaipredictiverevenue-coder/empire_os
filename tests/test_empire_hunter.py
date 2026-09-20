from types import SimpleNamespace

from empire_os.hunter.domain_intelligence import analyze_domain
from empire_os.hunter.models import VerificationState
from empire_os.hunter.pattern_brain import (
    generate_candidate,
    infer_pattern,
    learn_domain_pattern,
)
from empire_os.hunter.verification_mesh import VerificationMesh


class FakeMx:
    def validate(self, email):
        return SimpleNamespace(has_mx=True)

    def _mx_lookup(self, domain):
        return ["mx.example.test"]


def test_pattern_brain_learns_company_specific_pattern():
    pattern = learn_domain_pattern(
        [
            {
                "email": "jane.smith@acme.com",
                "person_name": "Jane Smith",
                "person_bound": True,
                "first_party": True,
            },
            {
                "email": "john.doe@acme.com",
                "person_name": "John Doe",
                "person_bound": True,
                "first_party": True,
            },
        ],
        domain="acme.com",
    )

    assert pattern.pattern == "first.last"
    assert pattern.observations == 2
    assert pattern.confidence > 0.8
    assert generate_candidate(
        "Mary Jones",
        "acme.com",
        pattern.pattern,
    ) == "mary.jones@acme.com"


def test_mx_only_candidate_is_probable_not_confirmed():
    mesh = VerificationMesh(mx_validator=FakeMx())
    result = mesh.verify(
        "jane.smith@acme.com",
        source="empire_pattern_brain",
        person_name="Jane Smith",
        person_bound=True,
        first_party=False,
    )

    assert result.state is VerificationState.PROBABLE
    assert result.mx_ok is True
    assert result.person_bound is True


def test_first_party_person_bound_contact_is_confirmed():
    mesh = VerificationMesh(mx_validator=FakeMx())
    result = mesh.verify(
        "jane.smith@acme.com",
        source="first_party_schema_person",
        source_url="https://acme.com/team",
        person_name="Jane Smith",
        person_title="CEO",
        person_bound=True,
        first_party=True,
    )

    assert result.state is VerificationState.CONFIRMED
    assert result.confidence >= 0.95


def test_verified_bounce_overrides_other_positive_evidence():
    mesh = VerificationMesh(mx_validator=FakeMx())
    result = mesh.verify(
        "jane.smith@acme.com",
        source="provider_lifecycle",
        person_name="Jane Smith",
        person_bound=True,
        first_party=True,
        bounced_evidence=True,
    )

    assert result.state is VerificationState.REJECTED
    assert result.bounced_evidence is True


def test_domain_intelligence_uses_first_party_person_schema():
    evidence = {
        "ok": True,
        "requested_url": "https://acme.com",
        "final_url": "https://acme.com/",
        "canonical_url": "https://acme.com/",
        "domain": "acme.com",
        "business_names": ["Acme Roofing"],
        "emails": ["info@acme.com", "jane.smith@acme.com"],
        "people": [
            {
                "name": "Jane Smith",
                "title": "CEO",
                "email": "jane.smith@acme.com",
                "url": "https://acme.com/team",
            },
            {
                "name": "John Doe",
                "title": "COO",
                "email": "",
                "url": "https://acme.com/team",
            },
        ],
        "pages_checked": [{"url": "https://acme.com/team"}],
        "evidence_score": 0.9,
    }

    report = analyze_domain(
        "https://acme.com",
        mesh=VerificationMesh(mx_validator=FakeMx()),
        probe=lambda *args, **kwargs: evidence,
    )

    assert report.outreach_ready is True
    assert report.pattern.pattern == "first.last"
    assert report.confirmed_contacts[0].email == "jane.smith@acme.com"
    generated = [
        row for row in report.contacts
        if row.source == "empire_pattern_brain"
    ]
    assert len(generated) == 1
    assert generated[0].email == "john.doe@acme.com"
    assert generated[0].state is VerificationState.PROBABLE


def test_infer_pattern_rejects_wrong_domain():
    assert infer_pattern(
        "jane.smith@other.com",
        "Jane Smith",
        domain="acme.com",
    ) is None


def test_unique_first_party_first_name_email_is_correlated():
    evidence = {
        "ok": True,
        "requested_url": "https://acme.com",
        "final_url": "https://acme.com/",
        "canonical_url": "https://acme.com/",
        "domain": "acme.com",
        "business_names": ["Acme Roofing"],
        "emails": ["jane@acme.com"],
        "people": [
            {
                "name": "Jane Smith",
                "title": "CEO",
                "email": "",
                "url": "https://acme.com/team",
            }
        ],
        "pages_checked": [{"url": "https://acme.com/team"}],
        "evidence_score": 0.9,
    }

    report = analyze_domain(
        "https://acme.com",
        mesh=VerificationMesh(mx_validator=FakeMx()),
        probe=lambda *args, **kwargs: evidence,
    )

    assert report.outreach_ready is True
    contact = report.confirmed_contacts[0]
    assert contact.email == "jane@acme.com"
    assert contact.person_name == "Jane Smith"
    assert contact.source == "first_party_name_correlation"


def test_ambiguous_first_name_email_stays_unbound():
    evidence = {
        "ok": True,
        "requested_url": "https://acme.com",
        "final_url": "https://acme.com/",
        "canonical_url": "https://acme.com/",
        "domain": "acme.com",
        "business_names": ["Acme Roofing"],
        "emails": ["jane@acme.com"],
        "people": [
            {"name": "Jane Smith", "title": "CEO", "email": "", "url": ""},
            {"name": "Jane Jones", "title": "COO", "email": "", "url": ""},
        ],
        "pages_checked": [],
        "evidence_score": 0.8,
    }

    report = analyze_domain(
        "https://acme.com",
        mesh=VerificationMesh(mx_validator=FakeMx()),
        probe=lambda *args, **kwargs: evidence,
    )

    assert report.outreach_ready is False
    email = next(
        item for item in report.contacts
        if item.email == "jane@acme.com"
    )
    assert email.person_bound is False
    assert email.state is VerificationState.PROBABLE


def test_known_person_can_be_bound_from_same_official_page_evidence():
    evidence = {
        "ok": True,
        "requested_url": "https://acme.com",
        "final_url": "https://acme.com/",
        "canonical_url": "https://acme.com/",
        "domain": "acme.com",
        "business_names": ["Acme Roofing"],
        "emails": ["jane@acme.com"],
        "people": [],
        "pages_checked": [{
            "url": "https://acme.com/team",
            "canonical_url": "https://acme.com/team",
            "emails": ["jane@acme.com"],
            "visible_text": (
                "Meet our team Jane Smith Chief Executive Officer "
                "Operations and company leadership"
            ),
        }],
        "evidence_score": 0.9,
    }

    report = analyze_domain(
        "https://acme.com",
        mesh=VerificationMesh(mx_validator=FakeMx()),
        probe=lambda *args, **kwargs: evidence,
        known_people=({
            "name": "Jane Smith",
            "title": "Chief Executive Officer",
        },),
    )

    assert report.outreach_ready is True
    contact = report.confirmed_contacts[0]
    assert contact.email == "jane@acme.com"
    assert contact.person_name == "Jane Smith"
    assert contact.source == "first_party_page_correlation"


def test_known_person_page_binding_requires_title_proximity_when_known():
    evidence = {
        "ok": True,
        "requested_url": "https://acme.com",
        "final_url": "https://acme.com/",
        "canonical_url": "https://acme.com/",
        "domain": "acme.com",
        "business_names": ["Acme Roofing"],
        "emails": ["jane@acme.com"],
        "people": [],
        "pages_checked": [{
            "url": "https://acme.com/team",
            "canonical_url": "https://acme.com/team",
            "emails": ["jane@acme.com"],
            "visible_text": (
                "Jane Smith Project Coordinator. "
                "Far away text Chief Executive Officer"
            ),
        }],
        "evidence_score": 0.9,
    }

    report = analyze_domain(
        "https://acme.com",
        mesh=VerificationMesh(mx_validator=FakeMx()),
        probe=lambda *args, **kwargs: evidence,
        known_people=({
            "name": "Jane Smith",
            "title": "Owner",
        },),
    )

    assert report.outreach_ready is False
