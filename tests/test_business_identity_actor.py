from empire_os.business_identity_actor import (
    run_business_identity_actor,
)
from empire_os.revenue_actor_registry import (
    actor_catalog,
)


def payload():
    return {
        "upstream_decision":
            "RESOLVE_IDENTITY",
        "signal_id": "signal-1",
        "source_url": (
            "https://www.linkedin.com/posts/"
            "jane-doe-123abc_looking-for-help-"
            "activity-1"
        ),
        "title":
            "Looking for an automation expert",
        "text":
            "Looking for an automation expert.",
        "niche": "saas",
        "metro": "online",
    }


def test_catalog_contains_business_identity():
    keys = {
        row["actor_key"]
        for row in actor_catalog()
    }

    assert "intent_brain" in keys
    assert "first_party_identity" in keys
    assert "business_identity" in keys


def test_wrong_upstream_state_fails_closed():
    row = payload()
    row["upstream_decision"] = "WATCH"

    result = run_business_identity_actor(
        row
    )

    assert result["decision"] == "NOT_ELIGIBLE"
    assert (
        result["governance"][
            "execution_authority"
        ]
        == "none"
    )


def test_social_result_alone_never_verifies():
    def search_fn(query, num=8):
        return [{
            "title":
                "Jane Doe - LinkedIn",
            "url":
                "https://linkedin.com/in/jane-doe",
            "snippet": "Jane Doe profile",
        }]

    result = run_business_identity_actor(
        payload(),
        search_fn=search_fn,
    )

    assert (
        result["decision"]
        == "BUSINESS_IDENTITY_UNRESOLVED"
    )

    assert (
        result["output"][
            "business_identity_verified"
        ]
        is False
    )


def test_first_party_person_plus_business_verifies():
    def search_fn(query, num=8):
        return [
            {
                "title":
                    "Jane Doe - LinkedIn",
                "url":
                    "https://linkedin.com/in/jane-doe",
                "snippet":
                    "Jane Doe",
            },
            {
                "title":
                    "Jane Doe | Example Labs",
                "url":
                    "https://examplelabs.com/team/jane-doe",
                "snippet":
                    "Jane Doe at Example Labs",
            },
        ]

    def probe_fn(url, **kwargs):
        assert url == "https://examplelabs.com/"

        return {
            "ok": True,
            "domain": "examplelabs.com",
            "title": "Example Labs",
            "description":
                "Automation company",
            "business_names": [
                "Example Labs",
            ],
            "schema_types": [
                "Organization",
            ],
            "people": [{
                "name": "Jane Doe",
                "title": "Founder",
                "url":
                    "https://examplelabs.com/team/jane-doe",
            }],
            "pages_checked": [],
        }

    def guard_fn(**kwargs):
        return {
            "candidate_url":
                "https://examplelabs.com/",
            "discovery_domain_supported":
                True,
            "existing_first_party_support":
                True,
        }

    result = run_business_identity_actor(
        payload(),
        search_fn=search_fn,
        probe_fn=probe_fn,
        guard_fn=guard_fn,
    )

    assert (
        result["decision"]
        == "BUSINESS_IDENTITY_VERIFIED"
    )

    output = result["output"]

    assert (
        output["business_identity_verified"]
        is True
    )
    assert (
        output["first_party_site_verified"]
        is True
    )
    assert (
        output["business_name"]
        == "Example Labs"
    )
    assert (
        output["website"]
        == "https://examplelabs.com/"
    )

    assert (
        result["governance"][
            "outreach_authorized"
        ]
        is False
    )
    assert (
        result["governance"][
            "canonical_promotion_performed"
        ]
        is False
    )


def test_site_without_matching_source_person_fails():
    def search_fn(query, num=8):
        return [{
            "title":
                "Example Labs",
            "url":
                "https://examplelabs.com/",
            "snippet":
                "Automation company",
        }]

    def probe_fn(url, **kwargs):
        return {
            "ok": True,
            "domain": "examplelabs.com",
            "business_names": [
                "Example Labs",
            ],
            "schema_types": [
                "Organization",
            ],
            "people": [{
                "name": "John Smith",
                "title": "Founder",
                "url":
                    "https://examplelabs.com/team/john",
            }],
        }

    result = run_business_identity_actor(
        payload(),
        search_fn=search_fn,
        probe_fn=probe_fn,
    )

    assert (
        result["decision"]
        == "BUSINESS_IDENTITY_UNRESOLVED"
    )


def test_guard_must_support_domain():
    def search_fn(query, num=8):
        return [{
            "title":
                "Jane Doe | Example Labs",
            "url":
                "https://examplelabs.com/team/jane-doe",
            "snippet":
                "Jane Doe",
        }]

    def probe_fn(url, **kwargs):
        return {
            "ok": True,
            "domain": "examplelabs.com",
            "business_names": [
                "Example Labs",
            ],
            "people": [{
                "name": "Jane Doe",
                "title": "Founder",
                "url":
                    "https://examplelabs.com/team/jane-doe",
            }],
        }

    def guard_fn(**kwargs):
        return {
            "discovery_domain_supported":
                False,
            "existing_first_party_support":
                False,
        }

    result = run_business_identity_actor(
        payload(),
        search_fn=search_fn,
        probe_fn=probe_fn,
        guard_fn=guard_fn,
    )

    assert (
        result["decision"]
        == "BUSINESS_IDENTITY_UNRESOLVED"
    )


def test_multiple_verified_domains_needs_review():
    def search_fn(query, num=8):
        return [
            {
                "title":
                    "Jane Doe - One",
                "url":
                    "https://one-company.com/team/jane",
                "snippet": "",
            },
            {
                "title":
                    "Jane Doe - Two",
                "url":
                    "https://two-company.com/team/jane",
                "snippet": "",
            },
        ]

    def probe_fn(url, **kwargs):
        host = (
            "One Ltd"
            if "one-company.com" in url
            else "Two Ltd"
        )

        root = (
            "https://one-company.com/"
            if "one-company.com" in url
            else "https://two-company.com/"
        )

        return {
            "ok": True,
            "business_names": [host],
            "people": [{
                "name": "Jane Doe",
                "title": "Founder",
                "url": root + "team/jane",
            }],
        }

    def guard_fn(**kwargs):
        return {
            "discovery_domain_supported":
                True,
        }

    result = run_business_identity_actor(
        payload(),
        search_fn=search_fn,
        probe_fn=probe_fn,
        guard_fn=guard_fn,
    )

    assert result["decision"] == "NEEDS_REVIEW"
    assert (
        result["output"][
            "business_identity_verified"
        ]
        is False
    )


def test_structured_linkedin_handle_yields_safe_name_seed():
    from empire_os.business_identity_actor import (
        _safe_name_seed_from_handle,
    )

    assert (
        _safe_name_seed_from_handle(
            "sahil-aggarwal-2b1a99221"
        )
        == "Sahil Aggarwal"
    )

    assert (
        _safe_name_seed_from_handle(
            "chase-manning-24712353"
        )
        == "Chase Manning"
    )


def test_unsegmented_handle_is_not_guessed():
    from empire_os.business_identity_actor import (
        _safe_name_seed_from_handle,
    )

    assert (
        _safe_name_seed_from_handle(
            "kimberlysperber"
        )
        == ""
    )

    assert (
        _safe_name_seed_from_handle(
            "kumsub"
        )
        == ""
    )


def test_discovery_plan_contains_name_seed_when_safe():
    from empire_os.business_identity_actor import (
        _discovery_query_plan,
    )

    plan = _discovery_query_plan(
        handle=
            "sahil-aggarwal-2b1a99221",
        title=
            "Looking for an SEO Team / Agency",
    )

    queries = [
        row["query"]
        for row in plan
    ]

    assert (
        '"sahil-aggarwal-2b1a99221"'
        in queries
    )

    assert (
        '"Sahil Aggarwal"'
        in queries
    )

    assert len(plan) <= 4


def test_name_seed_can_unlock_business_discovery():
    seen = []

    def search_fn(query, num=8):
        seen.append(query)

        if query == '"Sahil Aggarwal"':
            return [
                {
                    "title":
                        "Sahil Aggarwal | Example Labs",
                    "url":
                        "https://examplelabs.com/team/sahil-aggarwal",
                    "snippet":
                        "Sahil Aggarwal, Founder",
                }
            ]

        return []

    def probe_fn(url, **kwargs):
        return {
            "ok": True,
            "domain":
                "examplelabs.com",
            "business_names": [
                "Example Labs",
            ],
            "people": [{
                "name":
                    "Sahil Aggarwal",
                "title":
                    "Founder",
                "url":
                    "https://examplelabs.com/team/sahil-aggarwal",
            }],
        }

    def guard_fn(**kwargs):
        return {
            "discovery_domain_supported":
                True,
            "existing_first_party_support":
                True,
        }

    row = {
        "upstream_decision":
            "RESOLVE_IDENTITY",
        "signal_id":
            "sig-sahil",
        "source_url":
            "https://www.linkedin.com/posts/"
            "sahil-aggarwal-2b1a99221_activity-1",
        "title":
            "Looking for an SEO Team / Agency",
        "text":
            "Looking for an SEO team",
        "niche":
            "search",
        "metro":
            "online",
    }

    result = run_business_identity_actor(
        row,
        search_fn=search_fn,
        probe_fn=probe_fn,
        guard_fn=guard_fn,
    )

    assert (
        '"Sahil Aggarwal"'
        in seen
    )

    assert (
        result["decision"]
        == "BUSINESS_IDENTITY_VERIFIED"
    )

    assert (
        result["output"][
            "business_name"
        ]
        == "Example Labs"
    )



def test_provider_degradation_is_not_false_identity_unresolved(
    monkeypatch,
):
    import empire_os.business_identity_actor as bia

    row = {
        "upstream_decision":
            "RESOLVE_IDENTITY",
        "signal_id":
            "sig-provider-down",
        "source_url":
            "https://www.linkedin.com/posts/"
            "alex-example-123_activity-1",
        "title":
            "Looking for an SEO specialist",
        "text":
            "Looking for an SEO specialist",
        "niche":
            "search",
        "metro":
            "online",
    }

    degraded_search = (
        lambda *a, **k: []
    )

    monkeypatch.setattr(
        bia,
        "_default_search",
        degraded_search,
    )

    monkeypatch.setattr(
        bia,
        "search_reliable",
        lambda *a, **k: {
            "organic": [],
            "searchParameters": {
                "engine": "none",
                "search_state":
                    "PROVIDER_DEGRADED",
            },
            "error":
                "All engines failed",
        },
    )

    result = (
        bia.run_business_identity_actor(
            row,
            search_fn=
                bia._default_search,
        )
    )

    assert (
        result["decision"]
        == "DISCOVERY_PROVIDER_DEGRADED"
    )

    assert (
        "business_identity_search_provider_degraded"
        in result["blockers"]
    )

    assert (
        "no_non_social_business_domain_discovered"
        not in result["blockers"]
    )

    assert (
        result["governance"][
            "execution_authority"
        ]
        == "none"
    )



def test_reserved_documentation_domains_cannot_be_business_candidates():
    import empire_os.business_identity_actor as bia

    blocked = [
        "https://example.com/sahil",
        "https://example.org/company",
        "https://example.net/about",
        "https://fake.example/founder",
        "https://company.invalid/team",
        "https://company.test/about",
    ]

    for url in blocked:
        assert (
            bia._candidate_url_allowed(
                url
            )
            is False
        )
