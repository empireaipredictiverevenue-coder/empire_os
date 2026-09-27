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
const dir=await mkdtemp(join(tmpdir(),'empire-phase4-astra-evidence-'));
const pg=new EmbeddedPostgres({
  databaseDir:join(dir,'db'),user:'postgres',
  password:randomBytes(24).toString('hex'),port:55450,persistent:true,
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
    create role empire_outcome_recorder;
    create role empire_revenue_recognizer;
    create role empire_outcome_reader;
    create role empire_astra_observer nologin noinherit;
    create table prospects(id uuid primary key);
    create table prospect_qualifications(
      id uuid primary key, prospect_id uuid not null, score numeric not null,
      tier text not null, status text not null, scoring_version text not null,
      evidence_confidence numeric, scored_at timestamptz not null
    );
    create table prospect_entity_links(
      prospect_id uuid not null, active boolean not null default true
    );
    create table fulfilment_orders(
      prospect_id uuid not null, state text not null
    );
    create table buyers(
      is_active boolean, status text, commercial_activation_state text,
      daily_cap integer, calls_today integer
    );
    create table outbound_replies(classification text);
    create table gtm_jobs(status text, created_by text);
    create table buyer_candidate_reviews(status text, evidence jsonb);
  `);

  await admin.query(await readFile(
    join(root,'supabase/migrations',
      '20260919164500_phase4_astra_operational_evidence.sql'),'utf8'));
  await admin.query(await readFile(
    join(root,'supabase/migrations',
      '20260919224500_phase4_astra_filter_diagnostic_failures.sql'),'utf8'));
  await admin.query(await readFile(
    join(root,'supabase/migrations',
      '20260919225000_phase4_astra_outreach_ready_candidates.sql'),'utf8'));

  await test('observer can execute operational evidence only',async()=>{
    const result=(await asRole(
      'empire_astra_observer',
      'select public.get_astra_operational_evidence() result'
    )).rows[0].result;
    assert.equal(result.replies_waiting,0);
    assert.equal(result.failed_jobs,0);
    assert.equal(result.diagnostic_failed_jobs,0);
    assert.equal(result.owned_inventory_count,0);
    assert.equal(result.qualified_unallocated_count,0);
    assert.equal(result.active_buyer_capacity,0);
    assert.equal(result.buyer_candidates_due,0);
    assert.equal(result.buyer_reviews_pending_total,0);
    assert.ok(result.observed_at);
  });

  await test('public and commercial writer roles cannot execute RPC',async()=>{
    for(const role of [
      'anon','authenticated','empire_outcome_recorder',
      'empire_revenue_recognizer','empire_outcome_reader',
    ]){
      await assert.rejects(
        asRole(role,'select public.get_astra_operational_evidence()'),
        /permission denied for function get_astra_operational_evidence/
      );
    }
  });

  await test('observer has no direct operational table reads',async()=>{
    for(const table of [
      'prospect_qualifications','prospect_entity_links','fulfilment_orders',
      'buyers','outbound_replies','gtm_jobs','buyer_candidate_reviews',
    ]){
      await assert.rejects(
        asRole('empire_astra_observer',`select * from public.${table}`),
        /permission denied for table/
      );
    }
  });

  await test('operational evidence reflects only observed rows',async()=>{
    await admin.query(`
      insert into outbound_replies(classification)
      values ('unclassified'),('classified');
      insert into gtm_jobs(status,created_by) values
        ('failed','runtime_worker'),
        ('failed','manual_production_smoke'),
        ('done','runtime_worker');
      insert into buyer_candidate_reviews(status,evidence)
      values
        ('pending','{"outreach_ready":true}'::jsonb),
        ('pending','{"outreach_ready":false}'::jsonb),
        ('approved','{"outreach_ready":true}'::jsonb);
      insert into buyers(
        is_active,status,commercial_activation_state,daily_cap,calls_today
      ) values
        (true,'active','activated',10,3),
        (true,'active','pending',100,0);
    `);
    const result=(await asRole(
      'empire_astra_observer',
      'select public.get_astra_operational_evidence() result'
    )).rows[0].result;
    assert.equal(result.replies_waiting,1);
    assert.equal(result.failed_jobs,1);
    assert.equal(result.diagnostic_failed_jobs,1);
    assert.equal(result.buyer_candidates_due,1);
    assert.equal(result.buyer_reviews_pending_total,2);
    assert.equal(result.active_buyer_capacity,7);
  });

  console.log(
    passed+' Phase 4 Astra operational-evidence tests passed; '+
    'no production database contacted.'
  );
} finally {
  if(admin) await admin.end();
  await pg.stop();
}
