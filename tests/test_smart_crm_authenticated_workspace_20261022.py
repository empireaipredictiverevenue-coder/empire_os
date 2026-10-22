"""Signed Smart CRM workspace contract, candidate only: no production mutation."""
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]/"release_candidates/smart_crm_authenticated"
HTML=ROOT/"revenue_crm_action_console.html"
JS=ROOT/"revenue_crm_action_console.js"
PRODUCTION=Path(
 "/opt/empire-ai/crm-pilot-releases/agent-kanban-crm-20261022v1/empire_os/static")


def markup():
    return BeautifulSoup(HTML.read_text(encoding="utf-8"),"html.parser")


def test_six_navigation_destinations_are_authenticated_and_real():
    soup=markup()
    expected=[
       ("#contacts-workspace","Contacts"),
       ("#opportunities-workspace","Opportunities"),
       ("#sales-actions-workspace","Sales Actions"),
       ("#partner-conversations","Conversations"),
       ("#revenue-workspace","Revenue"),
       ("#intelligence-workspace","Startup & agents"),
    ]
    nav=soup.select_one('nav#workspace-nav[hidden]')
    assert nav is not None
    assert [(a.get("href"),a.get_text(strip=True)) for a in nav.select("a")]==expected
    assert all(soup.select_one(f'section#{href[1:]}') for href,_ in expected)
    assert soup.select_one("section#review-panel[hidden]")
    assert soup.select_one("form#login-form")
    assert not soup.select("script:not([src])")
    ids=[node["id"] for node in soup.select("[id]")]
    assert len(ids)==len(set(ids))


def test_existing_specialist_and_sales_sections_retained():
    soup=markup()
    assert soup.select_one("#buyer-results")
    assert soup.select_one("#solar-preview-results")
    assert soup.select_one("#partner-source-results")
    assert soup.select_one("#win-plan-results")
    assert soup.select_one("#inbound-source-results")
    assert soup.select_one("#sales-actions-workspace-status")
    assert soup.select_one("#kanban-results")
    assert soup.select_one("#revenue-evidence-status")
    text=soup.get_text(" ",strip=True)
    for term in ("Startup Revenue Intelligence","Research","Jev","ASTRA",
                 "tenant-scoped","not an independently verified personal-contact directory",
                 "no revenue amount claimed"):
        assert term.lower() in text.lower()


def test_candidate_keeps_prior_live_core_src_and_signed_auth():
    src=JS.read_text(encoding="utf-8")
    assert '"/v1/revenue-crm/auth/login"' in src
    assert 'result.scope !== "crm:read"' in src
    assert 'credentials: "omit"' in src
    assert 'cache: "no-store"' in src
    assert 'redirect: "error"' in src
    assert 'clearSession("Your CRM session expired' in src
    assert 'state.token = "";' in src
    assert 'localStorage' not in src
    assert 'sessionStorage' not in src
    assert 'state.records = []' in src
    assert '"/v1/revenue-crm/prospects?limit="' in src
    assert '"/v1/revenue-crm/buyers?limit=40"' in src
    assert '"/v1/revenue-crm/department-kanban?max_cards_per_lane=10"' in src
    assert 'data.tenant_scope !== "explicit_tenant"' in src
    assert 'data.execution_authority !== "none"' in src
    assert 'data.read_only !== true' in src
    assert 'const names = ["ready", "running", "review", "blocked", "done", "failed"]' in src
    assert 'new WebSocket' not in src
    assert 'navigator.sendBeacon' not in src


def test_no_revenue_or_startup_promotions_without_receipt():
    src=JS.read_text(encoding="utf-8")
    markup_html=HTML.read_text(encoding="utf-8")
    assert "Verified tenant settlement reader not connected" in markup_html
    assert "before CRM promotion" in markup_html
    assert "no agent work promoted" in src
    assert "No contact approval inferred" in src
    assert "No sends, stage changes or payment authority." in src
    assert "not a verified personal-contact directory" not in src  # no parallel tracking JS
    assert 'fetch("https://' not in src
    assert "payment.execute(" not in src


def test_candidate_is_exactly_two_staged_assets_not_inplace_live_replacement():
    assert HTML.is_file() and JS.is_file()
    assert PRODUCTION.joinpath(HTML.name).read_bytes()!=HTML.read_bytes()
    assert PRODUCTION.joinpath(JS.name).read_bytes()!=JS.read_bytes()
    assert PRODUCTION.joinpath(HTML.name).stat().st_size>1000
    assert PRODUCTION.joinpath(JS.name).stat().st_size>1000
