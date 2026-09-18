from empire_os.search_intelligence.models import PageLifecycleState
from empire_os.search_intelligence.robots import recommend_robots
from empire_os.search_intelligence.sitemap import build_sitemap_plan


def test_sitemap_includes_only_canonical_approved_indexable_urls():
    plan = build_sitemap_plan([
        {
            "url": "https://example.com/guides/a",
            "canonical_url": "https://example.com/guides/a",
            "page_type": "guides",
            "indexable": True,
            "index_state": PageLifecycleState.APPROVED,
        },
        {
            "url": "https://example.com/guides/b?utm=x",
            "canonical_url": "https://example.com/guides/b",
            "page_type": "guides",
            "indexable": True,
            "index_state": PageLifecycleState.APPROVED,
        },
        {
            "url": "https://example.com/guides/c",
            "canonical_url": "https://example.com/guides/c",
            "page_type": "guides",
            "indexable": False,
            "index_state": PageLifecycleState.NOINDEX,
        },
    ])
    assert plan["groups"] == {"guides": ["https://example.com/guides/a"]}
    assert plan["publish_allowed"] is False
    assert plan["submit_allowed"] is False
    reasons = {row["reason"] for row in plan["excluded"]}
    assert "noncanonical_url" in reasons
    assert "not_indexable" in reasons


def test_robots_governance_fails_closed():
    assert recommend_robots(
        "https://example.com/admin/users",
        quality_approved=True,
        canonical=True,
    ).robots == "noindex,nofollow"
    assert recommend_robots(
        "https://example.com/guides/a",
        quality_approved=None,
        canonical=True,
    ).robots == "noindex,follow"
    good = recommend_robots(
        "https://example.com/guides/a",
        quality_approved=True,
        canonical=True,
    )
    assert good.robots == "index,follow"
    assert good.execution_allowed is False
