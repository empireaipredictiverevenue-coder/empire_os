from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "deploy/empiredb/outbound_deliverability_roles.sql"
SH = ROOT / "scripts/provision_outbound_deliverability_roles.sh"


def test_deliverability_role_contract_is_least_privilege():
    sql = SQL.read_text(encoding="utf-8")
    lowered = sql.lower()

    assert "create role empire_outbound_deliverability_reader" in lowered
    assert "create role empire_outbound_deliverability_writer" in lowered
    assert "nologin" in lowered
    assert "nobypassrls" in lowered

    writer_grant = re.search(
        r"grant\s+select,\s*insert\s+on(?P<body>.*?)"
        r"to\s+empire_outbound_deliverability_writer;",
        lowered,
        flags=re.DOTALL,
    )
    assert writer_grant is not None
    body = writer_grant.group("body")
    assert "public.outbound_deliverability_observations" in body
    assert "public.outbound_ringleader_decisions" in body
    assert "public.outbound_capacity_ledger" not in body
    assert "public.outbound_mailboxes" not in body
    assert "public.outbound_domains" not in body

    assert "revoke update, delete, truncate, references, trigger" in lowered
    assert "public.outbound_capacity_ledger" in lowered
    assert "from empire_outbound_deliverability_writer;" in lowered


def test_role_contract_contains_no_data_dml_or_send_authority():
    lowered = SQL.read_text(encoding="utf-8").lower()

    assert re.search(r"(?m)^\s*insert\s+into\s+", lowered) is None
    assert re.search(r"(?m)^\s*update\s+", lowered) is None
    assert re.search(r"(?m)^\s*delete\s+from\s+", lowered) is None
    assert "claim_outbound_send" not in lowered
    assert "approve_outbound_intent" not in lowered
    assert "outbound_suppressions" not in lowered


def test_role_provisioner_requires_explicit_authority_expansion_gate():
    text = SH.read_text(encoding="utf-8")

    assert 'EMPIRE_OUTBOUND_ROLE_PROVISION_APPROVED:-' in text
    assert '!= "YES"' in text
    assert "exit 2" in text
    assert "EMPIREDB_MIGRATOR_DSN" in text
    assert "-v ON_ERROR_STOP=1 -1" in text
    assert "outbound_deliverability_roles.sql" in text
    assert "set -euo pipefail" in text
