from datetime import datetime, timezone
import json
from pathlib import Path

import scripts.refresh_adaptive_outreach_optimizer as runtime


NOW = datetime(2026, 10, 2, 21, 0, tzinfo=timezone.utc)


def test_refresh_writes_derived_learning_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr(
        runtime,
        "_records",
        lambda _dsn, lookback_days: [
            {
                "delivered": True,
                "classification": "positive",
                "metadata": {
                    "adaptive_outreach": {
                        "exact_segment": (
                            "managed_service|roofing|economic_buyer"
                        ),
                        "subject_arm": "company_question",
                        "body_arm": "plain_one_page",
                    },
                },
            },
            {
                "delivered": True,
                "classification": "unsubscribe",
                "metadata": {},
            },
        ],
    )
    payload = runtime.refresh(
        tmp_path,
        dsn="postgresql://not-used",
        lookback_days=90,
        now=NOW,
    )
    assert payload["learning_state"] == "LEARNING"
    assert payload["labelled_intent_count"] == 1
    assert payload["unlabelled_history_count"] == 1
    assert payload["historical_reply_classes"] == {
        "positive": 1,
        "unsubscribe": 1,
    }
    assert payload["outbound_mutation"] is False
    written = json.loads(
        (tmp_path / runtime.SNAPSHOT_PATH).read_text()
    )
    assert written["canonical_truth"] == (
        "EmpireDB outbound events + classified replies"
    )


def test_systemd_optimizer_is_read_only_derived_runtime():
    root = Path(__file__).resolve().parents[1]
    service = (
        root / "deploy/systemd/empire-adaptive-outreach-optimizer.service"
    ).read_text()
    timer = (
        root / "deploy/systemd/empire-adaptive-outreach-optimizer.timer"
    ).read_text()
    assert "EnvironmentFile=/etc/empiredb.env" in service
    assert "refresh_adaptive_outreach_optimizer.py" in service
    assert "ReadWritePaths=/srv/empire_os/runtime" in service
    assert "OnUnitActiveSec=10min" in timer
    assert "outbound-governor" not in service
    assert "sender" not in service.lower()
