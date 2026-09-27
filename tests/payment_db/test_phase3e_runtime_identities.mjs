// Isolated PostgreSQL test for Phase 3E dedicated runtime login identities.
import assert from 'node:assert/strict';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {randomBytes} from 'node:crypto';

const deps=process.env.EMPIRE_PG_TEST_DEPS; if(!deps) throw new Error('Set EMPIRE_PG_TEST_DEPS');
const {default:EmbeddedPostgres}=await import(pathToFileURL(join(deps,'node_modules/embedded-postgres/dist/index.js')));
const root=resolve(fileURLToPath(new URL('../..',import.meta.url)));
const dir=await mkdtemp(join(tmpdir(),'empire-phase3e-roles-'));
const pg=new EmbeddedPostgres({databaseDir:join(dir,'db'),user:'postgres',password:randomBytes(24).toString('hex'),port:55447,persistent:true,createPostgresUser:false,onLog:()=>{},onError:()=>{}});
let admin; let passed=0;
async function test(name,fn){await fn();passed++;console.log('PASS '+name);}

const pairs={
  empire_outbound_approver_login:'empire_outbound_approver',
  empire_outbound_sender_login:'empire_outbound_sender',
  empire_reply_ingest_login:'empire_reply_ingest',
  empire_closer_approver_login:'empire_closer_approver',
};

try{
  await pg.initialise(); await pg.start(); admin=pg.getPgClient(); await admin.connect();
  await admin.query(`
    create role service_role bypassrls;
    create role empire_outbound_approver nologin noinherit;
    create role empire_outbound_sender nologin noinherit;
    create role empire_reply_ingest nologin noinherit;
    create role empire_closer_approver nologin noinherit;
  `);
  const sql=await readFile(join(root,'supabase/migrations/20260917194500_phase3e_runtime_identities.sql'),'utf8');
  await admin.query(sql);

  await test('runtime identities are login-capable but unprivileged and passwordless',async()=>{
    const rows=(await admin.query(`
      select rolname,rolcanlogin,rolsuper,rolinherit,rolcreatedb,rolcreaterole,
             rolreplication,rolbypassrls,rolconnlimit,rolpassword
      from pg_authid where rolname = any($1::text[]) order by rolname
    `,[Object.keys(pairs)])).rows;
    assert.equal(rows.length,4);
    for(const r of rows){
      assert.equal(r.rolcanlogin,true); assert.equal(r.rolsuper,false);
      assert.equal(r.rolinherit,false); assert.equal(r.rolcreatedb,false);
      assert.equal(r.rolcreaterole,false); assert.equal(r.rolreplication,false);
      assert.equal(r.rolbypassrls,false); assert.equal(r.rolconnlimit,5);
      assert.equal(r.rolpassword,null);
    }
  });

  await test('each runtime identity belongs to exactly one permission role',async()=>{
    const rows=(await admin.query(`
      select member_role.rolname member, granted_role.rolname granted
      from pg_auth_members m
      join pg_roles member_role on member_role.oid=m.member
      join pg_roles granted_role on granted_role.oid=m.roleid
      where member_role.rolname = any($1::text[])
      order by member_role.rolname,granted_role.rolname
    `,[Object.keys(pairs)])).rows;
    assert.equal(rows.length,4);
    for(const [member,granted] of Object.entries(pairs)){
      const mine=rows.filter(r=>r.member===member).map(r=>r.granted);
      assert.deepEqual(mine,[granted]);
    }
  });

  await test('runtime identities carry defensive timeout settings',async()=>{
    const rows=(await admin.query(`select rolname,rolconfig from pg_roles where rolname=any($1::text[])`,[Object.keys(pairs)])).rows;
    for(const r of rows){
      assert.ok(r.rolconfig.includes('statement_timeout=15s'));
      assert.ok(r.rolconfig.includes('idle_in_transaction_session_timeout=30s'));
    }
  });

  console.log(`${passed} Phase 3E runtime identity tests passed; no production database contacted.`);
} finally {
  if(admin) await admin.end();
  await pg.stop();
}
