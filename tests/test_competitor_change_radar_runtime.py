"""Read-only original source selection, no extra scraper or scheduler."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from empire_os.competitor_call_channel_atlas import SOURCE, build_atlas
from scripts import review_competitor_change_radar as runner


def _atlas():
    root = Path(__file__).resolve().parents[1]
    return build_atlas(json.loads((root / SOURCE).read_text()),
                       now=datetime(2026, 10, 27, tzinfo=timezone.utc))


def test_rotates_across_original_public_sources(monkeypatch):
    requested = []
    monkeypatch.setattr(runner, "permitted_by_robots", lambda url: True)
    def fetch(url):
        requested.append(url)
        return "<html><body><p>Includes API access to the routing dashboard.</p></body></html>"
    monkeypatch.setattr(runner, "fetch_html", fetch)
    atlas = _atlas()
    cursor = 0
    total_checked = []
    for _ in range(5):
        rows, failures, cursor, checked = runner._live_rows(atlas, 2, cursor)
        assert len(checked) == 2
        assert len(rows) == 2
        assert failures == []
        assert len({urlsplit(u).hostname for u in checked}) == 2
        total_checked.extend(checked)
    assert len(set(total_checked)) >= 7
    assert requested == total_checked


def test_robots_failure_never_causes_fetch(monkeypatch):
    monkeypatch.setattr(runner, "permitted_by_robots", lambda url: False)
    monkeypatch.setattr(runner, "fetch_html", lambda url: pytest.fail("robots fail"))
    rows, failures, cursor, checked = runner._live_rows(_atlas(), 2, 0)
    assert len(checked) == 2
    assert len(failures) == 2
    assert rows == []


def test_untrusted_operator_domain_blocks_before_network(monkeypatch):
    a = _atlas()
    a["operator_profiles"][0]["sources"][0]["url"] = "https://127.0.0.1/private"
    monkeypatch.setattr(runner, "fetch_html", lambda url: pytest.fail("fetch"))
    monkeypatch.setattr(runner, "permitted_by_robots", lambda url: pytest.fail("robots"))
    with pytest.raises(ValueError, match="not permitted"):
        runner._live_rows(a, 2)
