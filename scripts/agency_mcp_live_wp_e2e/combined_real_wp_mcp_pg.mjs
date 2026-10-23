/**
 * True combined E2E: MCP guard -> private Python authority -> canonical 041
 * PostgreSQL SQL reader -> authenticated WordPress/MariaDB inventory.
 * Revokes a SYNTHETIC PostgreSQL fixture membership while MCP stays open.
 */
import { Client, InMemoryTransport } from '../../prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/node_modules/@modelcontextprotocol/client/dist/index.mjs'
import { createRevocationGuardedAgencyServer } from '../../prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/revocation-guard.mjs'
import { spawn, execFileSync } from 'node:child_process'
import { createInterface } from 'node:readline'
import { once } from 'node:events'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { statSync } from 'node:fs'

const env = process.env
const origin = env.YARD_BASE_URL
const stage = env.YARD_COMBINED_ROOT
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin??'') ||
    !stage?.startsWith('/tmp/empire_agency_combined_') ||
    env.PGHOST !== stage || !/^\d+$/.test(env.PGPORT??'') ||
    typeof env.YARD_MCP_APP_PASSWORD !== 'string' ||
    env.YARD_MCP_APP_PASSWORD.length < 20 ||
    statSync(stage).uid !== process.getuid()) {
  throw Error('Disposable combined WordPress + 041 PostgreSQL stage required')
}

const python = '/srv/empire_os/.venv/bin/python'
const script = resolve(dirname(fileURLToPath(import.meta.url)), 'combined_authority_bridge.py')
const authority = spawn(python, ['-B',script], {
  cwd:stage, env, stdio:['pipe','pipe','pipe'],shell:false
})
let bridgeReady = false
let bridgeClosed = false
let counter = 0
let outstanding = null
const messages=createInterface({input:authority.stdout, crlfDelay:Infinity})
let readyResolve,readyReject
const ready = new Promise((resolve,reject) => {
  readyResolve=resolve
  readyReject=reject
})
authority.on('error', err=>{
  bridgeClosed=true
  readyReject(Error('Private authority could not start'))
  if(outstanding){outstanding.resolve(false);outstanding=null}
})
authority.on('exit',()=>{
  bridgeClosed=true
  readyReject(Error('Private authority exited before startup'))
  if(outstanding){outstanding.resolve(false);outstanding=null}
})
messages.on('line',line=>{
  let msg
  try{msg=JSON.parse(line)}catch{
    if(outstanding){outstanding.resolve(false);outstanding=null}
    return
  }
  if (!bridgeReady) {
    if(msg.type==='ready'&&msg.canonical_sql_reader===true&&msg.production_authority===false) {
      bridgeReady=true
      readyResolve()
    } else readyReject(Error('Invalid private bridge startup'))
    return
  }
  if(outstanding&&msg.id===outstanding.id&&typeof msg.allowed==='boolean'){
    outstanding.resolve(msg.allowed)
    outstanding=null
  }
})
// Strip errors, never forward private bridge diagnostics to MCP or results.
authority.stderr.on('data',()=>{})
await Promise.race([
  ready, new Promise((_,reject)=>setTimeout(()=>reject(Error('Authority startup timeout')),9000))
])
const authorize = async operation => {
  if(!bridgeReady||bridgeClosed||outstanding)return false
  return new Promise(resolve=>{
    const id=++counter
    const timeout=setTimeout(()=>{
      if(outstanding?.id===id){outstanding=null;resolve(false)}
    },5000)
    outstanding={id,resolve:value=>{clearTimeout(timeout);resolve(value===true)}}
    authority.stdin.write(JSON.stringify({id,operation})+'\n', err=>{
      if(err&&outstanding?.id===id){
        const item=outstanding
        outstanding=null
        item.resolve(false)
      }
    })
  })
}
let calls=0
const header='Basic '+Buffer.from('demo_yard_admin:'+env.YARD_MCP_APP_PASSWORD).toString('base64')
async function query(path, opts) {
  calls++
  const url=new URL('/wp-json/empire-agency/v1/'+path,origin)
  for(const [name,value] of Object.entries(opts??{})) url.searchParams.set(name,String(value))
  const response=await fetch(url,{
    headers:{Authorization:header,Accept:'application/json'},
    redirect:'error',cache:'no-store',signal:AbortSignal.timeout(8000)
  })
  if(response.status!==200)throw Error('Real WordPress read was not HTTP 200')
  const body=await response.text()
  if(body.length>32768)throw Error('Oversized real WordPress payload')
  return JSON.parse(body)
}
const checked={}
function pass(label,ok) {
  if(!ok)throw Error('COMBINED_CANONICAL_MCP_TEST_FAILURE:'+label)
  checked[label]=true
}
const {server,closeAuthority}=createRevocationGuardedAgencyServer({
  capabilities:()=>query('capabilities'),
  vehicles:args=>query('vehicles',args)
},authorize)
const client=new Client({name:'empire-synthetic-canonical-db-wordpress-joined-test',version:'0.1.0'})
const [left,right]=InMemoryTransport.createLinkedPair()
try{
  await server.connect(right)
  await client.connect(left)
  const tools=await client.listTools()
  pass('two_read_only_mcp_tools',JSON.stringify(tools.tools.map(x=>x.name).sort())===
    JSON.stringify(['agency_get_capabilities','agency_list_demo_vehicles']))
  const cap=await client.callTool({name:'agency_get_capabilities',arguments:{}})
  pass('canonical_pg_membership_authorizes_real_wp_capability',
    cap.isError!==true&&JSON.parse(cap.content[0].text).writes_available===false)
  const vehicles=await client.callTool({name:'agency_list_demo_vehicles',arguments:{page:1,limit:2}})
  pass('canonical_pg_membership_authorizes_real_mariadb_inventory',
    vehicles.isError!==true&&JSON.parse(vehicles.content[0].text).items[0].title==='SYNTHETIC DEMO BLUE VAN')
  pass('two_wordpress_reads_before_revocation',calls===2)

  // The ONLY destructive membership change here is to a disposable, private
  // crm_membership_fixture Unix-socket PostgreSQL cluster, not EmpireDB.
  const sql = "UPDATE public.empire_crm_tenant_memberships SET status='disabled', revoked_at=CURRENT_TIMESTAMP WHERE tenant_id='510152ee-21b1-4d88-af83-3937718b4236'::uuid AND subject='synthetic:agency-owner'"
  execFileSync('/usr/bin/psql',['-X','-q','-v','ON_ERROR_STOP=1','-d','crm_membership_fixture','-c',sql],{
    cwd:stage,
    env:{...env,PGHOST:stage,PGPORT:env.PGPORT,PGUSER:'ubuntu',PGDATABASE:'crm_membership_fixture'},
    timeout:7000,stdio:['ignore','ignore','pipe']
  })
  const denied=await client.callTool({name:'agency_list_demo_vehicles',arguments:{page:1,limit:2}})
  pass('actual_041_membership_revoked_mid_mcp_session',denied.isError===true)
  pass('revoked_sql_member_prevented_all_wordpress_reads',calls===2)
  const deniedCap=await client.callTool({name:'agency_get_capabilities',arguments:{}})
  pass('capabilities_still_denied_after_real_pg_revocation',deniedCap.isError===true&&calls===2)
  closeAuthority()
  pass('closed_guard_stops_access_after_revocation',(await client.callTool({
    name:'agency_list_demo_vehicles',arguments:{page:1,limit:2}
  })).isError===true&&calls===2)
  console.log(JSON.stringify({
    status:'COMBINED_REAL_PG041_MCP_WP_MARIADB_REVOCATION_PASS',
    checks:checked,checks_passed:Object.keys(checked).length,
    authentic_postgresql_041_and_wordpress_mariadb:true,
    production_empiredb:false,synthetic_site_registry_and_test_signer:true,
    production_changes:false,public_bookings_or_payments:false
  }))
}finally {
  await client.close().catch(()=>{})
  await server.close().catch(()=>{})
  bridgeClosed=true
  authority.stdin.end()
  authority.kill('SIGTERM')
}
