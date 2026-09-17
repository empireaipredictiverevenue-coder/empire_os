// Isolated PostgreSQL regression tests for buyer verification -> BSC evidence.
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
const dataDir = await mkdtemp(join(tmpdir(), 'empire-buyer-payment-bridge-'));
const pg = new EmbeddedPostgres({
    databaseDir: join(dataDir, 'db'), user: 'postgres',
    password: randomBytes(24).toString('hex'), port: 55440,
    persistent: true, createPostgresUser: false,
    postgresFlags: ['-c', 'listen_addresses=127.0.0.1'],
    onLog: () => {}, onError: () => {},
});
const clients = [];
async function client() {
    const c = pg.getPgClient(); await c.connect(); clients.push(c);
    await c.query("set statement_timeout='8s'"); return c;
}
const terms = 'a'.repeat(64);
const payer = '0x' + '33'.repeat(20), treasury = '0x' + '22'.repeat(20);
const token = '0x55d398326f99059ff775485246999027b3197955';
let admin;
async function seedPayment({buyerId=randomUUID(), termsHash=terms, status='approved'}={}) {
    const orderId=randomUUID(), requestId=randomUUID(), evidenceId=randomUUID();
    await admin.query('insert into buyers(id) values($1) on conflict do nothing',[buyerId]);
    await admin.query('insert into fulfilment_orders values($1,$2,$3)',
        [orderId,buyerId,{commercial_terms_sha256:termsHash}]);
    await admin.query(`insert into bsc_payment_requests
        (id,buyer_id,fulfilment_order_id,amount_usdt,payer_address,treasury_address,
         commercial_terms_sha256,min_block_number,status,approved_by,approved_at,expires_at)
        values($1,$2,$3,100,$4,$5,$6,99,$7,'human',now()-interval '1 minute',now()+interval '1 day')`,
        [requestId,buyerId,orderId,payer,treasury,termsHash,status]);
    await admin.query(`insert into bsc_payment_evidence
        (id,request_id,fulfilment_order_id,chain_id,token_contract,block_number,
         amount_raw,confirmations,verified_at,sender_address,treasury_address,commercial_terms_sha256)
        values($1,$2,$3,56,$4,100,100000000000000000000,12,now(),$5,$6,$7)`,
        [evidenceId,requestId,orderId,token,payer,treasury,termsHash]);
    return {buyerId, orderId, requestId, evidenceId};
}
async function addCommercialEvidence({buyerId,evidenceId,termsHash=terms}={}) {
    const id=randomUUID();
    await admin.query(`insert into buyer_commercial_evidence
        (id,buyer_id,evidence_type,evidence_reference,niche,metro,daily_cap,
         price_per_lead_cents,verification_state,terms)
        values($1,$2,'verified_payment',$3,'roofing','glasgow',10,5000,'pending',$4)`,
        [id,buyerId,evidenceId,{commercial_terms_sha256:termsHash}]);
    return id;
}
let passed=0;
async function test(name, fn) { await fn(); passed++; console.log('PASS '+name); }
try {
    await pg.initialise(); await pg.start(); admin=await client();
    await admin.query(`create role anon; create role authenticated; create role service_role bypassrls;
        create table buyers(id uuid primary key);
        create table buyer_subscriptions(
            id uuid primary key,buyer_id uuid,active boolean,status text,
            max_leads_per_day integer,price_per_lead_cents integer,period_end timestamptz);
        create table fulfilment_orders(
            id uuid primary key,buyer_id uuid references buyers(id),commercial_payload jsonb);
        create table buyer_commercial_evidence(
            id uuid primary key,buyer_id uuid references buyers(id),evidence_type text,
            evidence_reference text,niche text,metro text,daily_cap integer,
            price_per_lead_cents integer,destination_phone text,webhook_url text,
            verification_state text default 'pending',verified_at timestamptz,verified_by text,
            terms jsonb default '{}'::jsonb,updated_at timestamptz default now());
        create table bsc_payment_requests(
            id uuid primary key,buyer_id uuid,fulfilment_order_id uuid,amount_usdt numeric,
            payer_address text,treasury_address text,commercial_terms_sha256 text,
            min_block_number bigint,status text,approved_by text,approved_at timestamptz,
            expires_at timestamptz);
        create table bsc_payment_evidence(
            id uuid primary key,request_id uuid,fulfilment_order_id uuid,chain_id integer,
            token_contract text,block_number bigint,amount_raw numeric,confirmations integer,
            verified_at timestamptz,sender_address text,treasury_address text,
            commercial_terms_sha256 text);`);
    await admin.query(await readFile(join(root,
        'supabase/migrations/20260917165008_bind_buyer_payment_to_bsc_evidence.sql'),'utf8'));

    await test('migration has no legacy crypto payment dependency', async () => {
        const r=await admin.query("select to_regclass('public.crypto_payment_requests') as legacy");
        assert.equal(r.rows[0].legacy,null);
    });
    await test('canonical BSC evidence verifies matching buyer and terms', async () => {
        const p=await seedPayment();
        const ce=await addCommercialEvidence({buyerId:p.buyerId,evidenceId:p.evidenceId});
        const result=(await admin.query(
            'select verify_buyer_commercial_evidence($1,$2) result',[ce,'offline-test-human']
        )).rows[0].result;
        assert.equal(result.decision,'verified');
        assert.equal((await admin.query(
            'select verification_state from buyer_commercial_evidence where id=$1',[ce]
        )).rows[0].verification_state,'verified');
    });
    await test('evidence for another buyer is rejected', async () => {
        const p=await seedPayment(), other=randomUUID();
        await admin.query('insert into buyers(id) values($1)',[other]);
        const ce=await addCommercialEvidence({buyerId:other,evidenceId:p.evidenceId});
        await assert.rejects(admin.query(
            'select verify_buyer_commercial_evidence($1,$2)',[ce,'offline-test-human']),
            /does not resolve to this buyer and terms/);
    });
    await test('commercial terms mismatch is rejected', async () => {
        const p=await seedPayment();
        const ce=await addCommercialEvidence({
            buyerId:p.buyerId,evidenceId:p.evidenceId,termsHash:'b'.repeat(64)});
        await assert.rejects(admin.query(
            'select verify_buyer_commercial_evidence($1,$2)',[ce,'offline-test-human']),
            /does not resolve to this buyer and terms/);
    });
    await test('non-service API roles cannot execute verifier', async () => {
        const p=await seedPayment();
        const ce=await addCommercialEvidence({buyerId:p.buyerId,evidenceId:p.evidenceId});
        for (const role of ['anon','authenticated']) {
            const c=await client(); await c.query('set role '+role);
            await assert.rejects(c.query(
                'select verify_buyer_commercial_evidence($1,$2)',[ce,'offline-test-human']),
                /permission denied/);
        }
    });
    console.log(passed+' buyer-payment bridge tests passed; no production database contacted.');
} finally {
    await Promise.allSettled(clients.map(c=>c.end()));
    await pg.stop();
}
