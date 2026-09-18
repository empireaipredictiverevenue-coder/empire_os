import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {randomBytes} from 'node:crypto';

const deps=process.env.EMPIRE_PG_TEST_DEPS;
if(!deps) throw new Error('Set EMPIRE_PG_TEST_DEPS');
const mod=await import(pathToFileURL(join(deps,'node_modules/embedded-postgres/dist/index.js')));
const EmbeddedPostgres=mod.default;
const root=resolve(fileURLToPath(new URL('../..',import.meta.url)));
const dir=await mkdtemp(join(tmpdir(),'empire-coder-state-'));
const pg=new EmbeddedPostgres({
  databaseDir:join(dir,'db'),user:'postgres',
  password:randomBytes(24).toString('hex'),
  port:55452,persistent:true,createPostgresUser:false,
  onLog:()=>{},onError:()=>{}
});
let admin; let passed=0;
async function test(name,fn){await fn();passed++;console.log('PASS '+name);}
async function asRole(sql,params=[]){
  const c=pg.getPgClient(); await c.connect();
  try{await c.query('set role empire_coder_state'); return await c.query(sql,params);}
  finally{await c.end();}
}
try{
  await pg.initialise(); await pg.start();
  admin=pg.getPgClient(); await admin.connect();
  await admin.query('create role anon; create role authenticated; create role service_role bypassrls; create table commercial_events(id uuid primary key);');
  const sql=await readFile(join(root,'supabase/migrations/20260918191000_empire_coder_state.sql'),'utf8');
  await admin.query(sql);

  await test('coder role restricted and login passwordless',async()=>{
    const rows=(await admin.query("select rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolconnlimit,rolpassword from pg_authid where rolname in ('empire_coder_state','empire_coder_state_login') order by rolname")).rows;
    assert.equal(rows.length,2);
    const role=rows.find(r=>r.rolname==='empire_coder_state');
    const login=rows.find(r=>r.rolname==='empire_coder_state_login');
    assert.equal(role.rolcanlogin,false);
    assert.equal(login.rolcanlogin,true);
    for(const row of rows){
      assert.equal(row.rolinherit,false);
      assert.equal(row.rolsuper,false);
      assert.equal(row.rolcreatedb,false);
      assert.equal(row.rolcreaterole,false);
      assert.equal(row.rolreplication,false);
      assert.equal(row.rolbypassrls,false);
    }
    assert.equal(login.rolconnlimit,3);
    assert.equal(login.rolpassword,null);
  });

  await test('task state stays OBSERVE and delete denied',async()=>{
    await asRole("insert into coder_tasks(id,objective,workspace,status,phase) values('coder_test','test task','/tmp/work','running','PLAN')");
    const row=(await asRole("select execution_mode from coder_tasks where id='coder_test'")).rows[0];
    assert.equal(row.execution_mode,'OBSERVE');
    await assert.rejects(asRole("delete from coder_tasks where id='coder_test'"),/permission denied/);
  });

  await test('first draft and single-candidate output cannot be actionable',async()=>{
    await assert.rejects(
      asRole("insert into coder_proposals(task_id,provider,model,stage,draft,revision_count,actionable) values('coder_test','ollama','qwen3-coder:30b','DRAFT','first answer',0,true)"),
      /violates check constraint/
    );
    await assert.rejects(
      asRole("insert into coder_proposals(task_id,provider,model,stage,draft,candidate_drafts,critique,refined,revision_count,actionable) values('coder_test','ollama','qwen3-coder:30b','REFINED','first answer','[\"first answer\"]'::jsonb,'review','better',1,true)"),
      /violates check constraint/
    );
    await asRole("insert into coder_proposals(task_id,provider,model,stage,draft,candidate_drafts,critique,refined,revision_count,actionable) values('coder_test','ollama','qwen3-coder:30b','REFINED','candidate one','[\"candidate one\",\"candidate two\"]'::jsonb,'comparative review','synthesized result',1,true)");
  });

  await test('command proposal requires best-of-N and non-denied policy',async()=>{
    await assert.rejects(
      asRole("insert into coder_command_proposals(task_id,provider,model,candidate_texts,critique,synthesized_text,argv,policy_decision,eligible) values('coder_test','ollama','qwen3-coder:30b','[\"one\"]'::jsonb,'review','final','[\"git\",\"status\"]'::jsonb,'allow',true)"),
      /violates check constraint/
    );
    await assert.rejects(
      asRole("insert into coder_command_proposals(task_id,provider,model,candidate_texts,critique,synthesized_text,argv,policy_decision,eligible) values('coder_test','ollama','qwen3-coder:30b','[\"one\",\"two\"]'::jsonb,'review','final','[\"git\",\"status\"]'::jsonb,'deny',true)"),
      /violates check constraint/
    );
    await asRole("insert into coder_command_proposals(task_id,provider,model,candidate_texts,critique,synthesized_text,argv,policy_decision,eligible) values('coder_test','ollama','qwen3-coder:30b','[\"one\",\"two\"]'::jsonb,'review','final','[\"git\",\"status\",\"--short\"]'::jsonb,'allow',true)");
  });

  await test('context snapshots append-only and knowledge metadata gardenable',async()=>{
    await asRole("insert into coder_context_snapshots(task_id,version,trigger,compact_context) values('coder_test',1,'checkpoint','{\"phase\":\"PLAN\"}'::jsonb)");
    await assert.rejects(
      asRole("update coder_context_snapshots set trigger='tampered' where task_id='coder_test'"),
      /permission denied/
    );
    await asRole("insert into coder_knowledge_sources(path,kind,status,authority,sha256,bytes,flags) values('docs/BLUEPRINT_V6.md','canonical','ACTIVE',100,'abc',123,'[]'::jsonb)");
    await asRole("update coder_knowledge_sources set last_scanned_at=now() where path='docs/BLUEPRINT_V6.md'");
  });

  await test('evidence tables append-only',async()=>{
    await asRole("insert into coder_tool_runs(task_id,tool,arguments_summary,policy_decision) values('coder_test','git','status --short','allow')");
    await assert.rejects(asRole("update coder_tool_runs set tool='tampered' where task_id='coder_test'"),/permission denied/);
  });

  await test('no commercial authority',async()=>{
    await assert.rejects(asRole('select * from commercial_events'),/permission denied/);
    await assert.rejects(asRole("insert into commercial_events(id) values(gen_random_uuid())"),/permission denied/);
  });

  console.log(passed+' Empire Coder state tests passed; no production database contacted.');
} finally {
  if(admin) await admin.end();
  await pg.stop();
}
