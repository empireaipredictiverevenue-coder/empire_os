"""Shared first-party provenance and identity contract regression tests."""
from empire_os.first_party_evidence_contract import first_party_contact_decision


def check(site="https://buyer.co.uk/", source="https://buyer.co.uk/team/",
          email="jane@buyer.co.uk", published=True):
    return first_party_contact_decision(
        website=site, source_url=source,
        email=email, direct_publication=published,
    )


def test_explicit_same_company_source_person_email_passes():
    assert check() == (True, "first_party_domain_alignment_confirmed")
    assert check(site="https://www.buyer.co.uk",
                 source="https://buyer.co.uk/team/jane") == (
                     True, "first_party_domain_alignment_confirmed"
                 )


def test_missing_company_identity_never_self_certifies_source():
    assert check(site="")[1] == "company_domain_unavailable"
    assert check(site=None)[0] is False


def test_shared_suffix_or_fake_subdomain_cannot_prove_company():
    assert check(source="https://buyer.co.uk.attacker.test/team/")[1] == (
        "source_company_domain_mismatch"
    )
    assert check(source="https://other.co.uk/team/")[0] is False
    assert check(email="jane@other.co.uk")[1] == "email_company_domain_mismatch"


def test_published_personal_contact_cannot_be_inferred_from_email_pattern():
    assert check(published=False)[1] == "direct_publication_unverified"
    assert check(published=None)[1] == "direct_publication_unverified"


def test_url_userinfo_and_scheme_spoofing_are_denied():
    assert check(source="https://buyer.co.uk@attacker.test/team")[0] is False
    assert check(source="javascript:https://buyer.co.uk/team")[1] == "source_url_not_http"
    assert check(source="https://buyer.co.uk:4443/team")[1] == "source_url_invalid"
    assert check(email="jane@@buyer.co.uk")[1] == "email_invalid"


def test_unverified_secondary_domain_alias_stays_blocked():
    assert check(email="jane@buyer-mail.co.uk")[0] is False
    assert check(source="https://buyer-support.co.uk/team")[0] is False
