// Isolated PostgreSQL governance tests. Never accepts a production connection string.
import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {randomUUID, randomBytes} from 'node:crypto';

const deps = process.env.EMPIRE_PG_TEST_DEPS;
if (!deps) throw new Error('Set EMPIRE_PG_TEST_DEPS to the isolated npm dependency directory');
const {default: EmbeddedPostgres} = await import(pathToFileURL(
  join(deps, 'node_modules/embedded-postgres/dist/index.js')));
const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const dataDir = await mkdtemp(join(tmpdir(), 'empire-payment-workflow-'));
const pg = new EmbeddedPostgres({
  databaseDir: join(dataDir, 'db'), user: 'postgres',
  password: randomBytes(24).toString('hex'), port: 55440,
  persistent: true, createPostgresUser: false,
  postgresFlags: ['-c', 'listen_addresses=127.0.0.1', '-c', 'max_connections=15'],
  onLog: () => {}, onError: () => {},
});
const clients = [];
async function client() {
  const c = pg.getPgClient(); await c.connect(); clients.push(c);
  await c.query("set statement_timeout='8s'"); return c;
}
const token = '0x55d398326f99059ff775485246999027b3197955';
const payer = '0x' + '33'.repeat(20), treasury = '0x' + '22'.repeat(20);
const terms = 'a'.repeat(64), blockHash = '0x' + '77'.repeat(32);
let admin, buyer, order, expiresAt;
function proof(tx = '0x' + randomBytes(32).toString('hex')) {
  return {verified:true, token_decimals:18, chain_id:56, token_contract:token,
    transaction_hash:tx, block_hash:blockHash, block_number:100, log_index:0,
    amount_raw:'100000000000000000000', confirmations:12,
    verified_at:new Date().toISOString(), sender_address:payer,
    treasury_address:treasury, commercial_terms_sha256:terms};
}
async function asRole(role, sql, params=[]) {
  const c = await client();
  try { await c.query('set role ' + role); return await c.query(sql, params); }
  finally { await c.end(); clients.splice(clients.indexOf(c), 1); }
}
async function propose(key, amount='100') {
  return (await asRole('service_role', `select public.propose_bsc_payment_request(
    $1,$2,$3,$4,$5,$6,$7,$8) as result`,
    [order,amount,payer,treasury,99,expiresAt,key,'empire_os.test'])).rows[0].result;
}
async function approve(id) {
  return (await asRole('empire_payment_approver',
    'select public.approve_bsc_payment_request($1,$2,$3) as result',
    [id,'human-test-approver','reviewed buyer, amount, treasury and terms'])).rows[0].result;
}
async function record(id, p=proof()) {
  return (await asRole('empire_bsc_verifier',
    'select public.record_bsc_payment_evidence($1,$2) as result',[id,p])).rows[0].result;
}
let passed=0;
async function test(name, fn) { await fn(); passed++; console.log('PASS '+name); }
try {
  await pg.initialise(); await pg.start(); admin=await client();
  await admin.query(`create role anon; create role authenticated;
    create role service_role bypassrls;
    create table buyers(id uuid primary key);
    create table fulfilment_orders(
      id uuid primary key,buyer_id uuid references buyers(id),state text,commercial_payload jsonb
    );`);
  buyer=randomUUID(); order=randomUUID(); expiresAt=new Date(Date.now()+60*60*1000);
  await admin.query('insert into buyers(id) values($1)',[buyer]);
  await admin.query("insert into fulfilment_orders values($1,$2,'accepted',$3)",
    [order,buyer,{commercial_terms_sha256:terms}]);
  await admin.query(await readFile(join(root,
    'supabase/migrations/20260917150504_bsc_usdt_payment_verification.sql'),'utf8'));
  await admin.query(await readFile(join(root,
    'supabase/migrations/20260917170234_govern_bsc_payment_requests.sql'),'utf8'));

  await test('governance roles are NOLOGIN and not granted to service_role', async()=>{
    const q=await admin.query(`select rolname,rolcanlogin from pg_roles
      where rolname in ('empire_payment_approver','empire_bsc_verifier') order by rolname`);
    assert.equal(q.rows.length,2); assert(q.rows.every(r=>r.rolcanlogin===false));
    const m=await admin.query(`select pg_has_role('service_role','empire_payment_approver','member') a,
      pg_has_role('service_role','empire_bsc_verifier','member') v`);
    assert.equal(m.rows[0].a,false); assert.equal(m.rows[0].v,false);
  });

  let requestId;
  await test('service_role proposes pending request idempotently', async()=>{
    const first=await propose('workflow:test:001'); requestId=first.request_id;
    assert.equal(first.decision,'proposed'); assert.equal(first.actual_revenue,false);
    const second=await propose('workflow:test:001');
    assert.equal(second.decision,'existing_request'); assert.equal(second.request_id,requestId);
  });
  await test('idempotency key cannot change payment terms', async()=>{
    await assert.rejects(propose('workflow:test:001','101'),/different payment terms/);
  });
  await test('service_role cannot approve or record evidence', async()=>{
    await assert.rejects(asRole('service_role',
      'select public.approve_bsc_payment_request($1,$2,$3)',
      [requestId,'agent','should fail']),/permission denied/);
    await assert.rejects(asRole('service_role',
      'select public.record_bsc_payment_evidence($1,$2)',
      [requestId,proof()]),/permission denied/);
  });
  await test('custom roles have no direct payment table writes', async()=>{
    await assert.rejects(asRole('empire_payment_approver',
      "update public.bsc_payment_requests set status='approved' where id=$1",[requestId]),
      /permission denied/);
    await assert.rejects(asRole('empire_bsc_verifier',
      'insert into public.bsc_payment_evidence default values'),/permission denied/);
  });
  await test('approver can inspect pending terms and verifier cannot approve', async()=>{
    const view=(await asRole('empire_payment_approver',
      'select public.get_bsc_payment_request_review($1) result',[requestId])).rows[0].result;
    assert.equal(view.status,'pending'); assert.equal(view.actual_revenue,false);
    await assert.rejects(asRole('empire_bsc_verifier',
      'select public.approve_bsc_payment_request($1,$2,$3)',
      [requestId,'verifier','should fail']),/permission denied/);
  });
  await test('human approver approves after order and terms recheck', async()=>{
    const result=await approve(requestId);
    assert.equal(result.decision,'approved'); assert.equal(result.actual_revenue,false);
    assert.equal((await approve(requestId)).decision,'existing_approval');
  });
  await test('dedicated verifier records only approved canonical evidence', async()=>{
    const result=await record(requestId);
    assert.equal(result.decision,'recorded'); assert.equal(result.actual_revenue,false);
    const review=(await asRole('empire_bsc_verifier',
      'select public.get_bsc_payment_request_review($1) result',[requestId])).rows[0].result;
    assert.equal(review.evidence_id,result.evidence_id);
    assert.equal(review.actual_revenue,false);
  });
  await test('request cannot be cancelled after evidence exists', async()=>{
    await assert.rejects(asRole('service_role',
      'select public.cancel_bsc_payment_request($1,$2,$3)',
      [requestId,'empire_os.test','payment observed']),/evidence already recorded/);
  });
  await test('payment governance audit is append-only', async()=>{
    const events=await admin.query('select event_type from bsc_payment_request_events where request_id=$1 order by created_at',[requestId]);
    assert.deepEqual(events.rows.map(x=>x.event_type),['proposed','approved','evidence_recorded']);
    await assert.rejects(admin.query(
      "update bsc_payment_request_events set actor='changed' where request_id=$1",[requestId]),/append-only/);
  });

  await test('verifier cannot record a pending request', async()=>{
    const oldOrder=order; order=randomUUID();
    await admin.query("insert into fulfilment_orders values($1,$2,'accepted',$3)",
      [order,buyer,{commercial_terms_sha256:terms}]);
    const pending=await propose('workflow:test:002');
    await assert.rejects(record(pending.request_id),/approved request/);
    await asRole('service_role','select public.cancel_bsc_payment_request($1,$2,$3)',
      [pending.request_id,'empire_os.test','test cleanup']);
    order=oldOrder;
  });
  await test('approval fails if commercial terms change after proposal', async()=>{
    const oldOrder=order; order=randomUUID();
    await admin.query("insert into fulfilment_orders values($1,$2,'accepted',$3)",
      [order,buyer,{commercial_terms_sha256:terms}]);
    const pending=await propose('workflow:test:003');
    await admin.query('update fulfilment_orders set commercial_payload=$2 where id=$1',
      [order,{commercial_terms_sha256:'b'.repeat(64)}]);
    await assert.rejects(approve(pending.request_id),/commercial terms changed/);
    await admin.query('update fulfilment_orders set commercial_payload=$2 where id=$1',
      [order,{commercial_terms_sha256:terms}]);
    const cancelled=(await asRole('service_role',
      'select public.cancel_bsc_payment_request($1,$2,$3) result',
      [pending.request_id,'empire_os.test','terms changed during review'])).rows[0].result;
    assert.equal(cancelled.decision,'cancelled');
    const replacement=await propose('workflow:test:004');
    assert.equal(replacement.decision,'proposed');
    order=oldOrder;
  });

  await test('proposal expiry window is bounded', async()=>{
    const c=await client();
    try {
      await c.query('set role service_role');
      await assert.rejects(c.query(`select public.propose_bsc_payment_request(
        $1,$2,$3,$4,$5,$6,$7,$8)`,
        [order,'100',payer,treasury,99,new Date(Date.now()+8*24*60*60*1000),
         'workflow:test:too-long','empire_os.test']),/10 minutes to 7 days/);
    } finally { await c.end(); clients.splice(clients.indexOf(c),1); }
  });
  await test('function ACLs preserve separation of duties', async()=>{
    const q=await admin.query(`select
      has_function_privilege('service_role','public.propose_bsc_payment_request(uuid,numeric,text,text,bigint,timestamptz,text,text)','EXECUTE') propose_service,
      has_function_privilege('service_role','public.approve_bsc_payment_request(uuid,text,text)','EXECUTE') approve_service,
      has_function_privilege('service_role','public.record_bsc_payment_evidence(uuid,jsonb)','EXECUTE') record_service,
      has_function_privilege('empire_payment_approver','public.approve_bsc_payment_request(uuid,text,text)','EXECUTE') approve_human,
      has_function_privilege('empire_payment_approver','public.record_bsc_payment_evidence(uuid,jsonb)','EXECUTE') record_human,
      has_function_privilege('empire_bsc_verifier','public.approve_bsc_payment_request(uuid,text,text)','EXECUTE') approve_verifier,
      has_function_privilege('empire_bsc_verifier','public.record_bsc_payment_evidence(uuid,jsonb)','EXECUTE') record_verifier`);
    const a=q.rows[0];
    assert.equal(a.propose_service,true); assert.equal(a.approve_service,false);
    assert.equal(a.record_service,false); assert.equal(a.approve_human,true);
    assert.equal(a.record_human,false); assert.equal(a.approve_verifier,false);
    assert.equal(a.record_verifier,true);
  });

  console.log(passed+' payment governance tests passed; no production database contacted.');
} finally {
  await Promise.allSettled(clients.map(c=>c.end()));
  await pg.stop();
}
