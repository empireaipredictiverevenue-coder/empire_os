"""Compare EmpireDB structural fingerprints to canonical Supabase snapshot."""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import psycopg

SOURCE = {
  "astra_observer_tokens": [
    true,
    false,
    3,
    "e08b79c448f87160e40286daf53f4680",
    2,
    "54a2a2f3d16e6cbb065811e7f149ba67",
    1,
    "2900dcfdd96591efa50ad51f3f2b3faa"
  ],
  "business_entities": [
    true,
    false,
    12,
    "e589ed4944d49f52028cb29efc51e36b",
    1,
    "4a8048121b6e98dc41b0ea5696870821",
    4,
    "3d2192634f20b666f750b7f249f8d25d"
  ],
  "business_entity_conflicts": [
    true,
    false,
    8,
    "b6646364c469c6f7314337d06b6b2f9c",
    3,
    "39eb4d516996fc76c2b80f4b18c852b4",
    4,
    "d8ad50cd21e5982ef20424de91ef1955"
  ],
  "buyer_candidate_review_events": [
    true,
    false,
    6,
    "6a37ebfb439e0a8493e826ba3998fd9b",
    3,
    "708a5ea42b7c99a061dfe9f2f4069cdf",
    2,
    "160b06ca09a9af5ee468414d6ee79409"
  ],
  "buyer_candidate_reviews": [
    true,
    false,
    16,
    "6f8b2b4f0f0de1f85e50d3d9eac810ba",
    7,
    "a9be7f93d3f624247939f0417fbaaeb3",
    3,
    "e236517826404ff9d937b3575f7f7911"
  ],
  "buyer_commercial_evidence": [
    true,
    false,
    19,
    "17655b408ba3c6000417d8c63414bdcb",
    8,
    "8b6e15e8da1da928379606ede5a72e5b",
    3,
    "cb4b5b2a092a7cffd083aefe38abec68"
  ],
  "buyer_scout_candidates": [
    true,
    false,
    24,
    "dfffda5ca14d8a6f1a9f0442ced492e4",
    7,
    "78a79a4b0b4d0cb3e09f6be022261ca7",
    5,
    "4623513d94ce9afa98acb6838b86f126"
  ],
  "buyer_subscriptions": [
    true,
    false,
    18,
    "75f05edc4ce9437ad8e7e7cc341a78d0",
    5,
    "918b23feb53d1a589f3255e5e4b61837",
    6,
    "f906510884bc1a7b88bd438b8ca480b0"
  ],
  "buyers": [
    true,
    false,
    42,
    "30699e2b2ef925e6a39c94ccdd97c9d7",
    2,
    "8016c0d2450d915df5500dc201772ba3",
    4,
    "f44877256750567d4f2be9e2262f6d83"
  ],
  "closer_cases": [
    true,
    false,
    12,
    "5d2ea6782228824c185526b1f15b2fcf",
    10,
    "9a9cb39d9531de51a783a4530b6dae84",
    3,
    "b1584c193a666bbab43a38b899b40f2a"
  ],
  "commercial_events": [
    true,
    false,
    18,
    "55a14742906a307e5ccc9569ceb54a59",
    8,
    "f6379a27fd5b9aefda8c90a6f01fe6f9",
    8,
    "395dc77e0c78b3991df654c848e46529"
  ],
  "commercial_evidence_registry": [
    true,
    false,
    23,
    "0c1d752cc1435605d35714b9fb06dae9",
    12,
    "189e1481e5b03b69a08dcf535efad8bd",
    4,
    "cf8db349512826e96aeea4887a3df69e"
  ],
  "commercial_product_catalog_events": [
    true,
    false,
    7,
    "7806e60e3bc1c6e10589c459be2db55b",
    3,
    "16f3d45e26b96a36034dec1bdd575628",
    2,
    "e38bdf34b969fcab31873e812cfc1ce3"
  ],
  "commercial_product_versions": [
    true,
    false,
    21,
    "923a098f05ad5ed9ff756890afd6eb75",
    6,
    "df1388b6a290f5cef65c6deb2aec8f1f",
    4,
    "0d0fadbd7bcaa4e4ee6743819686666e"
  ],
  "commercial_products": [
    true,
    false,
    17,
    "dbfc9cb99c5b317e4e9788e9f652d479",
    3,
    "20f696f3c46ebc575c566778e96c0a55",
    4,
    "24aa6e008dcb3e635ddb50aed6d0c430"
  ],
  "crypto_payment_requests": [
    true,
    false,
    17,
    "8775d8ee5e13c7a5ef0333f15b0dca51",
    3,
    "cd6f81b20fd76935c41c096734411c05",
    5,
    "007e2091650879e7bf10e3de5cfd7d58"
  ],
  "enriched_leads": [
    true,
    false,
    18,
    "7b74067846768b9e05d16880ea82906b",
    3,
    "0821d312ca0dd8228352d9a0a6245061",
    6,
    "581dd921d14f708d561754613fa3e49a"
  ],
  "fulfilment_orders": [
    true,
    false,
    23,
    "0b1fee027b52d6b2b175e44e4330e0db",
    6,
    "86310bb16dce6d91728c028ed395d8e4",
    6,
    "de7ce0f863efca5d28fec069af507488"
  ],
  "gtm_experiments": [
    true,
    false,
    13,
    "123adb07927f981efd26d6f94e721a1a",
    2,
    "65da9fae403804a650db57459b3a1f2e",
    3,
    "f1f782efabaa7e753a3b0cb7861553cb"
  ],
  "gtm_jobs": [
    true,
    false,
    27,
    "33ac42c3dedbcd26425b5553f01e810e",
    2,
    "c4d7ba36936e8e1e468210db14dd276c",
    8,
    "f9c10fb62d96df968ff57da2389e057c"
  ],
  "gtm_opportunities": [
    true,
    false,
    21,
    "74e178d86b4aa5fb60757db6a969e806",
    1,
    "b298bdde3345bff91f5d11582fc76909",
    5,
    "21cd1d650d0c511dc8c360d6666bcb82"
  ],
  "intelligence_contact_points": [
    true,
    false,
    12,
    "8b4c1e347678f40c3c72d357ba668fc3",
    8,
    "7d06ada40917dd4f5b5c362cb751890c",
    3,
    "6b421fcccbed97bb37d92dec67f1d363"
  ],
  "intelligence_facts": [
    true,
    false,
    14,
    "9b940463e301c4250952da60dc13fd33",
    5,
    "90bff74e1e579c5d5677c7b4c3b3dec2",
    3,
    "f519959c52c7f3b83254e77cff14c9bb"
  ],
  "intelligence_outcomes": [
    true,
    false,
    9,
    "15f73a587c7354cdf898c5cdd55806b1",
    3,
    "a4504f530cd56c2307c508a1260b30f1",
    2,
    "c1c3e4b2b1301150ca9b033885849eda"
  ],
  "intelligence_people": [
    true,
    false,
    7,
    "277e9d229e9ed8ccca695db7415d3b55",
    2,
    "db628ff99cb0e494a9b87a559e1cfddd",
    2,
    "384418bedeee1a0617d3efd43231ed5e"
  ],
  "intelligence_scores": [
    true,
    false,
    10,
    "5ca42bbe5bc4375efd04b49bd061019d",
    3,
    "ae730a927e46eef69047edc06ec9ed8a",
    3,
    "e045e764e9e0d60bf299b6ee72f4f94c"
  ],
  "intelligence_segments": [
    true,
    false,
    7,
    "bb5866a25dfff0cbb6294476203907ca",
    2,
    "108acc240b7f931ed943bfb93528f89d",
    2,
    "e3da54498b5551f0e195508983eab98e"
  ],
  "intelligence_signals": [
    true,
    false,
    11,
    "35c87bc093ad39ccbc959e791ebdf2be",
    5,
    "3ff8f0f2bebb6d05bde2077957190004",
    3,
    "eabf5993c20b627bfee522bece06837a"
  ],
  "intelligence_sources": [
    true,
    false,
    8,
    "10c131984080fae953229ddd6767e74d",
    5,
    "e433c66ca8a2c8e0d354523319853106",
    2,
    "106dedc543f1fc9973238dbcca02eaa3"
  ],
  "outbound_events": [
    true,
    false,
    8,
    "0573138d3ecc5610954081d8280e9f9f",
    3,
    "1e1a98fdfe72fe4866602d8cffae515b",
    2,
    "27717f457375f247d3063f5abda42d09"
  ],
  "outbound_intents": [
    true,
    false,
    21,
    "a868dba50274f802075dbe2f432488ab",
    9,
    "82cf9c7f479a17893118b1eb5a1c8b88",
    4,
    "1c29a9f12042f7d06077901a61c7fd85"
  ],
  "outbound_replies": [
    true,
    false,
    12,
    "7600a5989c2b348aba3c208ab8bcef6b",
    5,
    "6ddc818c9e58de00b4c14ead4a6b2a4b",
    3,
    "4e8ee459a9de400b71fa843b8851481a"
  ],
  "outbound_suppressions": [
    true,
    false,
    6,
    "5d40b2e3d08695306a423a46e2737777",
    3,
    "9d8d252142c93e0c5f8a1029da6adc2b",
    2,
    "92fb021da2bf26aef07cacf57ef4f517"
  ],
  "outreach_log": [
    true,
    false,
    18,
    "fa4fa3b09825a7d57303a000657426de",
    4,
    "6772ec717ff7d9fe92e16d6e0b0ec10d",
    4,
    "47aa47d246f0ea216269010cf32ef3b1"
  ],
  "prospect_acquisitions": [
    true,
    false,
    8,
    "7fb26cbb27f8304a42efe4593d13965c",
    3,
    "4b5cf2f6ac468fc98768395764afcb76",
    4,
    "d5f5b0685848db2329cbb0d8fa75d7c2"
  ],
  "prospect_entity_links": [
    true,
    false,
    8,
    "a1c0268fdb1d9785efa3b7bd13e7cb86",
    4,
    "fde5a445bfce516c819b2a32d44dfbc8",
    4,
    "2bd2961293d0461516b08ac9b4b8254f"
  ],
  "prospect_identity_claims": [
    true,
    false,
    3,
    "366902b7fb2195f0b83c1a0f1fa9d24f",
    2,
    "fc1ffffe22152795624b85276041c7f2",
    1,
    "038e72c96b20213d00832734a8ec3930"
  ],
  "prospect_qualifications": [
    true,
    false,
    22,
    "047c3525c1d7095bd54536318c6dab77",
    7,
    "7a5763dd716e57e2232aee75a6439a48",
    7,
    "058f9fde656bda51d27e58304a48e15d"
  ],
  "prospects": [
    true,
    false,
    19,
    "51a00c94b86aaa97bb4025e023ca64e3",
    1,
    "d00f24580483fd28ccf272b106d9c2ff",
    1,
    "c8a36328097b8be78f45afd4e5a1a997"
  ],
  "strike_packs": [
    true,
    false,
    19,
    "f67b4d63257a88aa579b27e73e56d295",
    3,
    "ff3156e46bcd9f66d4f56177d7e84974",
    2,
    "86981a327a609d3576b269ffb918dc39"
  ]
}

SQL = r"""
WITH wanted AS (
  SELECT unnest(%s::text[]) AS table_name
),
col_fp AS (
  SELECT c.table_name, count(*)::int AS column_count,
         md5(string_agg(concat_ws('|', c.ordinal_position::text,c.column_name,c.data_type,c.udt_name,c.is_nullable,
         coalesce(c.column_default,'<null>'),c.is_identity,c.is_generated,coalesce(c.character_maximum_length::text,'<null>'),
         coalesce(c.numeric_precision::text,'<null>'),coalesce(c.numeric_scale::text,'<null>')), E'\\n' ORDER BY c.ordinal_position)) AS columns_md5
  FROM information_schema.columns c JOIN wanted w USING(table_name)
  WHERE c.table_schema='public' GROUP BY c.table_name
),
con_fp AS (
  SELECT cls.relname AS table_name,count(*)::int AS constraint_count,
         md5(string_agg(concat_ws('|',con.contype::text,con.conname,pg_get_constraintdef(con.oid,true)),E'\\n' ORDER BY con.conname)) AS constraints_md5
  FROM pg_constraint con JOIN pg_class cls ON cls.oid=con.conrelid JOIN pg_namespace n ON n.oid=cls.relnamespace
  JOIN wanted w ON w.table_name=cls.relname WHERE n.nspname='public' GROUP BY cls.relname
),
idx_fp AS (
  SELECT i.tablename AS table_name,count(*)::int AS index_count,
         md5(string_agg(concat_ws('|',i.indexname,i.indexdef),E'\\n' ORDER BY i.indexname)) AS indexes_md5
  FROM pg_indexes i JOIN wanted w ON w.table_name=i.tablename WHERE i.schemaname='public' GROUP BY i.tablename
)
SELECT w.table_name,c.relrowsecurity,c.relforcerowsecurity,
       coalesce(col_fp.column_count,0),coalesce(col_fp.columns_md5,md5('')),
       coalesce(con_fp.constraint_count,0),coalesce(con_fp.constraints_md5,md5('')),
       coalesce(idx_fp.index_count,0),coalesce(idx_fp.indexes_md5,md5(''))
FROM wanted w JOIN pg_class c ON c.relname=w.table_name
JOIN pg_namespace n ON n.oid=c.relnamespace AND n.nspname='public'
LEFT JOIN col_fp USING(table_name) LEFT JOIN con_fp USING(table_name) LEFT JOIN idx_fp USING(table_name)
ORDER BY w.table_name
"""

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output-path",default="runtime/data_cloud/schema_parity_latest.json")
    a=ap.parse_args()
    dsn=os.environ.get("EMPIREDB_DSN")
    if not dsn: raise RuntimeError("EMPIREDB_DSN is required")
    names=sorted(SOURCE)
    out=[]
    with psycopg.connect(dsn,connect_timeout=5,application_name="empire-schema-parity") as c:
        c.execute("SET TRANSACTION READ ONLY")
        rows=c.execute(SQL,(names,)).fetchall()
    got={r[0]:list(r[1:]) for r in rows}
    for name in names:
        expected=SOURCE[name]
        actual=got.get(name)
        fields=["rls_enabled","rls_forced","column_count","columns_md5","constraint_count","constraints_md5","index_count","indexes_md5"]
        diffs=[fields[i] for i,(x,y) in enumerate(zip(expected,actual or [])) if x!=y]
        if actual is None: diffs=["missing_table"]
        out.append({"table":name,"match":not diffs,"differences":diffs,"source":expected,"target":actual})
    report={"schema_version":"empire.schema-parity.v1","tables_compared":len(names),"tables_matching":sum(x["match"] for x in out),
            "tables_different":sum(not x["match"] for x in out),"all_equal":all(x["match"] for x in out),"read_only":True,"tables":out}
    p=Path(a.output_path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:report[k] for k in ("tables_compared","tables_matching","tables_different","all_equal","read_only")},sort_keys=True))
    for x in out:
        if not x["match"]: print(json.dumps({"table":x["table"],"differences":x["differences"]},sort_keys=True))
if __name__=="__main__": main()
