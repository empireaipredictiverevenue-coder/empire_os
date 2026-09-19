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
const dir=await mkdtemp(join(tmpdir(),'empire-lead-intel-'));
const pg=new EmbeddedPostgres({
  databaseDir:join(dir,'db'),
  user:'postgres',
  password:randomBytes(24).toString('hex'),
  port:55461,
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

async function asRole(role,sql,params=[]){
  const client=pg.getPgClient();
  await client.connect();
  try{
    await client.query('set role '+role);
    return await client.query(sql,params);
  } finally {
    await client.end();
  }
}

try{
  await pg.initialise();
  await pg.start();
  admin=pg.getPgClient();
  await admin.connect();

  await admin.query(`
    create role anon;
    create role authenticated;
    create role service_role bypassrls;

    create table prospects(id uuid primary key);
    create table prospect_entity_links(id uuid primary key);
    create table business_entities(id uuid primary key);
    create table prospect_qualifications(id uuid primary key);
    create table prospect_acquisitions(id uuid primary key);
    create table intelligence_facts(id uuid primary key);
    create table intelligence_signals(id uuid primary key);
    create table intelligence_scores(id uuid primary key);
    create table intelligence_contact_points(id uuid primary key);
    create table intelligence_employment(id uuid primary key);
    create table commercial_events(id uuid primary key);

    alter table prospects enable row level security;
    alter table prospect_entity_links enable row level security;
    alter table business_entities enable row level security;
    alter table prospect_qualifications enable row level security;
    alter table prospect_acquisitions enable row level security;
    alter table intelligence_facts enable row level security;
    alter table intelligence_signals enable row level security;
    alter table intelligence_scores enable row level security;
    alter table intelligence_contact_points enable row level security;
    alter table intelligence_employment enable row level security;

    insert into prospects values(
      '00000000-0000-0000-0000-000000000001'
    );
    insert into intelligence_signals values(
      '00000000-0000-0000-0000-000000000002'
    );
  `);

  const migration=await readFile(
    join(
      root,
      'supabase/migrations/' +
      '20260919101500_phase3f_lead_intelligence_reader.sql'
    ),
    'utf8',
  );
  await admin.query(migration);

  await test('roles restricted and passwordless',async()=>{
    const rows=(await admin.query(`
      select rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,
             rolcreaterole,rolreplication,rolbypassrls,
             rolconnlimit,rolpassword
      from pg_authid
      where rolname in (
        'empire_lead_intelligence_reader',
        'empire_lead_intelligence_reader_login'
      )
      order by rolname
    `)).rows;

    assert.equal(rows.length,2);
    const role=rows.find(
      r=>r.rolname==='empire_lead_intelligence_reader'
    );
    const login=rows.find(
      r=>r.rolname==='empire_lead_intelligence_reader_login'
    );

    assert.equal(role.rolcanlogin,false);
    assert.equal(login.rolcanlogin,true);
    for(const row of rows){
      assert.equal(row.rolinherit,false);
      assert.equal(row.rolsuper,false);
      assert.equal(row.rolcreatedb,false);
      assert.equal(row.rolcreaterole,false);
      assert.equal(row.rolreplication,false);
      assert.equal(row.rolbypassrls,false);
    }
    assert.equal(login.rolconnlimit,5);
    assert.equal(login.rolpassword,null);
  });

  await test('login has exactly one capability membership',async()=>{
    const memberships=(await admin.query(`
      select granted.rolname
      from pg_auth_members m
      join pg_roles member on member.oid=m.member
      join pg_roles granted on granted.oid=m.roleid
      where member.rolname='empire_lead_intelligence_reader_login'
      order by granted.rolname
    `)).rows.map(row=>row.rolname);

    assert.deepEqual(
      memberships,
      ['empire_lead_intelligence_reader'],
    );
  });

  await test('reader can select canonical RLS tables',async()=>{
    const prospects=await asRole(
      'empire_lead_intelligence_reader',
      'select id from prospects',
    );
    assert.equal(prospects.rowCount,1);

    const signals=await asRole(
      'empire_lead_intelligence_reader',
      'select id from intelligence_signals',
    );
    assert.equal(signals.rowCount,1);

    const acquisitions=await asRole(
      'empire_lead_intelligence_reader',
      'select id from prospect_acquisitions',
    );
    assert.equal(acquisitions.rowCount,0);
  });

  await test('reader cannot write canonical tables',async()=>{
    await assert.rejects(
      asRole(
        'empire_lead_intelligence_reader',
        "insert into prospects values(" +
        "'00000000-0000-0000-0000-000000000003')",
      ),
      /permission denied/,
    );
    await assert.rejects(
      asRole(
        'empire_lead_intelligence_reader',
        'delete from intelligence_signals',
      ),
      /permission denied/,
    );
  });

  await test('reader cannot access unrelated commercial tables',async()=>{
    await assert.rejects(
      asRole(
        'empire_lead_intelligence_reader',
        'select * from commercial_events',
      ),
      /permission denied/,
    );
  });

  await test('NOINHERIT login must explicitly SET ROLE',async()=>{
    await assert.rejects(
      asRole(
        'empire_lead_intelligence_reader_login',
        'select * from prospects',
      ),
      /permission denied/,
    );
  });

  await test('login carries defensive timeouts',async()=>{
    const row=(await admin.query(`
      select rolconfig
      from pg_roles
      where rolname='empire_lead_intelligence_reader_login'
    `)).rows[0];

    assert.ok(row.rolconfig.includes('statement_timeout=15s'));
    assert.ok(
      row.rolconfig.includes(
        'idle_in_transaction_session_timeout=30s'
      )
    );
  });

  console.log(
    passed +
    ' Lead Intelligence reader tests passed; ' +
    'no production database contacted.'
  );
} finally {
  if(admin) await admin.end();
  await pg.stop();
}
