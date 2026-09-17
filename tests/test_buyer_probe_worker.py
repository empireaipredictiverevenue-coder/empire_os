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
