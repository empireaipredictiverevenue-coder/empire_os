"""Concise semantic inspection for EmpireDB schema drift.

Read-only. Emits normalized per-table column/default/nullability, constraints,
indexes and RLS state so canonical Supabase differences can be repaired without
comparing raw pg_dump formatting.
"""
from __future__ import annotations
import argparse, json, os
from pathlib import Path
from typing import Any
import psycopg

from empire_os.data_cloud_shadow_copy import SHADOW_TABLES, validate_manifest

SQL = r"""
WITH wanted AS (SELECT unnest(%s::text[]) AS table_name),
cols AS (
 SELECT c.table_name,
        jsonb_agg(jsonb_build_object(
          'name',c.column_name,'ordinal',c.ordinal_position,'udt',c.udt_name,
          'nullable',(c.is_nullable='YES'),'default',c.column_default,
          'char_max',c.character_maximum_length,
          'precision',c.numeric_precision,'scale',c.numeric_scale
        ) ORDER BY c.ordinal_position) AS items
 FROM information_schema.columns c
 JOIN wanted w USING(table_name)
 WHERE c.table_schema='public'
 GROUP BY c.table_name
),
cons AS (
 SELECT cl.relname AS table_name,
        jsonb_agg(jsonb_build_object(
          'type',con.contype::text,
          'columns',coalesce((
             SELECT jsonb_agg(att.attname ORDER BY u.ord)
             FROM unnest(con.conkey) WITH ORDINALITY u(attnum,ord)
             JOIN pg_attribute att
               ON att.attrelid=con.conrelid AND att.attnum=u.attnum
          ),'[]'::jsonb),
          'ref_table',
             CASE WHEN con.confrelid=0 THEN NULL
                  ELSE con.confrelid::regclass::text END,
          'ref_columns',coalesce((
             SELECT jsonb_agg(att.attname ORDER BY u.ord)
             FROM unnest(con.confkey) WITH ORDINALITY u(attnum,ord)
             JOIN pg_attribute att
               ON att.attrelid=con.confrelid AND att.attnum=u.attnum
          ),'[]'::jsonb),
          'delete_action',con.confdeltype::text,
          'update_action',con.confupdtype::text,
          'expr',CASE WHEN con.contype='c'
                      THEN pg_get_expr(con.conbin,con.conrelid,true)
                      ELSE NULL END
        ) ORDER BY con.contype::text, con.conname) AS items
 FROM pg_constraint con
 JOIN pg_class cl ON cl.oid=con.conrelid
 JOIN pg_namespace n ON n.oid=cl.relnamespace
 JOIN wanted w ON w.table_name=cl.relname
 WHERE n.nspname='public'
 GROUP BY cl.relname
),
idx AS (
 SELECT cl.relname AS table_name,
        jsonb_agg(jsonb_build_object(
          'unique',i.indisunique,
          'primary',i.indisprimary,
          'keys',(
             SELECT jsonb_agg(
               pg_get_indexdef(i.indexrelid,s.n,true)
               ORDER BY s.n
             )
             FROM generate_series(1,i.indnkeyatts) s(n)
          ),
          'predicate',pg_get_expr(i.indpred,i.indrelid,true)
        ) ORDER BY i.indisprimary DESC,i.indisunique DESC,i.indexrelid) AS items
 FROM pg_index i
 JOIN pg_class cl ON cl.oid=i.indrelid
 JOIN pg_namespace n ON n.oid=cl.relnamespace
 JOIN wanted w ON w.table_name=cl.relname
 WHERE n.nspname='public'
 GROUP BY cl.relname
)
SELECT w.table_name,
       c.relrowsecurity,
       c.relforcerowsecurity,
       coalesce(cols.items,'[]'::jsonb),
       coalesce(cons.items,'[]'::jsonb),
       coalesce(idx.items,'[]'::jsonb)
FROM wanted w
JOIN pg_class c ON c.relname=w.table_name
JOIN pg_namespace n ON n.oid=c.relnamespace AND n.nspname='public'
LEFT JOIN cols USING(table_name)
LEFT JOIN cons USING(table_name)
LEFT JOIN idx USING(table_name)
ORDER BY w.table_name
"""

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--output-path",default="runtime/data_cloud/empiredb_schema_semantic.json")
    args=ap.parse_args()
    dsn=os.environ.get("EMPIREDB_DSN")
    if not dsn: raise RuntimeError("EMPIREDB_DSN is required")
    validate_manifest()
    names=sorted(x.name for x in SHADOW_TABLES)
    with psycopg.connect(dsn,connect_timeout=5,application_name="empire-schema-semantic-inspect") as c:
        c.execute("SET TRANSACTION READ ONLY")
        rows=c.execute(SQL,(names,)).fetchall()
    payload={
      "schema_version":"empire.schema-semantic.v1",
      "read_only":True,
      "tables":{
        r[0]:{
          "rls_enabled":bool(r[1]),"rls_forced":bool(r[2]),
          "columns":r[3],"constraints":r[4],"indexes":r[5]
        } for r in rows
      }
    }
    p=Path(args.output_path); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({
      "read_only":True,
      "tables":len(payload["tables"]),
      "rls_enabled":sum(1 for x in payload["tables"].values() if x["rls_enabled"]),
      "output":str(p)
    },sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
