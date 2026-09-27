import json
import subprocess


def test_snapshot_script_builds_b2b_only_contract():
    result = subprocess.run(
        [".venv/bin/python", "scripts/build_legal_mass_tort_snapshot.py"],
        cwd="/srv/empire_os",
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["consumer_targeting"] is False
    assert payload["individual_health_legal_profiling"] is False
    assert payload["firm_buyer_intelligence"] is True
    assert payload["live_market_evidence_bound"] is False
    assert payload["market_opportunities_observed"] is None
