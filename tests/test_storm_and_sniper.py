"""Smoke tests for the storm predictor and warehouse sniper modules.

The real storm_predictor.py was salvaged from the original Empire-USA-Strike
code. The reddit_sniper.py replaced the old warehouse_sniper stub. These
tests verify the modules load cleanly and the basic observe/reason/act
contract is preserved.
"""
from empire_os.storm_predictor import StormPredictor, StormEvent, build_satellite_url
from empire_os.reddit_sniper import RedditSniper, RedditLead


class TestStormPredictor:
    def test_build(self):
        p = StormPredictor()
        assert p.events == []

    def test_observe(self):
        p = StormPredictor()
        s = p.observe()
        assert s["agent"] == "storm-predictor"

    def test_reason_returns_action(self):
        p = StormPredictor()
        d = p.reason({})
        assert "action" in d

    def test_act(self):
        p = StormPredictor()
        r = p.act('{"action": "scan"}')
        assert r["action"] == "scan"


class TestRedditSniper:
    def test_build(self):
        s = RedditSniper()
        assert s.leads == []

    def test_observe(self):
        s = RedditSniper()
        st = s.observe()
        assert st["agent"] == "reddit-sniper"

    def test_reason_returns_action(self):
        s = RedditSniper()
        d = s.reason({})
        assert "action" in d

    def test_act(self):
        s = RedditSniper()
        r = s.act('{"action": "skip"}')
        assert r["action"] == "skip"


class TestBuildSatelliteUrl:
    def test_with_key(self):
        url = build_satellite_url("33101", api_key="test")
        assert "33101" in url
        assert "test" in url

    def test_without_key(self):
        assert build_satellite_url("33101") == ""