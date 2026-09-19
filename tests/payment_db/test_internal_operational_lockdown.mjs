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
const dir=await mkdtemp(join(tmpdir(),'empire-op-lockdown-'));
const pg=new EmbeddedPostgres({
  databaseDir:join(dir,'db'),
  user:'postgres',
  password:randomBytes(24).toString('hex'),
  port:55463,
  persistent:true,
  createPostgresUser:false,
  onLog:()=>{},
  onError:()=>{},
});

const tables=[
  'agent_activity','agent_config','agent_roles','agent_task_queue',
  'agent_baselines','agent_improvements','watcher_findings',
  'self_healer_log','media_pipeline_runs','enrichment_pipeline_runs',
  'business_actions_log','business_recommendations',
];

let admin;
let passed=0;

async function test(name,fn){
  await fn();
  passed++;
  console.log('PASS '+name);
}

async function asRole(role,sql){
  const client=pg.getPgClient();
  await client.connect();
  try{
    await client.query('set role '+role);
    return await client.query(sql);
  } finally {
    await client.end();
  }
}

try{
  await pg.initialise();
  await pg.start();
  admin=pg.getPgClient();
  await admin.connect();

  await admin.query(
    'create role anon; '+
    'create role authenticated; '+
    'create role service_role bypassrls;'
  );

  for(const table of tables){
    await admin.query(
      'create table public.'+table+
      '(id bigint primary key, payload text)'
    );
    await admin.query(
      'grant select,insert,update,delete on public.'+
      table+' to anon,authenticated,service_role'
    );
    await admin.query(
      "insert into public."+table+
      " values(1,'preserve-me')"
    );
  }

  const migration=await readFile(
    join(
      root,
      'supabase/migrations/',
      '20260919112855_lock_internal_operational_surfaces.sql',
    ),
    'utf8',
  );
  await admin.query(migration);

  await test('all tables retain rows',async()=>{
    for(const table of tables){
      const row=(await admin.query(
        'select count(*)::int as n from public.'+table
      )).rows[0];
      assert.equal(row.n,1,table);
    }
  });

  await test('RLS enabled on all tables',async()=>{
    const sql=
      'select c.relname,c.relrowsecurity '+
      'from pg_class c join pg_namespace n on n.oid=c.relnamespace '+
      "where n.nspname='public' and c.relname = any($1::text[]) "+
      'order by c.relname';
    const rows=(await admin.query(sql,[tables])).rows;
    assert.equal(rows.length,tables.length);
    for(const row of rows){
      assert.equal(row.relrowsecurity,true,row.relname);
    }
  });

  await test('anon cannot select internal tables',async()=>{
    for(const table of tables){
      await assert.rejects(
        asRole('anon','select * from public.'+table),
        /permission denied/,
        table,
      );
    }
  });

  await test('authenticated cannot select internal tables',async()=>{
    for(const table of tables){
      await assert.rejects(
        asRole('authenticated','select * from public.'+table),
        /permission denied/,
        table,
      );
    }
  });

  await test('client writes are denied',async()=>{
    await assert.rejects(
      asRole(
        'authenticated',
        "insert into public.agent_activity values(2,'blocked')",
      ),
      /permission denied/,
    );
    await assert.rejects(
      asRole('anon','delete from public.watcher_findings'),
      /permission denied/,
    );
  });

  await test('service role retains server access',async()=>{
    for(const table of tables){
      const rows=await asRole(
        'service_role',
        'select * from public.'+table,
      );
      assert.equal(rows.rowCount,1,table);
    }
  });

  console.log(
    passed+
    ' operational lockdown tests passed; '+
    'no production database contacted.'
  );
} finally {
  if(admin) await admin.end();
  await pg.stop();
}
