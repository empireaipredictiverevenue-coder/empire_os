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
const dir=await mkdtemp(join(tmpdir(),'empire-task-rpc-'));
const pg=new EmbeddedPostgres({databaseDir:join(dir,'db'),user:'postgres',password:randomBytes(24).toString('hex'),port:55449,persistent:true,createPostgresUser:false,onLog:()=>{},onError:()=>{}});
let admin;
async function asRole(role,sql,args=[]){const c=pg.getPgClient();await c.connect();try{await c.query('begin');await c.query('set local role '+role);const r=await c.query(sql,args);await c.query('commit');return r;}finally{await c.end();}}
try {
  await pg.initialise(); await pg.start(); admin=pg.getPgClient(); await admin.connect();
  await admin.query(`create role anon; create role authenticated; create role service_role;
    create table public.agent_task_queue(ticket_id uuid primary key, task_type text, payload jsonb default '{}'::jsonb, priority int default 0, created_at timestamptz default now(), status text default 'To-Do', assigned_agent text, started_at timestamptz, result jsonb, error text, completed_at timestamptz);`);
  await admin.query(`create function public.claim_next_task(p_agent_name text,p_task_types text[]) returns jsonb language plpgsql security definer as $$ declare v public.agent_task_queue%rowtype; begin select * into v from public.agent_task_queue where status='To-Do' limit 1 for update skip locked; if v.ticket_id is null then return null; end if; update public.agent_task_queue set status='In Progress',assigned_agent=p_agent_name where ticket_id=v.ticket_id; return jsonb_build_object('ticket_id',v.ticket_id); end; $$;
    create function public.complete_task(p_ticket_id uuid,p_result jsonb default '{}'::jsonb,p_error text default null) returns boolean language plpgsql security definer as $$ begin update public.agent_task_queue set status=case when p_error is not null then 'Failed' else 'Done' end,result=p_result,error=p_error,completed_at=now() where ticket_id=p_ticket_id; return found; end; $$;`);
  const migration=await readFile(join(root,'supabase/migrations/20260917214235_harden_legacy_task_rpcs.sql'),'utf8');
  await admin.query(migration);
  const ticket=randomUUID();
  await admin.query("insert into public.agent_task_queue(ticket_id,task_type) values($1,'test')",[ticket]);
  await assert.rejects(asRole('anon',"select public.claim_next_task('anon',null)"),/permission denied/);
  await assert.rejects(asRole('authenticated',"select public.complete_task($1,'{}',null)",[ticket]),/permission denied/);
  const claimed=(await asRole('service_role',"select public.claim_next_task('worker',null) result")).rows[0].result;
  assert.equal(claimed.ticket_id,ticket);
  const completed=(await asRole('service_role',"select public.complete_task($1,'{}',null) result",[ticket])).rows[0].result;
  assert.equal(completed,true);
  const cfg=(await admin.query("select proconfig from pg_proc where oid='public.claim_next_task(text,text[])'::regprocedure")).rows[0].proconfig;
  assert.ok(cfg.includes('search_path=""') || cfg.includes('search_path='));
  console.log('PASS legacy task RPC hardening: anon/auth denied, service_role preserved, search_path pinned.');
} finally {
  if(admin) await admin.end();
  await pg.stop();
}
