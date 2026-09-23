from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_buyer_scout_has_no_standing_canonical_promotion_authority():
    service = (
        ROOT / "deploy/systemd/empire-buyer-acquisition-scout.service"
    ).read_text(encoding="utf-8")

    assert "promote_buyer_scout_raw_prospects.py" not in service
    assert "promote_buyer_scout_candidate_to_prospect" not in service
    assert "refresh_buyer_acquisition_team.py" in service
    assert service.index("refresh_buyer_acquisition_team.py") < service.index(
        "run_buyer_acquisition_scout.py"
    )
    assert "run_buyer_acquisition_scout.py" in service
    assert "build_buyer_scout_promotion_plan.py" in service


def test_governed_promotion_command_requires_explicit_execute_flag():
    script = (
        ROOT / "scripts/promote_buyer_scout_raw_prospects.py"
    ).read_text(encoding="utf-8")

    assert 'parser.add_argument("--execute", action="store_true")' in script
    assert 'parser.add_argument("--actor")' in script
    assert "execute=args.execute" in script
    assert "actor=args.actor" in script
