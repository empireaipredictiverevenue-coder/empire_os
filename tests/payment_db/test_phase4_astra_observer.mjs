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
const dir=await mkdtemp(join(tmpdir(),'empire-phase4-astra-'));
const pg=new EmbeddedPostgres({
  databaseDir:join(dir,'db'),user:'postgres',
  password:randomBytes(24).toString('hex'),port:55449,persistent:true,
  createPostgresUser:false,onLog:()=>{},onError:()=>{},
});
let admin; let passed=0;
async function test(name,fn){await fn();passed++;console.log('PASS '+name);}
async function asRole(role,sql,params=[]){
  const c=pg.getPgClient(); await c.connect();
  try{await c.query('set role '+role);return await c.query(sql,params);}
  finally{await c.end();}
}

try{
  await pg.initialise(); await pg.start();
  admin=pg.getPgClient(); await admin.connect();
  await admin.query(`
    create role anon;
    create role authenticated;
    create role service_role bypassrls;
    create table business_entities(id uuid primary key);
    create table prospects(id uuid primary key);
    create table buyers(id uuid primary key);
  `);

  await admin.query(await readFile(
    join(root,'migrations/002_commercial_control_plane.sql'),'utf8'));
  await admin.query(
    'grant select,insert,update,delete,truncate on commercial_events to service_role'
  );

  for(const file of [
    '20260917150504_bsc_usdt_payment_verification.sql',
    '20260917170234_govern_bsc_payment_requests.sql',
    '20260917174000_bsc_usdt_smart_contract_escrow.sql',
    '20260918123504_phase3f_outcome_feedback.sql',
    '20260918124631_phase3f_runtime_identities.sql',
    '20260918133000_phase4_astra_observer.sql',
  ]){
    await admin.query(await readFile(
      join(root,'supabase/migrations',file),'utf8'));
  }

  await test('Astra observer identity is restricted and passwordless',async()=>{
    const rows=(await admin.query(`
      select rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,
             rolcreaterole,rolreplication,rolbypassrls,rolconnlimit,rolpassword
      from pg_authid
      where rolname in ('empire_astra_observer','empire_astra_observer_login')
      order by rolname
    `)).rows;
    assert.equal(rows.length,2);

    const group=rows.find(r=>r.rolname==='empire_astra_observer');
    const login=rows.find(r=>r.rolname==='empire_astra_observer_login');
    assert.equal(group.rolcanlogin,false);
    assert.equal(login.rolcanlogin,true);
    for(const r of rows){
      assert.equal(r.rolinherit,false); assert.equal(r.rolsuper,false);
      assert.equal(r.rolcreatedb,false); assert.equal(r.rolcreaterole,false);
      assert.equal(r.rolreplication,false); assert.equal(r.rolbypassrls,false);
    }
    assert.equal(login.rolconnlimit,5);
    assert.equal(login.rolpassword,null);

    const membership=(await admin.query(`
      select granted_role.rolname granted
      from pg_auth_members m
      join pg_roles member_role on member_role.oid=m.member
      join pg_roles granted_role on granted_role.oid=m.roleid
      where member_role.rolname='empire_astra_observer_login'
    `)).rows.map(r=>r.granted);
    assert.deepEqual(membership,['empire_astra_observer']);
  });

  await test('Astra observer can execute only the feedback projection',async()=>{
    const feedback=(await asRole(
      'empire_astra_observer',
      'select public.get_commercial_outcome_feedback($1) result',
      [100],
    )).rows[0].result;
    assert.deepEqual(feedback,[]);

    await assert.rejects(
      asRole(
        'empire_astra_observer',
        `select public.record_commercial_outcome(
          $1,'confirmed','won',4.0,'test','ref','{}',$2,'astra'
        )`,
        ['00000000-0000-0000-0000-000000000001','phase4:blocked'],
      ),
      /permission denied for function record_commercial_outcome/
    );

    await assert.rejects(
      asRole(
        'empire_astra_observer',
        'select public.recognize_bsc_revenue($1,$2)',
        ['00000000-0000-0000-0000-000000000001','astra'],
      ),
      /permission denied for function recognize_bsc_revenue/
    );
  });

  await test('Astra observer has no direct commercial table writes',async()=>{
    await assert.rejects(
      asRole(
        'empire_astra_observer',
        `insert into commercial_events(
          event_type,channel,actor,payload,idempotency_key
        ) values('astra_test','astra','astra','{}','phase4:direct-write')`
      ),
      /permission denied for table commercial_events/
    );
  });

  await test('Astra login carries defensive timeout settings',async()=>{
    const row=(await admin.query(`
      select rolconfig from pg_roles
      where rolname='empire_astra_observer_login'
    `)).rows[0];
    assert.ok(row.rolconfig.includes('statement_timeout=15s'));
    assert.ok(row.rolconfig.includes(
      'idle_in_transaction_session_timeout=30s'));
  });

  console.log(
    passed+' Phase 4 Astra observer tests passed; no production database contacted.'
  );
} finally {
  if(admin) await admin.end();
  await pg.stop();
}
