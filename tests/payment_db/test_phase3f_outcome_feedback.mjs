import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {randomUUID, randomBytes} from 'node:crypto';

const deps=process.env.EMPIRE_PG_TEST_DEPS;
if(!deps) throw new Error('Set EMPIRE_PG_TEST_DEPS');
const {default:EmbeddedPostgres}=await import(pathToFileURL(
  join(deps,'node_modules/embedded-postgres/dist/index.js')));
const root=resolve(fileURLToPath(new URL('../..',import.meta.url)));
const dataDir=await mkdtemp(join(tmpdir(),'empire-phase3f-'));
const pg=new EmbeddedPostgres({
  databaseDir:join(dataDir,'db'),user:'postgres',
  password:randomBytes(24).toString('hex'),port:55443,persistent:true,
  createPostgresUser:false,
  postgresFlags:['-c','listen_addresses=127.0.0.1','-c','max_connections=20'],
  onLog:()=>{},onError:()=>{},
});
const clients=[];
async function client(){const c=pg.getPgClient();await c.connect();clients.push(c);return c;}
async function asRole(role,sql,params=[]){
  const c=await client();
  try{await c.query('set role '+role);return await c.query(sql,params);}
  finally{await c.end();clients.splice(clients.indexOf(c),1);}
}
let admin,passed=0;
async function test(name,fn){await fn();passed++;console.log('PASS '+name);}
const payer='0x'+'33'.repeat(20), treasury='0x'+'22'.repeat(20);
const contract='0x'+'11'.repeat(20), runtime='a'.repeat(64);
const terms='b'.repeat(64), blockHash='0x'+'77'.repeat(32);
const token='0x55d398326f99059ff775485246999027b3197955';
const nowIso=()=>new Date().toISOString();


function directProof(amount='100000000000000000000'){
  return {
    verified:true,token_decimals:18,chain_id:56,token_contract:token,
    transaction_hash:'0x'+randomBytes(32).toString('hex'),
    block_hash:blockHash,block_number:100,log_index:0,amount_raw:amount,
    confirmations:12,verified_at:nowIso(),sender_address:payer,
    treasury_address:treasury,commercial_terms_sha256:terms,
  };
}

async function createOrder({price=10000,state='accepted'}={}){
  const buyer=randomUUID(),prospect=randomUUID(),order=randomUUID();
  await admin.query(
    "insert into buyers(id,niche,metro,status) values($1,'roofing','houston','active')",
    [buyer]
  );
  await admin.query(
    "insert into prospects(id,business_name,niche,metro,status) values($1,'Test Prospect','roofing','houston','qualified')",
    [prospect]
  );
  await admin.query(`
    insert into fulfilment_orders(
      id,prospect_id,buyer_id,state,price_cents,
      acquisition_cost_cents,fulfilment_cost_cents,expected_margin_cents,
      commercial_payload
    ) values($1,$2,$3,$4,$5,2000,1000,$6,$7)
  `,[order,prospect,buyer,state,price,price-3000,{commercial_terms_sha256:terms}]);
  return {buyer,prospect,order};
}

async function approveRequest(requestId){
  return (await asRole('empire_payment_approver',
    'select public.approve_bsc_payment_request($1,$2,$3) result',
    [requestId,'phase3f-human','approved test payment'])).rows[0].result;
}


try{
  await pg.initialise(); await pg.start(); admin=await client();
  await admin.query(`create role anon; create role authenticated;
    create role service_role bypassrls;
    create table business_entities(id uuid primary key);
    create table prospects(
      id uuid primary key,business_name text,niche text,metro text,status text
    );
    create table buyers(
      id uuid primary key,niche text,metro text,status text
    );`);

  await admin.query(await readFile(join(root,'migrations/002_commercial_control_plane.sql'),'utf8'));
  // Mirror canonical production's legacy service_role event-write surface.
  await admin.query('grant select,insert,update,delete,truncate on commercial_events to service_role');
  for(const file of [
    '20260917150504_bsc_usdt_payment_verification.sql',
    '20260917170234_govern_bsc_payment_requests.sql',
    '20260917174000_bsc_usdt_smart_contract_escrow.sql',
    '20260918123504_phase3f_outcome_feedback.sql',
    '20260918124631_phase3f_runtime_identities.sql',
    '20260918191547_phase3f_commercial_figures.sql',
  ]){
    await admin.query(await readFile(join(root,'supabase/migrations',file),'utf8'));
  }

  await test('migration creates append-only outcome and revenue roles',async()=>{
    const q=await admin.query(`select
      has_function_privilege('empire_outcome_recorder',
        'public.record_commercial_outcome(uuid,text,text,numeric,text,text,jsonb,text,text)','EXECUTE') outcome_ok,
      has_function_privilege('empire_revenue_recognizer',
        'public.recognize_bsc_revenue(uuid,text)','EXECUTE') revenue_ok,
      has_function_privilege('service_role',
        'public.recognize_bsc_revenue(uuid,text)','EXECUTE') service_revenue`);
    assert.equal(q.rows[0].outcome_ok,true);
    assert.equal(q.rows[0].revenue_ok,true);
    assert.equal(q.rows[0].service_revenue,false);

    const roles=await admin.query(`
      select rolname,rolcanlogin,rolinherit,rolsuper,rolbypassrls
      from pg_roles
      where rolname in (
        'empire_outcome_recorder_login',
        'empire_revenue_recognizer_login'
      )
      order by rolname
    `);
    assert.equal(roles.rows.length,2);
    for(const role of roles.rows){
      assert.equal(role.rolcanlogin,true);
      assert.equal(role.rolinherit,false);
      assert.equal(role.rolsuper,false);
      assert.equal(role.rolbypassrls,false);
    }
  });

  await test('legacy zero-value event insert still works but forged finance is blocked',async()=>{
    await asRole('service_role',`
      insert into commercial_events(event_type,channel,actor,payload,idempotency_key)
      values('qualification_test','qualification','test','{}','phase3f:legacy:zero')
    `);
    await assert.rejects(
      asRole('service_role',`
        insert into commercial_events(
          event_type,channel,actor,amount_cents,cost_cents,margin_cents,payload,idempotency_key
        ) values('revenue_recognized','fake','fake',10000,0,10000,'{}','phase3f:fake:revenue')
      `),
      /financial commercial events require revenue recognizer role/
    );
  });


  const direct=await createOrder();
  let directRequest;
  await test('direct BSC evidence becomes bounded recognition work',async()=>{
    const expires=new Date(Date.now()+60*60*1000);
    const proposed=(await asRole('service_role',`
      select public.propose_bsc_payment_request($1,$2,$3,$4,$5,$6,$7,$8) result
    `,[direct.order,'100',payer,treasury,99,expires,'phase3f:direct:001','phase3f-test'])).rows[0].result;
    directRequest=proposed.request_id;
    await approveRequest(directRequest);
    const recorded=(await asRole('empire_bsc_verifier',
      'select public.record_bsc_payment_evidence($1,$2) result',
      [directRequest,directProof()])).rows[0].result;
    assert.equal(recorded.decision,'recorded');

    const work=(await asRole('empire_revenue_recognizer',
      'select public.list_revenue_recognition_work($1) result',[25])).rows[0].result;
    const item=work.find(x=>x.fulfilment_order_id===direct.order);
    assert.ok(item);
    assert.equal(item.direct_evidence,true);
    assert.equal(item.amount_matches,true);
  });

  await test('direct evidence recognizes exact approved revenue and margin once',async()=>{
    const result=(await asRole('empire_revenue_recognizer',
      'select public.recognize_bsc_revenue($1,$2) result',
      [direct.order,'phase3f-revenue-worker'])).rows[0].result;
    assert.equal(result.decision,'revenue_recognized');
    assert.equal(result.amount_cents,10000);
    assert.equal(result.cost_cents,3000);
    assert.equal(result.margin_cents,7000);
    assert.equal(result.settlement_source,'direct_payment');
    assert.equal(result.actual_revenue,true);

    const retry=(await asRole('empire_revenue_recognizer',
      'select public.recognize_bsc_revenue($1,$2) result',
      [direct.order,'phase3f-revenue-worker'])).rows[0].result;
    assert.equal(retry.decision,'existing_revenue');

    const order=(await admin.query(
      'select state,actual_margin_cents,paid_at,settled_at from fulfilment_orders where id=$1',
      [direct.order])).rows[0];
    assert.equal(order.state,'settled');
    assert.equal(Number(order.actual_margin_cents),7000);
    assert.ok(order.paid_at);
    assert.ok(order.settled_at);
  });


  await test('outcome recorder captures conversion and satisfaction without declaring revenue',async()=>{
    const result=(await asRole('empire_outcome_recorder',`
      select public.record_commercial_outcome(
        $1,'confirmed','won',4.5,'buyer_feedback',$2,$3,$4,$5
      ) result
    `,[
      direct.order,'feedback:buyer@example.com',
      {source:'test',note:'buyer confirmed successful outcome'},
      'phase3f:outcome:direct:001','phase3f-outcome-worker'
    ])).rows[0].result;
    assert.equal(result.decision,'recorded_outcome');
    assert.equal(result.actual_revenue,false);

    const order=(await admin.query(
      'select state,outcome_at from fulfilment_orders where id=$1',[direct.order]
    )).rows[0];
    assert.equal(order.state,'outcome_captured');
    assert.ok(order.outcome_at);

    const feedback=(await asRole('service_role',
      'select public.get_commercial_outcome_feedback($1) result',[100])).rows[0].result;
    const row=feedback.find(x=>x.fulfilment_order_id===direct.order);
    assert.ok(row);
    assert.equal(row.actual_revenue,true);
    assert.equal(Number(row.actual_revenue_cents),10000);
    assert.equal(Number(row.gross_profit_cents),7000);
    assert.equal(row.conversion_outcome,'won');
    assert.equal(Number(row.buyer_satisfaction),4.5);
    assert.equal(row.previous_purchase,true);
    assert.equal(row.converted,true);
  });

  await test('commercial outcome and event history are immutable',async()=>{
    await assert.rejects(
      admin.query("update commercial_outcomes set conversion_outcome='lost' where fulfilment_order_id=$1",[direct.order]),
      /commercial outcomes are append-only/
    );
    await assert.rejects(
      admin.query("update commercial_events set actor='tampered' where fulfilment_order_id=$1",[direct.order]),
      /commercial events are append-only/
    );
  });

  const mismatch=await createOrder();
  await test('verified payment with wrong economic amount is held, not recognized',async()=>{
    const expires=new Date(Date.now()+60*60*1000);
    const proposed=(await asRole('service_role',`
      select public.propose_bsc_payment_request($1,$2,$3,$4,$5,$6,$7,$8) result
    `,[mismatch.order,'99',payer,treasury,99,expires,'phase3f:direct:mismatch','phase3f-test'])).rows[0].result;
    await approveRequest(proposed.request_id);
    await asRole('empire_bsc_verifier',
      'select public.record_bsc_payment_evidence($1,$2)',
      [proposed.request_id,directProof('99000000000000000000')]);

    const work=(await asRole('empire_revenue_recognizer',
      'select public.list_revenue_recognition_work($1) result',[25])).rows[0].result;
    const item=work.find(x=>x.fulfilment_order_id===mismatch.order);
    assert.ok(item);
    assert.equal(item.amount_matches,false);

    await assert.rejects(
      asRole('empire_revenue_recognizer',
        'select public.recognize_bsc_revenue($1,$2)',
        [mismatch.order,'phase3f-revenue-worker']),
      /settlement amount does not equal approved USD price/
    );
  });


  const escrow=await createOrder();
  await test('released escrow evidence recognizes revenue only after release',async()=>{
    const expires=new Date(Date.now()+60*60*1000);
    const proposed=(await asRole('service_role',`
      select public.propose_bsc_escrow_request($1,$2,$3,$4,$5,$6,$7,$8) result
    `,[escrow.order,'100',payer,treasury,99,expires,'phase3f:escrow:001','phase3f-test'])).rows[0].result;
    const requestId=proposed.request_id;
    await approveRequest(requestId);

    const escrowId='0x'+requestId.replaceAll('-','').padStart(64,'0');
    const now=Math.floor(Date.now()/1000);
    const creation={
      verified:true,escrow_id:escrowId,payer_address:payer,
      amount_raw:'100000000000000000000',terms_hash:'0x'+terms,
      beneficiary_address:treasury,contract_address:contract,
      runtime_sha256:runtime,transaction_hash:'0x'+'88'.repeat(32),
      block_hash:blockHash,block_number:100,confirmations:12,
      funding_deadline:now+1800,refund_after:now+86400,
      block_timestamp:now,verified_at:nowIso(),
    };
    const created=(await asRole('empire_escrow_verifier',
      'select public.record_bsc_escrow_creation($1,$2) result',
      [requestId,creation])).rows[0].result;
    const agreementId=created.agreement_id;

    const lifecycle=(action,tx,party)=>({
      verified:true,action,escrow_id:escrowId,transaction_hash:tx,
      block_hash:blockHash,block_number:101,
      amount_raw:'100000000000000000000',party_address:party,
      confirmations:12,block_timestamp:Math.floor(Date.now()/1000),
      verified_at:nowIso(),
    });

    await asRole('empire_escrow_verifier',
      'select public.record_bsc_escrow_lifecycle($1,$2,$3)',
      [agreementId,'funded',lifecycle('funded','0x'+'99'.repeat(32),payer)]);

    await assert.rejects(
      asRole('empire_revenue_recognizer',
        'select public.recognize_bsc_revenue($1,$2)',
        [escrow.order,'phase3f-revenue-worker']),
      /no revenue-eligible verified BSC settlement evidence/
    );

    await asRole('empire_escrow_verifier',
      'select public.record_bsc_escrow_lifecycle($1,$2,$3)',
      [agreementId,'released',lifecycle('released','0x'+'aa'.repeat(32),treasury)]);

    const recognized=(await asRole('empire_revenue_recognizer',
      'select public.recognize_bsc_revenue($1,$2) result',
      [escrow.order,'phase3f-revenue-worker'])).rows[0].result;
    assert.equal(recognized.actual_revenue,true);
    assert.equal(recognized.settlement_source,'escrow_release');
    assert.equal(Number(recognized.amount_cents),10000);
    assert.equal(Number(recognized.margin_cents),7000);
  });

  await test('commercial scorecard exposes real figures and segment performance',async()=>{
    const scorecard=(await asRole('empire_outcome_reader',
      'select public.get_phase3f_commercial_scorecard($1) result',[30])).rows[0].result;
    assert.equal(Number(scorecard.actual_revenue_cents),20000);
    assert.equal(Number(scorecard.actual_cost_cents),6000);
    assert.equal(Number(scorecard.gross_profit_cents),14000);
    assert.equal(Number(scorecard.gross_margin_rate),0.7);
    assert.equal(Number(scorecard.gross_margin_pct),70);
    assert.equal(scorecard.currency,'USD');
    assert.equal(scorecard.settlement_asset,'USDT');
    assert.equal(scorecard.settlement_chain,'BSC');
    assert.equal(Number(scorecard.recognized_revenue_orders),2);
    assert.equal(Number(scorecard.outcome_orders),1);
    assert.equal(Number(scorecard.won),1);
    assert.equal(Number(scorecard.conversion_rate),1);
    assert.equal(Number(scorecard.conversion_rate_pct),100);
    assert.equal(Number(scorecard.average_buyer_satisfaction),4.5);
    assert.equal(Number(scorecard.revenue_per_recognized_order_cents),10000);
    assert.equal(scorecard.by_niche[0].niche,'roofing');
    assert.equal(scorecard.by_niche[0].metro,'houston');
    assert.equal(Number(scorecard.by_niche[0].actual_revenue_cents),20000);
    assert.equal(Number(scorecard.by_niche[0].gross_profit_cents),14000);
    assert.equal(scorecard.by_buyer.length,2);
    assert.equal(Number(scorecard.by_buyer[0].actual_cost_cents),3000);
    assert.equal(Number(scorecard.by_buyer[0].gross_margin_rate),0.7);

    const feedback=(await asRole('empire_outcome_reader',
      'select public.get_commercial_outcome_feedback($1) result',[100])).rows[0].result;
    assert.ok(feedback.length>=2);
    await assert.rejects(
      asRole('empire_outcome_reader','select count(*) from public.commercial_events'),
      /permission denied/
    );
  });

  console.log(passed+' Phase 3F outcome/revenue tests passed; no production database contacted.');
}finally{
  await Promise.allSettled(clients.map(c=>c.end()));
  await pg.stop();
}
