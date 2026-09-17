import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {randomBytes, randomUUID} from 'node:crypto';

const deps=process.env.EMPIRE_PG_TEST_DEPS; if(!deps) throw new Error('Set EMPIRE_PG_TEST_DEPS');
const {default:EmbeddedPostgres}=await import(pathToFileURL(join(deps,'node_modules/embedded-postgres/dist/index.js')));
const root=resolve(fileURLToPath(new URL('../..',import.meta.url)));
const dir=await mkdtemp(join(tmpdir(),'empire-buyer-review-'));
const pg=new EmbeddedPostgres({databaseDir:join(dir,'db'),user:'postgres',password:randomBytes(24).toString('hex'),port:55447,persistent:true,createPostgresUser:false,onLog:()=>{},onError:()=>{}});
let admin; const clients=[]; let passed=0;
async function client(){const c=pg.getPgClient();await c.connect();clients.push(c);return c;}
async function asRole(role,sql,args=[]){const c=await client();try{await c.query('begin');await c.query('set local role '+role);const r=await c.query(sql,args);await c.query('commit');return r;}finally{await c.end();clients.splice(clients.indexOf(c),1);}}
async function test(name,fn){await fn();passed++;console.log('PASS '+name);}
try{
  await pg.initialise(); await pg.start(); admin=await client();
  await admin.query(`create role anon; create role authenticated; create role service_role bypassrls;
    create table prospects(id uuid primary key); create table business_entities(id uuid primary key);
    create table buyers(id uuid primary key); create table gtm_opportunities(id uuid primary key);`);
  const outbound=await readFile(join(root,'supabase/migrations/20260917190000_governed_outbound_reply_capture.sql'),'utf8');
  await admin.query(outbound);
  const gate=await readFile(join(root,'supabase/migrations/20260917201500_buyer_candidate_review_gate.sql'),'utf8');
  await admin.query(gate);
  const prospect=randomUUID(), entity=randomUUID();
  await admin.query('insert into prospects(id) values($1)',[prospect]);
  await admin.query('insert into business_entities(id) values($1)',[entity]);
  const expires=new Date(Date.now()+3600_000).toISOString();
  let reviewId;

  await test('service nominates candidate but direct outbound is revoked',async()=>{
    const r=(await asRole('service_role',`select public.propose_buyer_candidate_review($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) result`,[
      prospect,entity,'Frank Smith','Founder','frank@acme.example','managed_service',90,1.0,{source:'website'},'cand-0001'
    ])).rows[0].result;
    reviewId=r.review_id; assert.equal(r.status,'pending');
    await assert.rejects(asRole('service_role',`select public.propose_outbound_intent($1,$2,null,null,'email',$3,'Hi','Body',null,'managed_service','idem-direct','planner',$4,'{}')`,[entity,prospect,'frank@acme.example',expires]),/permission denied/);
  });

  await test('unapproved candidate cannot create outbound intent',async()=>{
    await assert.rejects(asRole('service_role',`select public.propose_reviewed_outbound_intent($1,'Hi','Body',null,'idem-reviewed-1','planner',$2,'{}')`,[reviewId,expires]),/approved buyer candidate review required/);
  });

  await test('human approver owns candidate decision',async()=>{
    await assert.rejects(asRole('service_role','select public.review_buyer_candidate($1,$2,$3,$4)',[reviewId,'approved','planner','x']),/permission denied/);
    const r=(await asRole('empire_outbound_approver','select public.review_buyer_candidate($1,$2,$3,$4) result',[reviewId,'approved','human-reviewer','verified'])).rows[0].result;
    assert.equal(r.status,'approved');
  });

  await test('approved candidate can create pending outbound intent only',async()=>{
    const r=(await asRole('service_role',`select public.propose_reviewed_outbound_intent($1,'Hi Frank','Body with unsubscribe and footer',null,'idem-reviewed-2','planner',$2,'{}') result`,[reviewId,expires])).rows[0].result;
    assert.equal(r.status,'pending_approval');
    assert.equal(r.actual_revenue,false);
    const row=(await admin.query('select recipient,offer_key,status,metadata from outbound_intents where id=$1',[r.intent_id])).rows[0];
    assert.equal(row.recipient,'frank@acme.example');
    assert.equal(row.offer_key,'managed_service');
    assert.equal(row.status,'pending_approval');
    assert.equal(row.metadata.buyer_candidate_review_id,reviewId);
  });

  await test('candidate review tables deny direct writes',async()=>{
    for(const role of ['service_role','empire_outbound_approver']){
      await assert.rejects(asRole(role,`insert into buyer_candidate_reviews(prospect_id,contact_name,contact_title,contact_email,offer_key,company_score,decision_score,evidence,idempotency_key) values($1,'X Y','Owner','x@y.com','software_mrr',80,1,'{}','direct-x')`,[prospect]),/permission denied/);
    }
  });

  await test('candidate review events are append-only',async()=>{
    const id=(await admin.query('select id from buyer_candidate_review_events limit 1')).rows[0].id;
    await assert.rejects(admin.query("update buyer_candidate_review_events set actor='x' where id=$1",[id]),/append-only/);
  });

  console.log(`${passed} buyer candidate review-gate tests passed; no production database contacted.`);
} finally {
  await Promise.allSettled(clients.map(c=>c.end()));
  await pg.stop();
}
