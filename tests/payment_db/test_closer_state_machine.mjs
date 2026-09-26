// Isolated PostgreSQL test for Supabase-backed closer state machine.
import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {randomBytes, randomUUID} from 'node:crypto';
const deps=process.env.EMPIRE_PG_TEST_DEPS;if(!deps) throw new Error('Set EMPIRE_PG_TEST_DEPS');
const {default:EmbeddedPostgres}=await import(pathToFileURL(join(deps,'node_modules/embedded-postgres/dist/index.js')));
const root=resolve(fileURLToPath(new URL('../..',import.meta.url)));const dir=await mkdtemp(join(tmpdir(),'empire-closer-'));
const pg=new EmbeddedPostgres({databaseDir:join(dir,'db'),user:'postgres',password:randomBytes(24).toString('hex'),port:55445,persistent:true,createPostgresUser:false,onLog:()=>{},onError:()=>{}});
let admin;const clients=[];let passed=0;async function client(){const c=pg.getPgClient();await c.connect();clients.push(c);return c;}
async function asRole(role,sql,args=[]){const c=await client();try{await c.query('begin');await c.query('set local role '+role);const r=await c.query(sql,args);await c.query('commit');return r;}finally{await c.end();clients.splice(clients.indexOf(c),1);}}
async function test(name,fn){await fn();passed++;console.log('PASS '+name);}
try{await pg.initialise();await pg.start();admin=await client();
await admin.query(`create role anon;create role authenticated;create role service_role bypassrls;
create table prospects(id uuid primary key);create table business_entities(id uuid primary key);create table buyers(id uuid primary key);create table gtm_opportunities(id uuid primary key);
create table fulfilment_orders(id uuid primary key,entity_id uuid references business_entities(id),buyer_id uuid references buyers(id),state text,price_cents bigint,commercial_payload jsonb not null default '{}');`);
await admin.query(await readFile(join(root,'supabase/migrations/20260917190000_governed_outbound_reply_capture.sql'),'utf8'));
await admin.query(await readFile(join(root,'supabase/migrations/20260917193000_supabase_closer_state_machine.sql'),'utf8'));
const entity=randomUUID(),order=randomUUID(),intent=randomUUID(),reply=randomUUID();
await admin.query('insert into business_entities(id) values($1)',[entity]);
await admin.query(`insert into outbound_intents(id,entity_id,channel,recipient,normalized_recipient,body_text,status,idempotency_key,proposed_by,expires_at)
values($1,$2,'email','buyer@example.com','buyer@example.com','Body','replied','closer-intent-1','planner',now()+interval '1 day')`,[intent,entity]);
await admin.query(`insert into outbound_replies(id,intent_id,provider_message_id,from_contact,normalized_from_contact,body_text,classification,confidence,received_at,classified_at)
values($1,$2,'reply-closer-1','buyer@example.com','buyer@example.com','Interested','positive',0.95,now(),now())`,[reply,intent]);
let caseId;
await test('service opens case from genuine classified reply',async()=>{const r=(await asRole('service_role','select public.open_closer_case($1) result',[reply])).rows[0].result;caseId=r.case_id;assert.equal(r.state,'engaged');});
await test('service can recommend but cannot advance',async()=>{const r=(await asRole('service_role',`select public.record_closer_recommendation($1,'qualify',0.91,'{"signals":["positive_reply"]}','Thanks — a couple of questions first','closer:v1') result`,[caseId])).rows[0].result;assert.equal(r.decision,'recorded');await assert.rejects(asRole('service_role',`select public.advance_closer_case($1,'qualified','agent',null,'')`,[caseId]),/permission denied/);});
await test('human approver advances to qualified',async()=>{const r=(await asRole('empire_closer_approver',`select public.advance_closer_case($1,'qualified','phil',null,'reviewed') result`,[caseId])).rows[0].result;assert.equal(r.state,'qualified');});
await test('proposal state rejects missing canonical order',async()=>{await assert.rejects(asRole('empire_closer_approver',`select public.advance_closer_case($1,'proposal_ready','phil',null,'')`,[caseId]),/canonical fulfilment order required/);});
await admin.query(`insert into fulfilment_orders(id,entity_id,state,price_cents,commercial_payload) values($1,$2,'offered',250000,'{"commercial_terms_sha256":"${'a'.repeat(64)}"}')`,[order,entity]);
await test('proposal/payment states require canonical priced terms and accepted order',async()=>{
  let r=(await asRole('empire_closer_approver',`select public.advance_closer_case($1,'proposal_ready','phil',$2,'terms checked') result`,[caseId,order])).rows[0].result;assert.equal(r.state,'proposal_ready');
  r=(await asRole('empire_closer_approver',`select public.advance_closer_case($1,'proposal_approved','phil',$2,'approved') result`,[caseId,order])).rows[0].result;assert.equal(r.state,'proposal_approved');
  await assert.rejects(asRole('empire_closer_approver',`select public.advance_closer_case($1,'awaiting_payment','phil',$2,'')`,[caseId,order]),/accepted or invoiced order required/);
  await admin.query("update fulfilment_orders set state='accepted' where id=$1",[order]);
  r=(await asRole('empire_closer_approver',`select public.advance_closer_case($1,'awaiting_payment','phil',$2,'accepted') result`,[caseId,order])).rows[0].result;assert.equal(r.state,'awaiting_payment');
});
await test('closer layer cannot mark won or write tables directly',async()=>{
  await assert.rejects(asRole('empire_closer_approver',`select public.advance_closer_case($1,'won','phil',$2,'paid')`,[caseId,order]),/verified payment\/outcome gate/);
  await assert.rejects(asRole('empire_closer_approver',`update closer_cases set state='won' where id=$1`,[caseId]),/permission denied/);
});
await test('closer event ledger is append-only',async()=>{const id=(await admin.query('select id from closer_events limit 1')).rows[0].id;await assert.rejects(admin.query("update closer_events set actor='x' where id=$1",[id]),/append-only/);});
console.log(`${passed} closer state-machine tests passed; no production database contacted.`);
}finally{await Promise.allSettled(clients.map(c=>c.end()));await pg.stop();}
