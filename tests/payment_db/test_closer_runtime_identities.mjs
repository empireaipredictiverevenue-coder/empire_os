import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {randomBytes, randomUUID} from 'node:crypto';

const deps=process.env.EMPIRE_PG_TEST_DEPS;
if(!deps) throw new Error('Set EMPIRE_PG_TEST_DEPS');
const {default:EmbeddedPostgres}=await import(pathToFileURL(
  join(deps,'node_modules/embedded-postgres/dist/index.js')));
const root=resolve(fileURLToPath(new URL('../..',import.meta.url)));
const dir=await mkdtemp(join(tmpdir(),'empire-closer-runtime-'));
const pg=new EmbeddedPostgres({
  databaseDir:join(dir,'db'),user:'postgres',
  password:randomBytes(24).toString('hex'),port:55450,persistent:true,
  createPostgresUser:false,onLog:()=>{},onError:()=>{},
});
let admin;const clients=[];let passed=0;
async function client(){const c=pg.getPgClient();await c.connect();clients.push(c);return c;}
async function asRole(role,sql,args=[]){
  const c=await client();
  try{
    await c.query('begin');
    await c.query('set local role '+role);
    const r=await c.query(sql,args);
    await c.query('commit');
    return r;
  } finally {
    await c.end();
    clients.splice(clients.indexOf(c),1);
  }
}
async function test(name,fn){await fn();passed++;console.log('PASS '+name);}

try{
  await pg.initialise();await pg.start();admin=await client();
  await admin.query(`
    create role anon;
    create role authenticated;
    create role service_role bypassrls;
    create table prospects(id uuid primary key);
    create table business_entities(id uuid primary key);
    create table buyers(id uuid primary key);
    create table gtm_opportunities(id uuid primary key);
    create table fulfilment_orders(
      id uuid primary key,
      entity_id uuid references business_entities(id),
      buyer_id uuid references buyers(id),
      state text,
      price_cents bigint,
      commercial_payload jsonb not null default '{}'
    );
  `);
  for(const file of [
    '20260917190000_governed_outbound_reply_capture.sql',
    '20260917193000_supabase_closer_state_machine.sql',
    '20260918144500_phase3e_closer_runtime_identities.sql',
  ]){
    await admin.query(await readFile(
      join(root,'supabase/migrations',file),'utf8'));
  }

  const entity=randomUUID(),intent=randomUUID(),reply=randomUUID();
  await admin.query('insert into business_entities(id) values($1)',[entity]);
  await admin.query(`
    insert into outbound_intents(
      id,entity_id,channel,recipient,normalized_recipient,body_text,
      status,idempotency_key,proposed_by,expires_at
    ) values(
      $1,$2,'email','buyer@example.com','buyer@example.com','Body',
      'replied','closer-runtime-intent','planner',now()+interval '1 day'
    )
  `,[intent,entity]);
  await admin.query(`
    insert into outbound_replies(
      id,intent_id,provider_message_id,from_contact,normalized_from_contact,
      body_text,classification,confidence,received_at,classified_at
    ) values(
      $1,$2,'reply-runtime','buyer@example.com','buyer@example.com',
      'Interested','positive',0.93,now(),now()
    )
  `,[reply,intent]);

  await test('runtime logins are passwordless restricted identities',async()=>{
    const rows=(await admin.query(`
      select rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,
             rolcreaterole,rolreplication,rolbypassrls,rolconnlimit,rolpassword
      from pg_authid
      where rolname in (
        'empire_closer_observer_login',
        'empire_closer_planner_login',
        'empire_closer_approver_login'
      )
      order by rolname
    `)).rows;
    assert.equal(rows.length,3);
    for(const r of rows){
      assert.equal(r.rolcanlogin,true);
      assert.equal(r.rolinherit,false);
      assert.equal(r.rolsuper,false);
      assert.equal(r.rolcreatedb,false);
      assert.equal(r.rolcreaterole,false);
      assert.equal(r.rolreplication,false);
      assert.equal(r.rolbypassrls,false);
      assert.equal(r.rolconnlimit,5);
      assert.equal(r.rolpassword,null);
    }
  });

  await test('observer can list bounded work but cannot mutate',async()=>{
    const work=(await asRole(
      'empire_closer_observer',
      'select public.list_closer_work($1) result',
      [50],
    )).rows[0].result;
    assert.equal(work.length,1);
    assert.equal(work[0].reply_id,reply);
    assert.equal(work[0].classification,'positive');
    assert.equal(work[0].case_id,null);

    await assert.rejects(
      asRole(
        'empire_closer_observer',
        'select public.open_closer_case($1)',
        [reply],
      ),
      /permission denied for function open_closer_case/
    );
    await assert.rejects(
      asRole(
        'empire_closer_observer',
        'select * from public.closer_cases',
      ),
      /permission denied for table closer_cases/
    );
  });

  let caseId;
  await test('planner opens and recommends but cannot approve',async()=>{
    const opened=(await asRole(
      'empire_closer_planner',
      'select public.open_closer_case($1) result',
      [reply],
    )).rows[0].result;
    assert.equal(opened.state,'engaged');
    caseId=opened.case_id;

    const rec=(await asRole(
      'empire_closer_planner',
      `select public.record_closer_recommendation(
        $1,'qualify',0.93,'{"classification":"positive"}',null,'rules:v1'
      ) result`,
      [caseId],
    )).rows[0].result;
    assert.equal(rec.decision,'recorded');

    await assert.rejects(
      asRole(
        'empire_closer_planner',
        `select public.advance_closer_case(
          $1,'qualified','planner',null,''
        )`,
        [caseId],
      ),
      /permission denied for function advance_closer_case/
    );
    await assert.rejects(
      asRole(
        'empire_closer_planner',
        `update public.closer_cases set state='qualified' where id=$1`,
        [caseId],
      ),
      /permission denied for table closer_cases/
    );
  });

  await test('approver advances but cannot plan',async()=>{
    const advanced=(await asRole(
      'empire_closer_approver',
      `select public.advance_closer_case(
        $1,'qualified','human.operator',null,'reviewed'
      ) result`,
      [caseId],
    )).rows[0].result;
    assert.equal(advanced.state,'qualified');

    await assert.rejects(
      asRole(
        'empire_closer_approver',
        'select public.open_closer_case($1)',
        [reply],
      ),
      /permission denied for function open_closer_case/
    );
    await assert.rejects(
      asRole(
        'empire_closer_approver',
        `select public.record_closer_recommendation(
          $1,'prepare_proposal',0.8,'{}',null,'rules:v1'
        )`,
        [caseId],
      ),
      /permission denied for function record_closer_recommendation/
    );
  });

  await test('runtime login memberships are separated',async()=>{
    const rows=(await admin.query(`
      select member_role.rolname member, granted_role.rolname granted
      from pg_auth_members m
      join pg_roles member_role on member_role.oid=m.member
      join pg_roles granted_role on granted_role.oid=m.roleid
      where member_role.rolname like 'empire_closer_%_login'
      order by member_role.rolname
    `)).rows;
    assert.deepEqual(rows,[
      {member:'empire_closer_approver_login',granted:'empire_closer_approver'},
      {member:'empire_closer_observer_login',granted:'empire_closer_observer'},
      {member:'empire_closer_planner_login',granted:'empire_closer_planner'},
    ]);
  });

  console.log(
    passed+' closer runtime identity tests passed; no production database contacted.'
  );
} finally {
  await Promise.allSettled(clients.map(c=>c.end()));
  await pg.stop();
}
