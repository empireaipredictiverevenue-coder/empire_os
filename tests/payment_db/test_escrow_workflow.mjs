import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {randomUUID, randomBytes} from 'node:crypto';

const deps = process.env.EMPIRE_PG_TEST_DEPS;
if (!deps) throw new Error('Set EMPIRE_PG_TEST_DEPS to isolated npm dependency directory');
const {default: EmbeddedPostgres} = await import(pathToFileURL(
  join(deps, 'node_modules/embedded-postgres/dist/index.js')));
const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const dataDir = await mkdtemp(join(tmpdir(), 'empire-escrow-workflow-'));
const pg = new EmbeddedPostgres({
  databaseDir: join(dataDir,'db'), user:'postgres',
  password: randomBytes(24).toString('hex'), port:55441,
  persistent:true, createPostgresUser:false,
  postgresFlags:['-c','listen_addresses=127.0.0.1','-c','max_connections=15'],
  onLog:()=>{}, onError:()=>{},
});
const clients=[];
async function client(){ const c=pg.getPgClient(); await c.connect(); clients.push(c); return c; }
async function asRole(role,sql,params=[]){
  const c=await client(); try{ await c.query('set role '+role); return await c.query(sql,params); }
  finally{ await c.end(); clients.splice(clients.indexOf(c),1); }
}
const payer='0x'+'33'.repeat(20), beneficiary='0x'+'22'.repeat(20);
const contract='0x'+'11'.repeat(20), runtime='a'.repeat(64), terms='b'.repeat(64);
const blockHash='0x'+'77'.repeat(32), createTx='0x'+'88'.repeat(32);
const fundTx='0x'+'99'.repeat(32), releaseTx='0x'+'aa'.repeat(32);
let admin,buyer,order,expiresAt,requestId,agreementId;
function nowIso(){ return new Date().toISOString(); }
function lifecycle(action,tx,party){ return {
  verified:true, action, escrow_id:'0x'+requestId.replaceAll('-','').padStart(64,'0'),
  transaction_hash:tx, block_hash:blockHash,
  block_number:100, amount_raw:'100000000000000000000',
  party_address:party, confirmations:12,
  block_timestamp:Math.floor(Date.now()/1000), verified_at:nowIso(),
}; }
let passed=0;
async function test(name,fn){ await fn(); passed++; console.log('PASS '+name); }
try{
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
  for(const file of [
    '20260917150504_bsc_usdt_payment_verification.sql',
    '20260917170234_govern_bsc_payment_requests.sql',
    '20260917174000_bsc_usdt_smart_contract_escrow.sql']){
    await admin.query(await readFile(join(root,'supabase/migrations',file),'utf8'));
  }

  await test('service role proposes escrow request', async()=>{
    const result=(await asRole('service_role',`select public.propose_bsc_escrow_request(
      $1,$2,$3,$4,$5,$6,$7,$8) result`,
      [order,'100',payer,beneficiary,99,expiresAt,'escrow:test:001','empire_os.test'])).rows[0].result;
    requestId=result.request_id; assert.equal(result.settlement_mode,'escrow');
    assert.equal(result.actual_revenue,false);
  });
  await test('human approver still owns approval boundary', async()=>{
    const result=(await asRole('empire_payment_approver',
      'select public.approve_bsc_payment_request($1,$2,$3) result',
      [requestId,'human-test-approver','approved escrow commercial terms'])).rows[0].result;
    assert.equal(result.decision,'approved'); assert.equal(result.actual_revenue,false);
  });

  const escrowId='0x'+requestId.replaceAll('-','').padStart(64,'0');
  await test('escrow verifier records on-chain creation only', async()=>{
    const now=Math.floor(Date.now()/1000);
    const creation={verified:true, escrow_id:escrowId, payer_address:payer,
      amount_raw:'100000000000000000000', terms_hash:'0x'+terms,
      beneficiary_address:beneficiary, contract_address:contract,
      runtime_sha256:runtime, transaction_hash:createTx, block_hash:blockHash,
      block_number:100, funding_deadline:now+1800, refund_after:now+86400,
      block_timestamp:now, verified_at:nowIso()};
    const result=(await asRole('empire_escrow_verifier',
      'select public.record_bsc_escrow_creation($1,$2) result',[requestId,creation])).rows[0].result;
    agreementId=result.agreement_id; assert.equal(result.status,'open');
    assert.equal(result.actual_revenue,false);
  });

  await test('direct verifier cannot satisfy escrow request', async()=>{
    const direct={verified:true,token_decimals:18,chain_id:56,
      token_contract:'0x55d398326f99059ff775485246999027b3197955',
      transaction_hash:'0x'+'44'.repeat(32),block_hash:blockHash,block_number:100,
      log_index:0,amount_raw:'100000000000000000000',confirmations:12,
      verified_at:nowIso(),sender_address:payer,treasury_address:beneficiary,
      commercial_terms_sha256:terms};
    await assert.rejects(asRole('empire_bsc_verifier',
      'select public.record_bsc_payment_evidence($1,$2)',[requestId,direct]),/cannot satisfy an escrow request/);
  });
  await test('funding evidence records without revenue recognition', async()=>{
    const result=(await asRole('empire_escrow_verifier',
      'select public.record_bsc_escrow_lifecycle($1,$2,$3) result',
      [agreementId,'funded',lifecycle('funded',fundTx,payer)])).rows[0].result;
    assert.equal(result.status,'funded');
    assert.equal(result.revenue_eligible,false);
    assert.equal(result.actual_revenue,false);
  });

  await test('release evidence becomes revenue-eligible but not recognized revenue', async()=>{
    const result=(await asRole('empire_escrow_verifier',
      'select public.record_bsc_escrow_lifecycle($1,$2,$3) result',
      [agreementId,'released',lifecycle('released',releaseTx,beneficiary)])).rows[0].result;
    assert.equal(result.status,'released');
    assert.equal(result.revenue_eligible,true);
    assert.equal(result.actual_revenue,false);
  });

  await test('escrow verifier has no direct table writes', async()=>{
    await assert.rejects(asRole('empire_escrow_verifier',
      "update public.bsc_escrow_agreements set status='refunded' where id=$1",[agreementId]),
      /permission denied/);
    await assert.rejects(asRole('empire_escrow_verifier',
      'delete from public.bsc_escrow_evidence where agreement_id=$1',[agreementId]),
      /permission denied/);
  });
  await test('function ACLs keep service, approver and escrow verifier separated', async()=>{
    const q=await admin.query(`select
      has_function_privilege('service_role','public.propose_bsc_escrow_request(uuid,numeric,text,text,bigint,timestamptz,text,text)','EXECUTE') p,
      has_function_privilege('service_role','public.record_bsc_escrow_creation(uuid,jsonb)','EXECUTE') sc,
      has_function_privilege('empire_payment_approver','public.record_bsc_escrow_creation(uuid,jsonb)','EXECUTE') ac,
      has_function_privilege('empire_escrow_verifier','public.record_bsc_escrow_creation(uuid,jsonb)','EXECUTE') vc,
      has_function_privilege('empire_escrow_verifier','public.record_bsc_escrow_lifecycle(uuid,text,jsonb)','EXECUTE') vl`);
    const a=q.rows[0];
    assert.equal(a.p,true); assert.equal(a.sc,false); assert.equal(a.ac,false);
    assert.equal(a.vc,true); assert.equal(a.vl,true);
  });

  console.log(passed+' escrow workflow tests passed; no production database contacted.');
} finally {
  await Promise.allSettled(clients.map(c=>c.end()));
  await pg.stop();
}
