/** Actual disposable MariaDB WordPress HTTP + guarded MCP protocol / synthetic revocation. */
import {Client, InMemoryTransport} from '../../prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/node_modules/@modelcontextprotocol/client/dist/index.mjs'
import {createRevocationGuardedAgencyServer} from '../../prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/revocation-guard.mjs'

const origin=process.env.YARD_BASE_URL
const password=process.env.YARD_MCP_APP_PASSWORD
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin??'') || !password || password.length<20) {
  throw new Error('Disposable WordPress staging origin / secret missing')
}
let wpCalls=0
let memberActive=true
let siteActive=true
let registryActive=true
let credentialActive=true
const checks={}
function pass(name,condition) {
  if (!condition) throw new Error('GUARDED_WORDPRESS_MCP_TEST_FAILED '+name)
  checks[name]=true
}
const auth='Basic '+Buffer.from('demo_yard_admin:'+password).toString('base64')
async function read(path, query) {
  wpCalls++
  const url=new URL('/wp-json/empire-agency/v1/'+path,origin)
  for(const [key,value] of Object.entries(query??{}))url.searchParams.set(key,String(value))
  const res=await fetch(url,{
    headers:{Authorization:auth,Accept:'application/json'},redirect:'error',
    cache:'no-store',signal:AbortSignal.timeout(6500)
  })
  if (res.status!==200)throw Error('Real WordPress API refused read')
  const raw=await res.text()
  if(raw.length>32000)throw Error('Unexpected WordPress payload')
  return JSON.parse(raw)
}
const readers={
  capabilities:()=>read('capabilities'),
  vehicles:opts=>read('vehicles',opts)
}
const {server,closeAuthority}=createRevocationGuardedAgencyServer(readers,async permission => {
  return (permission==='capabilities:read'||permission==='vehicles:read') &&
    memberActive && siteActive && registryActive && credentialActive
})
const client=new Client({name:'disposable-real-wordpress-revocation-client',version:'0.1.0'})
const [toClient,toServer]=InMemoryTransport.createLinkedPair()
try {
  await server.connect(toServer)
  await client.connect(toClient)
  const tools=await client.listTools()
  pass('two_read_only_tools',JSON.stringify(tools.tools.map(x=>x.name).sort())===JSON.stringify([
    'agency_get_capabilities','agency_list_demo_vehicles']))
  const cap=await client.callTool({name:'agency_get_capabilities',arguments:{}})
  pass('authenticated_capabilities_real_wordpress',cap.isError!==true&&
    JSON.parse(cap.content[0].text).crm_connected===false)
  const inventory=await client.callTool({name:'agency_list_demo_vehicles',arguments:{page:1,limit:2}})
  pass('authenticated_synthetic_inventory_real_mariadb',inventory.isError!==true&&
    JSON.parse(inventory.content[0].text).items[0].title==='SYNTHETIC DEMO BLUE VAN')
  const baseline=wpCalls
  pass('exactly_two_wordpress_reads_before_revocation',baseline===2)
  memberActive=false
  const memberDenied=await client.callTool({name:'agency_list_demo_vehicles',arguments:{page:1,limit:2}})
  pass('mid_session_membership_revoked_denied_before_wordpress',memberDenied.isError===true&&wpCalls===baseline)
  memberActive=true
  siteActive=false
  const siteDenied=await client.callTool({name:'agency_get_capabilities',arguments:{}})
  pass('mid_session_site_grant_revoked_denied_before_wordpress',siteDenied.isError===true&&wpCalls===baseline)
  siteActive=true
  registryActive=false
  const registryDenied=await client.callTool({name:'agency_list_demo_vehicles',arguments:{page:1,limit:2}})
  pass('mid_session_registry_revoked_denied_before_wordpress',registryDenied.isError===true&&wpCalls===baseline)
  registryActive=true
  credentialActive=false
  const secretDenied=await client.callTool({name:'agency_get_capabilities',arguments:{}})
  pass('mid_session_credential_revoked_denied_before_wordpress',secretDenied.isError===true&&wpCalls===baseline)
  closeAuthority()
  const closed=await client.callTool({name:'agency_get_capabilities',arguments:{}})
  pass('closed_session_denied_before_wordpress',closed.isError===true&&wpCalls===baseline)
  console.log(JSON.stringify({
    status:'REAL_WORDPRESS_MYSQL_MCP_PER_TOOL_SYNTHETIC_REVOCATION_PASS',
    checks,checks_passed:Object.keys(checks).length,
    real_wordpress_mariadb_backend:true,
    synthetic_member_and_site_state:true,
    canonical_empiredb_membership_queried:false,
    production_changes:false
  }))
} finally {
  await client.close()
  await server.close()
}
