import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {randomBytes} from 'node:crypto';

const deps=process.env.EMPIRE_PG_TEST_DEPS;
if(!deps) throw new Error('Set EMPIRE_PG_TEST_DEPS');
const {default:EmbeddedPostgres}=await import(pathToFileURL(
  join(deps,'node_modules/embedded-postgres/dist/index.js')));
const root=resolve(fileURLToPath(new URL('../..',import.meta.url)));
const dir=await mkdtemp(join(tmpdir(),'empire-search-intel-'));
const pg=new EmbeddedPostgres({
  databaseDir:join(dir,'db'),
  user:'postgres',
  password:randomBytes(24).toString('hex'),
  port:55451,
  persistent:true,
  createPostgresUser:false,
  onLog:()=>{},
  onError:()=>{},
});
let admin;

try {
  await pg.initialise();
  await pg.start();
  admin=pg.getPgClient();
  await admin.connect();
  await admin.query('create role anon; create role authenticated; create role service_role bypassrls;');
  await admin.query(`
    create table unrelated_public_table(id integer primary key);
    grant select on unrelated_public_table to anon, authenticated;
    create table prospects(id uuid primary key);
    create table gtm_opportunities(id uuid primary key);
    create table fulfilment_orders(id uuid primary key);
    create table commercial_events(id uuid primary key);
  `);
  const sql=await readFile(
    join(root,'supabase/migrations/20260918134000_search_intelligence_foundation.sql'),
    'utf8'
  );
  await admin.query(sql);

  const expected=[
    'seo_sites','seo_pages','seo_queries','seo_opportunities',
    'seo_content_scores','seo_indexation','seo_search_console',
    'seo_revenue_attribution','seo_alerts','seo_refresh_queue'
  ];
  const rows=(await admin.query(
    `select tablename from pg_tables
     where schemaname='public' and tablename=any($1::text[])
     order by tablename`,
    [expected]
  )).rows.map(r=>r.tablename);
  assert.deepEqual(rows,[...expected].sort());

  const privileges=(await admin.query(`
    select
      has_table_privilege('anon','public.seo_pages','SELECT') anon_select,
      has_table_privilege('authenticated','public.seo_pages','SELECT') auth_select,
      has_table_privilege('service_role','public.seo_pages','SELECT') service_select,
      has_table_privilege('service_role','public.seo_pages','INSERT') service_insert,
      has_table_privilege('anon','public.unrelated_public_table','SELECT') unrelated_anon_select,
      has_table_privilege('authenticated','public.unrelated_public_table','SELECT') unrelated_auth_select
  `)).rows[0];
  assert.equal(privileges.anon_select,false);
  assert.equal(privileges.auth_select,false);
  assert.equal(privileges.service_select,true);
  assert.equal(privileges.service_insert,true);
  assert.equal(privileges.unrelated_anon_select,true);
  assert.equal(privileges.unrelated_auth_select,true);

  const historyPrivileges=(await admin.query(`
    select
      has_table_privilege('service_role','public.seo_revenue_attribution','SELECT') revenue_select,
      has_table_privilege('service_role','public.seo_revenue_attribution','INSERT') revenue_insert,
      has_table_privilege('service_role','public.seo_revenue_attribution','UPDATE') revenue_update,
      has_table_privilege('service_role','public.seo_revenue_attribution','DELETE') revenue_delete
  `)).rows[0];
  assert.equal(historyPrivileges.revenue_select,true);
  assert.equal(historyPrivileges.revenue_insert,true);
  assert.equal(historyPrivileges.revenue_update,false);
  assert.equal(historyPrivileges.revenue_delete,false);

  const idTypes=(await admin.query(`
    select column_name,data_type
    from information_schema.columns
    where table_schema='public'
      and table_name='seo_revenue_attribution'
      and column_name in (
        'prospect_id','opportunity_id','fulfilment_order_id','commercial_event_id'
      )
    order by column_name
  `)).rows;
  assert.equal(idTypes.length,4);
  assert.ok(idTypes.every(r=>r.data_type==='uuid'));

  await assert.rejects(
    admin.query(`
      insert into seo_pages(site_id,url,index_state)
      values(gen_random_uuid(),'https://example.com','FAKE_STATE')
    `),
    /violates foreign key constraint|violates check constraint/
  );

  console.log('3 Search Intelligence migration checks passed; no production database contacted.');
} finally {
  if(admin) await admin.end();
  await pg.stop();
}
