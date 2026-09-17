// Isolated PostgreSQL test for Phase 3E governed outbound/reply capture.
import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {randomBytes, randomUUID} from 'node:crypto';
const deps=process.env.EMPIRE_PG_TEST_DEPS; if(!deps) throw new Error('Set EMPIRE_PG_TEST_DEPS');
const {default:EmbeddedPostgres}=await import(pathToFileURL(join(deps,'node_modules/embedded-postgres/dist/index.js')));
const root=resolve(fileURLToPath(new URL('../..',import.meta.url)));
const dir=await mkdtemp(join(tmpdir(),'empire-outbound-'));
const pg=new EmbeddedPostgres({databaseDir:join(dir,'db'),user:'postgres',password:randomBytes(24).toString('hex'),port:55444,persistent:true,createPostgresUser:false,onLog:()=>{},onError:()=>{}});
let admin; const clients=[]; let passed=0;
async function client(){const c=pg.getPgClient();await c.connect();clients.push(c);return c;}
async function asRole(role,sql,args=[]){const c=await client();try{await c.query('begin');await c.query('set local role '+role);const r=await c.query(sql,args);await c.query('commit');return r;}finally{await c.end();clients.splice(clients.indexOf(c),1);}}
async function test(name,fn){await fn();passed++;console.log('PASS '+name);}
try{await pg.initialise();await pg.start();admin=await client();
await admin.query(`create role anon; create role authenticated; create role service_role bypassrls;
create table prospects(id uuid primary key); create table business_entities(id uuid primary key);
create table buyers(id uuid primary key); create table gtm_opportunities(id uuid primary key);`);
const sql=await readFile(join(root,'supabase/migrations/20260917190000_governed_outbound_reply_capture.sql'),'utf8'); await admin.query(sql);
const cancelSql=await readFile(join(root,'supabase/migrations/20260917230500_governed_outbound_cancel.sql'),'utf8'); await admin.query(cancelSql);
const entity=randomUUID(); await admin.query('insert into business_entities(id) values($1)',[entity]);
const expires=new Date(Date.now()+3600_000).toISOString(); let intentId,replyId;
await test('service role proposes but cannot approve or send',async()=>{
  const r=(await asRole('service_role',`select public.propose_outbound_intent($1,null,null,null,'email','buyer@example.com','Hello','Body',null,'white_label','idem-0001','planner',$2,'{}') result`,[entity,expires])).rows[0].result;
  intentId=r.intent_id; assert.equal(r.status,'pending_approval');
  await assert.rejects(asRole('service_role','select public.approve_outbound_intent($1,$2,$3)',[intentId,'human','ok']),/permission denied/);
  await assert.rejects(asRole('service_role','select public.claim_outbound_send($1,$2)',[intentId,'sender']),/permission denied/);
});
await test('human approver can cancel a pending proposal but service role cannot',async()=>{
  const r=(await asRole('service_role',`select public.propose_outbound_intent($1,null,null,null,'email','replace@example.com','Old','Old body',null,'white_label','idem-cancel-1','planner',$2,'{}') result`,[entity,expires])).rows[0].result;
  await assert.rejects(asRole('service_role','select public.cancel_outbound_intent($1,$2,$3)',[r.intent_id,'service','replace']),/permission denied/);
  const c=(await asRole('empire_outbound_approver','select public.cancel_outbound_intent($1,$2,$3) result',[r.intent_id,'phil','replace stale draft'])).rows[0].result;
  assert.equal(c.status,'cancelled');
  await assert.rejects(asRole('empire_outbound_sender','select public.claim_outbound_send($1,$2)',[r.intent_id,'sender']),/approved unexpired outbound intent required/);
});
await test('human approver owns approval',async()=>{
  const r=(await asRole('empire_outbound_approver','select public.approve_outbound_intent($1,$2,$3) result',[intentId,'phil','reviewed'])).rows[0].result;
  assert.equal(r.status,'approved');
});
await test('sender review is read-only and creates no send attempt',async()=>{
  const before=(await admin.query("select count(*)::int n from outbound_events where intent_id=$1 and event_type='send_attempt'",[intentId])).rows[0].n;
  const review=(await asRole('empire_outbound_sender','select public.get_outbound_intent_review($1) result',[intentId])).rows[0].result;
  assert.equal(review.decision,'review'); assert.equal(review.status,'approved');
  const after=(await admin.query("select count(*)::int n from outbound_events where intent_id=$1 and event_type='send_attempt'",[intentId])).rows[0].n;
  assert.equal(after,before);
});
await test('sender claims and records delivery only after approval',async()=>{
  const claim=(await asRole('empire_outbound_sender','select public.claim_outbound_send($1,$2) result',[intentId,'resend-worker'])).rows[0].result;
  assert.equal(claim.decision,'authorized_send'); assert.equal(claim.recipient,'buyer@example.com');
  const sent=(await asRole('empire_outbound_sender',`select public.record_outbound_delivery($1,'sent',$2,$3,'{}') result`,[intentId,'resend-worker','msg-1'])).rows[0].result;
  assert.equal(sent.status,'sent');
});
await test('reply ingest records and unsubscribe suppresses future contact',async()=>{
  const rr=(await asRole('empire_reply_ingest',`select public.ingest_outbound_reply($1,$2,$3,$4,$5,$6,'{}') result`,[intentId,'reply-1','buyer@example.com','Re: Hello','unsubscribe please',new Date().toISOString()])).rows[0].result;
  replyId=rr.reply_id; assert.equal(rr.classification,'unclassified');
  const cr=(await asRole('empire_reply_ingest',`select public.classify_outbound_reply($1,'unsubscribe',0.99,$2) result`,[replyId,'classifier'])).rows[0].result;
  assert.equal(cr.suppressed,true);
  const sup=(await admin.query("select count(*)::int n from outbound_suppressions where normalized_contact='buyer@example.com'")).rows[0].n; assert.equal(sup,1);
  await assert.rejects(asRole('service_role',`select public.propose_outbound_intent($1,null,null,null,'email','buyer@example.com','Again','Body',null,'white_label','idem-0002','planner',$2,'{}')`,[entity,expires]),/recipient suppressed/);
});
await test('custom roles have no direct table writes',async()=>{
  for(const role of ['empire_outbound_approver','empire_outbound_sender','empire_reply_ingest']){
    await assert.rejects(asRole(role,"insert into outbound_suppressions(normalized_contact,contact_type,reason,source) values('x@example.com','email','x','x')"),/permission denied/);
  }
});
await test('events are append-only',async()=>{
  const id=(await admin.query('select id from outbound_events limit 1')).rows[0].id;
  await assert.rejects(admin.query('update outbound_events set actor=\'x\' where id=$1',[id]),/append-only/);
});
console.log(`${passed} governed outbound tests passed; no production database contacted.`);
}finally{await Promise.allSettled(clients.map(c=>c.end()));await pg.stop();}
