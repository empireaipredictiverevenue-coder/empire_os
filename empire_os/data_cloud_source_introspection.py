"""Read-only PostgreSQL catalog introspection for Empire Data Cloud.

Queries returned by this module are SELECT/WITH statements only. They are used
to build source and target schema manifests for deterministic comparison.
"""
from __future__ import annotations

import re
from typing import Iterable


_SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _normalize_table_names(table_names: Iterable[str]) -> tuple[str, ...]:
    names: set[str] = set()
    for raw in table_names:
        name = str(raw).removeprefix("public.").strip()
        if not name or not _SAFE_NAME.fullmatch(name):
            raise ValueError(f"unsafe table name: {raw!r}")
        names.add(name)
    if not names:
        raise ValueError("at least one table is required")
    return tuple(sorted(names))


def _critical_cte(table_names: Iterable[str]) -> str:
    values = ",".join(f"('{name}')" for name in _normalize_table_names(table_names))
    return f"with critical(table_name) as (values {values})"


def schema_introspection_queries(
    table_names: Iterable[str],
) -> dict[str, str]:
    cte = _critical_cte(table_names)

    return {
        "tables": f"""
{cte}
select
  cls.relname as table_name,
  cls.relrowsecurity as rls_enabled,
  cls.relforcerowsecurity as force_rls
from pg_class cls
join pg_namespace ns on ns.oid = cls.relnamespace
join critical x on x.table_name = cls.relname
where ns.nspname = 'public' and cls.relkind = 'r'
order by cls.relname
""".strip(),
        "columns": f"""
{cte}
select
  c.table_name,
  c.ordinal_position,
  c.column_name,
  c.data_type,
  c.udt_name,
  c.is_nullable,
  c.column_default
from information_schema.columns c
join critical x on x.table_name = c.table_name
where c.table_schema = 'public'
order by c.table_name, c.ordinal_position
""".strip(),
        "constraints": f"""
{cte}
select
  cls.relname as table_name,
  con.conname as constraint_name,
  con.contype as constraint_type,
  pg_get_constraintdef(con.oid, true) as definition
from pg_constraint con
join pg_class cls on cls.oid = con.conrelid
join pg_namespace ns on ns.oid = cls.relnamespace
join critical x on x.table_name = cls.relname
where ns.nspname = 'public'
order by cls.relname, con.contype, con.conname
""".strip(),
        "indexes": f"""
{cte}
select
  i.tablename as table_name,
  i.indexname as index_name,
  i.indexdef as definition
from pg_indexes i
join critical x on x.table_name = i.tablename
where i.schemaname = 'public'
order by i.tablename, i.indexname
""".strip(),
        "policies": f"""
{cte}
select
  p.tablename as table_name,
  p.policyname as policy_name,
  p.permissive,
  p.roles,
  p.cmd,
  p.qual,
  p.with_check
from pg_policies p
join critical x on x.table_name = p.tablename
where p.schemaname = 'public'
order by p.tablename, p.policyname
""".strip(),
        "triggers": f"""
{cte}
select
  event_object_table as table_name,
  trigger_name,
  action_timing,
  event_manipulation,
  action_statement
from information_schema.triggers t
join critical x on x.table_name = t.event_object_table
where t.trigger_schema = 'public'
order by event_object_table, trigger_name, event_manipulation
""".strip(),
        "trigger_routines": f"""
{cte}
select distinct
  p.proname as routine_name,
  pg_get_function_identity_arguments(p.oid) as identity_arguments,
  pg_get_functiondef(p.oid) as definition
from pg_trigger trg
join pg_class cls on cls.oid = trg.tgrelid
join pg_namespace ns on ns.oid = cls.relnamespace
join pg_proc p on p.oid = trg.tgfoid
join critical x on x.table_name = cls.relname
where ns.nspname = 'public'
  and not trg.tgisinternal
order by p.proname, identity_arguments
""".strip(),
        "extensions": """
select extname, extversion
from pg_extension
order by extname
""".strip(),
    }


def queries_are_read_only(queries: dict[str, str]) -> bool:
    forbidden = (
        "insert ",
        "update ",
        "delete ",
        "alter ",
        "drop ",
        "create ",
        "truncate ",
        "grant ",
        "revoke ",
        "copy ",
    )
    for query in queries.values():
        normalized = " ".join(query.lower().split())
        if not normalized.startswith(("select ", "with ")):
            return False
        if any(token in normalized for token in forbidden):
            return False
    return True
