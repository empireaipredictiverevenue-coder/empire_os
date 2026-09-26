// Isolated PostgreSQL test for Empire Intelligence Fabric. Never uses production DB.
import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {randomBytes, randomUUID} from 'node:crypto';

const deps=process.env.EMPIRE_PG_TEST_DEPS;
if(!deps) throw new Error('Set EMPIRE_PG_TEST_DEPS');
const {default:EmbeddedPostgres}=await import(pathToFileURL(join(deps,'node_modules/embedded-postgres/dist/index.js')));
const root=resolve(fileURLToPath(new URL('../..',import.meta.url)));
const dir=await mkdtemp(join(tmpdir(),'empire-intelligence-'));
const pg=new EmbeddedPostgres({databaseDir:join(dir,'db'),user:'postgres',password:randomBytes(24).toString('hex'),port:55443,persistent:true,createPostgresUser:false,onLog:()=>{},onError:()=>{}});
const clients=[];
async function client(){const c=pg.getPgClient();await c.connect();clients.push(c);return c;}
let passed=0; async function test(name,fn){await fn();passed++;console.log('PASS '+name);}
let admin;
try{
  await pg.initialise(); await pg.start(); admin=await client();
  await admin.query(`create role anon; create role authenticated; create role service_role bypassrls;
    create table public.business_entities(id uuid primary key default gen_random_uuid(), canonical_name text);`);
  const sql=await readFile(join(root,'supabase/migrations/20260917183000_empire_intelligence_fabric.sql'),'utf8');
  await admin.query(sql);
  await test('creates six canonical TAM segments',async()=>{
    const q=await admin.query('select segment_key from public.intelligence_segments order by segment_key');
    assert.equal(q.rows.length,6);
    assert(q.rows.some(r=>r.segment_key==='tam_white_label'));
    assert(q.rows.some(r=>r.segment_key==='tam_high_ticket'));
  });
  await test('preserves company identity as external canonical anchor',async()=>{
    const company=randomUUID(); await admin.query('insert into public.business_entities(id,canonical_name) values($1,$2)',[company,'Acme Ltd']);
    const src=(await admin.query(`insert into public.intelligence_sources(source_key,source_type,display_name,authority_score)
      values('registry.test','public_registry','Registry Test',0.9) returning id`)).rows[0].id;
    await admin.query(`insert into public.intelligence_signals(entity_id,signal_type,signal_domain,observed_at,source_id,strength,confidence)
      values($1,'sales_hiring','intent',now(),$2,0.8,0.9)`,[company,src]);
    const n=(await admin.query('select count(*)::int n from public.intelligence_signals where entity_id=$1',[company])).rows[0].n;
    assert.equal(n,1);
  });
  await test('stores conflicting temporal facts without overwrite',async()=>{
    const company=(await admin.query(`insert into public.business_entities(canonical_name) values('Beta Ltd') returning id`)).rows[0].id;
    const src=(await admin.query(`select id from public.intelligence_sources limit 1`)).rows[0].id;
    await admin.query(`insert into public.intelligence_facts(entity_type,entity_id,fact_key,fact_value,source_id,confidence,first_seen_at,last_seen_at)
      values('company',$1,'employee_count','{"value":50}',$2,0.7,now(),now()),
            ('company',$1,'employee_count','{"value":62}',$2,0.8,now(),now())`,[company,src]);
    const n=(await admin.query(`select count(*)::int n from public.intelligence_facts where entity_id=$1 and fact_key='employee_count'`,[company])).rows[0].n;
    assert.equal(n,2);
  });
  await test('normal API roles cannot read or write intelligence tables',async()=>{
    for(const role of ['anon','authenticated']){
      const c=await client();
      try{await c.query('set role '+role); await assert.rejects(c.query('select * from public.intelligence_people'),/permission denied/);}finally{await c.end();clients.splice(clients.indexOf(c),1);}
    }
  });
  await test('migration creates no CRM or outreach tables',async()=>{
    const q=await admin.query(`select relname from pg_class where relnamespace='public'::regnamespace and relname in ('leads','outreach','buyers','fulfilment_orders')`);
    assert.equal(q.rows.length,0);
  });
  await test('scores retain model features and explanations for calibration',async()=>{
    const id=randomUUID();
    await admin.query(`insert into public.intelligence_scores(entity_type,entity_id,score_type,score,confidence,model_key,features,explanation)
      values('company',$1,'omega_fit',88.2,0.84,'omega:v1','{"intent":0.9}','{"why":["hiring"]}')`,[id]);
    const r=(await admin.query('select * from public.intelligence_scores where entity_id=$1',[id])).rows[0];
    assert.equal(Number(r.score),88.2); assert.equal(r.model_key,'omega:v1');
  });
  console.log(`${passed} intelligence fabric tests passed; no production database contacted.`);
} finally { await Promise.allSettled(clients.map(c=>c.end())); await pg.stop(); }
