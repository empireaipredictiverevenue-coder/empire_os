// Isolated PostgreSQL tests for governed fulfilment-order commercial terms.
import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {randomBytes, randomUUID} from 'node:crypto';
const deps=process.env.EMPIRE_PG_TEST_DEPS; if(!deps) throw new Error('Set EMPIRE_PG_TEST_DEPS');
const {default:EmbeddedPostgres}=await import(pathToFileURL(join(deps,'node_modules/embedded-postgres/dist/index.js')));
const root=resolve(fileURLToPath(new URL('../..',import.meta.url)));
const dir=await mkdtemp(join(tmpdir(),'empire-commercial-terms-'));
const pg=new EmbeddedPostgres({databaseDir:join(dir,'db'),user:'postgres',password:randomBytes(24).toString('hex'),port:55447,persistent:true,createPostgresUser:false,onLog:()=>{},onError:()=>{}});
let admin; const clients=[]; let passed=0;
async function client(){const c=pg.getPgClient();await c.connect();clients.push(c);return c;}
async function asRole(role,sql,args=[]){const c=await client();try{await c.query('begin');await c.query('set local role '+role);const r=await c.query(sql,args);await c.query('commit');return r;}finally{await c.end();clients.splice(clients.indexOf(c),1);}}
async function test(name,fn){await fn();passed++;console.log('PASS '+name);}
try{await pg.initialise();await pg.start();admin=await client();
await admin.query(`create role anon; create role authenticated; create role service_role bypassrls;
create table prospects(id uuid primary key); create table buyers(id uuid primary key);
create table fulfilment_orders(id uuid primary key,prospect_id uuid references prospects(id),buyer_id uuid references buyers(id),
 state text not null,price_cents bigint not null default 0,acquisition_cost_cents bigint not null default 0,
 fulfilment_cost_cents bigint not null default 0,expected_margin_cents bigint not null default 0,
 commercial_payload jsonb not null default '{}'::jsonb,updated_at timestamptz not null default now());
grant all on fulfilment_orders to anon,authenticated,service_role;
create or replace function public.test_allocate_order(p_id uuid,p_prospect uuid,p_buyer uuid) returns void language sql security definer set search_path='' as $$ insert into public.fulfilment_orders(id,prospect_id,buyer_id,state) values(p_id,p_prospect,p_buyer,'matched') $$;
grant execute on function public.test_allocate_order(uuid,uuid,uuid) to service_role;`);
const sql=await readFile(join(root,'supabase/migrations/20260917211500_governed_commercial_terms.sql'),'utf8');
await admin.query(sql);
const prospect=randomUUID(),buyer=randomUUID(),order=randomUUID();
await admin.query('insert into prospects(id) values($1)',[prospect]);
await admin.query('insert into buyers(id) values($1)',[buyer]);
await admin.query(`insert into fulfilment_orders(id,prospect_id,buyer_id,state) values($1,$2,$3,'matched')`,[order,prospect,buyer]);
const terms={currency:'USD',settlement_asset:'USDT',settlement_chain:'BSC',description:'Managed revenue service'};
let reviewId;

await test('service proposes profitable canonical terms but cannot edit order',async()=>{
  const r=(await asRole('service_role',`select public.propose_commercial_terms($1,250000,10000,40000,$2,'terms:test:001','planner') result`,[order,terms])).rows[0].result;
  reviewId=r.review_id; assert.equal(r.decision,'proposed'); assert.equal(r.expected_margin_cents,200000); assert.equal(r.actual_revenue,false);
  await assert.rejects(asRole('service_role',`update fulfilment_orders set price_cents=1 where id=$1`,[order]),/permission denied/);
  await assert.rejects(asRole('service_role',`select public.decide_commercial_terms($1,'approved','service','x')`,[reviewId]),/permission denied/);
});


await test('direct write revocation preserves security-definer allocation RPC path',async()=>{
  const order2=randomUUID();
  await asRole('service_role','select public.test_allocate_order($1,$2,$3)',[order2,prospect,buyer]);
  const row=(await admin.query('select state from fulfilment_orders where id=$1',[order2])).rows[0];
  assert.equal(row.state,'matched');
});

await test('commercial approver login is unprivileged and single-purpose',async()=>{
  const r=(await admin.query(`select r.rolcanlogin,r.rolsuper,r.rolcreaterole,r.rolcreatedb,r.rolreplication,r.rolbypassrls,a.rolpassword is null as passwordless from pg_roles r join pg_authid a on a.oid=r.oid where r.rolname='empire_commercial_approver_login'`)).rows[0];
  assert.equal(r.rolcanlogin,true); assert.equal(r.rolsuper,false); assert.equal(r.rolcreaterole,false); assert.equal(r.rolcreatedb,false); assert.equal(r.rolreplication,false); assert.equal(r.rolbypassrls,false); assert.equal(r.passwordless,true);
  const memberships=(await admin.query(`select r.rolname from pg_auth_members m join pg_roles r on r.oid=m.roleid join pg_roles u on u.oid=m.member where u.rolname='empire_commercial_approver_login' order by r.rolname`)).rows.map(x=>x.rolname);
  assert.deepEqual(memberships,['empire_commercial_approver']);
});

await test('proposal rejects loss-making or non-canonical settlement terms',async()=>{
  await assert.rejects(asRole('service_role',`select public.propose_commercial_terms($1,50000,30000,30000,$2,'terms:test:002','planner')`,[order,terms]),/positive expected margin/);
  const bad={currency:'USD',settlement_asset:'USDC',settlement_chain:'SOL',description:'bad rail'};
  await assert.rejects(asRole('service_role',`select public.propose_commercial_terms($1,250000,10000,40000,$2,'terms:test:003','planner')`,[order,bad]),/USDT\/BSC/);
});
await test('human approver owns terms approval and order becomes offered',async()=>{
  const r=(await asRole('empire_commercial_approver',`select public.decide_commercial_terms($1,'approved','phil','reviewed') result`,[reviewId])).rows[0].result;
  assert.equal(r.decision,'approved'); assert.equal(r.actual_revenue,false);
  const o=(await admin.query('select state,price_cents,expected_margin_cents,commercial_payload from fulfilment_orders where id=$1',[order])).rows[0];
  assert.equal(o.state,'offered'); assert.equal(Number(o.price_cents),250000); assert.equal(Number(o.expected_margin_cents),200000);
  assert.match(o.commercial_payload.commercial_terms_sha256,/^[0-9a-f]{64}$/);
});

await test('acceptance is separate and requires post-approval buyer evidence',async()=>{
  await assert.rejects(asRole('service_role',`select public.record_commercial_acceptance($1,'outbound_reply','reply-1',now(),'service')`,[reviewId]),/permission denied/);
  const before=new Date(Date.now()-3600_000).toISOString();
  await assert.rejects(asRole('empire_commercial_approver',`select public.record_commercial_acceptance($1,'outbound_reply','reply-1',$2,'phil')`,[reviewId,before]),/predate approved terms/);
  const r=(await asRole('empire_commercial_approver',`select public.record_commercial_acceptance($1,'outbound_reply','reply-1',clock_timestamp(),'phil') result`,[reviewId])).rows[0].result;
  assert.equal(r.decision,'accepted'); assert.equal(r.state,'accepted'); assert.equal(r.actual_revenue,false);
  const o=(await admin.query('select state,commercial_payload from fulfilment_orders where id=$1',[order])).rows[0];
  assert.equal(o.state,'accepted'); assert.equal(o.commercial_payload.buyer_acceptance_reference,'reply-1');
});

await test('commercial terms event ledger is append-only and tables deny direct writes',async()=>{
  const eid=(await admin.query('select id from commercial_terms_events limit 1')).rows[0].id;
  await assert.rejects(admin.query(`update commercial_terms_events set actor='x' where id=$1`,[eid]),/append-only/);
  await assert.rejects(asRole('empire_commercial_approver',`update commercial_terms_reviews set status='rejected' where id=$1`,[reviewId]),/permission denied/);
});
await test('review RPC is read-only',async()=>{
  const r=(await asRole('empire_commercial_approver','select public.get_commercial_terms_review($1) result',[reviewId])).rows[0].result;
  assert.equal(r.status,'approved'); assert.equal(r.price_cents,250000); assert.equal(r.actual_revenue,false);
});

console.log(`${passed} governed commercial-terms tests passed; no production database contacted.`);
}finally{await Promise.allSettled(clients.map(c=>c.end()));if(admin){await admin.end().catch(()=>{});}await pg.stop();}
