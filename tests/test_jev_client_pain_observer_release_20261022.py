from datetime import datetime, timezone
import json

import pytest

from scripts.run_jev_client_pain_observer_20261022 import run

NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)


def test_receipt_is_private_and_writes_only_derived_data(tmp_path):
    history = tmp_path / "history.json"
    inbox = tmp_path / "inbox.json"
    target = tmp_path / "private"
    observation = {
        "source": "reddit", "url": "https://www.reddit.com/r/SaaS/comments/abc/",
        "observed_at": NOW.isoformat(),
        "title": "My SaaS needs more leads", "text": "I own this SaaS and need more leads this week.",
    }
    history.write_text(json.dumps({"observations": [observation]}))
    inbox.write_text(json.dumps({}))
    before = history.read_bytes()
    output = run(history=history, inbox=inbox, output_dir=target,
                 write_private=True, now=NOW)
    assert history.read_bytes() == before
    assert output["concrete_pain_theme_count"] == 1
    assert output["verified_individual_clients"] == 0
    assert output["outreach_sent"] == 0
    assert output["network_calls"] == 0
    assert output["model_calls"] == 0
    assert target.stat().st_mode & 0o777 == 0o700
    for filename in ("private_latest.json", "aggregate_latest.json"):
        assert (target / filename).stat().st_mode & 0o777 == 0o600
    aggregate = (target / "aggregate_latest.json").read_text()
    assert "comments/abc" not in aggregate
    assert "My SaaS" not in aggregate
    assert json.loads((target / "private_latest.json").read_text())["items"][0]["private_evidence_url"]


def test_oversized_sources_refuse_partial_receipt(tmp_path):
    history = tmp_path / "history.json"
    inbox = tmp_path / "inbox.json"
    history.write_text(json.dumps({"observations": [{}] * 501}))
    inbox.write_text("{}")
    with pytest.raises(ValueError, match="review capacity"):
        run(history=history, inbox=inbox, output_dir=tmp_path / "result",
            write_private=True, now=NOW)
    assert not (tmp_path / "result").exists()


def test_symlink_source_is_rejected(tmp_path):
    real = tmp_path / "original.json"
    real.write_text('{"observations":[]}')
    linked = tmp_path / "source.json"
    linked.symlink_to(real)
    other = tmp_path / "inbox.json"
    other.write_text("{}")
    with pytest.raises(ValueError, match="unsafe source"):
        run(history=linked, inbox=other, now=NOW)


def test_no_write_dry_run(tmp_path):
    h = tmp_path / "observations.json"
    i = tmp_path / "signals.json"
    h.write_text('{"observations":[]}')
    i.write_text('{}')
    dst = tmp_path / "dry_result"
    a = run(history=h, inbox=i, output_dir=dst,
            write_private=False, now=NOW)
    assert not dst.exists()
    assert a["observations_submitted"] == 0
