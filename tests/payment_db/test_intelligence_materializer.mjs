import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {randomBytes} from 'node:crypto';

const deps=process.env.EMPIRE_PG_TEST_DEPS;
if(!deps) throw new Error('Set EMPIRE_PG_TEST_DEPS');
const {default:EmbeddedPostgres}=await import(pathToFileURL(
  join(deps,'node_modules/embedded-postgres/dist/index.js')
));
const root=resolve(fileURLToPath(new URL('../..',import.meta.url)));
const dir=await mkdtemp(join(tmpdir(),'empire-intel-materializer-'));
const pg=new EmbeddedPostgres({
  databaseDir:join(dir,'db'),
  user:'postgres',
  password:randomBytes(24).toString('hex'),
  port:55462,
  persistent:true,
  createPostgresUser:false,
  onLog:()=>{},
  onError:()=>{},
});

let admin;
let passed=0;

async function test(name,fn){
  await fn();
  passed++;
  console.log('PASS '+name);
}

async function asRole(role,sql,params=[]){
  const client=pg.getPgClient();
  await client.connect();
  try{
    await client.query('set role '+role);
    return await client.query(sql,params);
  } finally {
    await client.end();
  }
}

try{
  await pg.initialise();
  await pg.start();
  admin=pg.getPgClient();
  await admin.connect();

  await admin.query([
    'create role service_role bypassrls;',
    'create table prospects(id uuid primary key);',
    'create table prospect_entity_links(id uuid primary key,prospect_id uuid,entity_id uuid,match_score numeric,active boolean);'
    ,'create table prospect_qualifications(id uuid primary key,prospect_id uuid);'
    ,"create table intelligence_sources(id uuid primary key default gen_random_uuid(),source_key text unique not null,source_type text not null,display_name text not null,authority_score numeric not null,metadata jsonb not null default '{}'::jsonb);"
    ,'create table intelligence_facts(id uuid primary key default gen_random_uuid(),entity_type text not null,entity_id uuid not null,fact_key text not null,fact_value jsonb not null,source_id uuid not null references intelligence_sources(id),confidence numeric not null,first_seen_at timestamptz not null,last_seen_at timestamptz not null,evidence_hash text);'
    ,"create table intelligence_scores(id uuid primary key default gen_random_uuid(),entity_type text not null,entity_id uuid not null,score_type text not null,score numeric not null,confidence numeric not null,model_key text not null,features jsonb not null default '{}'::jsonb,explanation jsonb not null default '{}'::jsonb,scored_at timestamptz not null);"
    ,'create table commercial_events(id uuid primary key);'
    ,'alter table prospects enable row level security;'
    ,'alter table prospect_entity_links enable row level security;'
    ,'alter table prospect_qualifications enable row level security;'
    ,'alter table intelligence_sources enable row level security;'
    ,'alter table intelligence_facts enable row level security;'
    ,'alter table intelligence_scores enable row level security;'
    ,"insert into prospects values('00000000-0000-0000-0000-000000000001');"
  ].join('\n'));

  const migration=await readFile(
    join(root,'supabase/migrations/20260919123000_phase3f_intelligence_materializer.sql'),
    'utf8',
  );
  await admin.query(migration);
  const v2Compat=await readFile(
    join(root,'supabase/migrations/20260919130000_intelligence_materializer_v2_compat.sql'),
    'utf8',
  );
  await admin.query(v2Compat);

  await test('roles restricted and passwordless',async()=>{
    const rows=(await admin.query(
      "select rolname,rolcanlogin,rolinherit,rolsuper,rolbypassrls,rolconnlimit,rolpassword from pg_authid where rolname in ('empire_intelligence_materializer','empire_intelligence_materializer_login') order by rolname"
    )).rows;
    assert.equal(rows.length,2);
    const login=rows.find(r=>r.rolname==='empire_intelligence_materializer_login');
    assert.equal(login.rolcanlogin,true);
    assert.equal(login.rolconnlimit,3);
    assert.equal(login.rolpassword,null);
    for(const row of rows){
      assert.equal(row.rolinherit,false);
      assert.equal(row.rolsuper,false);
      assert.equal(row.rolbypassrls,false);
    }
  });

  await test('canonical sources are preseeded',async()=>{
    const rows=(await admin.query(
      "select source_key from intelligence_sources order by source_key"
    )).rows.map(r=>r.source_key);
    assert.deepEqual(rows,[
      'empire.prospect.canonical.v1',
      'empire.qualification.lead_scoring.v1',
      'empire.qualification.lead_scoring.v2',
    ]);
  });

  await test('materializer can read canonical inputs',async()=>{
    const rows=await asRole(
      'empire_intelligence_materializer',
      'select id from prospects',
    );
    assert.equal(rows.rowCount,1);
  });

  await test('valid canonical fact insert succeeds',async()=>{
    const source=(await admin.query(
      "select id from intelligence_sources where source_key='empire.prospect.canonical.v1'"
    )).rows[0].id;
    const sql=[
      'insert into intelligence_facts(',
      'entity_type,entity_id,fact_key,fact_value,source_id,confidence,',
      'first_seen_at,last_seen_at,evidence_hash) values(',
      "'company','00000000-0000-0000-0000-000000000011','niche',",
      "$2::jsonb,$1,0.9,now(),now(),'hash-1')",
      'returning id',
    ].join(' ');
    const inserted=await asRole(
      'empire_intelligence_materializer',
      sql,
      [source, JSON.stringify({value:'roofing'})],
    );
    assert.equal(inserted.rowCount,1);
  });

  await test('duplicate evidence hash is rejected',async()=>{
    const source=(await admin.query(
      "select id from intelligence_sources where source_key='empire.prospect.canonical.v1'"
    )).rows[0].id;
    const sql=[
      'insert into intelligence_facts(',
      'entity_type,entity_id,fact_key,fact_value,source_id,confidence,',
      'first_seen_at,last_seen_at,evidence_hash) values(',
      "'company','00000000-0000-0000-0000-000000000011','niche',",
      "$2::jsonb,$1,0.9,now(),now(),'hash-1')",
    ].join(' ');
    await assert.rejects(
      asRole(
        'empire_intelligence_materializer',
        sql,
        [source, JSON.stringify({value:'roofing'})],
      ),
      /duplicate key/,
    );
  });

  await test('wrong fact source is blocked by RLS',async()=>{
    const source=(await admin.query(
      "select id from intelligence_sources where source_key='empire.qualification.lead_scoring.v1'"
    )).rows[0].id;
    const sql=[
      'insert into intelligence_facts(',
      'entity_type,entity_id,fact_key,fact_value,source_id,confidence,',
      'first_seen_at,last_seen_at,evidence_hash) values(',
      "'company','00000000-0000-0000-0000-000000000012','niche',",
      "$2::jsonb,$1,0.9,now(),now(),'wrong-source')",
    ].join(' ');
    await assert.rejects(
      asRole(
        'empire_intelligence_materializer',
        sql,
        [source, JSON.stringify({value:'roofing'})],
      ),
      /row-level security/,
    );
  });

  await test('valid qualification score insert succeeds',async()=>{
    const sql=[
      'insert into intelligence_scores(',
      'entity_type,entity_id,score_type,score,confidence,',
      'model_key,features,explanation,scored_at) values(',
      "'company','00000000-0000-0000-0000-000000000011',",
      "'lead_qualification',76.4,0.6,'empire_os.lead_scoring:v1',",
      "'{}'::jsonb,'{}'::jsonb,'2026-09-19T09:05:00Z') returning id",
    ].join(' ');
    const inserted=await asRole(
      'empire_intelligence_materializer',
      sql,
    );
    assert.equal(inserted.rowCount,1);
  });

  await test('valid v2 qualification score insert succeeds',async()=>{
    const sql=[
      'insert into intelligence_scores(',
      'entity_type,entity_id,score_type,score,confidence,',
      'model_key,features,explanation,scored_at) values(',
      "'company','00000000-0000-0000-0000-000000000013',",
      "'lead_qualification',74.0,0.35,'empire_os.lead_scoring:v2',",
      "'{}'::jsonb,'{}'::jsonb,'2026-09-19T09:06:00Z') returning id",
    ].join(' ');
    const inserted=await asRole(
      'empire_intelligence_materializer',
      sql,
    );
    assert.equal(inserted.rowCount,1);
  });

  await test('wrong score model is blocked by RLS',async()=>{
    const sql=[
      'insert into intelligence_scores(',
      'entity_type,entity_id,score_type,score,confidence,',
      'model_key,features,explanation,scored_at) values(',
      "'company','00000000-0000-0000-0000-000000000012',",
      "'lead_qualification',80,0.7,'other.model:v1',",
      "'{}'::jsonb,'{}'::jsonb,now())",
    ].join(' ');
    await assert.rejects(
      asRole('empire_intelligence_materializer',sql),
      /row-level security/,
    );
  });

  await test('updates deletes and unrelated reads are denied',async()=>{
    await assert.rejects(
      asRole(
        'empire_intelligence_materializer',
        'update intelligence_scores set score=1',
      ),
      /permission denied/,
    );
    await assert.rejects(
      asRole(
        'empire_intelligence_materializer',
        'delete from intelligence_facts',
      ),
      /permission denied/,
    );
    await assert.rejects(
      asRole(
        'empire_intelligence_materializer',
        'select * from commercial_events',
      ),
      /permission denied/,
    );
  });

  await test('NOINHERIT login has no direct access',async()=>{
    await assert.rejects(
      asRole(
        'empire_intelligence_materializer_login',
        'select * from prospects',
      ),
      /permission denied/,
    );
  });

  console.log(
    passed +
    ' Intelligence materializer DB tests passed; ' +
    'no production database contacted.'
  );
} finally {
  if(admin) await admin.end();
  await pg.stop();
}
