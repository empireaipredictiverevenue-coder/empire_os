from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_global_growth_doctrine_is_canonical_and_global():
    text = read("docs/GLOBAL_OPPORTUNITY_GROWTH_DOCTRINE.md")
    required = (
        "Status: CANONICAL STRATEGY — LOCKED",
        "global Predictive Revenue operating system",
        "GLOBAL OPPORTUNITY GRAPH",
        "OPPORTUNITY FOUNDRY",
        "MARKET ENTRY OS",
        "EMPIRE ECONOMIC MEMORY",
        "Astra portfolio upgrade",
        "Anti-drift rules",
    )
    for marker in required:
        assert marker in text


def test_founder_console_remains_top_level_truth_surface():
    text = read("docs/FOUNDER_CONSOLE_OPERATING_SPEC.md")
    required = (
        "top-level truth surface",
        "Where are we making money?",
        "Where could we make more?",
        "What is stopping us?",
        "What should happen next?",
        "Revenue Pipeline / Commercial Loop",
        "Growth & Opportunities",
        "Global Markets",
        "Blueprint Control Room",
        "UNKNOWN is not 0",
    )
    for marker in required:
        assert marker in text


def test_blueprint_references_canonical_global_strategy_docs():
    text = read("docs/BLUEPRINT_V6.md")
    assert "## Global Growth Strategic Lock" in text
    assert "docs/GLOBAL_OPPORTUNITY_GROWTH_DOCTRINE.md" in text
    assert "docs/FOUNDER_CONSOLE_OPERATING_SPEC.md" in text
    assert (
        "docs/history/VULTR_BILLION_SCALE_ANALYSIS_RECOVERED_2026-09-20.txt"
        in text
    )


def test_closure_ledger_contains_founder_anti_drift_lock():
    text = read("docs/FOUNDER_CLOSURE_LEDGER_2026-09-20.md")
    assert "## Canonical Anti-Drift Strategy Lock — 2026-09-20" in text
    assert "global business / global revenue infrastructure company" in text
    assert "Global Opportunity Graph + Opportunity Foundry + Market Entry OS" in text
    assert "Founder Console is the top-level operating/truth cockpit" in text


def test_recovered_vultr_plan_is_preserved_but_not_promoted_to_current_truth():
    historical = ROOT / (
        "docs/history/VULTR_BILLION_SCALE_ANALYSIS_RECOVERED_2026-09-20.txt"
    )
    assert historical.exists()
    assert historical.stat().st_size > 5000

    doctrine = read("docs/GLOBAL_OPPORTUNITY_GROWTH_DOCTRINE.md")
    assert "historical strategy evidence, not current runtime truth" in doctrine
    assert (
        "Do not reuse old lead counts, SQLite architecture, "
        "revenue-per-cycle claims, forecasts or valuation scenarios as current facts"
        in doctrine
    )
