"""Content-integrity verification for EmpireDB migration copies."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable


_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _quote_identifier(value: str) -> str:
    if not _SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError(f"unsafe SQL identifier: {value!r}")
    return f'"{value}"'


def build_table_digest_query(
    table_name: str,
    *,
    order_columns: Iterable[str],
) -> str:
    """Build a read-only deterministic digest query for a Postgres table."""

    name = table_name.removeprefix("public.")
    quoted_table = _quote_identifier(name)
    columns = tuple(str(column) for column in order_columns)
    if not columns:
        raise ValueError("at least one deterministic order column is required")
    order_sql = ", ".join(f't.{_quote_identifier(column)}' for column in columns)

    return f"""
WITH digest_settings AS MATERIALIZED (
  SELECT
    set_config('TimeZone', 'UTC', true),
    set_config('bytea_output', 'hex', true)
)
SELECT
  count(*)::bigint AS row_count,
  encode(
    digest(
      coalesce(
        string_agg(
          encode(digest(to_jsonb(t)::text, 'sha256'), 'hex'),
          '' ORDER BY {order_sql}
        ),
        ''
      ),
      'sha256'
    ),
    'hex'
  ) AS content_sha256
FROM public.{quoted_table} AS t
CROSS JOIN digest_settings
""".strip()


@dataclass(frozen=True)
class TableCopyEvidence:
    table_name: str
    source_rows: int
    target_rows: int
    source_sha256: str
    target_sha256: str

    def validate(self) -> None:
        if self.source_rows < 0 or self.target_rows < 0:
            raise ValueError("row counts cannot be negative")
        for value in (self.source_sha256, self.target_sha256):
            if not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError("table digest must be lowercase sha256 hex")


def verify_table_copy(evidence: TableCopyEvidence) -> dict[str, object]:
    evidence.validate()
    findings: list[str] = []

    if evidence.source_rows != evidence.target_rows:
        findings.append("row_count_mismatch")
    if evidence.source_sha256 != evidence.target_sha256:
        findings.append("content_digest_mismatch")

    return {
        "schema_version": "empire.data-cloud-table-copy-verification.v1",
        "table_name": evidence.table_name,
        "verified": not findings,
        "findings": findings,
        "evidence": asdict(evidence),
    }


def verify_copy_manifest(
    evidence_rows: Iterable[TableCopyEvidence],
) -> dict[str, object]:
    results = [verify_table_copy(evidence) for evidence in evidence_rows]
    failed = [
        result["table_name"]
        for result in results
        if not result["verified"]
    ]
    return {
        "schema_version": "empire.data-cloud-copy-manifest-verification.v1",
        "verified": not failed and bool(results),
        "table_count": len(results),
        "failed_tables": failed,
        "results": results,
        "authority": {
            "canonical_promotion": False,
            "source_mutation": False,
            "target_mutation": False,
        },
    }
