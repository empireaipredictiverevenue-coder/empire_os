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
const dir=await mkdtemp(join(tmpdir(),'empire-search-reader-'));
const pg=new EmbeddedPostgres({
  databaseDir:join(dir,'db'),
  user:'postgres',
  password:randomBytes(24).toString('hex'),
  port:55453,
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
  await admin.query(
    'create role anon; create role authenticated; create role service_role bypassrls;'
  );
  await admin.query(`
    create table prospects(id uuid primary key);
    create table gtm_opportunities(id uuid primary key);
    create table fulfilment_orders(id uuid primary key);
    create table commercial_events(id uuid primary key);
    create table unrelated_public_table(id integer primary key);
  `);

  const foundation=await readFile(
    join(root,'supabase/migrations/20260918134000_search_intelligence_foundation.sql'),
    'utf8'
  );
  const reader=await readFile(
    join(root,'supabase/migrations/20260919152313_phase5_search_reader.sql'),
    'utf8'
  );
  await admin.query(foundation);
  await admin.query(reader);

  const roleChecks=(await admin.query(`
    select
      has_table_privilege(
        'empire_search_reader','public.seo_pages','SELECT'
      ) as page_select,
      has_table_privilege(
        'empire_search_reader','public.seo_pages','INSERT'
      ) as page_insert,
      has_table_privilege(
        'empire_search_reader','public.unrelated_public_table','SELECT'
      ) as unrelated_select,
      pg_has_role(
        'empire_search_reader_login','empire_search_reader','MEMBER'
      ) as login_member
  `)).rows[0];
  assert.equal(roleChecks.page_select,true);
  assert.equal(roleChecks.page_insert,false);
  assert.equal(roleChecks.unrelated_select,false);
  assert.equal(roleChecks.login_member,true);

  const tenantA=(await admin.query(`
    insert into public.seo_sites(tenant_key,name,base_url)
    values('tenant-a','A','https://a.example')
    returning id
  `)).rows[0].id;
  const tenantB=(await admin.query(`
    insert into public.seo_sites(tenant_key,name,base_url)
    values('tenant-b','B','https://b.example')
    returning id
  `)).rows[0].id;

  await admin.query(
    `insert into public.seo_pages(site_id,url,index_state)
     values($1,'https://a.example/one','DISCOVERED'),
           ($2,'https://b.example/two','DISCOVERED')`,
    [tenantA,tenantB]
  );

  await admin.query('set role empire_search_reader');
  await admin.query(
    `select set_config('app.tenant_key','tenant-a',false)`
  );

  const sites=(await admin.query(
    'select tenant_key from public.seo_sites order by tenant_key'
  )).rows.map(row=>row.tenant_key);
  assert.deepEqual(sites,['tenant-a']);

  const pages=(await admin.query(
    'select url from public.seo_pages order by url'
  )).rows.map(row=>row.url);
  assert.deepEqual(pages,['https://a.example/one']);

  await assert.rejects(
    admin.query(
      `insert into public.seo_sites(tenant_key,base_url)
       values('tenant-a','https://new.example')`
    ),
    /permission denied|violates row-level security/
  );

  await admin.query('reset role');

  console.log(
    '4 Phase 5 Search reader checks passed; no production database contacted.'
  );
} finally {
  if(admin) await admin.end();
  await pg.stop();
}
