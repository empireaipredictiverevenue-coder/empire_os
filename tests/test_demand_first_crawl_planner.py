import argparse
import ast
import builtins
from dataclasses import replace
import importlib
from pathlib import Path

import pytest

from empire_os.demand_first_crawl_planner import (
    ALLOWED_SOURCES,
    plan_demand_first_crawl,
)
from empire_os.demand_genesis import DemandPlan
from empire_os.demand_readiness import DemandReadiness
from empire_os.demand_registry import DemandRegistryRecord


ROOT = Path(__file__).resolve().parents[1]


def record():
    return DemandRegistryRecord(
        plan=DemandPlan(
            plan_id="plan-test", channel="aeo", objective="Qualified discovery",
            audience="Roofing buyers", evidence_refs=("demand:test",),
            success_metric="qualified_inbound_conversations",
        ),
        readiness=DemandReadiness(
            plan_id="plan-test", ready_for_review=True, evidence_score=0.9,
            readiness_reason="evidence_sufficient_for_operator_review",
            missing_evidence=(),
        ),
        evidence={"source": "test fixture"},
    )


def proposal(**overrides):
    kwargs = dict(
        source="overpass", niche="roofing", max_candidates=7,
        source_capability_evidence_refs=("capability:test",),
    )
    kwargs.update(overrides)
    return plan_demand_first_crawl(record(), **kwargs)


def test_without_approval_requires_review_and_emits_no_args():
    plan = proposal()
    assert plan.state == "REVIEW_REQUIRED"
    assert plan.dispatch_ready is False
    assert plan.crawler_cli_args == ()
    assert plan.as_dict()["execution_authority"] == "none"
    assert plan.demand_evidence_refs == ("demand:test",)
    assert plan.source_capability_evidence_refs == ("capability:test",)


def test_approved_args_are_deterministic_and_preserve_bound_and_evidence():
    kwargs = dict(metro="New York", approval_evidence_refs=("approval:test",))
    first, second = proposal(**kwargs), proposal(**kwargs)
    assert first == second
    assert first.as_dict() == second.as_dict()
    assert first.state == "READY_FOR_CRAWLER_DISPATCH"
    assert first.dispatch_ready is True
    assert first.execution_authority == "none"
    assert first.approval_evidence_refs == ("approval:test",)
    assert first.crawler_cli_args == (
        "--source", "overpass", "--niche", "roofing", "--metro", "New York",
        "--max-candidates", "7",
    )


@pytest.mark.parametrize("target", [
    {"niche": "roofing"}, {"niche": None, "metro": "London"},
    {"niche": None, "country": "GB"}, {"country": "US"},
])
def test_args_match_actual_runner_parser_without_importing_or_running_it(target):
    # Extract only argparse declarations: importing the runner creates log dirs,
    # and calling main would cross the execution boundary.
    tree = ast.parse((ROOT / "empire_os/crawler_runner.py").read_text())
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "main")
    declarations = []
    for node in main.body:
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr == "parse_args"):
            break
        declarations.append(node)
    namespace = {"argparse": argparse}
    exec(compile(ast.Module(body=declarations, type_ignores=[]),
                 "crawler-parser-only", "exec"), namespace)
    plan = proposal(**target, max_candidates=1, approval_evidence_refs=("approval:test",))
    parsed = namespace["parser"].parse_args(plan.crawler_cli_args)
    assert parsed.source == plan.source
    assert parsed.niche == plan.niche
    assert parsed.metro == plan.metro
    assert parsed.country == plan.country
    assert parsed.max_candidates == 1


@pytest.mark.parametrize("overrides", [
    {"source": "unknown"}, {"source": "biz_search"}, {"source": ""},
    {"source": "overpass_osm"}, {"source": None},
    {"niche": None}, {"niche": " "}, {"metro": ""},
    {"metro": "London", "country": "GB"}, {"country": "United Kingdom"},
    {"max_candidates": None}, {"max_candidates": 0}, {"max_candidates": -1},
    {"max_candidates": True}, {"max_candidates": 1.5}, {"max_candidates": "7"},
    {"source_capability_evidence_refs": ()},
    {"source_capability_evidence_refs": (" ",)},
    {"source_capability_evidence_refs": "capability:test"},
    {"approval_evidence_refs": True}, {"approval_evidence_refs": ("",)},
    {"approval_evidence_refs": "approval:test"},
    {"approval_evidence_refs": (None,)},
    {"niche": "--dry-run"}, {"metro": "London\n--source=reddit"},
    {"metro": "London\x00"},
])
def test_invalid_input_fails_closed(overrides):
    with pytest.raises(ValueError):
        proposal(**overrides)


@pytest.mark.parametrize("change", ["not_ready", "mismatch", "authority", "evidence", "blank_refs"])
def test_invalid_demand_record_blocks_even_with_approval(change):
    item = record()
    if change == "not_ready":
        item = replace(item, readiness=replace(item.readiness, ready_for_review=False))
    elif change == "mismatch":
        item = replace(item, readiness=replace(item.readiness, plan_id="another-plan"))
    elif change == "authority":
        item = replace(item, plan=replace(item.plan, execution_authority="crawl"))
    elif change == "evidence":
        item = replace(item, evidence={})
    else:
        item = replace(item, plan=replace(item.plan, evidence_refs=(" ",)))
    with pytest.raises(ValueError):
        plan_demand_first_crawl(
            item, source="overpass", niche="roofing", max_candidates=1,
            source_capability_evidence_refs=("capability:test",),
            approval_evidence_refs=("approval:test",),
        )


def test_allowlist_matches_real_source_registrations_without_loading_adapters():
    names = set()
    for path in (ROOT / "empire_os/lead_sources").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "SourceInfo"):
                continue
            fields = {kw.arg: kw.value.value for kw in node.keywords
                      if isinstance(kw.value, ast.Constant)}
            if fields.get("tier") == "real":
                names.add(fields["name"])
    assert ALLOWED_SOURCES == names


def test_planner_does_not_import_execution_dependencies_or_perform_io(monkeypatch):
    import empire_os.demand_first_crawl_planner as planner

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        assert not name.startswith((
            "empire_os.crawler_runner", "empire_os.lead_sources", "subprocess",
            "socket", "requests", "httpx", "psycopg", "sqlite3",
        ))
        return original_import(name, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("planner must not perform IO")

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    importlib.reload(planner)
    assert proposal().state == "REVIEW_REQUIRED"
    assert proposal(approval_evidence_refs=("approval:test",)).dispatch_ready


def test_max_candidates_matches_guarded_acquisition_bound():
    with pytest.raises(ValueError, match="between 1 and 25"):
        proposal(max_candidates=26)
