import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {randomBytes} from 'node:crypto';

const deps=process.env.EMPIRE_PG_TEST_DEPS;
if(!deps) throw new Error('Set EMPIRE_PG_TEST_DEPS');

const {default:EmbeddedPostgres}=await import(pathToFileURL(
  join(deps,'node_modules/embedded-postgres/dist/index.js')
));
const root=resolve(fileURLToPath(new URL('../..',import.meta.url)));
const dir=await mkdtemp(join(tmpdir(),'empire-internal-lockdown-'));
const pg=new EmbeddedPostgres({
  databaseDir:join(dir,'db'),
  user:'postgres',
  password:randomBytes(24).toString('hex'),
  port:55463,
  persistent:true,
  createPostgresUser:false,
  onLog:()=>{},
  onError:()=>{},
});

let admin;
let passed=0;

async function test(name,fn){
  await fn();
  passed++;
  console.log('PASS '+name);
}

async function asRole(role,sql){
  const client=pg.getPgClient();
  await client.connect();
  try{
    await client.query('set role '+role);
    return await client.query(sql);
  } finally {
    await client.end();
  }
}

try{
  await pg.initialise();
  await pg.start();
  admin=pg.getPgClient();
  await admin.connect();

  await admin.query([
    'create role anon;',
    'create role authenticated;',
    'create role service_role bypassrls;',
    'create table b2b_leads(id uuid primary key, company_name text);',
    'create table empire_revenue_ledger(id uuid primary key, amount numeric);',
    'create table crypto_payment_requests(id uuid primary key, customer_email text);',
    'grant all privileges on table b2b_leads to anon,authenticated,service_role;',
    'grant all privileges on table empire_revenue_ledger to anon,authenticated,service_role;',
    'grant all privileges on table crypto_payment_requests to anon,authenticated,service_role;',
    "insert into b2b_leads values('00000000-0000-0000-0000-000000000001','Acme');",
    "insert into empire_revenue_ledger values('00000000-0000-0000-0000-000000000002',42);",
    "insert into crypto_payment_requests values('00000000-0000-0000-0000-000000000003','buyer@example.com');",
  ].join('\n'));

  const migration=await readFile(
    join(root,'supabase/migrations/20260919124500_lock_internal_legacy_surfaces.sql'),
    'utf8',
  );
  await admin.query(migration);

  await test('RLS enabled on all locked tables',async()=>{
    const rows=(await admin.query(
      "select relname,relrowsecurity from pg_class where relname in ('b2b_leads','empire_revenue_ledger','crypto_payment_requests') order by relname"
    )).rows;
    assert.equal(rows.length,3);
    for(const row of rows){
      assert.equal(row.relrowsecurity,true);
    }
  });

  await test('anon cannot read or write',async()=>{
    for(const table of [
      'b2b_leads',
      'empire_revenue_ledger',
      'crypto_payment_requests',
    ]){
      await assert.rejects(
        asRole('anon','select * from '+table),
        /permission denied/,
      );
      await assert.rejects(
        asRole('anon','delete from '+table),
        /permission denied/,
      );
    }
  });

  await test('authenticated cannot read or write',async()=>{
    for(const table of [
      'b2b_leads',
      'empire_revenue_ledger',
      'crypto_payment_requests',
    ]){
      await assert.rejects(
        asRole('authenticated','select * from '+table),
        /permission denied/,
      );
      await assert.rejects(
        asRole('authenticated','update '+table+' set id=id'),
        /permission denied/,
      );
    }
  });

  await test('service_role retains internal access',async()=>{
    for(const table of [
      'b2b_leads',
      'empire_revenue_ledger',
      'crypto_payment_requests',
    ]){
      const rows=await asRole(
        'service_role',
        'select count(*)::int as n from '+table,
      );
      assert.equal(rows.rows[0].n,1);
    }
  });

  await test('existing rows are preserved',async()=>{
    const counts=(await admin.query([
      "select count(*)::int as n from b2b_leads",
      "union all select count(*)::int from empire_revenue_ledger",
      "union all select count(*)::int from crypto_payment_requests",
    ].join(' '))).rows.map(r=>r.n);
    assert.deepEqual(counts,[1,1,1]);
  });

  await test('client grants are fully revoked',async()=>{
    for(const role of ['anon','authenticated']){
      for(const table of [
        'b2b_leads',
        'empire_revenue_ledger',
        'crypto_payment_requests',
      ]){
        const row=(await admin.query(
          "select has_table_privilege($1,$2,'SELECT') as s, has_table_privilege($1,$2,'INSERT') as i, has_table_privilege($1,$2,'UPDATE') as u, has_table_privilege($1,$2,'DELETE') as d",
          [role,table],
        )).rows[0];
        assert.deepEqual(row,{s:false,i:false,u:false,d:false});
      }
    }
  });

  console.log(
    passed +
    ' internal surface lockdown DB tests passed; ' +
    'no production database contacted.'
  );
} finally {
  if(admin) await admin.end();
  await pg.stop();
}
