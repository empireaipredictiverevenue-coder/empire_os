from datetime import date, timedelta

from empire_os.copy_intelligence_review_bridge import draft_first_touch


def inputs():
    assertion = {"statement": "Example announced a service expansion", "source_ref": "fixture:public", "observed_date": "2026-10-10", "upstream_verified": True, "kind": "observed"}
    offer = {"statement": "Revenue intelligence review", "source_ref": "fixture:offer", "observed_date": "2026-10-10", "upstream_verified": True, "kind": "offer"}
    return dict(company="Example Ltd", metro="London", contact_role="Founder", product_code="EMPIRE_RESEARCH", product_name="Empire AI revenue intelligence", audience="growth leader", trigger=assertion, approved_offer=offer)


def test_real_canonical_execution_requires_review():
    r = draft_first_touch(**inputs())
    assert r["status"] == "canonical_draft_requires_review"
    assert r["draft"]["requires_human_review"] is True
    assert r["draft"]["body"] and r["draft"]["subject"]
    assert r["send_allowed"] is False and r["delivery_authority"] == "NONE"
    assert "fixture:public" in r["draft"]["evidence_used"]


def test_stable_draft_fingerprint_and_copy_variant_change():
    first = draft_first_touch(**inputs())
    repeated = draft_first_touch(**inputs())
    assert first['draft_id'].startswith('copy-sha256:')
    assert first['draft_id'] == repeated['draft_id']
    changed = inputs()
    changed['trigger']['statement'] = 'Example announced an additional product line'
    second = draft_first_touch(**changed)
    assert second['draft_id'] != first['draft_id']
    assert not second['send_allowed']


def test_unverified_observation_fails_closed():
    a = inputs(); a["trigger"]["upstream_verified"] = False
    assert draft_first_touch(**a)["status"] == "blocked_evidence"


def test_hypothesis_cannot_be_masqueraded_as_observation():
    a = inputs(); a["trigger"]["kind"] = "hypothesis"
    assert draft_first_touch(**a)["status"] == "blocked_evidence"


def test_future_dated_evidence_rejected():
    a = inputs(); a["trigger"]["observed_date"] = (date.today() + timedelta(days=1)).isoformat()
    assert draft_first_touch(**a)["status"] == "blocked_evidence"


def test_fake_guarantee_rejected():
    a = inputs(); a["approved_offer"]["statement"] = "Guaranteed growth"
    assert draft_first_touch(**a)["status"] == "blocked_evidence"


def test_missing_offer_source_rejected():
    a = inputs(); a["approved_offer"]["source_ref"] = ""
    assert draft_first_touch(**a)["status"] == "blocked_evidence"


def test_standalone_bridge_uses_shared_final_email_identity():
    from empire_os.copy_fingerprint import fingerprint_final_email
    result = draft_first_touch(**inputs())
    assert result['draft_id'] == fingerprint_final_email(
        subject=result['draft']['subject'], body=result['draft']['body'])
