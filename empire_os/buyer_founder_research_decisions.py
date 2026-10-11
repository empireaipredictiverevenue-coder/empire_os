"""Fail-closed, research-only founder decisions for buyer qualification snapshots."""
import json
from pathlib import Path

FILE = 'founder_research_decisions_20261009.json'
ALLOWED = {'astoriacompany.com', 'rvnu.com', 'buythecalls.com'}


def load_research_decisions(directory: Path) -> set[str]:
    path = Path(directory) / FILE
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        raise ValueError('founder_research_decisions_missing_or_unsafe')
    payload = json.loads(path.read_text(encoding='utf-8'))
    if (payload.get('schema_version') != 'empire.founder_research_decisions.v1'
        or payload.get('mode') != 'OBSERVE'
        or payload.get('source') != 'explicit_founder_chat_decision'
        or payload.get('execution_authority') != 'none'
        or any(payload.get(k) is not False for k in (
            'outbound_authorized', 'outbound_sent', 'traffic_authorized',
            'commercial_terms_approved', 'qualification_override',
            'manual_hold_override', 'db_write_authorized'))):
        raise ValueError('founder_research_decisions_unsafe_authority')
    rows = payload.get('decisions')
    if not isinstance(rows, list) or len(rows) != 3:
        raise ValueError('founder_research_decisions_invalid_count')
    found = set()
    for row in rows:
        if not isinstance(row, dict) or row.get('decision') != 'CONTINUE_RESEARCH':
            raise ValueError('founder_research_decisions_invalid_decision')
        domain = row.get('domain')
        if domain not in ALLOWED or domain in found:
            raise ValueError('founder_research_decisions_invalid_domain')
        found.add(domain)
    if found != ALLOWED:
        raise ValueError('founder_research_decisions_incomplete')
    return found
