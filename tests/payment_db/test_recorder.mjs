// Isolated real PostgreSQL tests. Never accepts a production connection string.
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
const dataDir = await mkdtemp(join(tmpdir(), 'empire-bsc-test-data-'));
const pg = new EmbeddedPostgres({
    databaseDir: join(dataDir, 'db'), user: 'postgres',
    password: randomBytes(24).toString('hex'), port: 55439,
    persistent: true, createPostgresUser: false,
    postgresFlags: ['-c', 'listen_addresses=127.0.0.1', '-c', 'max_connections=15'],
    onLog: () => {}, onError: () => {},
});
const clients = [];
async function client() {
    const c = pg.getPgClient();
    await c.connect();
    clients.push(c);
    await c.query("set statement_timeout='8s'");
    return c;
}
const token = '0x55d398326f99059ff775485246999027b3197955';
const payer = '0x' + '33'.repeat(20), treasury = '0x' + '22'.repeat(20);
const terms = 'a'.repeat(64), block = '0x' + '77'.repeat(32);
function proof(tx = '0x' + randomBytes(32).toString('hex')) {
    return {verified:true, token_decimals:18, chain_id:56, token_contract:token,
        transaction_hash:tx, block_hash:block, block_number:100, log_index:0,
        amount_raw:'100000000000000000000', confirmations:12,
        verified_at:new Date().toISOString(), sender_address:payer,
        treasury_address:treasury, commercial_terms_sha256:terms};
}
let admin;
async function request(orderId) {
    const buyer = randomUUID(), order = orderId || randomUUID(), id = randomUUID();
    if (!orderId) {
        await admin.query('insert into buyers(id) values($1)', [buyer]);
        await admin.query("insert into fulfilment_orders values($1,$2,'accepted',$3)",
            [order,buyer,{commercial_terms_sha256:terms}]);
    }
    const b = orderId ? (await admin.query('select buyer_id from fulfilment_orders where id=$1',
        [order])).rows[0].buyer_id : buyer;
    await admin.query(`insert into bsc_payment_requests
        (id,buyer_id,fulfilment_order_id,amount_usdt,payer_address,treasury_address,
         commercial_terms_sha256,min_block_number,status,approved_by,approved_at,expires_at)
        values($1,$2,$3,100,$4,$5,$6,99,'approved','offline-test-human',now(),now()+interval '1 day')`,
        [id,b,order,payer,treasury,terms]);
    return {id,order,buyer:b};
}
async function record(c, id, p) {
    return (await c.query('select record_bsc_payment_evidence($1,$2) as result',[id,p])).rows[0].result;
}
let passed = 0;
async function test(name, fn) {
    await fn(); passed++; console.log('PASS ' + name);
}
try {
    await pg.initialise();
    await pg.start();
    admin = await client();
    // Minimal dependency schema fixtures; all rows stay inside this disposable DB.
    await admin.query(`create role anon; create role authenticated;
        create role service_role bypassrls;
        create table buyers(id uuid primary key);
        create table fulfilment_orders(id uuid primary key,buyer_id uuid references buyers(id),
            state text,commercial_payload jsonb);`);
    await admin.query(await readFile(join(root,
        'supabase/migrations/20260917150504_bsc_usdt_payment_verification.sql'),'utf8'));
    await test('migration applies on real PostgreSQL', async () => {
        assert.equal((await admin.query("select count(*) from bsc_payment_evidence")).rows[0].count,'0');
    });
    await test('valid evidence and retry create one row', async () => {
        const r=await request(), p=proof();
        assert.equal((await record(admin,r.id,p)).decision,'recorded');
        assert.equal((await record(admin,r.id,p)).decision,'already_recorded');
        assert.equal((await admin.query('select count(*) from bsc_payment_evidence where request_id=$1',
            [r.id])).rows[0].count,'1');
    });
    for (const [field,value] of [
        ['sender_address',treasury], ['treasury_address',payer],
        ['commercial_terms_sha256','b'.repeat(64)], ['amount_raw','99999999999999999999'],
        ['block_number',98], ['confirmations',11], ['chain_id',1],
        ['verified',false], ['token_decimals',6], ['transaction_hash',null],
        ['verified_at','2020-01-01T00:00:00Z'],
    ]) await test('reject invalid '+field, async () => {
        const r=await request();
        await assert.rejects(record(admin,r.id,{...proof(),[field]:value}));
    });
    await test('cancelled request fails', async () => {
        const r=await request();
        await admin.query("update bsc_payment_requests set status='cancelled' where id=$1",[r.id]);
        await assert.rejects(record(admin,r.id,proof()),/approved request/);
    });
    await test('approved terms cannot change', async () => {
        const r=await request();
        await assert.rejects(admin.query('update bsc_payment_requests set amount_usdt=1 where id=$1',
            [r.id]),/immutable/);
    });
    await test('changed order terms fail', async () => {
        const r=await request();
        await admin.query("update fulfilment_orders set commercial_payload='{}' where id=$1",[r.order]);
        await assert.rejects(record(admin,r.id,proof()),/terms mismatch/);
    });
    await test('payment evidence cannot be updated or deleted', async () => {
        const r=await request(); await record(admin,r.id,proof());
        await assert.rejects(admin.query('delete from bsc_payment_evidence where request_id=$1',
            [r.id]),/append-only/);
        await assert.rejects(admin.query('update bsc_payment_evidence set confirmations=20 where request_id=$1',
            [r.id]),/append-only/);
    });
    await test('simultaneous replay across requests has one winner', async () => {
        const a=await request(), b=await request(), p=proof();
        const c1=await client(), c2=await client();
        const results=await Promise.allSettled([record(c1,a.id,p),record(c2,b.id,p)]);
        assert.equal(results.filter(x=>x.status==='fulfilled').length,1);
        assert.equal(results.filter(x=>x.status==='rejected').length,1);
        assert.equal((await admin.query('select count(*) from bsc_payment_evidence where transaction_hash=$1',
            [p.transaction_hash])).rows[0].count,'1');
    });
    await test('simultaneous same-request retry is idempotent', async () => {
        const r=await request(), p=proof(), c1=await client(), c2=await client();
        const results=await Promise.all([record(c1,r.id,p),record(c2,r.id,p)]);
        assert.deepEqual(results.map(r=>r.decision).sort(),['already_recorded','recorded']);
    });
    await test('retry cannot change payer or treasury', async () => {
        const r=await request(), p=proof();
        await record(admin,r.id,p);
        await assert.rejects(record(admin,r.id,{...p,sender_address:treasury}),/different evidence/);
        await assert.rejects(record(admin,r.id,{...p,treasury_address:payer}),/different evidence/);
    });
    await test('one order cannot receive two payment claims', async () => {
        const a=await request(), b=await request(a.order);
        await record(admin,a.id,proof());
        await assert.rejects(record(admin,b.id,proof()),/unique constraint/);
    });
    for (const role of ['anon','authenticated','service_role']) {
        await test(role+' cannot record payments', async () => {
            const c=await client(), r=await request();
            await c.query('set role '+role);
            await assert.rejects(record(c,r.id,proof()),/permission denied/);
            await assert.rejects(c.query("insert into bsc_payment_evidence default values"),
                /permission denied/);
        });
    }
    console.log(passed+' database tests passed; no production database contacted.');
} finally {
    await Promise.allSettled(clients.map(c=>c.end()));
    await pg.stop();
}
